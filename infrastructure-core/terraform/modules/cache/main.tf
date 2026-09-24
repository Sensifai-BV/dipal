resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-redis-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-subnet-group"
    }
  )
}

resource "aws_elasticache_parameter_group" "main" {
  name   = "${var.project_name}-${var.environment}-redis-params"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-params"
    }
  )
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = "${var.project_name}-${var.environment}-redis"
  description                = "Redis cluster for ${var.project_name} ${var.environment}"
  engine                     = "redis"
  engine_version             = var.redis_version
  node_type                  = var.node_type
  num_cache_clusters         = var.num_cache_nodes
  parameter_group_name       = aws_elasticache_parameter_group.main.name
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [var.security_group_id]
  automatic_failover_enabled = var.num_cache_nodes > 1
  multi_az_enabled           = var.num_cache_nodes > 1
  at_rest_encryption_enabled = true
  transit_encryption_enabled = false
  snapshot_retention_limit   = var.snapshot_retention_limit
  snapshot_window            = var.snapshot_window
  maintenance_window         = var.maintenance_window
  notification_topic_arn     = var.notification_topic_arn

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_engine_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "engine-log"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-redis"
    }
  )
}

resource "aws_cloudwatch_log_group" "redis_slow_log" {
  name              = "/aws/elasticache/${var.project_name}-${var.environment}/redis-slow-log"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-slow-log"
    }
  )
}

resource "aws_cloudwatch_log_group" "redis_engine_log" {
  name              = "/aws/elasticache/${var.project_name}-${var.environment}/redis-engine-log"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-engine-log"
    }
  )
}

locals {
  # For single node (num_cache_nodes = 1), use primary_endpoint_address
  # For cluster mode (num_cache_nodes > 1), use configuration_endpoint_address if available
  redis_endpoint = (
    var.num_cache_nodes > 1
    ? coalesce(aws_elasticache_replication_group.main.configuration_endpoint_address, aws_elasticache_replication_group.main.primary_endpoint_address)
    : aws_elasticache_replication_group.main.primary_endpoint_address
  )
}

resource "aws_ssm_parameter" "redis_endpoint" {
  name  = "/${var.project_name}/${var.environment}/redis-endpoint"
  type  = "String"
  value = local.redis_endpoint

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-endpoint"
    }
  )
}

resource "aws_ssm_parameter" "redis_port" {
  name  = "/${var.project_name}/${var.environment}/redis-port"
  type  = "String"
  value = tostring(aws_elasticache_replication_group.main.port)

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-redis-port"
    }
  )
}
