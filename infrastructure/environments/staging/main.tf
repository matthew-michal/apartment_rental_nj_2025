# Staging Environment Infrastructure
# This creates all AWS resources for the apartment pipeline staging environment

terraform {
  required_version = ">= 1.6.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state in S3
  backend "s3" {
    bucket         = "apartment-pipeline-terraform-state"
    key            = "staging/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "staging"
      Project     = "apartment-pipeline"
      ManagedBy   = "Terraform"
      Owner       = "MLOps Team"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id    = data.aws_caller_identity.current.account_id
  region        = data.aws_region.current.name
  environment   = "staging"
  project_name  = "apartment-pipeline"
  
  # Common tags
  common_tags = {
    Environment = local.environment
    Project     = local.project_name
    ManagedBy   = "Terraform"
  }
}

#######################
# ECR Repository
#######################
resource "aws_ecr_repository" "app" {
  name                 = "${local.project_name}-${local.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = local.common_tags
}

# Lifecycle policy to keep only recent images
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["staging-"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Expire untagged images older than 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

#######################
# S3 Buckets
#######################

# MLflow artifacts bucket
module "mlflow_bucket" {
  source = "../../modules/s3"

  bucket_name       = "${local.project_name}-mlflow-${local.environment}-${local.account_id}"
  environment       = local.environment
  project_name      = local.project_name
  purpose           = "MLflow Artifacts"
  enable_versioning = true
  
  lifecycle_rules = [
    {
      id      = "archive-old-models"
      enabled = true
      prefix  = "models/"
      transitions = [
        {
          days          = 90
          storage_class = "STANDARD_IA"
        },
        {
          days          = 180
          storage_class = "GLACIER"
        }
      ]
    }
  ]
}

# Training data bucket
module "training_bucket" {
  source = "../../modules/s3"

  bucket_name       = "${local.project_name}-training-${local.environment}-${local.account_id}"
  environment       = local.environment
  project_name      = local.project_name
  purpose           = "Training Data"
  enable_versioning = true
  
  lifecycle_rules = [
    {
      id               = "expire-old-daily-data"
      enabled          = true
      prefix           = "daily/"
      expiration_days  = 90  # Keep daily predictions for 3 months
    }
  ]
}

# Daily predictions bucket
module "predictions_bucket" {
  source = "../../modules/s3"

  bucket_name       = "${local.project_name}-predictions-${local.environment}-${local.account_id}"
  environment       = local.environment
  project_name      = local.project_name
  purpose           = "Daily Predictions"
  enable_versioning = false
  
  lifecycle_rules = [
    {
      id               = "expire-old-predictions"
      enabled          = true
      expiration_days  = 30
    }
  ]
}

#######################
# Secrets Manager
#######################
resource "aws_secretsmanager_secret" "api_keys" {
  name        = "${local.project_name}-api-keys-${local.environment}"
  description = "API keys and credentials for apartment pipeline"

  tags = local.common_tags
}

# Note: Secret values should be set manually or via separate process
# aws secretsmanager put-secret-value --secret-id <secret-name> --secret-string '{"RENTCAST_API_KEY":"xxx","SENDER_EMAIL":"xxx"}'

#######################
# SNS Topics for Alerts
#######################
resource "aws_sns_topic" "alerts" {
  name = "${local.project_name}-alerts-${local.environment}"

  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "email_alerts" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

#######################
# SQS Dead Letter Queue
#######################
resource "aws_sqs_queue" "dlq" {
  name                      = "${local.project_name}-dlq-${local.environment}"
  message_retention_seconds = 1209600  # 14 days

  tags = local.common_tags
}

#######################
# Lambda Functions
#######################

# Daily predictions Lambda
module "lambda_daily" {
  source = "../../modules/lambda"

  function_name         = "${local.project_name}-daily-predictions-${local.environment}"
  environment           = local.environment
  project_name          = local.project_name
  version               = var.image_tag
  image_uri             = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  handler_command       = ["deployment.lambda.lambda_daily_run.lambda_handler"]
  memory_size           = 1024
  timeout               = 300
  ephemeral_storage_size = 1024
  log_retention_days    = 30
  
  mlflow_bucket_name    = module.mlflow_bucket.bucket_name
  mlflow_bucket_arn     = module.mlflow_bucket.bucket_arn
  training_bucket_name  = module.training_bucket.bucket_name
  training_bucket_arn   = module.training_bucket.bucket_arn
  secrets_arn           = aws_secretsmanager_secret.api_keys.arn
  dlq_arn               = aws_sqs_queue.dlq.arn
  alarm_sns_arns        = [aws_sns_topic.alerts.arn]
  
  environment_variables = {
    PREDICTIONS_BUCKET = module.predictions_bucket.bucket_name
    SECRET_NAME        = aws_secretsmanager_secret.api_keys.name
  }
}

# Weekly training Lambda
module "lambda_weekly" {
  source = "../../modules/lambda"

  function_name         = "${local.project_name}-weekly-training-${local.environment}"
  environment           = local.environment
  project_name          = local.project_name
  version               = var.image_tag
  image_uri             = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  handler_command       = ["deployment.lambda.lambda_training.lambda_handler"]
  memory_size           = 2048
  timeout               = 900  # 15 minutes
  ephemeral_storage_size = 2048
  log_retention_days    = 30
  
  mlflow_bucket_name    = module.mlflow_bucket.bucket_name
  mlflow_bucket_arn     = module.mlflow_bucket.bucket_arn
  training_bucket_name  = module.training_bucket.bucket_name
  training_bucket_arn   = module.training_bucket.bucket_arn
  secrets_arn           = aws_secretsmanager_secret.api_keys.arn
  dlq_arn               = aws_sqs_queue.dlq.arn
  alarm_sns_arns        = [aws_sns_topic.alerts.arn]
}

#######################
# EventBridge Rules for Scheduling
#######################

# Daily predictions at 6 AM EST (11 AM UTC)
resource "aws_cloudwatch_event_rule" "daily_predictions" {
  name                = "${local.project_name}-daily-${local.environment}"
  description         = "Trigger daily apartment predictions"
  schedule_expression = "cron(0 11 * * ? *)"  # 6 AM EST

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "daily_predictions" {
  rule      = aws_cloudwatch_event_rule.daily_predictions.name
  target_id = "lambda"
  arn       = module.lambda_daily.alias_arn
}

resource "aws_lambda_permission" "allow_eventbridge_daily" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_daily.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_predictions.arn
  qualifier     = local.environment
}

# Weekly training on Sunday at 1 AM EST (6 AM UTC)
resource "aws_cloudwatch_event_rule" "weekly_training" {
  name                = "${local.project_name}-weekly-${local.environment}"
  description         = "Trigger weekly model training"
  schedule_expression = "cron(0 6 ? * SUN *)"  # Sunday 1 AM EST

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "weekly_training" {
  rule      = aws_cloudwatch_event_rule.weekly_training.name
  target_id = "lambda"
  arn       = module.lambda_weekly.alias_arn
}

resource "aws_lambda_permission" "allow_eventbridge_weekly" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_weekly.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_training.arn
  qualifier     = local.environment
}

#######################
# CloudWatch Dashboard
#######################
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.project_name}-${local.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", { stat = "Sum", label = "Daily Lambda Invocations" }],
            [".", "Errors", { stat = "Sum", label = "Errors" }],
            [".", "Duration", { stat = "Average", label = "Avg Duration (ms)" }]
          ]
          period = 300
          stat   = "Average"
          region = local.region
          title  = "Lambda Metrics"
        }
      },
      {
        type = "log"
        properties = {
          query   = "SOURCE '/aws/lambda/${module.lambda_daily.function_name}' | fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20"
          region  = local.region
          title   = "Recent Errors"
        }
      }
    ]
  })
}
