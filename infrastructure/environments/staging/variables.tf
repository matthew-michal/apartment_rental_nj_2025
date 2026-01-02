# infrastructure/environments/staging/variables.tf

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "staging"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "VPC ID to deploy resources"
  type        = string
}

variable "ecr_repository_name" {
  description = "ECR repository name"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "mlflow_db_instance_class" {
  description = "RDS instance class for MLflow database"
  type        = string
  default     = "db.t3.micro"
}

variable "mlflow_server_cpu" {
  description = "CPU units for MLflow server"
  type        = number
  default     = 512
}

variable "mlflow_server_memory" {
  description = "Memory for MLflow server in MB"
  type        = number
  default     = 1024
}

variable "training_cpu" {
  description = "CPU units for training task"
  type        = number
  default     = 2048
}

variable "training_memory" {
  description = "Memory for training task in MB"
  type        = number
  default     = 4096
}

variable "training_schedule" {
  description = "EventBridge schedule for training"
  type        = string
  default     = "cron(0 15 ? * SUN *)"
}

variable "daily_lambda_memory" {
  description = "Memory for daily predictions Lambda"
  type        = number
  default     = 1024
}

variable "daily_lambda_timeout" {
  description = "Timeout for daily predictions Lambda"
  type        = number
  default     = 300
}
