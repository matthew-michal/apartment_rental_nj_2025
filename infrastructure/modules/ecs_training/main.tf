# infrastructure/modules/ecs_training/main.tf

# IAM Role for ECS Task Execution
resource "aws_iam_role" "training_execution" {
  name = "${var.environment}-training-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_iam_role_policy_attachment" "training_execution" {
  role       = aws_iam_role.training_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM Role for ECS Task (Training job permissions)
resource "aws_iam_role" "training_task" {
  name = "${var.environment}-training-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# S3 access for training data and model storage
resource "aws_iam_role_policy" "training_s3" {
  name = "${var.environment}-training-s3-policy"
  role = aws_iam_role.training_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ]
      Resource = [
        "${var.training_bucket_arn}",
        "${var.training_bucket_arn}/*",
        "${var.mlflow_bucket_arn}",
        "${var.mlflow_bucket_arn}/*"
      ]
    }]
  })
}

# Secrets Manager access for API keys
resource "aws_iam_role_policy" "training_secrets" {
  name = "${var.environment}-training-secrets-policy"
  role = aws_iam_role.training_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [var.secrets_manager_arn]
    }]
  })
}

# STS access to get account ID
resource "aws_iam_role_policy" "training_sts" {
  name = "${var.environment}-training-sts-policy"
  role = aws_iam_role.training_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sts:GetCallerIdentity"
      ]
      Resource = "*"
    }]
  })
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "training" {
  name              = "/ecs/${var.environment}-training"
  retention_in_days = 30

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "training" {
  family                   = "${var.environment}-training"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.training_execution.arn
  task_role_arn            = aws_iam_role.training_task.arn

  container_definitions = jsonencode([{
    name  = "training"
    image = var.ecr_image_uri

    environment = [
      {
        name  = "ENVIRONMENT"
        value = var.environment
      },
      {
        name  = "AWS_DEFAULT_REGION"
        value = var.region
      },
      {
        name  = "MLFLOW_TRACKING_URI"
        value = var.mlflow_tracking_uri
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.training.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "training"
      }
    }

    # Override entrypoint to run training script
    entryPoint = ["python"]
    command    = ["src/models/training.py"]
  }])

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# EventBridge IAM Role
resource "aws_iam_role" "eventbridge" {
  name = "${var.environment}-training-eventbridge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
    }]
  })

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_iam_role_policy" "eventbridge_ecs" {
  name = "${var.environment}-eventbridge-ecs-policy"
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ecs:RunTask"
      ]
      Resource = [
        aws_ecs_task_definition.training.arn
      ]
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.training_execution.arn,
          aws_iam_role.training_task.arn
        ]
    }]
  })
}

# EventBridge Rule for Weekly Training (Sunday 10 AM EST)
resource "aws_cloudwatch_event_rule" "training_schedule" {
  name                = "${var.environment}-training-schedule"
  description         = "Trigger weekly model training every Sunday at 10 AM EST"
  schedule_expression = var.schedule_expression

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_cloudwatch_event_target" "training" {
  rule      = aws_cloudwatch_event_rule.training_schedule.name
  target_id = "training-task"
  arn       = var.ecs_cluster_arn
  role_arn  = aws_iam_role.eventbridge.arn

  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.training.arn
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = var.private_subnet_ids
      security_groups  = [var.mlflow_ecs_security_group_id]
      assign_public_ip = false
    }
  }
}
