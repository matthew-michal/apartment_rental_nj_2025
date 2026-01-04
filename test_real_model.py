import boto3
import json

client = boto3.client('lambda', region_name='us-east-1')

print("🚀 Testing Lambda with REAL MLflow model...")
print(f"   Model run_id: 28a34f7c3a1d4dc8bd5abe08fe53c97c")
print(f"   RMSE: $610.95")
print()

response = client.invoke(
    FunctionName='apartment-pipeline-daily-predictions-staging',
    InvocationType='RequestResponse',
    Payload=json.dumps({
        'dry_run': False,  # Load REAL model!
        'limit': 5,
        'min_savings': 50
    })
)

result = json.loads(response['Payload'].read())
body = json.loads(result.get('body', '{}'))

if result.get('statusCode') == 200:
    print("✅ SUCCESS!")
    print()
    results = body.get('results', {})
    print(f"📊 Total Predictions: {results.get('total_predictions')}")
    print(f"🎯 Best Deals Found: {results.get('best_deals_count')}")
    print(f"💰 Avg Predicted: ${results.get('avg_predicted_price', 0):.2f}")
    print(f"💵 Avg Actual: ${results.get('avg_actual_price', 0):.2f}")
    print(f"🏆 Top Saving: ${results.get('top_saving', 0):.2f}")
    print(f"🔖 Model: {results.get('model_run_id')}")
else:
    print("❌ FAILED!")
    print(json.dumps(result, indent=2))
