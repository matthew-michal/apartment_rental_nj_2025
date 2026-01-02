variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (staging/production)"
  type        = string
  default     = "staging"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "apartment-rental-nj"
}

variable "image_tag" {
  description = "Docker image tag for Lambda deployment"
  type        = string
  default     = "staging-latest"
}

variable "alert_email" {
  description = "Email address for CloudWatch alerts"
  type        = string
}

variable "rentcast_api_key" {
  description = "Rentcast API key (will be stored in Secrets Manager)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "db_password" {
  description = "Database password (will be stored in Secrets Manager)"
  type        = string
  sensitive   = true
  default     = ""
}
