# Environment
environment = "staging"
aws_region  = "us-east-1"

# VPC Configuration
vpc_id = "vpc-001b53d0ecdac6d3c"

# ECR
ecr_repository_name = "apartment-pipeline"

# MLflow Database
mlflow_db_instance_class = "db.t3.micro"

# MLflow Server
mlflow_server_cpu    = 512
mlflow_server_memory = 1024

# Training Task
training_cpu      = 2048
training_memory   = 4096
training_schedule = "cron(0 15 ? * SUN *)"

# Lambda
daily_lambda_memory  = 1024
daily_lambda_timeout = 300