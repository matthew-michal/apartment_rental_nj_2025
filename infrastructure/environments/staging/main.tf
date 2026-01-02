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

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }

  tags = {
    Tier = "Private"
  }
}

# ECR Repository (already exists)
data "aws_ecr_repository" "app" {
  name = var.ecr_repository_name
}

# S3 Buckets for MLflow, Training, Predictions
module "mlflow_bucket" {
  source = "../../modules/s3"

  bucket_name = "apartment-pipeline-mlflow-${var.environment}-${data.aws_caller_identity.current.account_id}"
  environment = var.environment

  enable_versioning = true
  lifecycle_rules = [{
    id                                 = "cleanup-old-experiments"
    enabled                            = true
    expiration_days                    = 90
    noncurrent_version_expiration_days = 30
  }]
}

module "training_bucket" {
  source = "../../modules/s3"

  bucket_name = "apartment-pipeline-training-${var.environment}-${data.aws_caller_identity.current.account_id}"
  environment = var.environment

  enable_versioning = true
  lifecycle_rules = [{
    id                                 = "keep-latest-only"
    enabled                            = true
    noncurrent_version_expiration_days = 7
  }]
}

module "predictions_bucket" {
  source = "../../modules/s3"

  bucket_name = "apartment-pipeline-predictions-${var.environment}-${data.aws_caller_identity.current.account_id}"
  environment = var.environment

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

# RDS Postgres for MLflow
module "mlflow_db" {
  source = "../../modules/rds_postgres"

  environment           = var.environment
  vpc_id                = var.vpc_id
  private_subnet_ids    = data.aws_subnets.private.ids
  ecs_security_group_id = module.mlflow_server.ecs_security_group_id
  db_instance_class     = var.mlflow_db_instance_class
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
  db_username            = module.mlflow_db.db_username
  db_password            = module.mlflow_db.db_password_secret_arn # Will be read from Secrets Manager
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

# Lambda for Daily Predictions (already exists - update to use MLflow)
module "lambda_daily" {
  source = "../../modules/lambda"

  function_name = "apartment-pipeline-daily-predictions-${var.environment}"
  environment   = var.environment

  ecr_image_uri = "${data.aws_ecr_repository.app.repository_url}:latest"

  memory_size = var.daily_lambda_memory
  timeout     = var.daily_lambda_timeout

  environment_variables = {
    ENVIRONMENT         = var.environment
    MLFLOW_TRACKING_URI = module.mlflow_server.mlflow_tracking_uri
    MLFLOW_BUCKET       = module.mlflow_bucket.bucket_name
    TRAINING_BUCKET     = module.training_bucket.bucket_name
    PREDICTIONS_BUCKET  = module.predictions_bucket.bucket_name
  }

  s3_bucket_arns = [
    module.mlflow_bucket.bucket_arn,
    module.training_bucket.bucket_arn,
    module.predictions_bucket.bucket_arn
  ]

  secrets_manager_arn = aws_secretsmanager_secret.api_keys.arn
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
