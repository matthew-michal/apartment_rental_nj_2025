import xgboost as xgb
import pandas as pd
from pathlib import Path
import pickle
from math import radians, cos
from datetime import datetime, date, timedelta
import pandas as pd
from sklearn.model_selection import train_test_split
import mlflow
import os
from sklearn.metrics import mean_squared_error
import matplotlib.pyplot as plt
from hyperopt import fmin, tpe, hp, STATUS_OK, Trials
from hyperopt.pyll import scope
from prefect import flow, task
from sklearn.preprocessing import LabelEncoder
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
import xgboost as xgb

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
                # Handle unseen labels by filtering or using a default
                encoder = self.encoders[col]
                mask = X_copy[col].isin(encoder.classes_)
                X_copy.loc[mask, col] = encoder.transform(X_copy.loc[mask, col])
                # For unseen values, assign 0 (or could use most frequent class)
                X_copy.loc[~mask, col] = 0
        return X_copy

os.environ["AWS_PROFILE"] = "default"

TRACKING_SERVER_HOST = "ec2-3-80-40-111.compute-1.amazonaws.com" # fill in with the public DNS of the EC2 instance
mlflow.set_tracking_uri(f"http://{TRACKING_SERVER_HOST}:5000")

nj_transit_locations = {
    'brick_church': [40.76581846318419, -74.21915255150205],
    'chatham': [40.7401922968325, -74.38473871480802],
    'convent_station': [40.778934521406896, -74.44347183325733],
    'denville': [40.88348292558847, -74.48184630211975],
    'dover': [40.887548571222204, -74.55589964058176],
    'east_orange': [40.761460414532, -74.21100276083385],
    'hackettstown': [40.85215082333791, -74.83467888781628],
    'highland_avenue': [40.766972457228775, -74.24355123014908],
    'hoboken': [40.70898046045857, -74.0246430608362], #
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


mlflow.set_experiment("north-nj-apartments-experiment-v3")

models_folder = Path('models')
models_folder.mkdir(exist_ok=True)


@task(retries=4, retry_delay_seconds=2, log_prints=True)
def read_dataframe():
    df = pd.read_csv('seventh_load.csv')
    df2 = pd.read_csv('training_load.csv')
    df = pd.concat([df,df2]).drop_duplicates()
    print(df.shape)

    return df


@task(retries=2, retry_delay_seconds=2)
def create_X(df):
    # df.zipCode = df.zipCode.astype(str)
    df['lat_long'] = df.latitude.astype(str) + '_' + df.longitude.astype(str)
    df['station'] = df.lat_long.apply(find_station)

    feats = [
        # 'city',
        'latitude', 'longitude',
        'station',
        'propertyType','bedrooms', 'bathrooms', 'yearBuilt', 'lotSize'
    ]


    X = df[feats]

    # if le_pt is None:
    #     le_pt = LabelEncoder()
    #     X['propertyType'] = le_pt.fit_transform(X['propertyType'])
    # else:
    #     X['propertyType'] = le_pt.transform(X['propertyType'])

    # if le_station is None:
    #     le_station = LabelEncoder()
    #     X['station'] = le_station.fit_transform(X['station'])
    # else:
    #     X['station'] = le_station.transform(X['station'])

    # return X, le_pt, le_station
    return X

@task(retries=2, retry_delay_seconds=2, log_prints=True)
def tune_models(X_train, y_train, X_test, y_test):

    # Define search space
    space = {
        'learning_rate': hp.uniform('learning_rate', 0.01, 0.3),
        'max_depth': hp.choice('max_depth', range(3, 10)),
        'min_child_weight': hp.uniform('min_child_weight', 1, 10),
        'reg_alpha': hp.uniform('reg_alpha', 0, 1),
        'reg_lambda': hp.uniform('reg_lambda', 0, 1)
    }
    
    def objective(params):
        with mlflow.start_run():
            # Log parameters
            mlflow.log_params(params)
            
            # Train model
            model = xgb.XGBRegressor(
                objective='reg:linear',
                n_estimators=100,
                random_state=42,
                **params
            )
            pipeline = Pipeline([
                ('encoder', LabelEncoderTransformer()),
                ('regressor', model)
            ])
            
            pipeline.fit(X_train, y_train)
            
            # Make predictions
            y_pred = pipeline.predict(X_test)
            
            # Calculate RMSE
            rmse = (mean_squared_error(y_test, y_pred))**(0.5)
            
            # Log metrics
            mlflow.log_metric("rmse", rmse)
            mlflow.log_metric("mse", mean_squared_error(y_test, y_pred))
            
            # Log model
            mlflow.xgboost.log_model(model, "model")
            
            return {'loss': rmse, 'status': STATUS_OK}
    
    # Run hyperparameter optimization
    trials = Trials()
    best = fmin(
        fn=objective,
        space=space,
        algo=tpe.suggest,
        max_evals=50,  # Adjust based on your time constraints
        trials=trials
    )
    
    # Get the best run
    best_run = min(trials.results, key=lambda x: x['loss'])
    best_rmse = best_run['loss']
    
    print(f"Best hyperparameters: {best}")
    print(f"Best RMSE: {best_rmse}")
    
    return best, best_rmse



@task(retries=2, retry_delay_seconds=2, log_prints=True)
def train_model(X_train, y_train, X_test, y_test, best):



    # train = xgb.DMatrix(X_train, label=y_train,enable_categorical=True)
    # valid = xgb.DMatrix(X_test, label=y_test,enable_categorical=True)

    # best_params = {
    #     'learning_rate': 0.05972322932431019,
    #     'max_depth': 6,
    #     'min_child_weight': 10.65084675866938,
    #     'objective': 'reg:linear',
    #     'reg_alpha': 0.3134223536955863,
    #     'reg_lambda': 0.08592250762440364,
    #     'seed': 42
    # }
    best_params = best
    best_params['objective'] = 'reg:linear'
    best_params['seed'] = 42

    with mlflow.start_run() as run:
        
        mlflow.log_params(best_params)
        
        # Create and train the pipeline instead of individual components
        pipeline = Pipeline([
            ('encoder', LabelEncoderTransformer()),
            ('regressor', xgb.XGBRegressor(**best_params, n_estimators=1000))
        ])
        
        # Fit the pipeline (this will fit both the encoder and XGBoost)
        pipeline.fit(X_train, y_train)
        
        # Make predictions for evaluation
        y_pred = pipeline.predict(X_test)  # Use X_test instead of valid
        rmse = (mean_squared_error(y_test, y_pred))**(0.5)
        mlflow.log_metric("rmse", rmse)
        
        # Log the entire pipeline as a sklearn model
        mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="pipeline_model",
            registered_model_name="apartment-rent-pipeline"  # Optional
        )
        
        run_id = run.info.run_id

    return run_id   

@flow
def run():
    df = read_dataframe()
    
    feats = [
        # 'city',
        'latitude', 'longitude',
        # 'station',
        'propertyType','bedrooms', 'bathrooms', 'yearBuilt', 'lotSize'
    ]

    X_train, X_test, y_train, y_test = train_test_split(
    df[feats], df.price, test_size=0.2, random_state=42
)

    X_train = create_X(X_train)
    X_test = create_X(X_test)

    best, _ = tune_models(X_train, y_train, X_test, y_test)

    run_id = train_model(X_train, y_train, X_test, y_test, best)
    print(f"MLflow run_id: {run_id}")
    return run_id

if __name__ == "__main__":
    # import argparse

    # parser = argparse.ArgumentParser(description='Train a model to predict taxi trip duration.')
    # parser.add_argument('--year', type=int, required=True, help='Year of the data to train on')
    # parser.add_argument('--month', type=int, required=True, help='Month of the data to train on')
    # args = parser.parse_args()

    # run_id = run(year=args.year, month=args.month)
    run_id = run()

    with open("run_id.txt", "w") as f:
        f.write(run_id)

# def objective(params):
#     with mlflow.start_run():

#         mlflow.set_tag("developer", "mmichal")
#         mlflow.set_tag("model", "xgboost")

#         mlflow.log_params(params)

#         booster = xgb.train(
#             params=params,
#             dtrain=train,
#             num_boost_round=1000,
#             evals=[(valid, "validation")],
#             early_stopping_rounds = 50
#         )

#         y_pred = booster.predict(valid)
#         rmse = root_mean_squared_error(y_test, y_pred)
#         mlflow.log_metric("rmse", rmse)

#     return {'loss': rmse, 'status': STATUS_OK}


# search_space = {
#     'max_depth': scope.int(hp.quniform('max_depth', 4, 100, 1)),
#     'learning_rate': hp.loguniform('learning_rate', -3, 0), # exp(-3), exp(0) -> [0.05, 1]
#     'reg_alpha': hp.loguniform('reg_alpha', -5, -1),
#     'reg_lambda': hp.loguniform('reg_lambda', -6, -1),
#     'min_child_weight': hp.loguniform('min_child_weight', -1, 3),
#     'objective': 'reg:linear',
#     'seed':42
# }

# best_result = fmin(
#     fn=objective,
#     space=search_space,
#     algo=tpe.suggest,
#     max_evals=500,
#     trials=Trials()
# )










