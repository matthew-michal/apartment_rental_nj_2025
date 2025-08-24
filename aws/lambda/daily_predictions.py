"""
Clean AWS Lambda wrapper for daily predictions.
This imports from the deployment lambda file but with proper path handling.
"""
import sys
import os

# Add paths for imports
sys.path.append('/app')  # For AWS Lambda
sys.path.append('/app/deployment/lambda')  # For the original lambda file
sys.path.append('../../deployment/lambda')  # For local testing

# Import the original lambda handler
from lambda_daily_run import lambda_handler

# Re-export the handler (this is what AWS will call)
__all__ = ['lambda_handler']
