# infrastructure/modules/mlflow_server/main.tf

# ECS Cluster for MLflow
resource "aws_ecs_cluster" "mlflow" {
  name = "${var.environment}-mlflow-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${var.environment}-mlflow-cluster"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "mlflow" {
  name              = "/ecs/${var.environment}-mlflow"
  retention_in_days = 30

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Security Group for MLflow ECS tasks
resource "aws_security_group" "mlflow_ecs" {
  name        = "${var.environment}-mlflow-ecs-sg"
  description = "Security group for MLflow ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    description     = "MLflow HTTP from ALB"
    from_port       = 5000
    to_port         = 5000
    protocol        = "tcp"
    security_groups = [aws_security_group.mlflow_alb.id]
  }

  ingress {
    description = "MLflow HTTP from VPC (Internal Tasks)"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr] 
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.environment}-mlflow-ecs-sg"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Application Load Balancer
resource "aws_security_group" "mlflow_alb" {
  name        = "${var.environment}-mlflow-alb-sg"
  description = "Security group for MLflow ALB"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP from the Internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Change from [var.vpc_cidr] to allow your home IP
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.environment}-mlflow-alb-sg"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_lb" "mlflow" {
  name               = "${var.environment}-mlflow-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.mlflow_alb.id]
  subnets            = var.public_subnet_ids

  tags = {
    Name        = "${var.environment}-mlflow-alb"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_lb_target_group" "mlflow" {
  name        = "${var.environment}-mlflow-tg"
  port        = 5000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }

  tags = {
    Name        = "${var.environment}-mlflow-tg"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_lb_listener" "mlflow" {
  load_balancer_arn = aws_lb.mlflow.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mlflow.arn
  }
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "mlflow_execution" {
  name = "${var.environment}-mlflow-execution-role"

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

resource "aws_iam_role_policy_attachment" "mlflow_execution" {
  role       = aws_iam_role.mlflow_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow reading DB password from Secrets Manager
resource "aws_iam_role_policy" "mlflow_secrets" {
  name = "${var.environment}-mlflow-secrets-policy"
  role = aws_iam_role.mlflow_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [var.db_password_secret_arn]
    }]
  })
}

# IAM Role for ECS Task (MLflow server permissions)
resource "aws_iam_role" "mlflow_task" {
  name = "${var.environment}-mlflow-task-role"

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

# S3 access for artifacts
resource "aws_iam_role_policy" "mlflow_s3" {
  name = "${var.environment}-mlflow-s3-policy"
  role = aws_iam_role.mlflow_task.id

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
        "${var.mlflow_bucket_arn}",
        "${var.mlflow_bucket_arn}/*"
      ]
    }]
  })
}

# ECS Task Definition
resource "aws_ecs_task_definition" "mlflow" {
  family                   = "${var.environment}-mlflow"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.mlflow_execution.arn
  task_role_arn            = aws_iam_role.mlflow_task.arn

  container_definitions = jsonencode([{
    name  = "mlflow"
    image = "ghcr.io/mlflow/mlflow:v2.9.2"

    command = [
      "mlflow",
      "server",
      "--backend-store-uri", "postgresql://${var.db_username}:${var.db_password}@${var.db_endpoint}/${var.db_name}",
      "--default-artifact-root", "s3://${var.mlflow_bucket_name}/mlflow",
      "--host", "0.0.0.0",
      "--port", "5000"
    ]

    portMappings = [{
      containerPort = 5000
      protocol      = "tcp"
    }]

    environment = [
      {
        name  = "AWS_DEFAULT_REGION"
        value = var.region
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.mlflow.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "mlflow"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:5000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ECS Service
resource "aws_ecs_service" "mlflow" {
  name            = "${var.environment}-mlflow-service"
  cluster         = aws_ecs_cluster.mlflow.id
  task_definition = aws_ecs_task_definition.mlflow.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.mlflow_ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.mlflow.arn
    container_name   = "mlflow"
    container_port   = 5000
  }

  depends_on = [aws_lb_listener.mlflow]

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
