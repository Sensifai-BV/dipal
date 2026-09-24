output "ecs_cluster_id" {
  description = "ID of the ECS cluster"
  value       = aws_ecs_cluster.main.id
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.app.name
}

output "ecs_task_family" {
  description = "Family of the ECS task definition"
  value       = aws_ecs_task_definition.app.family
}

output "celery_worker_service_name" {
  description = "Name of the Celery worker ECS service"
  value       = aws_ecs_service.celery_worker.name
}

output "celery_worker_task_family" {
  description = "Family of the Celery worker task definition"
  value       = aws_ecs_task_definition.celery_worker.family
}
