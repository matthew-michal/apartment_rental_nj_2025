# lambda_training.py - Updated for your AWS setup

import json
import os
import boto3
import numpy as np
from datetime import datetime
import pandas as pd
import mlflow
from sklearn.model_selection import train_test_split
from training_model import (
    LabelEncoderTransformer, find_station, tune_models, 
    train_model, create_X
)
from monitoring_config import MLPipelineMonitor

# Initialize AWS clients and monitor
s3_client = boto3.client('s3')
ssm_client = boto3.client('ssm')
monitor = MLPipelineMonitor()

# Configuration using your specific buckets
MLFLOW_BUCKET = 'mlflow-artifact-mmichal'
TRAINING_BUCKET = 'training-data-bucket-mmichal-apartments-nj'
MLFLOW_TRACKING_URI = os.environ.get('MLFLOW_TRACKING_URI')

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

def download_training_data():
    """Download training data from your S3 bucket"""
    try:
        print("Downloading training data from S3...")
        
        # Use forward slashes and avoid temp directory issues
        local_file = 'training_load.csv'  # Use current directory instead of /tmp
        s3_client.download_file(TRAINING_BUCKET, 'training_load.csv', local_file)
        
        # Load data
        df = pd.read_csv(local_file)
        
        print(f"Training data loaded: {df.shape}")
        print(f"Data columns: {list(df.columns)}")
        
        # Log data quality
        monitor.log_data_quality_metrics(df, 'training_data')
        
        return df
        
    except Exception as e:
        print(f"Error loading training data: {e}")
        raise

def save_model_artifacts(run_id):
    """Save model artifacts to your S3 buckets"""
    try:
        # Use current directory instead of /tmp for Windows compatibility
        run_id_file = 'run_id.txt'
        
        with open(run_id_file, 'w') as f:
            f.write(run_id)
        
        s3_client.upload_file(run_id_file, MLFLOW_BUCKET, 'models/run_id.txt')
        
        # Also save with timestamp for versioning
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        s3_client.upload_file(run_id_file, MLFLOW_BUCKET, f'models/run_id_{timestamp}.txt')
        
        print(f"Model artifacts saved for run_id: {run_id}")
        
        # Save training metadata
        metadata = {
            'run_id': run_id,
            'timestamp': datetime.now().isoformat(),
            'training_completed': True
        }
        
        metadata_file = 'training_metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        s3_client.upload_file(metadata_file, MLFLOW_BUCKET, f'models/training_metadata_{timestamp}.json')
        
    except Exception as e:
        print(f"Error saving model artifacts: {e}")
        raise

def lambda_handler(event, context):
    """Main Lambda handler for model training"""
    try:
        print(f"Starting model training at {datetime.now()}")
        monitor.log_pipeline_start('training', event)
        
        # Set MLflow tracking URI
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment("north-nj-apartments-experiment-v3")
        
        # Load training data from your S3 bucket
        df = download_training_data()
        
        # Prepare features
        feats = [
            'latitude', 'longitude',
            'propertyType','bedrooms', 'bathrooms', 'yearBuilt', 'lotSize'
        ]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            df[feats], df.price, test_size=0.2, random_state=42
        )
        
        print(f"Training set size: {X_train.shape}")
        print(f"Test set size: {X_test.shape}")
        
        # Create features (add station information)
        X_train = create_X(X_train)
        X_test = create_X(X_test)
        
        # Hyperparameter tuning
        print("Starting hyperparameter tuning...")
        best_params, best_rmse = tune_models(X_train, y_train, X_test, y_test)
        print(f"Best hyperparameters found with RMSE: {best_rmse}")
        
        # Train final model
        print("Training final model...")
        run_id = train_model(X_train, y_train, X_test, y_test, best_params)
        
        # Log model performance
        monitor.log_model_performance({
            'rmse': float(best_rmse),
            'training_samples': len(X_train),
            'test_samples': len(X_test)
        })
        
        # Save artifacts to your S3 buckets
        save_model_artifacts(run_id)
        
        results = make_json_safe({
            'run_id': run_id,
            'best_rmse': best_rmse,
            'best_params': best_params,
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'features_used': feats + ['station']
        })
        
        print(f"Model training completed successfully!")
        print(f"Run ID: {run_id}")
        print(f"Best RMSE: {best_rmse}")
        
        monitor.log_pipeline_success('training', results)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Model training completed successfully',
                'results': results,
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Training Lambda execution failed: {str(e)}")
        monitor.log_pipeline_failure('training', e, {
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