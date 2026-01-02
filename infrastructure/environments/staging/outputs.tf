# infrastructure/environments/staging/outputs.tf

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
  description = "Name of the daily predictions Lambda function"
  value       = module.lambda_daily.function_name
}

output "mlflow_tracking_uri" {
  description = "MLflow tracking server URI"
  value       = module.mlflow_server.mlflow_tracking_uri
}

output "mlflow_db_endpoint" {
  description = "RDS endpoint for MLflow database"
  value       = module.mlflow_db.db_endpoint
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.mlflow_server.ecs_cluster_name
}

output "training_task_definition_arn" {
  description = "ARN of the training task definition"
  value       = module.training_task.task_definition_arn
}

output "secret_arn" {
  description = "ARN of the secrets in Secrets Manager"
  value       = aws_secretsmanager_secret.api_keys.arn
  sensitive   = true
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = data.aws_ecr_repository.app.repository_url
}
