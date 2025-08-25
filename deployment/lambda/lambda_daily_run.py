# lambda_daily_run.py - Updated with Evidently monitoring for apartment rental pipeline
import json
import os
import boto3
import sys
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import mlflow
import psycopg
import logging
from io import StringIO

from training_model import find_station
from initial_data_pull_test import data_pull
from email_options import send_predictions_email
from monitoring_config import MLPipelineMonitor
from src.data.accumulator import TrainingDataAccumulator

from evidently import ColumnMapping
from evidently.report import Report
from evidently.metrics import (
    ColumnDriftMetric, 
    DatasetDriftMetric, 
    DatasetMissingValuesMetric,
    ColumnSummaryMetric,
    RegressionQualityMetric
)

# sys.path.append('/app')  # For Docker/Lambda
sys.path.append('../../')  # For local development

# Initialize AWS clients
s3_client = boto3.client('s3')
ssm_client = boto3.client('ssm')

# Configuration using your specific buckets
MLFLOW_BUCKET = 'mlflow-artifact-mmichal'
TRAINING_BUCKET = 'training-data-bucket-mmichal-apartments-nj'
MLFLOW_TRACKING_URI = os.environ.get('MLFLOW_TRACKING_URI')

# Initialize monitor
monitor = MLPipelineMonitor()

# # Features for apartment rental model
NUMERICAL_FEATURES = ['latitude', 'longitude', 'bedrooms', 'bathrooms', 'yearBuilt', 'lotSize']
CATEGORICAL_FEATURES = ['station', 'propertyType']
# ALL_FEATURES = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
# Match the exact order the model was trained with
ALL_FEATURES = ['latitude', 'longitude', 'station', 'propertyType', 'bedrooms', 'bathrooms', 'yearBuilt', 'lotSize']
TARGET_COLUMN = 'price'
PREDICTION_COLUMN = 'price_preds'

# Database setup for metrics
CREATE_METRICS_TABLE = """
CREATE TABLE IF NOT EXISTS apartment_metrics (
    timestamp TIMESTAMP,
    prediction_drift FLOAT,
    num_drifted_columns INTEGER,
    share_missing_values FLOAT,
    target_drift FLOAT,
    prediction_mae FLOAT,
    prediction_rmse FLOAT,
    data_points INTEGER,
    avg_predicted_price FLOAT,
    avg_actual_price FLOAT,
    price_diff_std FLOAT,
    good_deals_count INTEGER
);
"""

# Add to lambda_daily_run.py
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")

def get_secret_parameter(parameter_name):
    """Get parameter from AWS Systems Manager Parameter Store"""
    try:
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error getting parameter {parameter_name}: {e}")
        return None

def get_db_connection():
    """Get PostgreSQL connection for metrics storage"""
    try:
        # Get DB credentials from Parameter Store
        db_host = get_secret_parameter('/ml-pipeline/db-host') or 'localhost'
        db_port = get_secret_parameter('/ml-pipeline/db-port') or '5432'
        db_name = get_secret_parameter('/ml-pipeline/db-name') or 'apartment_monitoring'
        db_user = get_secret_parameter('/ml-pipeline/db-user') or 'postgres'
        db_password = get_secret_parameter('/ml-pipeline/db-password') or 'example'
        
        conn_string = f"host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password}"
        return psycopg.connect(conn_string, autocommit=True)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def setup_database():
    """Setup database and tables for metrics"""
    try:
        conn = get_db_connection()
        if conn:
            with conn.cursor() as curr:
                curr.execute(CREATE_METRICS_TABLE)
            conn.close()
            print("Database setup completed")
    except Exception as e:
        print(f"Error setting up database: {e}")

def load_data_with_fallback():
    """Load data with multiple fallback options"""
    try:
        # Try to get API key from Parameter Store
        api_key = get_secret_parameter('/ml-pipeline/api-key')
        if api_key:
            os.environ['API_KEY'] = api_key
        
        # Pull fresh data with debugging
        df = data_pull()
        print(f"API response type: {type(df)}")
        print(f"API response (first 200 chars): {str(df)[:200]}")

        if isinstance(df, str):
            print(f"Full API response: {df}")
            raise Exception(f"API returned string instead of DataFrame: {df}")
            
        if df is None:
            raise Exception("API returned None")
            
        print(f"Fresh data pulled successfully: {df.shape}")
        
        # Validate the data_pull result
        if isinstance(df, str):
            print(f"API returned string instead of DataFrame: {df[:100]}...")
            raise Exception("API returned invalid format")
        
        if df is None or len(df) == 0:
            raise Exception("No data returned from API")
            
        print(f"Fresh data pulled: {df.shape}")
        
        # Save fresh data to S3 for backup
        current_date = datetime.now().strftime('%Y%m%d_%H%M')
        csv_file = f'data_pull_{current_date}.csv'
        df.to_csv(csv_file, index=False)
        s3_client.upload_file(csv_file, TRAINING_BUCKET, f'daily-data/{csv_file}')
        
        return df
        
    except Exception as e:
        print(f"Error pulling fresh data: {e}")
        
        # Try to load cached data from S3
        try:
            # Look for the most recent data file
            response = s3_client.list_objects_v2(
                Bucket=TRAINING_BUCKET,
                Prefix='daily-data/',
                MaxKeys=10
            )
            
            if 'Contents' in response:
                latest_file = sorted(response['Contents'], key=lambda x: x['LastModified'])[-1]
                cached_file = 'cached_data.csv'
                s3_client.download_file(TRAINING_BUCKET, latest_file['Key'], cached_file)
                df = pd.read_csv(cached_file)
                print(f"Using cached data: {df.shape}")
                return df
            else:
                raise ValueError("No cached data available")
                
        except Exception as cache_error:
            print(f"Error loading cached data: {cache_error}")
            
            # Final fallback: create mock current data for testing
            print("Creating mock data for testing...")
            mock_data = pd.DataFrame({
                'id': range(1, 21),
                'latitude': [40.7128 + i*0.01 for i in range(20)],
                'longitude': [-74.0060 - i*0.005 for i in range(20)],
                'propertyType': ['Apartment'] * 20,
                'bedrooms': [2, 3, 1, 2, 3] * 4,
                'bathrooms': [1, 2, 1, 1, 2] * 4,
                'yearBuilt': [2010 + i for i in range(20)],
                'lotSize': [1000 + i*50 for i in range(20)],
                'price': [2500 + i*100 for i in range(20)]
            })
            
            print(f"Mock data created: {mock_data.shape}")
            return mock_data

def load_reference_data():
    """Load reference data for drift detection"""
    try:
        # Fix: Use current directory instead of /tmp to avoid Windows path issues
        reference_file = 'reference_data.csv'
        s3_client.download_file(TRAINING_BUCKET, 'reference-data/reference_data.csv', reference_file)
        reference_data = pd.read_csv(reference_file)
        print(f"Reference data loaded: {reference_data.shape}")
        return reference_data
    except Exception as e:
        print(f"Error loading reference data: {e}")
        # If no reference data exists, create it from training data
        try:
            # Load training data as reference
            training_file = 'training_ref.csv'
            s3_client.download_file(TRAINING_BUCKET, 'training_load.csv', training_file)
            reference_data = pd.read_csv(training_file).sample(n=min(1000, len(pd.read_csv(training_file))))
            
            # Add station information
            reference_data['lat_long'] = reference_data.latitude.astype(str) + '_' + reference_data.longitude.astype(str)
            reference_data['station'] = reference_data.lat_long.apply(find_station)
            
            # Save as reference data to S3
            reference_data.to_csv('reference_data.csv', index=False)
            s3_client.upload_file('reference_data.csv', TRAINING_BUCKET, 'reference-data/reference_data.csv')
            
            print(f"Created reference data from training set: {reference_data.shape}")
            return reference_data
        except Exception as ref_error:
            print(f"Error creating reference data: {ref_error}")
            return None

def calculate_evidently_metrics(current_data, reference_data, timestamp):
    """Calculate Evidently metrics and store in database"""
    try:
        # Ensure both datasets have the same columns
        common_columns = list(set(current_data.columns) & set(reference_data.columns))
        current_subset = current_data[common_columns].copy()
        reference_subset = reference_data[common_columns].copy()
        
        # Handle missing values
        current_subset = current_subset.fillna(0)
        reference_subset = reference_subset.fillna(0)

        for col in current_subset.columns:
            if current_subset[col].dtype == 'object':
                # Convert any dict/complex objects to strings
                current_subset[col] = current_subset[col].astype(str)
                reference_subset[col] = reference_subset[col].astype(str)
        
        # Column mapping for Evidently
        column_mapping = ColumnMapping(
            target=TARGET_COLUMN,
            prediction=PREDICTION_COLUMN,
            numerical_features=[col for col in NUMERICAL_FEATURES if col in common_columns],
            categorical_features=[col for col in CATEGORICAL_FEATURES if col in common_columns]
        )
        
        # Create Evidently report
        report = Report(metrics=[
            ColumnDriftMetric(column_name=PREDICTION_COLUMN),
            ColumnDriftMetric(column_name=TARGET_COLUMN),
            DatasetDriftMetric(),
            DatasetMissingValuesMetric(),
            RegressionQualityMetric() if TARGET_COLUMN in current_subset.columns else ColumnSummaryMetric(column_name=PREDICTION_COLUMN)
        ])
        
        # Run the report
        report.run(
            reference_data=reference_subset,
            current_data=current_subset,
            column_mapping=column_mapping
        )
        
        result = report.as_dict()
        
        # Extract metrics
        prediction_drift = result['metrics'][0]['result']['drift_score']
        target_drift = result['metrics'][1]['result']['drift_score'] if len(result['metrics']) > 1 else 0
        num_drifted_columns = result['metrics'][2]['result']['number_of_drifted_columns']
        share_missing_values = result['metrics'][3]['result']['current']['share_of_missing_values']
        
        # Regression quality metrics if available
        prediction_mae = 0
        prediction_rmse = 0
        if len(result['metrics']) > 4 and 'mean_abs_error' in result['metrics'][4]['result']['current']:
            prediction_mae = result['metrics'][4]['result']['current']['mean_abs_error']
            prediction_rmse = result['metrics'][4]['result']['current']['rmse']
        
        # Additional business metrics
        avg_predicted_price = float(current_data[PREDICTION_COLUMN].mean())
        avg_actual_price = float(current_data[TARGET_COLUMN].mean()) if TARGET_COLUMN in current_data.columns else 0
        price_diff_std = float(current_data['price_diff'].std()) if 'price_diff' in current_data.columns else 0
        good_deals_count = int((current_data['price_diff'] > 100).sum()) if 'price_diff' in current_data.columns else 0
        
        # Store metrics in database
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as curr:
                    curr.execute(
                        """INSERT INTO apartment_metrics 
                           (timestamp, prediction_drift, num_drifted_columns, share_missing_values, 
                            target_drift, prediction_mae, prediction_rmse, data_points, 
                            avg_predicted_price, avg_actual_price, price_diff_std, good_deals_count) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (timestamp, prediction_drift, num_drifted_columns, share_missing_values,
                         target_drift, prediction_mae, prediction_rmse, len(current_data),
                         avg_predicted_price, avg_actual_price, price_diff_std, good_deals_count)
                    )
                conn.close()
                print(f"Metrics stored for timestamp: {timestamp}")
            except Exception as db_error:
                print(f"Error storing metrics in database: {db_error}")
                conn.close()
        
        # Save report to S3
        report_json = json.dumps(result, indent=2, default=str)
        report_file = f'evidently_report_{timestamp.strftime("%Y%m%d_%H%M")}.json'  # Current directory
        with open(report_file, 'w') as f:
            f.write(report_json)
        
        s3_client.upload_file(
            report_file, 
            MLFLOW_BUCKET, 
            f'monitoring/evidently_reports/report_{timestamp.strftime("%Y%m%d_%H%M")}.json'
        )
        
        return {
            'prediction_drift': prediction_drift,
            'target_drift': target_drift,
            'num_drifted_columns': num_drifted_columns,
            'share_missing_values': share_missing_values,
            'prediction_mae': prediction_mae,
            'prediction_rmse': prediction_rmse
        }
        
    except Exception as e:
        print(f"Error calculating Evidently metrics: {e}")
        return None

def load_pipeline():
    """Load ML pipeline from MLflow using your bucket"""
    try:
        # Try to get run_id from your MLflow bucket
        run_id = None
        try:
            response = s3_client.get_object(Bucket=MLFLOW_BUCKET, Key='models/run_id.txt')
            run_id = response['Body'].read().decode('utf-8').strip()
            print(f"Loaded run_id from S3: {run_id}")
        except Exception as e:
            print(f"Could not load run_id from S3: {e}")
        
        if run_id:
            model_uri = f"runs:/{run_id}/pipeline_model"
        else:
            # Fallback to latest model from registry
            model_uri = "models:/apartment-rent-pipeline/latest"
        
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        loaded_pipeline = mlflow.sklearn.load_model(model_uri)
        print(f"Successfully loaded pipeline from: {model_uri}")
        return loaded_pipeline
        
    except Exception as e:
        print(f"Error loading pipeline: {e}")
        raise

def load_data():
    """Load and prepare data with fixed file paths"""
    try:
        # Get API key from Parameter Store
        api_key = get_secret_parameter('/ml-pipeline/api-key')
        
        # Pass API key directly to data_pull function
        df = data_pull(api_key=api_key)
        print(f"Fresh data pulled: {df.shape}")
        
        # Save fresh data to S3 for backup with fixed path
        current_date = datetime.now().strftime('%d%B%Y')
        csv_file = f'data_pull_{current_date}.csv'
        df.to_csv(csv_file, index=False)
        s3_client.upload_file(csv_file, TRAINING_BUCKET, f'daily-data/data_pull_{current_date}.csv')
        
    except Exception as e:
        print(f"Error pulling fresh data: {e}")
        # Try to load cached data from S3
        try:
            response = s3_client.list_objects_v2(
                Bucket=TRAINING_BUCKET,
                Prefix='daily-data/',
                MaxKeys=10
            )
            
            if 'Contents' in response:
                latest_file = sorted(response['Contents'], key=lambda x: x['LastModified'])[-1]
                cached_file = 'cached_data.csv'
                s3_client.download_file(TRAINING_BUCKET, latest_file['Key'], cached_file)
                df = pd.read_csv(cached_file)
                print(f"Using cached data: {df.shape}")
            else:
                raise ValueError("No cached data available")
        except Exception as cache_error:
            print(f"Error loading cached data: {cache_error}")
            raise ValueError("No data available - both fresh pull and cached data failed")
    
    # CRITICAL: Prepare the features that your model expects
    df['lat_long'] = df.latitude.astype(str) + '_' + df.longitude.astype(str)
    df['station'] = df.lat_long.apply(find_station)
    
    print(f"Features prepared. Data shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    
    return df

def predict_and_monitor(df, pipeline, reference_data):
    """Make predictions, calculate metrics, and send email"""
    # Make predictions
    predictions = pipeline.predict(df[ALL_FEATURES])
    df[PREDICTION_COLUMN] = predictions
    df['price_diff'] = df[TARGET_COLUMN] - df[PREDICTION_COLUMN]
    
    current_timestamp = datetime.now()
    
    # Calculate Evidently metrics
    evidently_metrics = calculate_evidently_metrics(df, reference_data, current_timestamp)
    
    # Log data quality metrics using existing monitor
    monitor.log_data_quality_metrics(df, 'predictions')
    
    # Save results to S3
    current_date = current_timestamp.strftime('%Y%m%d_%H%M')
    results_file = f'predictions_{current_date}.csv'  # Current directory
    df.to_csv(results_file, index=False)
    s3_client.upload_file(results_file, MLFLOW_BUCKET, f'predictions/predictions_{current_date}.csv')

    try:
        accumulator = TrainingDataAccumulator()
        accumulation_stats = accumulator.add_daily_predictions(df)
        print(f"✅ Training data accumulated: {accumulation_stats}")
    except Exception as e:
        print(f"⚠️ Training accumulation failed: {e}")

    # Send email
    try:
        email_password = get_secret_parameter('/ml-pipeline/email-password')
        if email_password:
            send_predictions_email(
                df=df.sort_values('price_diff'),
                recipient_emails="Enter email",
                sender_email="Enter email",
                sender_password=email_password
            )
            print("Email sent successfully")
    except Exception as e:
        print(f"Error sending email: {e}")
        # Don't fail the entire pipeline if email fails
    
    return df, evidently_metrics

def lambda_handler(event, context):
    """Main Lambda handler for daily predictions with monitoring"""
    try:
        print(f"Starting daily prediction run with monitoring at {datetime.now()}")
        monitor.log_pipeline_start('daily_predictions', event)
        
        # Setup database for metrics
        setup_database()
        
        # Load pipeline, reference data, and current data
        pipeline = load_pipeline()
        reference_data = load_reference_data()
        current_data = load_data()
        
        # Make predictions and calculate monitoring metrics
        results_df, evidently_metrics = predict_and_monitor(current_data, pipeline, reference_data)
        
        # Log summary results
        results = {
            'total_predictions': len(results_df),
            'avg_predicted_price': float(results_df[PREDICTION_COLUMN].mean()),
            'avg_actual_price': float(results_df[TARGET_COLUMN].mean()) if TARGET_COLUMN in results_df.columns else None,
            'price_diff_std': float(results_df['price_diff'].std()),
            'best_deals_count': int((results_df['price_diff'] > 100).sum()),
            'monitoring_metrics': evidently_metrics
        }
        
        print(f"Predictions completed for {len(results_df)} properties")
        print(f"Average predicted price: ${results['avg_predicted_price']:.2f}")
        print(f"Properties with good deals (>$100 under predicted): {results['best_deals_count']}")
        
        if evidently_metrics:
            print(f"Data drift detected in {evidently_metrics['num_drifted_columns']} columns")
            print(f"Prediction drift score: {evidently_metrics['prediction_drift']:.4f}")
        
        # Log top deals
        top_deals = results_df.nlargest(10, 'price_diff')[['id', TARGET_COLUMN, PREDICTION_COLUMN, 'price_diff', 'station']]
        print("Top 10 deals:")
        print(top_deals.to_string())
        
        monitor.log_pipeline_success('daily_predictions', results)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Daily predictions with monitoring completed successfully',
                'results': results,
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Lambda execution failed: {str(e)}")
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