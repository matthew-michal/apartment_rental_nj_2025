# infrastructure/modules/rds_postgres/outputs.tf

output "db_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.mlflow.endpoint
}

output "db_name" {
  description = "Database name"
  value       = aws_db_instance.mlflow.db_name
}

output "db_username" {
  description = "Database username"
  value       = aws_db_instance.mlflow.username
  sensitive   = true
}

output "db_password_secret_arn" {
  description = "ARN of Secrets Manager secret containing DB password"
  value       = aws_secretsmanager_secret.mlflow_db_password.arn
}

output "db_security_group_id" {
  description = "Security group ID for the database"
  value       = aws_security_group.mlflow_db.id
}
