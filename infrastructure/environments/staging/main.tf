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

# Get all subnets in the VPC (default VPC subnets)
data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
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

# SIMPLIFIED: Deploy MLflow + RDS together without circular dependency
# Strategy: RDS security group allows all traffic from VPC CIDR (simple but works)

module "mlflow_db" {
  source = "../../modules/rds_postgres"

  environment           = var.environment
  vpc_id                = var.vpc_id
  vpc_cidr              = data.aws_vpc.main.cidr_block
  private_subnet_ids    = data.aws_subnets.private.ids
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
  private_subnet_ids = data.aws_subnets.private.ids

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
  private_subnet_ids           = data.aws_subnets.private.ids
  mlflow_ecs_security_group_id = module.mlflow_server.ecs_security_group_id

  ecr_image_uri       = "${data.aws_ecr_repository.app.repository_url}:latest"
  mlflow_tracking_uri = module.mlflow_server.mlflow_tracking_uri

  training_bucket_arn = module.training_bucket.bucket_arn
  mlflow_bucket_arn   = module.mlflow_bucket.bucket_arn
  secrets_manager_arn = aws_secretsmanager_secret.api_keys.arn

  cpu                 = var.training_cpu
  memory              = var.training_memory
  schedule_expression = var.training_schedule

  depends_on = [module.mlflow_server]
}

# Lambda for Daily Predictions
module "lambda_daily" {
  source = "../../modules/lambda"

  function_name = "apartment-pipeline-daily-predictions-${var.environment}"
  environment   = var.environment

  image_uri = "${data.aws_ecr_repository.app.repository_url}:latest"

  memory_size = var.daily_lambda_memory
  timeout     = var.daily_lambda_timeout

  environment_variables = {
    ENVIRONMENT         = var.environment
    MLFLOW_TRACKING_URI = module.mlflow_server.mlflow_tracking_uri
    MLFLOW_BUCKET       = module.mlflow_bucket.bucket_name
    TRAINING_BUCKET     = module.training_bucket.bucket_name
    PREDICTIONS_BUCKET  = module.predictions_bucket.bucket_name
  }

  # Lambda module required variables
  mlflow_bucket_name   = module.mlflow_bucket.bucket_name
  mlflow_bucket_arn    = module.mlflow_bucket.bucket_arn
  training_bucket_name = module.training_bucket.bucket_name
  training_bucket_arn  = module.training_bucket.bucket_arn
  secrets_arn          = aws_secretsmanager_secret.api_keys.arn
}

# EventBridge Rule for Daily Predictions
resource "aws_cloudwatch_event_rule" "daily_predictions" {
  name                = "${var.environment}-daily-predictions"
  description         = "Trigger daily predictions at 11 AM EST"
  schedule_expression = "cron(0 16 * * ? *)" # 11 AM EST = 16:00 UTC

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_cloudwatch_event_target" "daily_predictions" {
  rule      = aws_cloudwatch_event_rule.daily_predictions.name
  target_id = "daily-predictions-lambda"
  arn       = module.lambda_daily.function_arn

  input = jsonencode({
    dry_run = true
    limit   = 100
  })
}

resource "aws_lambda_permission" "allow_eventbridge_daily" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_daily.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_predictions.arn
}
