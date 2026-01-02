# infrastructure/modules/mlflow_server/outputs.tf

output "mlflow_tracking_uri" {
  description = "MLflow tracking server URI"
  value       = "http://${aws_lb.mlflow.dns_name}"
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.mlflow.dns_name
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.mlflow.name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.mlflow.arn
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.mlflow.name
}

output "ecs_security_group_id" {
  description = "Security group ID for ECS tasks"
  value       = aws_security_group.mlflow_ecs.id
}
