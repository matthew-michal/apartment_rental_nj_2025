# Lambda Function Module
# This creates a Lambda function with proper IAM roles, logging, and monitoring

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.function_name}-role"
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
  }
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Custom policy for S3, SES, Secrets Manager access
resource "aws_iam_policy" "lambda_custom_policy" {
  name        = "${var.function_name}-policy"
  description = "Custom policy for ${var.function_name}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 Access for MLflow artifacts and training data
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          "${var.mlflow_bucket_arn}/*",
          var.mlflow_bucket_arn,
          "${var.training_bucket_arn}/*",
          var.training_bucket_arn
        ]
      },
      # SES for sending email alerts
      {
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "*"
      },
      # Secrets Manager for API keys
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.secrets_arn
      },
      # CloudWatch for custom metrics
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "ApartmentPipeline"
          }
        }
      },
      # SQS for dead letter queue
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = var.dlq_arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_custom" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_custom_policy.arn
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.function_name}-logs"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Lambda Function
resource "aws_lambda_function" "function" {
  function_name = var.function_name
  role          = aws_iam_role.lambda_role.arn
  
  # Container image from ECR
  package_type = "Image"
  image_uri    = var.image_uri
  
  # Image config specifies the CMD override
  image_config {
    command = var.handler_command
  }

  # Resource configuration
  memory_size = var.memory_size
  timeout     = var.timeout
  
  # Environment variables
  environment {
    variables = merge(
      {
        ENVIRONMENT        = var.environment
        MLFLOW_BUCKET      = var.mlflow_bucket_name
        TRAINING_BUCKET    = var.training_bucket_name
        LOG_LEVEL         = var.log_level
      },
      var.environment_variables
    )
  }

  # Ephemeral storage (for temporary data processing)
  ephemeral_storage {
    size = var.ephemeral_storage_size
  }

  # Reserved concurrent executions (prevent runaway costs)
  reserved_concurrent_executions = var.reserved_concurrency

  # Dead letter queue for failed invocations
  dead_letter_config {
    target_arn = var.dlq_arn
  }

  # VPC configuration (if needed)
  dynamic "vpc_config" {
    for_each = var.vpc_config != null ? [var.vpc_config] : []
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }

  # Ensure log group is created first
  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy_attachment.lambda_custom
  ]

  tags = {
    Name        = var.function_name
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
    Version     = var.image_tag
  }
}

# Lambda Alias for blue/green deployments
resource "aws_lambda_alias" "function_alias" {
  name             = var.environment
  function_name    = aws_lambda_function.function.function_name
  function_version = aws_lambda_function.function.version

  # Routing config for canary deployments
  # routing_config {
  #   additional_version_weights = var.canary_weights
  # }
}

# CloudWatch Alarms for monitoring
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.function_name}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = var.error_threshold
  alarm_description   = "This metric monitors Lambda errors"
  alarm_actions       = var.alarm_sns_arns

  dimensions = {
    FunctionName = aws_lambda_function.function.function_name
  }

  tags = {
    Name        = "${var.function_name}-error-alarm"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.function_name}-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = var.duration_threshold
  alarm_description   = "This metric monitors Lambda execution time"
  alarm_actions       = var.alarm_sns_arns

  dimensions = {
    FunctionName = aws_lambda_function.function.function_name
  }

  tags = {
    Name        = "${var.function_name}-duration-alarm"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${var.function_name}-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors Lambda throttling"
  alarm_actions       = var.alarm_sns_arns

  dimensions = {
    FunctionName = aws_lambda_function.function.function_name
  }

  tags = {
    Name        = "${var.function_name}-throttle-alarm"
    Environment = var.environment
  }
}
