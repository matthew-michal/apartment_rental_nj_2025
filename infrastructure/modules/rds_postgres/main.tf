# infrastructure/modules/rds_postgres/main.tf

resource "aws_db_subnet_group" "mlflow" {
  name       = "${var.environment}-mlflow-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name        = "${var.environment}-mlflow-db-subnet-group"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_security_group" "mlflow_db" {
  name        = "${var.environment}-mlflow-db-sg"
  description = "Security group for MLflow RDS Postgres"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from ECS tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.ecs_security_group_id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.environment}-mlflow-db-sg"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "random_password" "mlflow_db_password" {
  length  = 16
  special = true
}

resource "aws_secretsmanager_secret" "mlflow_db_password" {
  name = "${var.environment}-mlflow-db-password"

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_secretsmanager_secret_version" "mlflow_db_password" {
  secret_id = aws_secretsmanager_secret.mlflow_db_password.id
  secret_string = jsonencode({
    username = "mlflow"
    password = random_password.mlflow_db_password.result
  })
}

resource "aws_db_instance" "mlflow" {
  identifier        = "${var.environment}-mlflow-db"
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = var.db_instance_class
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "mlflow"
  username = "mlflow"
  password = random_password.mlflow_db_password.result

  db_subnet_group_name   = aws_db_subnet_group.mlflow.name
  vpc_security_group_ids = [aws_security_group.mlflow_db.id]

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  skip_final_snapshot       = true # Set to false in production!
  final_snapshot_identifier = "${var.environment}-mlflow-db-final-snapshot"

  # Performance insights
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Name        = "${var.environment}-mlflow-db"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
