"""
Daily apartment predictions Lambda handler.

This function runs daily to:
1. Fetch new apartment listings from Rentcast API
2. Load the latest trained model from MLflow
3. Make price predictions
4. Identify good deals (apartments priced below prediction)
5. Send email alerts for best deals
6. Accumulate data for training
7. Monitor and log metrics
"""

import json
import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, List

import pandas as pd
import numpy as np
import boto3
import mlflow

# Add paths for imports
sys.path.append('/app')

# Import our modules
from src.config.environment import get_config, get_secret
from src.data.collection import ApartmentDataCollector
from src.data.accumulator import TrainingDataAccumulator
from src.models.training import create_X
from src.monitoring.config import MLPipelineMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize services
config = get_config()
monitor = MLPipelineMonitor()
s3_client = boto3.client('s3', region_name=config.aws_region)
ses_client = boto3.client('ses', region_name=config.aws_region)


def make_json_safe(obj):
    """Convert numpy types to JSON-serializable Python types"""
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj


def load_model():
    """Load the latest trained model from MLflow"""
    try:
        logger.info("Loading model from MLflow...")
        
        # Get MLflow tracking URI from environment (set by Terraform)
        mlflow_tracking_uri = os.environ.get('MLFLOW_TRACKING_URI')
        if mlflow_tracking_uri:
            logger.info(f"Using MLflow tracking URI: {mlflow_tracking_uri}")
            mlflow.set_tracking_uri(mlflow_tracking_uri)
        else:
            logger.warning("MLFLOW_TRACKING_URI not set, using default")
        
        # Option 1: Try to load from latest_run.json in S3
        try:
            mlflow_bucket = os.environ.get('MLFLOW_BUCKET')
            
            if mlflow_bucket:
                run_info_obj = s3_client.get_object(
                    Bucket=mlflow_bucket,
                    Key='models/latest_run.json'
                )
                run_info = json.loads(run_info_obj['Body'].read().decode('utf-8'))
                run_id = run_info['run_id']
                logger.info(f"Using model from run_id: {run_id}")
                
                # Load model using MLflow pyfunc (works with both S3 and server)
                model_uri = f"runs:/{run_id}/model"
                model = mlflow.pyfunc.load_model(model_uri)
                logger.info(f"✅ Model loaded successfully from run {run_id}")
                return model, run_id
        except Exception as e:
            logger.warning(f"Could not load from latest_run.json: {e}")
        
        # Option 2: Load from registered model
        try:
            environment = os.environ.get('ENVIRONMENT', 'staging')
            model_name = f"apartment-rental-predictor-{environment}"
            model_uri = f"models:/{model_name}/latest"
            model = mlflow.pyfunc.load_model(model_uri)
            logger.info(f"✅ Model loaded from registered model: {model_name}")
            return model, model_name
        except Exception as e:
            logger.error(f"Failed to load from registered model: {e}")
            raise Exception("Could not load model from MLflow - no valid model found")
        
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


def make_predictions(df: pd.DataFrame, model) -> pd.DataFrame:
    """
    Make price predictions for apartments.
    
    Args:
        df: DataFrame with apartment features
        model: Trained model pipeline
    
    Returns:
        DataFrame with predictions added
    """
    try:
        logger.info(f"Making predictions for {len(df)} apartments...")
        
        # Prepare features (same as training)
        df_copy = df.copy()
        X = create_X(df_copy)
        
        # Make predictions
        predictions = model.predict(X)
        
        # Add predictions to dataframe
        df['price_preds'] = predictions
        df['price_diff'] = df['price'] - df['price_preds']
        
        logger.info("✅ Predictions completed")
        logger.info(f"   - Average predicted price: ${df['price_preds'].mean():.2f}")
        logger.info(f"   - Average actual price: ${df['price'].mean():.2f}")
        logger.info(f"   - Average difference: ${df['price_diff'].mean():.2f}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error making predictions: {e}")
        raise


def identify_good_deals(
    df: pd.DataFrame,
    min_savings: float = 100.0,
    max_deals: int = 20
) -> pd.DataFrame:
    """
    Identify apartments that are good deals.
    
    Args:
        df: DataFrame with predictions
        min_savings: Minimum savings to be considered a good deal
        max_deals: Maximum number of deals to return
    
    Returns:
        DataFrame with good deals, sorted by savings
    """
    # Find apartments priced below prediction
    good_deals = df[df['price_diff'] > min_savings].copy()
    
    # Sort by price difference (best deals first)
    good_deals = good_deals.sort_values('price_diff', ascending=False)
    
    # Limit to top deals
    good_deals = good_deals.head(max_deals)
    
    logger.info(f"✅ Identified {len(good_deals)} good deals (>${min_savings} savings)")
    
    return good_deals


def format_deal_for_email(deal: pd.Series) -> str:
    """Format a single deal for email"""
    return f"""
🏠 {deal.get('propertyType', 'Property')} - ${deal.get('price', 0):,.0f}/month
   💰 Predicted Fair Price: ${deal['price_preds']:,.0f}
   ✅ Your Savings: ${deal['price_diff']:,.0f}/month
   
   📍 Location: {deal.get('city', 'N/A')}, NJ
   🛏️  {deal.get('bedrooms', 'N/A')} bed, {deal.get('bathrooms', 'N/A')} bath
   📅 Built: {deal.get('yearBuilt', 'N/A')}
   📏 Lot Size: {deal.get('lotSize', 'N/A'):,.0f} sq ft
   
   🔗 Link: {deal.get('url', 'No URL available')}
    """.strip()


def send_email_alert(good_deals: pd.DataFrame, total_listings: int):
    """
    Send email alert with good deals.
    
    Args:
        good_deals: DataFrame with good deals
        total_listings: Total number of listings processed
    """
    try:
        # Get email addresses from secrets
        try:
            sender_email = get_secret('SENDER_EMAIL')
            recipient_email = get_secret('RECIPIENT_EMAIL')
        except Exception as e:
            logger.warning(f"Could not get email addresses from secrets: {e}")
            # Fallback to environment variables
            sender_email = os.environ.get('SENDER_EMAIL')
            recipient_email = os.environ.get('RECIPIENT_EMAIL')
        
        if not sender_email or not recipient_email:
            logger.warning("Email addresses not configured, skipping email alert")
            return
        
        # Prepare email content
        if len(good_deals) == 0:
            subject = f"🏠 No Great Deals Today ({total_listings} listings checked)"
            body = f"""
Hello!

Today's apartment scan didn't find any exceptional deals.

📊 Summary:
- Total listings checked: {total_listings}
- Good deals found: 0
- Minimum savings threshold: $100/month

The model will keep monitoring and alert you when better opportunities appear.

Happy house hunting!
            """.strip()
        else:
            subject = f"🎉 {len(good_deals)} Great Apartment Deals Found!"
            
            deals_text = "\n\n" + "="*60 + "\n\n".join([
                format_deal_for_email(deal)
                for _, deal in good_deals.iterrows()
            ])
            
            total_savings = good_deals['price_diff'].sum()
            avg_savings = good_deals['price_diff'].mean()
            
            body = f"""
Hello!

Found {len(good_deals)} great apartment deals today! 🎉

📊 Summary:
- Total listings checked: {total_listings}
- Good deals found: {len(good_deals)}
- Average savings: ${avg_savings:,.0f}/month
- Total potential savings: ${total_savings:,.0f}/month

{deals_text}

💡 These apartments are priced significantly below their predicted fair market value based on location, size, and features.

Happy house hunting!
            """.strip()
        
        # Send email via SES
        response = ses_client.send_email(
            Source=sender_email,
            Destination={'ToAddresses': [recipient_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body}}
            }
        )
        
        logger.info(f"✅ Email sent successfully (MessageId: {response['MessageId']})")
        
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        # Don't raise - email failure shouldn't fail the whole function


def save_results_to_s3(df: pd.DataFrame, good_deals: pd.DataFrame) -> Dict[str, str]:
    """
    Save results to S3 for record keeping.
    
    Returns:
        Dictionary with S3 keys where data was saved
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        date_prefix = datetime.now().strftime('%Y/%m/%d')
        
        # Save all predictions
        predictions_key = f"daily/{date_prefix}/predictions_{timestamp}.csv"
        csv_buffer = df.to_csv(index=False)
        
        s3_client.put_object(
            Bucket=config.predictions_bucket or config.training_bucket,
            Key=predictions_key,
            Body=csv_buffer,
            ContentType='text/csv'
        )
        
        # Save good deals separately
        deals_key = None
        if len(good_deals) > 0:
            deals_key = f"daily/{date_prefix}/good_deals_{timestamp}.csv"
            deals_csv = good_deals.to_csv(index=False)
            
            s3_client.put_object(
                Bucket=config.predictions_bucket or config.training_bucket,
                Key=deals_key,
                Body=deals_csv,
                ContentType='text/csv'
            )
        
        logger.info(f"✅ Results saved to S3:")
        logger.info(f"   - Predictions: {predictions_key}")
        if deals_key:
            logger.info(f"   - Good deals: {deals_key}")
        
        return {
            'predictions_key': predictions_key,
            'deals_key': deals_key
        }
        
    except Exception as e:
        logger.error(f"Error saving results to S3: {e}")
        return {}


def lambda_handler(event, context):
    """
    Main Lambda handler for daily predictions.
    
    Event parameters:
        - dry_run (bool): If True, skip data collection and email
        - limit (int): Limit number of listings to process (for testing)
        - min_savings (float): Minimum savings for good deals
    """
    try:
        logger.info(f"Starting daily predictions at {datetime.now()}")
        logger.info(f"Environment: {config.environment}")
        logger.info(f"Event: {json.dumps(event)}")
        
        monitor.log_pipeline_start('daily_predictions', event)
        
        # Parse event parameters
        dry_run = event.get('dry_run', True)
        limit = event.get('limit', None)
        min_savings = event.get('min_savings', 100.0)
        
        if dry_run:
            logger.info("🧪 DRY RUN MODE - Using sample data, no emails")
        
        # Step 1: Collect apartment listings
        if not dry_run:
            logger.info("Step 1: Collecting apartment listings...")
            collector = ApartmentDataCollector()
            df = collector.collect_listings(max_pages=15)
            
            if limit:
                df = df.head(limit)
                logger.info(f"Limited to {limit} listings for testing")
        else:
            # For dry run, create sample data
            logger.info("Creating sample data for dry run...")
            df = pd.DataFrame({
                'id': range(10),
                'price': [2000, 2200, 1800, 2500, 1900, 2100, 2300, 1850, 2050, 2150],
                'latitude': [40.8] * 10,
                'longitude': [-74.4] * 10,
                'propertyType': ['Apartment'] * 10,
                'bedrooms': [2] * 10,
                'bathrooms': [2] * 10,
                'yearBuilt': [2015] * 10,
                'lotSize': [1200] * 10,
            })
        
        # Log data quality
        monitor.log_data_quality_metrics(df, 'daily_listings')
        
        # Step 2: Load model
        if not dry_run:
            logger.info("Step 2: Loading trained model...")
            model, run_id = load_model()
        else:
            logger.info("Step 2: Skipping model load in dry run mode")
            logger.info("   Creating dummy model for testing...")
            
            # Create a simple dummy model for dry run testing
            from sklearn.linear_model import LinearRegression
            from sklearn.pipeline import Pipeline
            from src.models.training import LabelEncoderTransformer
            
            # Train a quick dummy model on the sample data
            X_sample = create_X(df.copy())
            dummy_regressor = LinearRegression()
            
            model = Pipeline([
                ('encoder', LabelEncoderTransformer()),
                ('regressor', dummy_regressor)
            ])
            
            # Fit on sample data so predictions work
            model.fit(X_sample, df['price'])
            run_id = "dry-run-dummy-model"
            
            logger.info("   ✅ Dummy model created for dry run")
        
        # Step 3: Make predictions
        logger.info("Step 3: Making predictions...")
        df = make_predictions(df, model)
        
        # Step 4: Identify good deals
        logger.info("Step 4: Identifying good deals...")
        good_deals = identify_good_deals(df, min_savings=min_savings)
        
        # Step 5: Save results to S3
        logger.info("Step 5: Saving results to S3...")
        s3_keys = save_results_to_s3(df, good_deals)
        
        # Step 6: Accumulate data for training
        logger.info("Step 6: Accumulating data for training...")
        accumulator = TrainingDataAccumulator()
        accumulation_stats = accumulator.add_daily_predictions(df)
        
        # Step 7: Send email alerts (unless dry run)
        if not dry_run and len(good_deals) > 0:
            logger.info("Step 7: Sending email alerts...")
            send_email_alert(good_deals, len(df))
        else:
            logger.info("Step 7: Skipping email (dry run or no deals)")
        
        # Prepare results
        results = make_json_safe({
            'total_predictions': len(df),
            'best_deals_count': len(good_deals),
            'avg_predicted_price': float(df['price_preds'].mean()),
            'avg_actual_price': float(df['price'].mean()),
            'top_saving': float(good_deals['price_diff'].max()) if len(good_deals) > 0 else 0,
            'model_run_id': run_id,
            's3_keys': s3_keys,
            'accumulation_stats': accumulation_stats,
            'dry_run': dry_run
        })
        
        logger.info("✅ Daily predictions completed successfully!")
        logger.info(f"Results: {json.dumps(results, indent=2)}")
        
        monitor.log_pipeline_success('daily_predictions', results)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Daily predictions completed successfully',
                'results': results,
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        error_message = f"Daily predictions failed: {str(e)}"
        logger.error(error_message, exc_info=True)
        
        monitor.log_pipeline_failure('daily_predictions', e, {
            'event': event,
            'context': str(context)
        })
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }


# For local testing
if __name__ == "__main__":
    # Simulate Lambda event
    test_event = {
        'dry_run': True,
        'limit': 50
    }
    
    class MockContext:
        pass
    
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
