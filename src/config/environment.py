"""
Environment configuration for apartment ML pipeline.
Handles environment-specific settings for dev/staging/production.
"""

import os
import json
import boto3
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class EnvironmentConfig:
    """Configuration for a specific environment"""
    environment: str
    aws_region: str
    mlflow_bucket: str
    training_bucket: str
    predictions_bucket: str
    mlflow_tracking_uri: str
    sns_topic_arn: Optional[str]
    secret_name: str
    log_level: str
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_staging(self) -> bool:
        return self.environment == "staging"
    
    @property
    def is_dev(self) -> bool:
        return self.environment == "dev"


class ConfigurationManager:
    """
    Manages environment configuration for the ML pipeline.
    
    Reads from environment variables (set by Terraform/Lambda) and
    provides a unified configuration interface.
    """
    
    def __init__(self):
        self.environment = os.environ.get('ENVIRONMENT', 'dev')
        self.aws_region = os.environ.get('AWS_REGION', 'us-east-1')
        
        # Initialize AWS clients
        self.secretsmanager = boto3.client('secretsmanager', region_name=self.aws_region)
        self._secrets_cache = {}
        
    def get_config(self) -> EnvironmentConfig:
        """Get configuration for current environment"""
        
        # These come from Terraform via Lambda environment variables
        config = EnvironmentConfig(
            environment=self.environment,
            aws_region=self.aws_region,
            mlflow_bucket=os.environ.get('MLFLOW_BUCKET'),
            training_bucket=os.environ.get('TRAINING_BUCKET'),
            predictions_bucket=os.environ.get('PREDICTIONS_BUCKET'),
            mlflow_tracking_uri=self._get_mlflow_tracking_uri(),
            sns_topic_arn=os.environ.get('SNS_TOPIC_ARN'),
            secret_name=os.environ.get('SECRET_NAME', f'apartment-pipeline-api-keys-{self.environment}'),
            log_level=os.environ.get('LOG_LEVEL', 'INFO')
        )
        
        # Validate required settings
        self._validate_config(config)
        
        return config
    
    def _get_mlflow_tracking_uri(self) -> str:
        """
        Get MLflow tracking URI based on environment.
        
        For Lambda: Use S3 backend
        For local development: Can use EC2 instance or local server
        """
        # Check for explicit override (for local development)
        if 'MLFLOW_TRACKING_URI' in os.environ:
            return os.environ['MLFLOW_TRACKING_URI']
        
        # For Lambda/production: use S3 backend
        mlflow_bucket = os.environ.get('MLFLOW_BUCKET')
        if mlflow_bucket:
            return f's3://{mlflow_bucket}/mlflow'
        
        # Fallback for local development
        return 'sqlite:///mlflow.db'
    
    def _validate_config(self, config: EnvironmentConfig):
        """Validate that required configuration is present"""
        required_fields = [
            ('mlflow_bucket', config.mlflow_bucket),
            ('training_bucket', config.training_bucket),
        ]
        
        missing = [name for name, value in required_fields if not value]
        
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}. "
                f"These should be set as environment variables by Terraform/Lambda."
            )
    
    def get_secret(self, secret_key: str) -> str:
        """
        Retrieve a secret from AWS Secrets Manager.
        
        Secrets are cached to avoid repeated API calls.
        
        Args:
            secret_key: The key within the secret (e.g., 'RENTCAST_API_KEY')
        
        Returns:
            The secret value
        """
        config = self.get_config()
        secret_name = config.secret_name
        
        # Check cache first
        if secret_name in self._secrets_cache:
            secrets = self._secrets_cache[secret_name]
        else:
            # Fetch from Secrets Manager
            try:
                response = self.secretsmanager.get_secret_value(SecretId=secret_name)
                secrets = json.loads(response['SecretString'])
                self._secrets_cache[secret_name] = secrets
            except Exception as e:
                raise ValueError(
                    f"Failed to retrieve secrets from '{secret_name}': {e}"
                ) from e
        
        # Return specific key
        if secret_key not in secrets:
            raise KeyError(
                f"Secret key '{secret_key}' not found in '{secret_name}'. "
                f"Available keys: {list(secrets.keys())}"
            )
        
        return secrets[secret_key]
    
    def get_all_secrets(self) -> Dict[str, str]:
        """Get all secrets from Secrets Manager"""
        config = self.get_config()
        secret_name = config.secret_name
        
        if secret_name in self._secrets_cache:
            return self._secrets_cache[secret_name]
        
        try:
            response = self.secretsmanager.get_secret_value(SecretId=secret_name)
            secrets = json.loads(response['SecretString'])
            self._secrets_cache[secret_name] = secrets
            return secrets
        except Exception as e:
            raise ValueError(
                f"Failed to retrieve secrets from '{secret_name}': {e}"
            ) from e


# Global configuration instance
config_manager = ConfigurationManager()


def get_config() -> EnvironmentConfig:
    """Convenience function to get current environment configuration"""
    return config_manager.get_config()


def get_secret(secret_key: str) -> str:
    """Convenience function to get a secret"""
    return config_manager.get_secret(secret_key)


# Example usage:
if __name__ == "__main__":
    # Test configuration
    config = get_config()
    print(f"Environment: {config.environment}")
    print(f"MLflow Bucket: {config.mlflow_bucket}")
    print(f"Training Bucket: {config.training_bucket}")
    print(f"Tracking URI: {config.mlflow_tracking_uri}")
    
    # Test secrets (will fail without actual secrets configured)
    try:
        api_key = get_secret('RENTCAST_API_KEY')
        print(f"API Key retrieved: {api_key[:5]}...")
    except Exception as e:
        print(f"Could not retrieve API key: {e}")
