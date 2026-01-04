import boto3
import json

client = boto3.client('lambda', region_name='us-east-1')

print("🚀 Testing Lambda with Prefect fix...")
print()

try:
    response = client.invoke(
        FunctionName='apartment-pipeline-daily-predictions-staging',
        InvocationType='RequestResponse',
        Payload=json.dumps({'dry_run': False, 'limit': 10})
    )
    
    status = response['StatusCode']
    print(f"Status Code: {status}")
    
    if status == 200:
        print("✅ Lambda invoked successfully!")
    
    result = json.loads(response['Payload'].read())
    print("\nResponse:")
    print(json.dumps(result, indent=2))
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
