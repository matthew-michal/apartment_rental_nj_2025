# S3 Bucket Module
# Creates S3 buckets for MLflow artifacts, training data, and predictions

resource "aws_s3_bucket" "bucket" {
  bucket = var.bucket_name

  tags = {
    Name        = var.bucket_name
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
    Purpose     = var.purpose
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "bucket_pab" {
  bucket = aws_s3_bucket.bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning
resource "aws_s3_bucket_versioning" "bucket_versioning" {
  bucket = aws_s3_bucket.bucket.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "bucket_encryption" {
  bucket = aws_s3_bucket.bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_id
    }
    bucket_key_enabled = true
  }
}

# Lifecycle rules for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "bucket_lifecycle" {
  count  = var.lifecycle_rules != null ? 1 : 0
  bucket = aws_s3_bucket.bucket.id

  dynamic "rule" {
    for_each = var.lifecycle_rules
    content {
      id     = rule.value.id
      status = rule.value.enabled ? "Enabled" : "Disabled"

      # Transition to cheaper storage classes
      dynamic "transition" {
        for_each = lookup(rule.value, "transitions", null) != null ? rule.value.transitions : []
        content {
          days          = transition.value.days
          storage_class = transition.value.storage_class
        }
      }

      # Expire old objects
      dynamic "expiration" {
        for_each = lookup(rule.value, "expiration_days", null) != null ? [1] : []
        content {
          days = rule.value.expiration_days
        }
      }

      # Filter by prefix if specified
      filter {
        # If prefix specified, use it; otherwise empty filter = all objects
        prefix = lookup(rule.value, "prefix", "")

      }
    }
  }
}

# Bucket policy for Lambda access
resource "aws_s3_bucket_policy" "bucket_policy" {
  count  = var.allow_lambda_arns != null ? 1 : 0
  bucket = aws_s3_bucket.bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAccess"
        Effect = "Allow"
        Principal = {
          AWS = var.allow_lambda_arns
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.bucket.arn,
          "${aws_s3_bucket.bucket.arn}/*"
        ]
      }
    ]
  })
}

# Enable CloudWatch metrics for S3
resource "aws_s3_bucket_metric" "bucket_metrics" {
  bucket = aws_s3_bucket.bucket.id
  name   = "EntireBucket"
}

# CORS configuration (if needed for web access)
resource "aws_s3_bucket_cors_configuration" "bucket_cors" {
  count  = var.cors_rules != null ? 1 : 0
  bucket = aws_s3_bucket.bucket.id

  dynamic "cors_rule" {
    for_each = var.cors_rules
    content {
      allowed_headers = cors_rule.value.allowed_headers
      allowed_methods = cors_rule.value.allowed_methods
      allowed_origins = cors_rule.value.allowed_origins
      expose_headers  = cors_rule.value.expose_headers
      max_age_seconds = cors_rule.value.max_age_seconds
    }
  }
}

# Event notifications (if needed for triggering Lambda)
resource "aws_s3_bucket_notification" "bucket_notification" {
  count  = var.event_lambda_arns != null ? 1 : 0
  bucket = aws_s3_bucket.bucket.id

  dynamic "lambda_function" {
    for_each = var.event_lambda_arns
    content {
      lambda_function_arn = lambda_function.value
      events              = ["s3:ObjectCreated:*"]
      filter_prefix       = lookup(lambda_function.value, "prefix", "")
      filter_suffix       = lookup(lambda_function.value, "suffix", "")
    }
  }
}
