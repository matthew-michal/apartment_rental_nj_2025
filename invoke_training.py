import boto3
import time
import sys

# Constants matching your Terraform logs
CLUSTER_NAME = "staging-mlflow-cluster"
TASK_DEFINITION = "staging-training" 
REGION = "us-east-1"

def trigger_training():
    ecs = boto3.client('ecs', region_name=REGION)
    ec2 = boto3.client('ec2', region_name=REGION)

    print(f"🚀 Initializing Manual Training Trigger...")

    try:
        # 1. Discover Networking (Private Subnets)
        subnets = ec2.describe_subnets(
            Filters=[{'Name': 'tag:Name', 'Values': ['*private*']}]
        )['Subnets']
        subnet_ids = [s['SubnetId'] for s in subnets]
        
        # 2. Discover Security Group (Look for the MLflow ECS group)
        sgs = ec2.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': ['*mlflow-ecs*', '*training*']}]
        )['SecurityGroups']
        sg_ids = [sg['GroupId'] for sg in sgs]

        if not subnet_ids or not sg_ids:
            print("❌ Error: Could not auto-discover Networking. Check AWS Auth/Region.")
            return

        # 3. Start the Task
        print(f"📡 Starting Task '{TASK_DEFINITION}' on Cluster '{CLUSTER_NAME}'...")
        run_response = ecs.run_task(
            cluster=CLUSTER_NAME,
            taskDefinition=TASK_DEFINITION,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': subnet_ids,
                    'securityGroups': sg_ids,
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
        print(f"🔗 Monitor in Console: https://{REGION}.console.aws.amazon.com/ecs/v2/clusters/{CLUSTER_NAME}/tasks/{task_id}")
        
        # 4. The Waiter Logic
        print("\n⏳ Waiting for training to complete (this may take several minutes)...")
        last_status = None
        
        while True:
            desc = ecs.describe_tasks(cluster=CLUSTER_NAME, tasks=[task_arn])
            task = desc['tasks'][0]
            current_status = task['lastStatus']
            
            if current_status != last_status:
                print(f"   🔹 Status update: {current_status}")
                last_status = current_status
            
            if current_status == 'STOPPED':
                # Check exit code to see if it actually worked
                exit_code = task['containers'][0].get('ExitCode', 'Unknown')
                reason = task.get('stoppedReason', 'No reason provided')
                
                if exit_code == 0:
                    print(f"\n✨ SUCCESS: Training completed with Exit Code 0.")
                else:
                    print(f"\n💥 FAILED: Task stopped with Exit Code {exit_code}.")
                    print(f"   Reason: {reason}")
                break
                
            time.sleep(15) # Poll every 15 seconds

    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    trigger_training()