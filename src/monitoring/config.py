# monitoring_config.py - Monitoring and alerting configuration for apartment ML pipeline

import json
import os
import boto3
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd

class MLPipelineMonitor:
    """
    Centralized monitoring class for the apartment ML pipeline.
    Handles logging, metrics, alerts, and monitoring for all pipeline components.
    """
    
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
        self.sns = boto3.client('sns')
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # SNS topic for alerts (from environment variable)
        self.sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        
        # CloudWatch namespace for custom metrics
        self.cloudwatch_namespace = 'MLPipeline/ApartmentRent'
        
    def log_pipeline_start(self, pipeline_type: str, event: Dict[str, Any]):
        """Log the start of a pipeline execution"""
        self.logger.info(f"Pipeline {pipeline_type} started with event: {event}")
        
        # Send custom metric to CloudWatch
        self._put_cloudwatch_metric('pipeline_start', 1, pipeline_type)
        
    def log_pipeline_success(self, pipeline_type: str, results: Dict[str, Any]):
        """Log successful pipeline completion"""
        self.logger.info(f"Pipeline {pipeline_type} completed successfully")
        self.logger.info(f"Results: {json.dumps(results, indent=2, default=str)}")
        
        # Send success metric to CloudWatch
        self._put_cloudwatch_metric('pipeline_success', 1, pipeline_type)
        
        # Log specific metrics based on pipeline type
        if pipeline_type == 'daily_predictions':
            self._log_prediction_metrics(results)
        elif pipeline_type == 'training':
            self._log_training_metrics(results)
            
    def log_pipeline_failure(self, pipeline_type: str, error: Exception, context: Dict[str, Any]):
        """Log pipeline failure and send alerts"""
        error_message = str(error)
        self.logger.error(f"Pipeline {pipeline_type} failed: {error_message}")
        self.logger.error(f"Context: {json.dumps(context, indent=2, default=str)}")
        
        # Send failure metric to CloudWatch
        self._put_cloudwatch_metric('pipeline_failure', 1, pipeline_type)
        
        # Send SNS alert
        self._send_failure_alert(pipeline_type, error_message, context)
        
    def log_data_quality_metrics(self, df: pd.DataFrame, data_type: str):
        """Log data quality metrics for monitoring"""
        try:
            # Basic data quality metrics
            total_rows = len(df)
            missing_values_pct = df.isnull().sum().sum() / (len(df) * len(df.columns))
            duplicate_rows = df.duplicated().sum()
            
            # Price-specific metrics if available
            price_metrics = {}
            if 'price' in df.columns:
                price_metrics = {
                    'avg_price': float(df['price'].mean()),
                    'median_price': float(df['price'].median()),
                    'price_std': float(df['price'].std()),
                    'min_price': float(df['price'].min()),
                    'max_price': float(df['price'].max())
                }
            
            # Location metrics if available
            location_metrics = {}
            if 'latitude' in df.columns and 'longitude' in df.columns:
                location_metrics = {
                    'unique_locations': len(df[['latitude', 'longitude']].drop_duplicates()),
                    'lat_range': float(df['latitude'].max() - df['latitude'].min()),
                    'lon_range': float(df['longitude'].max() - df['longitude'].min())
                }
            
            metrics_summary = {
                'data_type': data_type,
                'total_rows': total_rows,
                'missing_values_pct': float(missing_values_pct),
                'duplicate_rows': int(duplicate_rows),
                'timestamp': datetime.now().isoformat(),
                **price_metrics,
                **location_metrics
            }
            
            self.logger.info(f"Data quality metrics for {data_type}: {json.dumps(metrics_summary, indent=2)}")
            
            # Send key metrics to CloudWatch
            self._put_cloudwatch_metric('data_quality_missing_pct', missing_values_pct * 100, data_type)
            self._put_cloudwatch_metric('data_quality_row_count', total_rows, data_type)
            self._put_cloudwatch_metric('data_quality_duplicates', duplicate_rows, data_type)
            
            if price_metrics:
                self._put_cloudwatch_metric('avg_price', price_metrics['avg_price'], data_type)
                
            # Alert if data quality issues detected
            if missing_values_pct > 0.2:  # More than 20% missing values
                self._send_data_quality_alert(data_type, 'High missing values', missing_values_pct)
                
            if total_rows < 50:  # Very low data volume
                self._send_data_quality_alert(data_type, 'Low data volume', total_rows)
                
        except Exception as e:
            self.logger.error(f"Error calculating data quality metrics: {e}")
            
    def log_model_performance(self, performance_metrics: Dict[str, Any]):
        """Log model performance metrics"""
        try:
            self.logger.info(f"Model performance: {json.dumps(performance_metrics, indent=2)}")
            
            # Send performance metrics to CloudWatch
            if 'rmse' in performance_metrics:
                self._put_cloudwatch_metric('model_rmse', performance_metrics['rmse'], 'training')
                
            if 'training_samples' in performance_metrics:
                self._put_cloudwatch_metric('training_samples', performance_metrics['training_samples'], 'training')
                
            if 'test_samples' in performance_metrics:
                self._put_cloudwatch_metric('test_samples', performance_metrics['test_samples'], 'training')
                
            # Alert if model performance is poor
            if 'rmse' in performance_metrics and performance_metrics['rmse'] > 500:  # RMSE threshold
                self._send_performance_alert('High RMSE detected', performance_metrics['rmse'])
                
        except Exception as e:
            self.logger.error(f"Error logging model performance: {e}")
            
    def log_drift_metrics(self, drift_results: Dict[str, Any]):
        """Log data drift detection results"""
        try:
            self.logger.info(f"Drift detection results: {json.dumps(drift_results, indent=2)}")
            
            # Send drift metrics to CloudWatch
            if 'prediction_drift' in drift_results:
                self._put_cloudwatch_metric('prediction_drift_score', drift_results['prediction_drift'], 'monitoring')
                
            if 'num_drifted_columns' in drift_results:
                self._put_cloudwatch_metric('num_drifted_columns', drift_results['num_drifted_columns'], 'monitoring')
                
            if 'share_missing_values' in drift_results:
                self._put_cloudwatch_metric('missing_values_share', drift_results['share_missing_values'], 'monitoring')
                
            # Alert if significant drift detected
            if drift_results.get('num_drifted_columns', 0) > 3:
                self._send_drift_alert('Significant data drift detected', drift_results)
                
            if drift_results.get('prediction_drift', 0) > 0.5:
                self._send_drift_alert('High prediction drift detected', drift_results)
                
        except Exception as e:
            self.logger.error(f"Error logging drift metrics: {e}")
            
    def _put_cloudwatch_metric(self, metric_name: str, value: float, dimension_value: str):
        """Send custom metric to CloudWatch"""
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.cloudwatch_namespace,
                MetricData=[
                    {
                        'MetricName': metric_name,
                        'Value': value,
                        'Unit': 'None',
                        'Dimensions': [
                            {
                                'Name': 'PipelineType',
                                'Value': dimension_value
                            }
                        ],
                        'Timestamp': datetime.now()
                    }
                ]
            )
        except Exception as e:
            self.logger.error(f"Error sending CloudWatch metric {metric_name}: {e}")
            
    def _send_failure_alert(self, pipeline_type: str, error_message: str, context: Dict[str, Any]):
        """Send failure alert via SNS"""
        if not self.sns_topic_arn:
            self.logger.warning("No SNS topic configured for alerts")
            return
            
        try:
            subject = f"🚨 Apartment ML Pipeline Failure - {pipeline_type}"
            message = f"""
Pipeline Failure Alert

Pipeline Type: {pipeline_type}
Timestamp: {datetime.now().isoformat()}
Error: {error_message}

Context:
{json.dumps(context, indent=2, default=str)}

Please check CloudWatch logs for more details.
            """.strip()
            
            self.sns.publish(
                TopicArn=self.sns_topic_arn,
                Subject=subject,
                Message=message
            )
            
        except Exception as e:
            self.logger.error(f"Error sending failure alert: {e}")
            
    def _send_data_quality_alert(self, data_type: str, issue: str, value: Any):
        """Send data quality alert"""
        if not self.sns_topic_arn:
            return
            
        try:
            subject = f"⚠️ Data Quality Issue - {data_type}"
            message = f"""
Data Quality Alert

Data Type: {data_type}
Issue: {issue}
Value: {value}
Timestamp: {datetime.now().isoformat()}

Please investigate data sources and processing pipeline.
            """.strip()
            
            self.sns.publish(
                TopicArn=self.sns_topic_arn,
                Subject=subject,
                Message=message
            )
            
        except Exception as e:
            self.logger.error(f"Error sending data quality alert: {e}")
            
    def _send_drift_alert(self, issue: str, drift_results: Dict[str, Any]):
        """Send data drift alert"""
        if not self.sns_topic_arn:
            return
            
        try:
            subject = f"📊 Data Drift Alert - Apartment ML Pipeline"
            message = f"""
Data Drift Alert

Issue: {issue}
Timestamp: {datetime.now().isoformat()}

Drift Metrics:
{json.dumps(drift_results, indent=2, default=str)}

Consider retraining the model or investigating data sources.
            """.strip()
            
            self.sns.publish(
                TopicArn=self.sns_topic_arn,
                Subject=subject,
                Message=message
            )
            
        except Exception as e:
            self.logger.error(f"Error sending drift alert: {e}")
            
    def _send_performance_alert(self, issue: str, rmse_value: float):
        """Send model performance alert"""
        if not self.sns_topic_arn:
            return
            
        try:
            subject = f"📈 Model Performance Alert"
            message = f"""
Model Performance Alert

Issue: {issue}
RMSE: {rmse_value:.2f}
Timestamp: {datetime.now().isoformat()}

Model performance has degraded. Consider retraining with fresh data.
            """.strip()
            
            self.sns.publish(
                TopicArn=self.sns_topic_arn,
                Subject=subject,
                Message=message
            )
            
        except Exception as e:
            self.logger.error(f"Error sending performance alert: {e}")
            
    def _log_prediction_metrics(self, results: Dict[str, Any]):
        """Log specific metrics for prediction pipeline"""
        if 'total_predictions' in results:
            self._put_cloudwatch_metric('daily_predictions_count', results['total_predictions'], 'daily_predictions')
            
        if 'best_deals_count' in results:
            self._put_cloudwatch_metric('good_deals_found', results['best_deals_count'], 'daily_predictions')
            
        if 'avg_predicted_price' in results:
            self._put_cloudwatch_metric('avg_predicted_price', results['avg_predicted_price'], 'daily_predictions')
            
    def _log_training_metrics(self, results: Dict[str, Any]):
        """Log specific metrics for training pipeline"""
        if 'best_rmse' in results:
            self._put_cloudwatch_metric('training_rmse', results['best_rmse'], 'training')
            
        if 'training_samples' in results:
            self._put_cloudwatch_metric('training_data_size', results['training_samples'], 'training')
            
        if 'run_id' in results:
            self.logger.info(f"New model trained with run_id: {results['run_id']}")

# Global monitor instance
monitor = MLPipelineMonitor()