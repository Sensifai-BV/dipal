output "redis_endpoint" {
  description = "Redis endpoint address"
  value       = local.redis_endpoint
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.main.port
}

output "redis_id" {
  description = "Redis replication group ID"
  value       = aws_elasticache_replication_group.main.id
}
