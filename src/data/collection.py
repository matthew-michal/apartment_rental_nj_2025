"""
Data collection module for apartment listings.
Updated to work in Lambda environment with proper error handling.
"""

import requests
import json
import pandas as pd
import pickle
import os
import boto3
from typing import Optional, Dict, Any
from datetime import datetime
import logging

# Import configuration
import sys
sys.path.append('/app')  # For Lambda
from src.config.environment import get_config, get_secret

logger = logging.getLogger(__name__)


class ApartmentDataCollector:
    """
    Collects apartment listing data from Rentcast API.
    Handles API key management, pagination, and error handling.
    """
    
    # Default search parameters (North NJ, Morristown area)
    DEFAULT_URL = (
        "https://api.rentcast.io/v1/listings/rental/long-term"
        "?latitude=40.8314005740992"
        "&longitude=-74.40197132373629"
        "&radius=12"
        "&status=Active"
        "&limit=500"
    )
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize data collector.
        
        Args:
            api_key: Rentcast API key. If None, will fetch from Secrets Manager.
        """
        self.config = get_config()
        
        # Get API key from Secrets Manager if not provided
        if api_key is None:
            try:
                self.api_key = get_secret('RENTCAST_API_KEY')
                logger.info("Retrieved API key from Secrets Manager")
            except Exception as e:
                logger.warning(f"Could not get API key from Secrets Manager: {e}")
                # Fallback to environment variable for local development
                self.api_key = os.getenv('API_KEY')
                if not self.api_key:
                    raise ValueError(
                        "No API key found. Set RENTCAST_API_KEY in Secrets Manager "
                        "or API_KEY in environment variables."
                    )
        else:
            self.api_key = api_key
        
        self.headers = {
            "accept": "application/json",
            "X-Api-Key": self.api_key
        }
        
        self.s3_client = boto3.client('s3', region_name=self.config.aws_region)
    
    def collect_listings(
        self,
        url: Optional[str] = None,
        max_pages: int = 15,
        save_raw: bool = True
    ) -> pd.DataFrame:
        """
        Collect apartment listings from Rentcast API.
        
        Args:
            url: API URL to use. If None, uses default North NJ search.
            max_pages: Maximum number of pages to fetch (500 listings per page).
            save_raw: Whether to save raw response to S3.
        
        Returns:
            DataFrame with apartment listings
        """
        if url is None:
            url = self.DEFAULT_URL
        
        logger.info(f"Starting data collection (max {max_pages} pages)...")
        
        all_listings = []
        page = 0
        
        while page < max_pages:
            try:
                # Build URL with pagination
                page_url = url if page == 0 else f"{url}&offset={500 * page}"
                
                logger.info(f"Fetching page {page + 1}...")
                response = requests.get(page_url, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                # Parse response
                data = response.json()
                
                # Save raw response if requested
                if save_raw and self.config.predictions_bucket:
                    self._save_raw_response(response, page)
                
                # Filter out history field (large and not needed)
                filtered_data = [
                    {k: v for k, v in item.items() if k != "history"}
                    for item in data
                ]
                
                if not filtered_data:
                    logger.info(f"No more listings found on page {page + 1}")
                    break
                
                all_listings.extend(filtered_data)
                logger.info(f"Collected {len(filtered_data)} listings from page {page + 1}")
                
                # Check if we got a full page (if not, we're done)
                if len(filtered_data) < 500:
                    logger.info("Received partial page, ending collection")
                    break
                
                page += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"API request failed on page {page + 1}: {e}")
                if page == 0:
                    # If first page fails, raise error
                    raise
                else:
                    # If later page fails, just log and continue with what we have
                    logger.warning(f"Continuing with {len(all_listings)} listings collected so far")
                    break
            
            except Exception as e:
                logger.error(f"Unexpected error on page {page + 1}: {e}")
                raise
        
        # Convert to DataFrame
        df = pd.DataFrame(all_listings)
        
        logger.info(f"✅ Data collection complete: {len(df)} total listings")
        logger.info(f"Columns: {list(df.columns)}")
        
        return df
    
    def _save_raw_response(self, response: requests.Response, page: int):
        """Save raw API response to S3 for debugging/auditing"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"raw/rentcast_response_{timestamp}_page_{page}.json"
            
            self.s3_client.put_object(
                Bucket=self.config.predictions_bucket,
                Key=filename,
                Body=response.text,
                ContentType='application/json'
            )
            
            logger.debug(f"Saved raw response to s3://{self.config.predictions_bucket}/{filename}")
            
        except Exception as e:
            logger.warning(f"Could not save raw response to S3: {e}")
    
    def save_to_s3(self, df: pd.DataFrame, prefix: str = "daily") -> str:
        """
        Save DataFrame to S3.
        
        Args:
            df: DataFrame to save
            prefix: S3 key prefix (e.g., 'daily', 'training')
        
        Returns:
            S3 key where data was saved
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{prefix}/listings_{timestamp}.csv"
        
        # Save to local file first (Lambda /tmp directory)
        local_file = f"/tmp/listings_{timestamp}.csv"
        df.to_csv(local_file, index=False)
        
        # Upload to S3
        bucket = self.config.predictions_bucket or self.config.training_bucket
        
        self.s3_client.upload_file(
            local_file,
            bucket,
            filename
        )
        
        logger.info(f"Saved data to s3://{bucket}/{filename}")
        
        # Clean up local file
        try:
            os.remove(local_file)
        except Exception as e:
            logger.warning(f"Could not remove temp file: {e}")
        
        return filename
    
    def get_collection_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get statistics about collected data"""
        stats = {
            'total_listings': len(df),
            'unique_ids': df['id'].nunique() if 'id' in df.columns else 0,
            'timestamp': datetime.now().isoformat(),
        }
        
        # Price statistics
        if 'price' in df.columns:
            stats.update({
                'avg_price': float(df['price'].mean()),
                'median_price': float(df['price'].median()),
                'min_price': float(df['price'].min()),
                'max_price': float(df['price'].max()),
                'price_std': float(df['price'].std())
            })
        
        # Property type distribution
        if 'propertyType' in df.columns:
            stats['property_types'] = df['propertyType'].value_counts().to_dict()
        
        # Bedroom distribution
        if 'bedrooms' in df.columns:
            stats['bedroom_dist'] = df['bedrooms'].value_counts().to_dict()
        
        return stats


def data_pull(api_key: Optional[str] = None, max_pages: int = 15) -> pd.DataFrame:
    """
    Legacy function for backward compatibility.
    
    Args:
        api_key: Optional API key
        max_pages: Maximum pages to fetch
    
    Returns:
        DataFrame with listings
    """
    collector = ApartmentDataCollector(api_key=api_key)
    return collector.collect_listings(max_pages=max_pages)


# Example usage
if __name__ == '__main__':
    # For local testing
    collector = ApartmentDataCollector()
    df = collector.collect_listings(max_pages=2)
    
    print(f"Collected {len(df)} listings")
    print(df.head())
    
    stats = collector.get_collection_stats(df)
    print(json.dumps(stats, indent=2, default=str))
