"""
Clean AWS Lambda wrapper for daily predictions.
This imports from the deployment lambda file but with proper path handling.
"""
import sys
import os

# Add proper path handling
sys.path.append('/app')
sys.path.append('/app/deployment/lambda')
sys.path.append(os.path.join(os.path.dirname(__file__), '../../deployment/lambda'))

from lambda_daily_run import lambda_handler

# Re-export the handler (this is what AWS will call)
__all__ = ['lambda_handler']
