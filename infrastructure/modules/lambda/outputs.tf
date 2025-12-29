# Lambda Module Outputs

output "function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.function.function_name
}

output "function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.function.arn
}

output "function_qualified_arn" {
  description = "Qualified ARN of the Lambda function with version"
  value       = aws_lambda_function.function.qualified_arn
}

output "function_version" {
  description = "Version of the Lambda function"
  value       = aws_lambda_function.function.version
}

output "alias_arn" {
  description = "ARN of the Lambda alias"
  value       = aws_lambda_alias.function_alias.arn
}

output "invoke_arn" {
  description = "Invoke ARN of the Lambda function (for API Gateway, EventBridge)"
  value       = aws_lambda_function.function.invoke_arn
}

output "role_arn" {
  description = "ARN of the IAM role for Lambda"
  value       = aws_iam_role.lambda_role.arn
}

output "log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

output "error_alarm_arn" {
  description = "ARN of the error CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.lambda_errors.arn
}

output "duration_alarm_arn" {
  description = "ARN of the duration CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.lambda_duration.arn
}
