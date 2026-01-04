# infrastructure/environments/staging/main.tf

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  backend "s3" {
    bucket         = "apartment-pipeline-terraform-state-231917356461"
    key            = "staging/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "apartment-pipeline-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Get existing VPC data
data "aws_vpc" "main" {
  id = var.vpc_id
}

# 1. Get ALL subnets first
data "aws_subnets" "all" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
}

# 1. Get detailed data for the subnets we found
data "aws_subnet" "details" {
  for_each = toset(data.aws_subnets.all.ids)
  id       = each.value
}

locals {
  # Dynamically pick subnets that have "map_public_ip_on_launch" enabled
  public_subnet_ids = [
    for s in data.aws_subnet.details : s.id if s.map_public_ip_on_launch == true
  ]
  
  # For a Default VPC, usually all are public, so we can use them all 
  # or just the filtered ones for both to ensure the ALB is happy.
  private_subnet_ids = data.aws_subnets.all.ids
}

# ECR Repository (already exists)
data "aws_ecr_repository" "app" {
  name = var.ecr_repository_name
}

# S3 Buckets for MLflow, Training, Predictions
module "mlflow_bucket" {
  source = "../../modules/s3"

  project_name = "apartment-pipeline"
  bucket_name  = "apartment-pipeline-mlflow-${var.environment}-${data.aws_caller_identity.current.account_id}"
  environment  = var.environment

  enable_versioning = true
  lifecycle_rules = [{
    id              = "cleanup-old-experiments"
    enabled         = true
    expiration_days = 90
  }]
}

module "training_bucket" {
  source = "../../modules/s3"

  project_name = "apartment-pipeline"
  bucket_name  = "apartment-pipeline-training-${var.environment}-${data.aws_caller_identity.current.account_id}"
  environment  = var.environment

  enable_versioning = true
  lifecycle_rules = [{
    id              = "cleanup-old-training-data"
    enabled         = true
    expiration_days = 365 # Keep training data for 1 year
  }]
}

module "predictions_bucket" {
  source = "../../modules/s3"

  project_name = "apartment-pipeline"
  bucket_name  = "apartment-pipeline-predictions-${var.environment}-${data.aws_caller_identity.current.account_id}"
  environment  = var.environment

  enable_versioning = false
  lifecycle_rules = [{
    id              = "cleanup-old-predictions"
    enabled         = true
    expiration_days = 90
  }]
}

# Secrets Manager for API Keys
resource "aws_secretsmanager_secret" "api_keys" {
  name = "apartment-pipeline-api-keys-${var.environment}"

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# SQS Dead Letter Queue for Lambda
resource "aws_sqs_queue" "dlq" {
  name                      = "apartment-pipeline-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# SIMPLIFIED: Deploy MLflow + RDS together without circular dependency
# Strategy: RDS security group allows all traffic from VPC CIDR (simple but works)

module "mlflow_db" {
  source = "../../modules/rds_postgres"

  environment           = var.environment
  vpc_id                = var.vpc_id
  vpc_cidr              = data.aws_vpc.main.cidr_block
  private_subnet_ids    = local.private_subnet_ids
  ecs_security_group_id = null # Will allow VPC CIDR in module
  db_instance_class     = var.mlflow_db_instance_class
}

# Read DB password from Secrets Manager
data "aws_secretsmanager_secret_version" "mlflow_db_password" {
  secret_id  = module.mlflow_db.db_password_secret_arn
  depends_on = [module.mlflow_db]
}

locals {
  db_credentials = jsondecode(data.aws_secretsmanager_secret_version.mlflow_db_password.secret_string)
}

# MLflow Tracking Server (ECS Fargate)
module "mlflow_server" {
  source = "../../modules/mlflow_server"

  environment        = var.environment
  region             = var.aws_region
  vpc_id             = var.vpc_id
  vpc_cidr           = data.aws_vpc.main.cidr_block
  private_subnet_ids = local.public_subnet_ids
  public_subnet_ids  = local.public_subnet_ids

  mlflow_bucket_name = module.mlflow_bucket.bucket_name
  mlflow_bucket_arn  = module.mlflow_bucket.bucket_arn

  db_endpoint            = module.mlflow_db.db_endpoint
  db_name                = module.mlflow_db.db_name
  db_username            = local.db_credentials.username
  db_password            = local.db_credentials.password
  db_password_secret_arn = module.mlflow_db.db_password_secret_arn

  cpu    = var.mlflow_server_cpu
  memory = var.mlflow_server_memory

  depends_on = [module.mlflow_db]
}

# ECS Training Task (Scheduled Weekly)
module "training_task" {
  source = "../../modules/ecs_training"

  environment                  = var.environment
  region                       = var.aws_region
  ecs_cluster_arn              = module.mlflow_server.ecs_cluster_arn
  private_subnet_ids           = local.public_subnet_ids
  mlflow_ecs_security_group_id = module.mlflow_server.ecs_security_group_id

  # ecr_image_uri       = "${data.aws_ecr_repository.app.repository_url}:latest" # old uri with errors
  ecr_image_uri = var.image_uri
  mlflow_tracking_uri = module.mlflow_server.mlflow_tracking_uri

  training_bucket_arn = module.training_bucket.bucket_arn
  mlflow_bucket_arn   = module.mlflow_bucket.bucket_arn
  secrets_manager_arn = aws_secretsmanager_secret.api_keys.arn

  cpu                 = var.training_cpu
  memory              = var.training_memory
  schedule_expression = var.training_schedule

  aws_sts_regional_endpoints = "regional"

  depends_on = [module.mlflow_server]
}

# Lambda for Daily Predictions
# Consolidated Lambda Module Call
module "lambda_daily" {
  source = "../../modules/lambda"

  # Core Identification
  function_name = "apartment-pipeline-daily-predictions-${var.environment}"
  environment   = var.environment
  project_name  = "apartment-pipeline"

  # Resource Config
  image_uri    = var.image_uri
  memory_size  = var.daily_lambda_memory
  timeout      = var.daily_lambda_timeout

  # Scheduler Settings (Matching your new variables)
  schedule_expression = var.daily_prediction_schedule
  schedule_timezone   = var.schedule_timezone

  # REQUIRED: Bucket & Secret Attributes (Fixing the errors in the image)
  mlflow_bucket_name   = module.mlflow_bucket.bucket_name
  mlflow_bucket_arn    = module.mlflow_bucket.bucket_arn
  training_bucket_name = module.training_bucket.bucket_name
  training_bucket_arn  = module.training_bucket.bucket_arn
  secrets_arn          = aws_secretsmanager_secret.api_keys.arn
  dlq_arn              = aws_sqs_queue.dlq.arn

  # Environment Variables
  environment_variables = {
    ENVIRONMENT         = var.environment
    MLFLOW_TRACKING_URI = module.mlflow_server.mlflow_tracking_uri
    SENDER_EMAIL        = "matthew.michal11@gmail.com"
    RECIPIENT_EMAIL     = "matthew.michal11@gmail.com"
    # Note: MLFLOW_BUCKET and TRAINING_BUCKET are handled inside the module 
    # based on the bucket_name variables passed above.
  }
}

# --- VPC Endpoints for Private Connectivity ---

# 1. Security Group for the Interface Endpoints
resource "aws_security_group" "vpc_endpoints" {
  name        = "staging-vpc-endpoints-sg"
  description = "Allow ECS tasks to reach ECR and Secrets Manager"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    # Allow traffic from your ECS Training Task security group
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }

  tags = {
    Environment = var.environment
    Name        = "staging-vpc-endpoints-sg"
  }
}

# 2. ECR API (Interface) - For service authentication
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
}

# 3. ECR DKR (Interface) - For pulling image layers
resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
}

# 4. Secrets Manager (Interface) - For API keys
resource "aws_vpc_endpoint" "secrets" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
}

# 5. S3 (Gateway) - Required by ECR and your training script
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  # Using the Route Table ID you just found
  route_table_ids   = ["rtb-0f853af5706493d77"] 
}

# 6. CloudWatch Logs Endpoint (Interface) - For task logging
resource "aws_vpc_endpoint" "logs" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]

  tags = {
    Environment = var.environment
    Name        = "staging-logs-endpoint"
  }
}

# 7. STS Endpoint (Interface) - To get account/identity info
resource "aws_vpc_endpoint" "sts" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.sts"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]

  tags = {
    Environment = var.environment
    Name        = "staging-sts-endpoint"
  }
}
