# Lambda Module Variables

variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
  default     = "apartment-pipeline"
}

variable "image_tag" {
  description = "Version tag for the deployment"
  type        = string
  default     = "latest"
}

variable "image_uri" {
  description = "ECR image URI for the Lambda function"
  type        = string
}

variable "handler_command" {
  description = "Override CMD for the container image"
  type        = list(string)
  default     = []
}

variable "memory_size" {
  description = "Amount of memory in MB for Lambda function"
  type        = number
  default     = 512
}

variable "timeout" {
  description = "Timeout in seconds for Lambda function"
  type        = number
  default     = 300
}

variable "ephemeral_storage_size" {
  description = "Size of ephemeral storage in MB"
  type        = number
  default     = 512
}

variable "reserved_concurrency" {
  description = "Reserved concurrent executions"
  type        = number
  default     = -1 # No limit
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "log_level" {
  description = "Logging level"
  type        = string
  default     = "INFO"
}

variable "environment_variables" {
  description = "Additional environment variables"
  type        = map(string)
  default     = {}
}

variable "mlflow_bucket_name" {
  description = "S3 bucket name for MLflow artifacts"
  type        = string
}

variable "mlflow_bucket_arn" {
  description = "S3 bucket ARN for MLflow artifacts"
  type        = string
}

variable "training_bucket_name" {
  description = "S3 bucket name for training data"
  type        = string
}

variable "training_bucket_arn" {
  description = "S3 bucket ARN for training data"
  type        = string
}

variable "secrets_arn" {
  description = "ARN of Secrets Manager secret containing API keys"
  type        = string
}

variable "dlq_arn" {
  description = "ARN of SQS queue for dead letter queue"
  type        = string
  default     = ""
}

variable "vpc_config" {
  description = "VPC configuration for Lambda"
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "alarm_sns_arns" {
  description = "SNS topic ARNs for CloudWatch alarms"
  type        = list(string)
  default     = []
}

variable "error_threshold" {
  description = "Threshold for error alarms"
  type        = number
  default     = 5
}

variable "duration_threshold" {
  description = "Threshold for duration alarms (milliseconds)"
  type        = number
  default     = 60000 # 60 seconds
}
