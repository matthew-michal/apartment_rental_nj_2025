# infrastructure/modules/ecs_training/variables.tf

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "ecs_cluster_arn" {
  description = "ARN of the ECS cluster to run training tasks"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "mlflow_ecs_security_group_id" {
  description = "Security group ID for ECS tasks (from MLflow module)"
  type        = string
}

variable "ecr_image_uri" {
  description = "ECR image URI for training container"
  type        = string
}

variable "mlflow_tracking_uri" {
  description = "MLflow tracking server URI"
  type        = string
}

variable "training_bucket_arn" {
  description = "S3 bucket ARN for training data"
  type        = string
}

variable "mlflow_bucket_arn" {
  description = "S3 bucket ARN for MLflow artifacts"
  type        = string
}

variable "secrets_manager_arn" {
  description = "ARN of Secrets Manager secret containing API keys"
  type        = string
}

variable "cpu" {
  description = "CPU units for ECS task (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 2048
}

variable "memory" {
  description = "Memory for ECS task in MB"
  type        = number
  default     = 4096
}

variable "schedule_expression" {
  description = "EventBridge schedule expression (cron or rate)"
  type        = string
  default     = "cron(0 15 ? * SUN *)" # 10 AM EST = 15:00 UTC on Sundays
}

variable "aws_sts_regional_endpoints" {
  description = "The type of STS regional endpoint to use. Use 'regional' to avoid global STS timeouts."
  type        = string
  default     = "regional" # Provides a safe default
}
