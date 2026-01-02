import xgboost as xgb
import pandas as pd
from pathlib import Path
from datetime import datetime
import os
import json
import boto3
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from hyperopt import fmin, tpe, hp, STATUS_OK, Trials
import mlflow
import mlflow.sklearn
import mlflow.xgboost

# Optional Prefect support
try:
    from prefect import flow, task
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    def flow(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return decorator
    
    def task(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return decorator

from sklearn.preprocessing import LabelEncoder
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline

class LabelEncoderTransformer(BaseEstimator, TransformerMixin):
    def __init__(self, columns=['propertyType', 'station']):
        self.columns = columns
        self.encoders = {}
        
    def fit(self, X, y=None):
        for col in self.columns:
            if col in X.columns:
                self.encoders[col] = LabelEncoder()
                self.encoders[col].fit(X[col])
        return self
    
    def transform(self, X):
        X_copy = X.copy()
        for col in self.columns:
            if col in X_copy.columns and col in self.encoders:
                encoder = self.encoders[col]
                mask = X_copy[col].isin(encoder.classes_)
                X_copy.loc[mask, col] = encoder.transform(X_copy.loc[mask, col])
                X_copy.loc[~mask, col] = 0
        return X_copy

# AWS Configuration
if not os.environ.get('AWS_EXECUTION_ENV'):
    os.environ["AWS_PROFILE"] = "default"

sts = boto3.client('sts')
account_id = sts.get_caller_identity()['Account']
environment = os.environ.get('ENVIRONMENT', 'staging')

# MLflow Configuration
MLFLOW_TRACKING_URI = os.environ.get('MLFLOW_TRACKING_URI', 'http://localhost:5000')
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment("apartment-rental-price-prediction")

print(f"MLflow Tracking URI: {MLFLOW_TRACKING_URI}")

nj_transit_locations = {
    'brick_church': [40.76581846318419, -74.21915255150205],
    'chatham': [40.7401922968325, -74.38473871480802],
    'convent_station': [40.778934521406896, -74.44347183325733],
    'denville': [40.88348292558847, -74.48184630211975],
    'dover': [40.887548571222204, -74.55589964058176],
    'east_orange': [40.761460414532, -74.21100276083385],
    'hackettstown': [40.85215082333791, -74.83467888781628],
    'highland_avenue': [40.766972457228775, -74.24355123014908],
    'hoboken': [40.70898046045857, -74.0246430608362],
    'lake_hopatcong': [40.904119814030835, -74.66555031993157],
    'madison': [40.757211574757704, -74.41541459013588],
    'maplewood': [40.7311582228973, -74.27530904549292],
    'millburn': [40.72583754037974, -74.303745189671],
    'morris_plains': [40.828733316576745, -74.47839671850174],
    'morristown': [40.79756715723661, -74.47460155149217],
    'mountain_station': [40.76109170550611, -74.25347657839343],
    'mount_arlington': [40.89752890181971, -74.63289981056195],
    'mount_olive': [40.90760134999547, -74.73072365897825],
    'mount_tabor': [40.8759878570467, -74.48183704548632],
    'netcong': [40.898021200833895, -74.70758666495435],
    'newark_broad': [40.74757642090106, -74.17199820501222],
    'orange': [40.77209415825383, -74.23309422970475],
    'secaucus_junction': [40.76142100515953, -74.07575294623813],
    'short_hills': [40.725313887730955, -74.3238799338488],
    'south_orange': [40.74603125221472, -74.26046288967005],
    'summit': [40.71681594165216, -74.35768690713812]
}

def find_station(lat_long):
    apt_lat, apt_long = lat_long.split('_')
    apt_lat, apt_long = float(apt_lat), float(apt_long)

    for train_station, locations in nj_transit_locations.items():
        middle_lat = locations[0]
        middle_long = locations[1]
        small_lat, large_lat = middle_lat - 0.75 / 68.97, middle_lat + 0.75 / 68.97
        small_long, large_long = middle_long - 0.75 / 55.77, middle_long + 0.75 / 55.77

        if apt_lat >= small_lat and apt_lat <= large_lat:
            if apt_long >= small_long and apt_long <= large_long:
                return train_station
    return 'not close'


@task(retries=4, retry_delay_seconds=2, log_prints=True)
def read_dataframe():
    import io
    
    bucket = os.getenv("MLFLOW_BUCKET_NAME", f"apartment-pipeline-mlflow-{environment}-{account_id}")
    print(f"Loading training data from s3://{bucket}/training/")
    
    s3 = boto3.client('s3')
    
    # Read seventh_load.csv
    obj1 = s3.get_object(Bucket=bucket, Key='training/seventh_load.csv')
    df = pd.read_csv(io.BytesIO(obj1['Body'].read()))
    print(f"Loaded seventh_load.csv: {df.shape}")
    
    # Read training_load.csv
    obj2 = s3.get_object(Bucket=bucket, Key='training/training_load.csv')
    df2 = pd.read_csv(io.BytesIO(obj2['Body'].read()))
    print(f"Loaded training_load.csv: {df2.shape}")
    
    df = pd.concat([df, df2]).drop_duplicates()
    print(f"Combined dataset: {df.shape}")
    
    return df


@task(retries=2, retry_delay_seconds=2)
def create_X(df):
    df['lat_long'] = df.latitude.astype(str) + '_' + df.longitude.astype(str)
    df['station'] = df.lat_long.apply(find_station)
    
    feats = [
        'latitude', 'longitude', 'station',
        'propertyType', 'bedrooms', 'bathrooms', 'yearBuilt', 'lotSize'
    ]
    
    return df[feats]


@task(retries=2, retry_delay_seconds=2, log_prints=True)
def tune_models(X_train, y_train, X_test, y_test):
    """Hyperparameter tuning WITH MLflow tracking"""
    
    print("="*60)
    print("Starting hyperparameter tuning with MLflow tracking...")
    print("="*60)
    
    space = {
        'learning_rate': hp.uniform('learning_rate', 0.01, 0.3),
        'max_depth': hp.choice('max_depth', range(3, 10)),
        'min_child_weight': hp.uniform('min_child_weight', 1, 10),
        'reg_alpha': hp.uniform('reg_alpha', 0, 1),
        'reg_lambda': hp.uniform('reg_lambda', 0, 1)
    }
    
    def objective(params):
        # Start MLflow run for this trial
        with mlflow.start_run(nested=True):
            mlflow.log_params(params)
            mlflow.set_tag("model_type", "xgboost")
            mlflow.set_tag("phase", "hyperparameter_tuning")
            
            model = xgb.XGBRegressor(
                objective='reg:squarederror',
                n_estimators=100,
                random_state=42,
                **params
            )
            
            pipeline = Pipeline([
                ('encoder', LabelEncoderTransformer()),
                ('regressor', model)
            ])
            
            pipeline.fit(X_train, y_train)
            y_pred = pipeline.predict(X_test)
            
            rmse = (mean_squared_error(y_test, y_pred))**(0.5)
            mse = mean_squared_error(y_test, y_pred)
            
            mlflow.log_metric("rmse", rmse)
            mlflow.log_metric("mse", mse)
            
            print(f"Trial RMSE: {rmse:.2f} | lr={params['learning_rate']:.3f}, depth={params['max_depth']}")
            
            return {'loss': rmse, 'status': STATUS_OK}
    
    # Run optimization
    trials = Trials()
    best = fmin(
        fn=objective,
        space=space,
        algo=tpe.suggest,
        max_evals=50,
        trials=trials
    )
    
    best_run = min(trials.results, key=lambda x: x['loss'])
    best_rmse = best_run['loss']
    
    print("="*60)
    print(f"Hyperparameter tuning complete!")
    print(f"Best hyperparameters: {best}")
    print(f"Best RMSE: {best_rmse:.2f}")
    print("="*60)
    
    return best, best_rmse


@task(retries=2, retry_delay_seconds=2, log_prints=True)
def train_model(X_train, y_train, X_test, y_test, best, best_rmse):
    """Train final model and log to MLflow"""
    
    print("="*60)
    print("Training final model with best parameters...")
    print("="*60)
    
    best_params = best.copy()
    best_params['objective'] = 'reg:squarederror'
    best_params['seed'] = 42
    
    # Create pipeline
    pipeline = Pipeline([
        ('encoder', LabelEncoderTransformer()),
        ('regressor', xgb.XGBRegressor(**best_params, n_estimators=1000))
    ])
    
    # Fit pipeline
    pipeline.fit(X_train, y_train)
    
    # Evaluate
    y_pred = pipeline.predict(X_test)
    rmse = (mean_squared_error(y_test, y_pred))**(0.5)
    mse = mean_squared_error(y_test, y_pred)
    
    print(f"Final model RMSE: {rmse:.2f}")
    print(f"Final model MSE: {mse:.2f}")
    
    # Log everything to MLflow (this happens within the parent run)
    mlflow.log_params(best_params)
    mlflow.log_param("n_estimators", 1000)
    mlflow.log_param("training_samples", len(X_train))
    mlflow.log_param("test_samples", len(X_test))
    
    mlflow.log_metric("final_rmse", rmse)
    mlflow.log_metric("final_mse", mse)
    mlflow.log_metric("best_tuning_rmse", best_rmse)
    
    mlflow.set_tag("model_type", "xgboost_production")
    mlflow.set_tag("environment", environment)
    mlflow.set_tag("features", ",".join(X_train.columns.tolist()))
    
    # Log model using MLflow
    mlflow.sklearn.log_model(
        sk_model=pipeline,
        artifact_path="model",
        registered_model_name=f"apartment-rental-predictor-{environment}"
    )
    
    print("="*60)
    print("Model logged to MLflow successfully!")
    print("="*60)
    
    return rmse


@flow
def run():
    """Main training flow with MLflow tracking"""
    
    print("="*60)
    print("NJ Apartment Rental Price Prediction - Model Training")
    print(f"Environment: {environment}")
    print(f"MLflow Tracking URI: {MLFLOW_TRACKING_URI}")
    print("="*60)
    
    # Start parent MLflow run
    with mlflow.start_run(run_name=f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}") as run:
        
        mlflow.set_tag("pipeline", "apartment_rental_training")
        mlflow.set_tag("environment", environment)
        mlflow.set_tag("date", datetime.now().isoformat())
        
        # Load data
        df = read_dataframe()
        mlflow.log_param("total_samples", len(df))
        
        feats = [
            'latitude', 'longitude',
            'propertyType', 'bedrooms', 'bathrooms', 'yearBuilt', 'lotSize'
        ]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            df[feats], df.price, test_size=0.2, random_state=42
        )
        
        print(f"\nTraining set: {X_train.shape}")
        print(f"Test set: {X_test.shape}")
        
        mlflow.log_param("test_size", 0.2)
        mlflow.log_param("random_state", 42)
        
        # Create features
        X_train = create_X(X_train)
        X_test = create_X(X_test)
        
        # Hyperparameter tuning
        best, best_rmse = tune_models(X_train, y_train, X_test, y_test)
        
        # Train final model
        final_rmse = train_model(X_train, y_train, X_test, y_test, best, best_rmse)
        
        # Save run info to S3 (for Lambda to find latest model)
        run_id = run.info.run_id
        s3 = boto3.client('s3')
        bucket = f"apartment-pipeline-mlflow-{environment}-{account_id}"
        
        run_info = {
            'run_id': run_id,
            'timestamp': datetime.now().isoformat(),
            'rmse': float(final_rmse),
            'environment': environment,
            'mlflow_tracking_uri': MLFLOW_TRACKING_URI
        }
        
        s3.put_object(
            Bucket=bucket,
            Key='models/latest_run.json',
            Body=str(run_info).encode('utf-8')
        )
        
        print("="*60)
        print("✅ Training completed successfully!")
        print(f"MLflow Run ID: {run_id}")
        print(f"Final RMSE: {final_rmse:.2f}")
        print(f"Model registered as: apartment-rental-predictor-{environment}")
        print("="*60)
        
        return run_id


if __name__ == "__main__":
    run_id = run()
    print(f"\n✅ Pipeline completed! MLflow Run ID: {run_id}")
