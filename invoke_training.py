import boto3
import time
import sys

# Constants matching your verified infrastructure
CLUSTER_NAME = "staging-mlflow-cluster"
TASK_DEFINITION = "staging-training" 
REGION = "us-east-1"

# Hardcoded from your AWS Console screenshot and debug logs
# Using the first two subnets from your list for high availability
SUBNET_IDS = ["subnet-0419d763ef9fa2b24", "subnet-08e8b15f8ec14faf6"] 
SECURITY_GROUP_IDS = ["sg-051ba8280cc33ca3f"] 

def trigger_training():
    ecs = boto3.client('ecs', region_name=REGION)

    print(f"🚀 Initializing Manual Training Trigger...")
    print(f"📡 Target Cluster: {CLUSTER_NAME}")
    print(f"📡 Task Definition: {TASK_DEFINITION}")

    try:
        # Start the Task
        run_response = ecs.run_task(
            cluster=CLUSTER_NAME,
            taskDefinition=TASK_DEFINITION,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': SUBNET_IDS,
                    'securityGroups': SECURITY_GROUP_IDS,
                    'assignPublicIp': 'DISABLED'
                }
            }
        )

        if run_response['failures']:
            print(f"❌ Failed to start: {run_response['failures']}")
            return

        task_arn = run_response['tasks'][0]['taskArn']
        task_id = task_arn.split('/')[-1]
        print(f"✅ Task started! ID: {task_id}")
        print(f"🔗 Monitor: https://{REGION}.console.aws.amazon.com/ecs/v2/clusters/{CLUSTER_NAME}/tasks/{task_id}")
        
        # The Waiter Logic
        print("\n⏳ Monitoring training progress...")
        last_status = None
        
        while True:
            desc = ecs.describe_tasks(cluster=CLUSTER_NAME, tasks=[task_arn])
            task = desc['tasks'][0]
            current_status = task['lastStatus']
            
            if current_status != last_status:
                print(f"   🔹 Status: {current_status}")
                last_status = current_status
            
            if current_status == 'STOPPED':
                exit_code = task['containers'][0].get('ExitCode', 'Unknown')
                if exit_code == 0:
                    print(f"\n✨ SUCCESS: Training completed (Exit 0).")
                else:
                    print(f"\n💥 FAILED: Task stopped with Exit Code {exit_code}.")
                    print(f"   Reason: {task.get('stoppedReason', 'Unknown')}")
                break
                
            time.sleep(15)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    trigger_training()