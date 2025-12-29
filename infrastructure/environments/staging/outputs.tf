output "mlflow_bucket_name" {
  description = "Name of the MLflow artifacts bucket"
  value       = module.mlflow_bucket.bucket_name
}

output "training_bucket_name" {
  description = "Name of the training data bucket"
  value       = module.training_bucket.bucket_name
}

output "predictions_bucket_name" {
  description = "Name of the predictions bucket"
  value       = module.predictions_bucket.bucket_name
}

output "daily_lambda_function_name" {
  description = "Name of the daily run Lambda function"
  value       = module.lambda_daily.function_name
}

output "training_lambda_function_name" {
  description = "Name of the training Lambda function"
  value       = module.lambda_weekly.function_name
}

output "secret_arn" {
  description = "ARN of the secrets in Secrets Manager"
  value       = aws_secretsmanager_secret.api_keys.arn
  sensitive   = true
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alerts"
  value       = aws_sns_topic.alerts.arn
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.app.repository_url
}
