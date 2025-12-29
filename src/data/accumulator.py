"""
Training data accumulator that works in Lambda environment.
Uses S3 for storage instead of local filesystem.
"""

import pandas as pd
import boto3
import io
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import logging

import sys
sys.path.append('/app')
from src.config.environment import get_config

logger = logging.getLogger(__name__)


class TrainingDataAccumulator:
    """
    Accumulates daily prediction data into training dataset.
    
    Works in both Lambda (S3-based) and local development environments.
    """
    
    def __init__(
        self,
        base_training_key: str = "training/training_base.csv",
        accumulated_key: str = "training/training_accumulated.csv"
    ):
        """
        Initialize accumulator.
        
        Args:
            base_training_key: S3 key for base training data
            accumulated_key: S3 key for accumulated training data
        """
        self.config = get_config()
        self.s3_client = boto3.client('s3', region_name=self.config.aws_region)
        self.training_bucket = self.config.training_bucket
        
        self.base_training_key = base_training_key
        self.accumulated_key = accumulated_key
        
        # For local development fallback
        self.local_base_path = Path("data/training/training_base.csv")
        self.local_accumulated_path = Path("data/training/training_accumulated.csv")
    
    def add_daily_predictions(self, daily_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Add daily prediction data to accumulated training set.
        
        Args:
            daily_df: DataFrame with daily predictions
        
        Returns:
            Statistics about the accumulation
        """
        try:
            logger.info("Starting training data accumulation...")
            
            # Load existing accumulated data or start with base
            accumulated_df = self._load_accumulated_data()
            initial_size = len(accumulated_df)
            
            # Prepare daily data for training (remove prediction-specific columns)
            training_cols = [
                col for col in daily_df.columns 
                if col not in ['price_preds', 'price_diff', 'predicted_price', 'deal_score']
            ]
            
            # Ensure we have the essential columns
            required_cols = ['id', 'price', 'latitude', 'longitude', 'propertyType', 
                           'bedrooms', 'bathrooms', 'yearBuilt', 'lotSize']
            
            missing_cols = [col for col in required_cols if col not in training_cols]
            if missing_cols:
                logger.warning(f"Missing required columns: {missing_cols}")
            
            daily_training = daily_df[training_cols].copy()
            logger.info(f"Prepared {len(daily_training)} rows from daily predictions")
            
            # Combine and remove duplicates based on ID
            combined_df = pd.concat([accumulated_df, daily_training], ignore_index=True)
            
            # Remove duplicates, keeping most recent
            if 'id' in combined_df.columns:
                deduplicated_df = combined_df.drop_duplicates(subset=['id'], keep='last')
            else:
                logger.warning("No 'id' column found, skipping deduplication")
                deduplicated_df = combined_df
            
            # Save accumulated data back to S3
            self._save_accumulated_data(deduplicated_df)
            
            # Calculate statistics
            added_rows = len(daily_training)
            final_rows = len(deduplicated_df)
            duplicates_removed = len(combined_df) - final_rows
            growth_pct = ((final_rows - initial_size) / initial_size * 100) if initial_size > 0 else 0
            
            stats = {
                'added_rows': added_rows,
                'duplicates_removed': duplicates_removed,
                'initial_size': initial_size,
                'final_size': final_rows,
                'net_growth': final_rows - initial_size,
                'growth_percentage': growth_pct,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Training data accumulated:")
            logger.info(f"   - Added {added_rows} new rows")
            logger.info(f"   - Removed {duplicates_removed} duplicates")
            logger.info(f"   - Net growth: +{stats['net_growth']} rows ({growth_pct:.1f}%)")
            logger.info(f"   - Final training set size: {final_rows:,} rows")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error accumulating training data: {e}")
            raise
    
    def _load_accumulated_data(self) -> pd.DataFrame:
        """
        Load accumulated training data from S3 or fallback to base data.
        
        Returns:
            DataFrame with training data
        """
        # Try to load accumulated data from S3
        try:
            logger.info(f"Attempting to load accumulated data from S3: {self.accumulated_key}")
            obj = self.s3_client.get_object(
                Bucket=self.training_bucket,
                Key=self.accumulated_key
            )
            df = pd.read_csv(io.BytesIO(obj['Body'].read()))
            logger.info(f"Loaded existing accumulated data from S3: {len(df):,} rows")
            return df
            
        except self.s3_client.exceptions.NoSuchKey:
            logger.info("No accumulated data found, loading base training data...")
            return self._load_base_data()
            
        except Exception as e:
            logger.warning(f"Error loading accumulated data from S3: {e}")
            logger.info("Falling back to base training data...")
            return self._load_base_data()
    
    def _load_base_data(self) -> pd.DataFrame:
        """
        Load base training data from S3 or local filesystem.
        
        Returns:
            DataFrame with base training data
        """
        # Try S3 first
        try:
            logger.info(f"Loading base training data from S3: {self.base_training_key}")
            obj = self.s3_client.get_object(
                Bucket=self.training_bucket,
                Key=self.base_training_key
            )
            df = pd.read_csv(io.BytesIO(obj['Body'].read()))
            logger.info(f"Loaded base training data from S3: {len(df):,} rows")
            return df
            
        except Exception as e:
            logger.warning(f"Could not load base data from S3: {e}")
            
            # Fallback to local filesystem (for local development)
            if self.local_base_path.exists():
                logger.info(f"Loading base data from local file: {self.local_base_path}")
                df = pd.read_csv(self.local_base_path)
                logger.info(f"Loaded base training data locally: {len(df):,} rows")
                return df
            
            # If nothing works, create minimal DataFrame
            logger.warning("No base training data found! Creating empty DataFrame")
            return pd.DataFrame()
    
    def _save_accumulated_data(self, df: pd.DataFrame):
        """
        Save accumulated data to S3.
        
        Args:
            df: DataFrame to save
        """
        try:
            # Save to S3
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            
            self.s3_client.put_object(
                Bucket=self.training_bucket,
                Key=self.accumulated_key,
                Body=csv_buffer.getvalue(),
                ContentType='text/csv'
            )
            
            logger.info(f"Saved accumulated data to s3://{self.training_bucket}/{self.accumulated_key}")
            
            # Also save a timestamped backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_key = f"training/backups/training_accumulated_{timestamp}.csv"
            
            self.s3_client.put_object(
                Bucket=self.training_bucket,
                Key=backup_key,
                Body=csv_buffer.getvalue(),
                ContentType='text/csv'
            )
            
            logger.debug(f"Backup saved to s3://{self.training_bucket}/{backup_key}")
            
        except Exception as e:
            logger.error(f"Error saving accumulated data to S3: {e}")
            
            # Fallback: save locally if S3 fails (for development)
            if self.config.environment == 'dev':
                self.local_accumulated_path.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(self.local_accumulated_path, index=False)
                logger.warning(f"Saved to local file as fallback: {self.local_accumulated_path}")
            else:
                raise
    
    def reset_accumulated_data(self) -> int:
        """
        Reset accumulated data to base training set.
        
        Returns:
            Number of rows in reset dataset
        """
        try:
            logger.info("Resetting accumulated training data to base dataset...")
            
            base_df = self._load_base_data()
            self._save_accumulated_data(base_df)
            
            logger.info(f"🔄 Reset accumulated training data to base dataset ({len(base_df):,} rows)")
            return len(base_df)
            
        except Exception as e:
            logger.error(f"Error resetting accumulated data: {e}")
            raise
    
    def get_training_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get statistics about current training data.
        
        Returns:
            Dictionary with statistics, or None if data not available
        """
        try:
            accumulated_df = self._load_accumulated_data()
            base_df = self._load_base_data()
            
            base_size = len(base_df)
            accumulated_size = len(accumulated_df)
            growth = accumulated_size - base_size
            growth_pct = (growth / base_size * 100) if base_size > 0 else 0
            
            stats = {
                'base_size': base_size,
                'accumulated_size': accumulated_size,
                'growth': growth,
                'growth_percentage': growth_pct,
                'timestamp': datetime.now().isoformat()
            }
            
            # Add data quality metrics
            if not accumulated_df.empty:
                stats['missing_values_pct'] = (
                    accumulated_df.isnull().sum().sum() / 
                    (len(accumulated_df) * len(accumulated_df.columns)) * 100
                )
                
                if 'price' in accumulated_df.columns:
                    stats['avg_price'] = float(accumulated_df['price'].mean())
                    stats['price_std'] = float(accumulated_df['price'].std())
            
            logger.info(f"📊 Training Data Stats:")
            logger.info(f"   - Base dataset: {base_size:,} rows")
            logger.info(f"   - Current accumulated: {accumulated_size:,} rows")
            logger.info(f"   - Growth: +{growth:,} rows ({growth_pct:.1f}%)")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting training stats: {e}")
            return None
    
    def get_accumulated_dataframe(self) -> pd.DataFrame:
        """
        Get the current accumulated training DataFrame.
        
        Returns:
            DataFrame with accumulated training data
        """
        return self._load_accumulated_data()


# Example usage
if __name__ == "__main__":
    # Test the accumulator
    accumulator = TrainingDataAccumulator()
    
    # Get current stats
    stats = accumulator.get_training_stats()
    if stats:
        print(f"Current training data: {stats['accumulated_size']:,} rows")
        print(f"Growth: {stats['growth_percentage']:.1f}%")
