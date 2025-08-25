# ml_pipeline_flows.py - Convert Lambda functions to Prefect flows

from prefect import flow, task
from datetime import datetime
import json

# Import your existing Lambda functions
try:
    import sys
    sys.path.append('../deployment/lambda')
    from lambda_daily_run import lambda_handler as daily_handler
    from lambda_training import lambda_handler as training_handler
except ImportError as e:
    print(f"Warning: Could not import lambda functions: {e}")
    daily_handler = None
    training_handler = None

@task(retries=3, retry_delay_seconds=60)
def run_daily_predictions():
    """Task to run daily apartment predictions"""
    if daily_handler is None:
        print("Daily handler not available - simulating...")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Daily predictions completed (simulated)',
                'timestamp': datetime.now().isoformat()
            })
        }
    
    # Create mock event and context for Lambda function
    event = {'source': 'prefect-flow', 'type': 'predictions'}
    context = type('Context', (), {'aws_request_id': 'prefect-test'})()
    
    try:
        result = daily_handler(event, context)
        print(f"Daily predictions completed: {result}")
        return result
    except Exception as e:
        print(f"Daily predictions failed: {e}")
        raise

@task(retries=2, retry_delay_seconds=120)
def run_model_training():
    """Task to run model training"""
    if training_handler is None:
        print("Training handler not available - simulating...")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Model training completed (simulated)',
                'timestamp': datetime.now().isoformat()
            })
        }
    
    # Create mock event and context for Lambda function
    event = {'source': 'prefect-flow', 'type': 'model_training'}
    context = type('Context', (), {'aws_request_id': 'prefect-training'})()
    
    try:
        result = training_handler(event, context)
        print(f"Model training completed: {result}")
        return result
    except Exception as e:
        print(f"Model training failed: {e}")
        raise

@flow(name="daily-apartment-predictions", log_prints=True)
def daily_predictions_flow():
    """Daily apartment predictions pipeline"""
    print("Starting daily apartment predictions pipeline...")
    
    try:
        result = run_daily_predictions()
        print("Daily predictions pipeline completed successfully!")
        return {
            'status': 'success',
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Daily predictions pipeline failed: {e}")
        raise

@flow(name="weekly-model-training", log_prints=True)
def weekly_training_flow():
    """Weekly model training pipeline"""
    print("Starting weekly model training pipeline...")
    
    try:
        result = run_model_training()
        print("Model training pipeline completed successfully!")
        return {
            'status': 'success',
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Model training pipeline failed: {e}")
        raise

@flow(name="full-ml-pipeline", log_prints=True)
def full_ml_pipeline():
    """Complete ML pipeline: training then predictions"""
    print("Starting complete ML pipeline...")
    
    # Run training first
    training_result = run_model_training()
    print("Training completed, now running predictions...")
    
    # Then run predictions
    prediction_result = run_daily_predictions()
    
    return {
        'status': 'success',
        'training_result': training_result,
        'prediction_result': prediction_result,
        'timestamp': datetime.now().isoformat()
    }

if __name__ == "__main__":
    # Test the flows locally
    print("Testing daily predictions flow...")
    daily_result = daily_predictions_flow()
    print(f"Daily result: {daily_result}")
    
    print("\nTesting training flow...")
    training_result = weekly_training_flow()
    print(f"Training result: {training_result}")