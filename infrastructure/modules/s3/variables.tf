variable "bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
}

variable "environment" {
  description = "Environment name (staging/production)"
  type        = string
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
}

variable "purpose" {
  description = "Purpose of the bucket"
  type        = string
  default     = ""
}

variable "enable_versioning" {
  description = "Enable versioning for the bucket"
  type        = bool
  default     = false
}

variable "kms_key_id" {
  description = "KMS key ID for encryption (if null, uses AWS managed key)"
  type        = string
  default     = null
}

variable "lifecycle_rules" {
  description = "Lifecycle rules for the bucket"
  type = list(object({
    id              = string
    enabled         = bool
    expiration_days = optional(number)
    prefix          = optional(string)
    transitions = optional(list(object({
      days          = number
      storage_class = string
    })))
  }))
  default = null
}

variable "allow_lambda_arns" {
  description = "List of Lambda function ARNs to grant access"
  type        = list(string)
  default     = null
}

variable "cors_rules" {
  description = "CORS rules for the bucket"
  type = list(object({
    allowed_headers = list(string)
    allowed_methods = list(string)
    allowed_origins = list(string)
    expose_headers  = optional(list(string))
    max_age_seconds = optional(number)
  }))
  default = null
}

variable "event_lambda_arns" {
  description = "Lambda functions to trigger on S3 events"
  type        = list(string)
  default     = null
}
