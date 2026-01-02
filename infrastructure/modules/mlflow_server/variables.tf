# infrastructure/modules/mlflow_server/variables.tf

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "mlflow_bucket_name" {
  description = "S3 bucket name for MLflow artifacts"
  type        = string
}

variable "mlflow_bucket_arn" {
  description = "S3 bucket ARN for MLflow artifacts"
  type        = string
}

variable "db_endpoint" {
  description = "RDS Postgres endpoint"
  type        = string
}

variable "db_name" {
  description = "Database name"
  type        = string
}

variable "db_username" {
  description = "Database username"
  type        = string
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "db_password_secret_arn" {
  description = "ARN of Secrets Manager secret containing DB password"
  type        = string
}

variable "cpu" {
  description = "CPU units for ECS task (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 512
}

variable "memory" {
  description = "Memory for ECS task in MB"
  type        = number
  default     = 1024
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for the ALB"
  type        = list(string)
}
