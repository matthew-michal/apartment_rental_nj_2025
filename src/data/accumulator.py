import pandas as pd
from pathlib import Path
from datetime import datetime

class TrainingDataAccumulator:
    def __init__(self, base_training_path="data/training/training_base.csv", 
                 accumulated_path="data/training/training_accumulated.csv"):
        self.base_training_path = Path(base_training_path)
        self.accumulated_path = Path(accumulated_path)
    
    def add_daily_predictions(self, daily_df):
        """Add daily prediction data to accumulated training set"""
        try:
            # Load existing accumulated data or start with base
            if self.accumulated_path.exists():
                accumulated_df = pd.read_csv(self.accumulated_path)
                print(f"Loaded existing accumulated data: {len(accumulated_df)} rows")
            else:
                accumulated_df = pd.read_csv(self.base_training_path)
                print(f"Starting from base training data: {len(accumulated_df)} rows")
            
            # Prepare daily data for training (remove prediction columns)
            training_cols = [col for col in daily_df.columns 
                           if col not in ['price_preds', 'price_diff']]
            daily_training = daily_df[training_cols].copy()
            
            # Combine and remove duplicates based on ID
            combined_df = pd.concat([accumulated_df, daily_training], ignore_index=True)
            deduplicated_df = combined_df.drop_duplicates(subset=['id'], keep='last')
            
            # Save accumulated data
            deduplicated_df.to_csv(self.accumulated_path, index=False)
            
            added_rows = len(daily_training)
            final_rows = len(deduplicated_df)
            duplicates_removed = len(combined_df) - final_rows
            
            print(f"✅ Training data accumulated:")
            print(f"   - Added {added_rows} new rows")
            print(f"   - Removed {duplicates_removed} duplicates")
            print(f"   - Final training set size: {final_rows} rows")
            
            return {
                'added_rows': added_rows,
                'duplicates_removed': duplicates_removed,
                'final_size': final_rows
            }
            
        except Exception as e:
            print(f"❌ Error accumulating training data: {e}")
            raise
    
    def reset_accumulated_data(self):
        """Reset accumulated data to base training set"""
        base_df = pd.read_csv(self.base_training_path)
        base_df.to_csv(self.accumulated_path, index=False)
        print(f"🔄 Reset accumulated training data to base dataset ({len(base_df)} rows)")
        return len(base_df)
    
    def get_training_stats(self):
        """Get statistics about current training data"""
        try:
            if self.accumulated_path.exists():
                accumulated_df = pd.read_csv(self.accumulated_path)
                base_df = pd.read_csv(self.base_training_path)
                
                stats = {
                    'base_size': len(base_df),
                    'accumulated_size': len(accumulated_df),
                    'growth': len(accumulated_df) - len(base_df),
                    'growth_percentage': ((len(accumulated_df) - len(base_df)) / len(base_df)) * 100
                }
                
                print(f"📊 Training Data Stats:")
                print(f"   - Base dataset: {stats['base_size']:,} rows")
                print(f"   - Current accumulated: {stats['accumulated_size']:,} rows") 
                print(f"   - Growth: +{stats['growth']:,} rows ({stats['growth_percentage']:.1f}%)")
                
                return stats
            else:
                print("No accumulated data yet. Will start from base dataset.")
                return None
        except Exception as e:
            print(f"❌ Error getting training stats: {e}")
            return None