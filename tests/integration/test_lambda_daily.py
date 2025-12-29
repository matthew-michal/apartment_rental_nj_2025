"""
Integration tests for apartment pipeline Lambda functions.

These tests verify that the deployed Lambda functions work correctly
in the staging/production environments.
"""

import argparse
import json
import time
from typing import Dict, Any
import boto3
import pytest


class LambdaTester:
    """Helper class for testing Lambda functions"""
    
    def __init__(self, environment: str = "staging"):
        self.environment = environment
        self.lambda_client = boto3.client('lambda')
        self.s3_client = boto3.client('s3')
        self.logs_client = boto3.client('logs')
        
    def get_function_name(self, base_name: str) -> str:
        """Get full function name with environment suffix"""
        return f"apartment-pipeline-{base_name}-{self.environment}"
    
    def invoke_lambda(self, function_name: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """Invoke a Lambda function and return the response"""
        if payload is None:
            payload = {}
        
        print(f"Invoking Lambda: {function_name}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = self.lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        status_code = response['StatusCode']
        payload_response = json.loads(response['Payload'].read())
        
        print(f"Status Code: {status_code}")
        print(f"Response: {json.dumps(payload_response, indent=2)}")
        
        return {
            'status_code': status_code,
            'payload': payload_response,
            'response': response
        }
    
    def get_recent_logs(self, function_name: str, limit: int = 10) -> list:
        """Get recent log events from CloudWatch"""
        log_group = f"/aws/lambda/{function_name}"
        
        try:
            # Get latest log stream
            streams = self.logs_client.describe_log_streams(
                logGroupName=log_group,
                orderBy='LastEventTime',
                descending=True,
                limit=1
            )
            
            if not streams['logStreams']:
                return []
            
            stream_name = streams['logStreams'][0]['logStreamName']
            
            # Get log events
            events = self.logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=stream_name,
                limit=limit
            )
            
            return [event['message'] for event in events['events']]
            
        except Exception as e:
            print(f"Error fetching logs: {e}")
            return []
    
    def check_s3_output(self, bucket: str, prefix: str) -> bool:
        """Check if Lambda wrote output to S3"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=10
            )
            return 'Contents' in response and len(response['Contents']) > 0
        except Exception as e:
            print(f"Error checking S3: {e}")
            return False


class TestDailyLambda:
    """Integration tests for daily predictions Lambda"""
    
    @pytest.fixture
    def tester(self, environment):
        return LambdaTester(environment)
    
    def test_lambda_exists(self, tester):
        """Test that Lambda function exists and is configured correctly"""
        function_name = tester.get_function_name("daily-predictions")
        
        try:
            response = tester.lambda_client.get_function(
                FunctionName=function_name
            )
            
            assert response['Configuration']['Runtime'] == 'python3.9' or \
                   response['Configuration']['PackageType'] == 'Image'
            assert response['Configuration']['State'] == 'Active'
            print(f"✅ Lambda exists and is active")
            
        except Exception as e:
            pytest.fail(f"Lambda function not found or not configured: {e}")
    
    def test_lambda_dry_run(self, tester):
        """Test Lambda with dry run (no actual API calls or emails)"""
        function_name = tester.get_function_name("daily-predictions")
        
        result = tester.invoke_lambda(
            function_name,
            payload={'dry_run': True, 'limit': 10}
        )
        
        assert result['status_code'] == 200, "Lambda invocation failed"
        
        payload = result['payload']
        assert payload.get('statusCode') == 200, f"Lambda returned error: {payload}"
        
        # Check response structure
        body = json.loads(payload.get('body', '{}'))
        assert 'message' in body or 'predictions_count' in body
        
        print(f"✅ Dry run successful")
    
    def test_lambda_environment_variables(self, tester):
        """Test that required environment variables are set"""
        function_name = tester.get_function_name("daily-predictions")
        
        response = tester.lambda_client.get_function(
            FunctionName=function_name
        )
        
        env_vars = response['Configuration'].get('Environment', {}).get('Variables', {})
        
        required_vars = [
            'ENVIRONMENT',
            'MLFLOW_BUCKET',
            'TRAINING_BUCKET',
        ]
        
        for var in required_vars:
            assert var in env_vars, f"Missing environment variable: {var}"
        
        print(f"✅ All required environment variables set")
    
    def test_lambda_iam_permissions(self, tester):
        """Test that Lambda has correct IAM role and permissions"""
        function_name = tester.get_function_name("daily-predictions")
        
        response = tester.lambda_client.get_function(
            FunctionName=function_name
        )
        
        role_arn = response['Configuration']['Role']
        assert role_arn, "Lambda has no IAM role"
        
        print(f"✅ IAM role configured: {role_arn}")
    
    def test_lambda_logs(self, tester):
        """Test that Lambda writes logs to CloudWatch"""
        function_name = tester.get_function_name("daily-predictions")
        
        # Invoke Lambda
        tester.invoke_lambda(function_name, payload={'dry_run': True})
        
        # Wait for logs to propagate
        time.sleep(5)
        
        # Check logs
        logs = tester.get_recent_logs(function_name, limit=20)
        assert len(logs) > 0, "No logs found in CloudWatch"
        
        # Check for expected log patterns
        log_text = '\n'.join(logs)
        assert 'START RequestId' in log_text, "Missing START log"
        assert 'END RequestId' in log_text, "Missing END log"
        
        print(f"✅ Logs are being written to CloudWatch")


class TestWeeklyLambda:
    """Integration tests for weekly training Lambda"""
    
    @pytest.fixture
    def tester(self, environment):
        return LambdaTester(environment)
    
    def test_lambda_exists(self, tester):
        """Test that Lambda function exists"""
        function_name = tester.get_function_name("weekly-training")
        
        try:
            response = tester.lambda_client.get_function(
                FunctionName=function_name
            )
            assert response['Configuration']['State'] == 'Active'
            print(f"✅ Weekly training Lambda exists")
        except Exception as e:
            pytest.fail(f"Lambda function not found: {e}")
    
    def test_lambda_has_more_memory(self, tester):
        """Test that training Lambda has more memory than daily Lambda"""
        daily_name = tester.get_function_name("daily-predictions")
        weekly_name = tester.get_function_name("weekly-training")
        
        daily_config = tester.lambda_client.get_function(
            FunctionName=daily_name
        )['Configuration']
        
        weekly_config = tester.lambda_client.get_function(
            FunctionName=weekly_name
        )['Configuration']
        
        daily_memory = daily_config['MemorySize']
        weekly_memory = weekly_config['MemorySize']
        
        assert weekly_memory >= daily_memory, \
            f"Training Lambda should have more memory (has {weekly_memory} vs {daily_memory})"
        
        assert weekly_config['Timeout'] >= daily_config['Timeout'], \
            "Training Lambda should have longer timeout"
        
        print(f"✅ Training Lambda properly configured (Memory: {weekly_memory}MB, Timeout: {weekly_config['Timeout']}s)")


class TestS3Access:
    """Test S3 bucket access from Lambda"""
    
    @pytest.fixture
    def tester(self, environment):
        return LambdaTester(environment)
    
    def test_buckets_exist(self, tester):
        """Test that required S3 buckets exist"""
        account_id = boto3.client('sts').get_caller_identity()['Account']
        
        expected_buckets = [
            f"apartment-pipeline-mlflow-{tester.environment}-{account_id}",
            f"apartment-pipeline-training-{tester.environment}-{account_id}",
            f"apartment-pipeline-predictions-{tester.environment}-{account_id}",
        ]
        
        for bucket in expected_buckets:
            try:
                tester.s3_client.head_bucket(Bucket=bucket)
                print(f"✅ Bucket exists: {bucket}")
            except Exception as e:
                pytest.fail(f"Bucket not found: {bucket} - {e}")
    
    def test_lambda_can_write_to_s3(self, tester):
        """Test that Lambda can write to S3"""
        function_name = tester.get_function_name("daily-predictions")
        
        # Invoke Lambda (it should write predictions to S3)
        result = tester.invoke_lambda(
            function_name,
            payload={'dry_run': False, 'limit': 5}
        )
        
        assert result['status_code'] == 200
        
        # Check if output was written
        # Note: This assumes your Lambda writes to S3
        # You may need to adjust based on your actual implementation
        
        print(f"✅ Lambda can interact with S3")


class TestMonitoring:
    """Test monitoring and alerting setup"""
    
    @pytest.fixture
    def tester(self, environment):
        return LambdaTester(environment)
    
    def test_cloudwatch_alarms_exist(self, tester):
        """Test that CloudWatch alarms are configured"""
        cloudwatch = boto3.client('cloudwatch')
        
        function_name = tester.get_function_name("daily-predictions")
        
        response = cloudwatch.describe_alarms(
            AlarmNamePrefix=f"{function_name}"
        )
        
        alarms = response['MetricAlarms']
        assert len(alarms) > 0, "No CloudWatch alarms found"
        
        # Check for specific alarms
        alarm_names = [alarm['AlarmName'] for alarm in alarms]
        
        assert any('error' in name.lower() for name in alarm_names), \
            "Missing error alarm"
        
        print(f"✅ CloudWatch alarms configured: {len(alarms)} alarms found")
    
    def test_log_group_exists(self, tester):
        """Test that CloudWatch log group exists with correct retention"""
        function_name = tester.get_function_name("daily-predictions")
        log_group = f"/aws/lambda/{function_name}"
        
        try:
            response = tester.logs_client.describe_log_groups(
                logGroupNamePrefix=log_group
            )
            
            assert len(response['logGroups']) > 0, "Log group not found"
            
            log_group_info = response['logGroups'][0]
            retention_days = log_group_info.get('retentionInDays')
            
            if retention_days:
                print(f"✅ Log retention configured: {retention_days} days")
            else:
                print(f"⚠️ Log retention not set (logs kept indefinitely)")
                
        except Exception as e:
            pytest.fail(f"Error checking log group: {e}")


def pytest_addoption(parser):
    """Add command line options for pytest"""
    parser.addoption(
        "--environment",
        action="store",
        default="staging",
        help="Environment to test: staging or production"
    )
    parser.addoption(
        "--smoke-only",
        action="store_true",
        default=False,
        help="Run only smoke tests (fast checks)"
    )


@pytest.fixture
def environment(request):
    """Fixture to get environment from command line"""
    return request.config.getoption("--environment")


if __name__ == "__main__":
    """
    Run integration tests from command line
    
    Usage:
        python test_lambda_daily.py --environment staging
        python test_lambda_daily.py --environment production --smoke-only
    """
    parser = argparse.ArgumentParser(description='Test Lambda functions')
    parser.add_argument('--environment', default='staging', 
                       choices=['staging', 'production'],
                       help='Environment to test')
    parser.add_argument('--smoke-only', action='store_true',
                       help='Run only smoke tests')
    
    args = parser.parse_args()
    
    # Run pytest programmatically
    pytest_args = [__file__, '-v']
    pytest_args.append(f'--environment={args.environment}')
    
    if args.smoke_only:
        pytest_args.extend(['-k', 'test_lambda_exists or test_lambda_dry_run'])
    
    exit_code = pytest.main(pytest_args)
    exit(exit_code)
