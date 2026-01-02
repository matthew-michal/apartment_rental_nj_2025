# infrastructure/modules/ecs_training/outputs.tf

output "task_definition_arn" {
  description = "ARN of the training task definition"
  value       = aws_ecs_task_definition.training.arn
}

output "eventbridge_rule_name" {
  description = "Name of the EventBridge rule for training schedule"
  value       = aws_cloudwatch_event_rule.training_schedule.name
}

output "log_group_name" {
  description = "CloudWatch log group name for training logs"
  value       = aws_cloudwatch_log_group.training.name
}
