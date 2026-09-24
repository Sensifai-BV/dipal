# ============================================
# CloudWatch Alarms
# ============================================

# ECS Backend Alarms
resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  alarm_name          = "${var.project_name}-${var.environment}-ecs-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "ECS backend CPU utilization above 80%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.ecs_service_name
  }

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-ecs-cpu-high" })
}

resource "aws_cloudwatch_metric_alarm" "ecs_memory_high" {
  alarm_name          = "${var.project_name}-${var.environment}-ecs-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "ECS backend memory utilization above 80%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.ecs_service_name
  }

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-ecs-memory-high" })
}

# RDS Alarms
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${var.project_name}-${var.environment}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU utilization above 80%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = var.db_instance_id
  }

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-rds-cpu-high" })
}

resource "aws_cloudwatch_metric_alarm" "rds_storage_low" {
  alarm_name          = "${var.project_name}-${var.environment}-rds-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 2000000000
  alarm_description   = "RDS free storage below 2GB"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = var.db_instance_id
  }

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-rds-storage-low" })
}

# Redis Alarms
resource "aws_cloudwatch_metric_alarm" "redis_cpu_high" {
  alarm_name          = "${var.project_name}-${var.environment}-redis-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 75
  alarm_description   = "Redis CPU utilization above 75%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = var.redis_id
  }

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-redis-cpu-high" })
}

resource "aws_cloudwatch_metric_alarm" "redis_memory_high" {
  alarm_name          = "${var.project_name}-${var.environment}-redis-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Redis memory utilization above 80%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = var.redis_id
  }

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-redis-memory-high" })
}

# ALB Alarms
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.project_name}-${var.environment}-alb-5xx-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_ELB_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "ALB 5XX errors above 10 in 5 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-alb-5xx-high" })
}

resource "aws_cloudwatch_metric_alarm" "alb_target_5xx" {
  alarm_name          = "${var.project_name}-${var.environment}-alb-target-5xx-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "ALB target 5XX errors above 10 in 5 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-alb-target-5xx-high" })
}

resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_hosts" {
  alarm_name          = "${var.project_name}-${var.environment}-alb-unhealthy-hosts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "ALB has unhealthy targets"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-alb-unhealthy-hosts" })
}

# GPU EC2 Instance Status Check Alarm
resource "aws_cloudwatch_metric_alarm" "gpu_instance_status" {
  count = var.enable_gpu_instance ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-gpu-instance-status"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  threshold           = 1
  alarm_description   = "GPU EC2 instance failed status check (instance may be unreachable or impaired)"
  treat_missing_data  = "breaching"

  metric_query {
    id          = "statuscheck"
    expression  = "FILL(m1, 1)"
    label       = "StatusCheckFailed"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "StatusCheckFailed"
      namespace   = "AWS/EC2"
      period      = 300
      stat        = "Maximum"

      dimensions = {
        InstanceId = var.gpu_instance_id
      }
    }
  }

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-gpu-instance-status" })
}

# ============================================
# CloudWatch Dashboard
# ============================================

locals {
  # SQS widgets - one per queue
  sqs_metric_widgets = [for q in var.sqs_queue_names : {
    type   = "metric"
    x      = 0
    y      = 0
    width  = 12
    height = 6
    properties = {
      metrics = [
        ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", q.name, { stat = "Sum" }],
        [".", "ApproximateNumberOfMessagesNotVisible", ".", ".", { stat = "Sum" }],
        [".", "NumberOfMessagesSent", ".", ".", { stat = "Sum" }],
        [".", "NumberOfMessagesReceived", ".", ".", { stat = "Sum" }]
      ]
      period  = 300
      region  = var.region
      title   = "SQS: ${q.label}"
      view    = "timeSeries"
      stacked = false
    }
  }]

  sqs_dlq_widgets = [for q in var.sqs_queue_names : {
    type   = "metric"
    x      = 12
    y      = 0
    width  = 12
    height = 6
    properties = {
      metrics = [
        ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "${q.name}-dlq", { stat = "Sum", color = "#d62728" }]
      ]
      period  = 300
      region  = var.region
      title   = "DLQ: ${q.label}"
      view    = "timeSeries"
      stacked = false
    }
  }]

  # AI ECS service widgets
  ai_ecs_widgets = [for svc in var.ai_ecs_service_names : {
    type   = "metric"
    x      = 0
    y      = 0
    width  = 12
    height = 6
    properties = {
      metrics = [
        ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", svc, { stat = "Average" }],
        [".", "MemoryUtilization", ".", ".", ".", ".", { stat = "Average" }]
      ]
      period  = 300
      region  = var.region
      title   = "AI ECS: ${svc}"
      view    = "timeSeries"
      stacked = false
    }
  }]

  # NAT Gateway widgets
  nat_widgets = [for i, id in var.nat_gateway_ids : {
    type   = "metric"
    x      = (i % 2) * 12
    y      = 0
    width  = 12
    height = 6
    properties = {
      metrics = [
        ["AWS/NATGateway", "BytesOutToDestination", "NatGatewayId", id, { stat = "Sum" }],
        [".", "BytesInFromSource", ".", ".", { stat = "Sum" }],
        [".", "PacketsDropCount", ".", ".", { stat = "Sum", color = "#d62728" }],
        [".", "ErrorPortAllocation", ".", ".", { stat = "Sum", color = "#ff7f0e" }]
      ]
      period  = 300
      region  = var.region
      title   = "NAT Gateway ${i + 1}"
      view    = "timeSeries"
      stacked = false
    }
  }]
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = concat(
      # ============================================
      # Section: ALB
      # ============================================
      [
        {
          type   = "text"
          x      = 0
          y      = 0
          width  = 24
          height = 1
          properties = {
            markdown = "# Application Load Balancer"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 1
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix, { stat = "Sum", label = "Requests" }]
            ]
            period  = 60
            region  = var.region
            title   = "ALB Request Count"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 1
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { stat = "Average", label = "Avg" }],
              ["...", { stat = "p99", label = "p99" }],
              ["...", { stat = "p95", label = "p95" }]
            ]
            period  = 60
            region  = var.region
            title   = "ALB Response Time"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 1
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ApplicationELB", "HTTPCode_ELB_2XX_Count", "LoadBalancer", var.alb_arn_suffix, { stat = "Sum", label = "2XX", color = "#2ca02c" }],
              [".", "HTTPCode_ELB_4XX_Count", ".", ".", { stat = "Sum", label = "4XX", color = "#ff7f0e" }],
              [".", "HTTPCode_ELB_5XX_Count", ".", ".", { stat = "Sum", label = "5XX", color = "#d62728" }],
              [".", "HTTPCode_Target_2XX_Count", ".", ".", { stat = "Sum", label = "Target 2XX", color = "#98df8a" }],
              [".", "HTTPCode_Target_4XX_Count", ".", ".", { stat = "Sum", label = "Target 4XX", color = "#ffbb78" }],
              [".", "HTTPCode_Target_5XX_Count", ".", ".", { stat = "Sum", label = "Target 5XX", color = "#ff9896" }]
            ]
            period  = 60
            region  = var.region
            title   = "ALB HTTP Status Codes"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 7
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ApplicationELB", "HealthyHostCount", "TargetGroup", var.target_group_arn_suffix, "LoadBalancer", var.alb_arn_suffix, { stat = "Average", label = "Healthy", color = "#2ca02c" }],
              [".", "UnHealthyHostCount", ".", ".", ".", ".", { stat = "Average", label = "Unhealthy", color = "#d62728" }]
            ]
            period  = 60
            region  = var.region
            title   = "ALB Target Health"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 7
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ApplicationELB", "ActiveConnectionCount", "LoadBalancer", var.alb_arn_suffix, { stat = "Sum", label = "Active" }],
              [".", "NewConnectionCount", ".", ".", { stat = "Sum", label = "New" }]
            ]
            period  = 60
            region  = var.region
            title   = "ALB Connections"
            view    = "timeSeries"
            stacked = false
          }
        },
      ],

      # ============================================
      # Section: ECS Backend & Celery
      # ============================================
      [
        {
          type   = "text"
          x      = 0
          y      = 13
          width  = 24
          height = 1
          properties = {
            markdown = "# ECS Services (Backend & Celery)"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 14
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name, { stat = "Average", label = "Backend CPU" }],
              ["...", var.celery_worker_service_name, { stat = "Average", label = "Celery CPU" }]
            ]
            period  = 300
            region  = var.region
            title   = "ECS CPU Utilization"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 14
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ECS", "MemoryUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name, { stat = "Average", label = "Backend Memory" }],
              ["...", var.celery_worker_service_name, { stat = "Average", label = "Celery Memory" }]
            ]
            period  = 300
            region  = var.region
            title   = "ECS Memory Utilization"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 14
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name, { stat = "Average", label = "Backend Tasks" }],
              ["...", var.celery_worker_service_name, { stat = "Average", label = "Celery Tasks" }]
            ]
            period  = 300
            region  = var.region
            title   = "ECS Running Tasks"
            view    = "timeSeries"
            stacked = false
          }
        },
      ],

      # ============================================
      # Section: AI ECS Services (dynamic)
      # ============================================
      length(var.ai_ecs_service_names) > 0 ? [
        {
          type   = "text"
          x      = 0
          y      = 20
          width  = 24
          height = 1
          properties = {
            markdown = "# AI ECS Services"
          }
        }
      ] : [],
      local.ai_ecs_widgets,

      # ============================================
      # Section: RDS
      # ============================================
      [
        {
          type   = "text"
          x      = 0
          y      = 26
          width  = 24
          height = 1
          properties = {
            markdown = "# RDS PostgreSQL"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 27
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.db_instance_id, { stat = "Average" }]
            ]
            period  = 300
            region  = var.region
            title   = "RDS CPU Utilization"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 27
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/RDS", "FreeableMemory", "DBInstanceIdentifier", var.db_instance_id, { stat = "Average", label = "Freeable Memory" }]
            ]
            period  = 300
            region  = var.region
            title   = "RDS Freeable Memory"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 27
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", var.db_instance_id, { stat = "Average" }]
            ]
            period  = 300
            region  = var.region
            title   = "RDS Free Storage"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 33
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", var.db_instance_id, { stat = "Sum" }]
            ]
            period  = 300
            region  = var.region
            title   = "RDS Connections"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 33
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/RDS", "ReadIOPS", "DBInstanceIdentifier", var.db_instance_id, { stat = "Average", label = "Read IOPS" }],
              [".", "WriteIOPS", ".", ".", { stat = "Average", label = "Write IOPS" }]
            ]
            period  = 300
            region  = var.region
            title   = "RDS IOPS"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 33
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/RDS", "ReadLatency", "DBInstanceIdentifier", var.db_instance_id, { stat = "Average", label = "Read Latency" }],
              [".", "WriteLatency", ".", ".", { stat = "Average", label = "Write Latency" }]
            ]
            period  = 300
            region  = var.region
            title   = "RDS Latency"
            view    = "timeSeries"
            stacked = false
          }
        },
      ],

      # ============================================
      # Section: ElastiCache / Redis
      # ============================================
      [
        {
          type   = "text"
          x      = 0
          y      = 39
          width  = 24
          height = 1
          properties = {
            markdown = "# ElastiCache Redis"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 40
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ElastiCache", "CPUUtilization", "ReplicationGroupId", var.redis_id, { stat = "Average" }],
              [".", "EngineCPUUtilization", ".", ".", { stat = "Average", label = "Engine CPU" }]
            ]
            period  = 300
            region  = var.region
            title   = "Redis CPU Utilization"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 40
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ElastiCache", "DatabaseMemoryUsagePercentage", "ReplicationGroupId", var.redis_id, { stat = "Average", label = "Memory %" }],
              [".", "FreeableMemory", ".", ".", { stat = "Average", label = "Freeable Memory" }]
            ]
            period  = 300
            region  = var.region
            title   = "Redis Memory"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 40
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ElastiCache", "CurrConnections", "ReplicationGroupId", var.redis_id, { stat = "Sum", label = "Current" }],
              [".", "NewConnections", ".", ".", { stat = "Sum", label = "New" }]
            ]
            period  = 300
            region  = var.region
            title   = "Redis Connections"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 46
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ElastiCache", "CacheHits", "ReplicationGroupId", var.redis_id, { stat = "Sum", label = "Hits", color = "#2ca02c" }],
              [".", "CacheMisses", ".", ".", { stat = "Sum", label = "Misses", color = "#d62728" }]
            ]
            period  = 300
            region  = var.region
            title   = "Redis Cache Hits vs Misses"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 46
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ElastiCache", "NetworkBytesIn", "ReplicationGroupId", var.redis_id, { stat = "Sum", label = "Bytes In" }],
              [".", "NetworkBytesOut", ".", ".", { stat = "Sum", label = "Bytes Out" }]
            ]
            period  = 300
            region  = var.region
            title   = "Redis Network I/O"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 46
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/ElastiCache", "CurrItems", "ReplicationGroupId", var.redis_id, { stat = "Average", label = "Items" }],
              [".", "Evictions", ".", ".", { stat = "Sum", label = "Evictions", color = "#d62728" }]
            ]
            period  = 300
            region  = var.region
            title   = "Redis Items & Evictions"
            view    = "timeSeries"
            stacked = false
          }
        },
      ],

      # ============================================
      # Section: SQS Queues (dynamic)
      # ============================================
      length(var.sqs_queue_names) > 0 ? [
        {
          type   = "text"
          x      = 0
          y      = 52
          width  = 24
          height = 1
          properties = {
            markdown = "# SQS Queues"
          }
        }
      ] : [],
      local.sqs_metric_widgets,
      local.sqs_dlq_widgets,

      # ============================================
      # Section: EFS
      # ============================================
      [
        {
          type   = "text"
          x      = 0
          y      = 59
          width  = 24
          height = 1
          properties = {
            markdown = "# EFS (Elastic File System)"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 60
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/EFS", "TotalIOBytes", "FileSystemId", var.efs_id, { stat = "Sum", label = "Total I/O" }]
            ]
            period  = 300
            region  = var.region
            title   = "EFS Total I/O (Bytes)"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 60
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/EFS", "ClientConnections", "FileSystemId", var.efs_id, { stat = "Sum" }]
            ]
            period  = 300
            region  = var.region
            title   = "EFS Client Connections"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 60
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/EFS", "StorageBytes", "FileSystemId", var.efs_id, "StorageClass", "Total", { stat = "Average", label = "Total Storage" }]
            ]
            period  = 86400
            region  = var.region
            title   = "EFS Storage Size"
            view    = "timeSeries"
            stacked = false
          }
        },
      ],

      # ============================================
      # Section: CloudFront
      # ============================================
      [
        {
          type   = "text"
          x      = 0
          y      = 66
          width  = 24
          height = 1
          properties = {
            markdown = "# CloudFront (Frontend CDN)"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 67
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/CloudFront", "Requests", "DistributionId", var.cloudfront_distribution_id, "Region", "Global", { stat = "Sum" }]
            ]
            period  = 300
            region  = "us-east-1"
            title   = "CloudFront Requests"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 67
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/CloudFront", "BytesDownloaded", "DistributionId", var.cloudfront_distribution_id, "Region", "Global", { stat = "Sum", label = "Downloaded" }],
              [".", "BytesUploaded", ".", ".", ".", ".", { stat = "Sum", label = "Uploaded" }]
            ]
            period  = 300
            region  = "us-east-1"
            title   = "CloudFront Data Transfer"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 67
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["AWS/CloudFront", "4xxErrorRate", "DistributionId", var.cloudfront_distribution_id, "Region", "Global", { stat = "Average", label = "4XX %", color = "#ff7f0e" }],
              [".", "5xxErrorRate", ".", ".", ".", ".", { stat = "Average", label = "5XX %", color = "#d62728" }]
            ]
            period  = 300
            region  = "us-east-1"
            title   = "CloudFront Error Rates"
            view    = "timeSeries"
            stacked = false
          }
        },
      ],

      # ============================================
      # Section: NAT Gateway (dynamic)
      # ============================================
      length(var.nat_gateway_ids) > 0 ? [
        {
          type   = "text"
          x      = 0
          y      = 73
          width  = 24
          height = 1
          properties = {
            markdown = "# NAT Gateways"
          }
        }
      ] : [],
      local.nat_widgets,

      # ============================================
      # Section: Application Logs
      # ============================================
      [
        {
          type   = "text"
          x      = 0
          y      = 80
          width  = 24
          height = 1
          properties = {
            markdown = "# Application Logs"
          }
        },
        {
          type   = "log"
          x      = 0
          y      = 81
          width  = 12
          height = 6
          properties = {
            query  = "SOURCE '/ecs/${var.project_name}-${var.environment}' | fields @timestamp, @message | filter @message like /ERROR|Exception|Traceback/ | sort @timestamp desc | limit 50"
            region = var.region
            title  = "Backend Error Logs"
            view   = "table"
          }
        },
        {
          type   = "log"
          x      = 12
          y      = 81
          width  = 12
          height = 6
          properties = {
            query  = "SOURCE '/ecs/${var.project_name}-${var.environment}' | fields @timestamp, @message | sort @timestamp desc | limit 30"
            region = var.region
            title  = "Recent Backend Logs"
            view   = "table"
          }
        },
      ],
      # ============================================
      # Section: Django Application Metrics (Summary)
      # ============================================
      [
        {
          type   = "text"
          x      = 0
          y      = 87
          width  = 24
          height = 1
          properties = {
            markdown = "# Django Application Metrics  *(full detail → ${var.project_name}-${var.environment}-django-dashboard)*"
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 88
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["PhotoGear/Django", "HttpRequestsTotal", { stat = "Maximum", label = "Total Requests" }]
            ]
            period  = 60
            region  = var.region
            title   = "HTTP Requests Total"
            view    = "timeSeries"
            stacked = false
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 88
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["PhotoGear/Django", "RequestLatencyAvg", { stat = "Average", label = "Avg" }],
              ["PhotoGear/Django", "RequestLatencyP50", { stat = "Average", label = "p50" }],
              ["PhotoGear/Django", "RequestLatencyP90", { stat = "Average", label = "p90" }],
              ["PhotoGear/Django", "RequestLatencyP99", { stat = "Average", label = "p99" }]
            ]
            period  = 60
            region  = var.region
            title   = "Request Latency (ms)"
            view    = "timeSeries"
            stacked = false
            yAxis = {
              left = { min = 0, label = "ms" }
            }
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 88
          width  = 8
          height = 6
          properties = {
            metrics = [
              ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "200", { stat = "Maximum", label = "200" }],
              ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "201", { stat = "Maximum", label = "201" }],
              ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "400", { stat = "Maximum", label = "400" }],
              ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "404", { stat = "Maximum", label = "404" }],
              ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "500", { stat = "Maximum", label = "500" }]
            ]
            period  = 60
            region  = var.region
            title   = "Responses by Status Code"
            view    = "timeSeries"
            stacked = true
          }
        },
      ]
    )
  })
}

# ============================================
# GPU Instance Dashboard
# ============================================

resource "aws_cloudwatch_dashboard" "gpu" {
  count          = var.enable_gpu_instance ? 1 : 0
  dashboard_name = "${var.project_name}-${var.environment}-gpu-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "# GPU Instance (${var.gpu_instance_id})"
        }
      },

      # CPU
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/EC2", "CPUUtilization", "InstanceId", var.gpu_instance_id, { stat = "Average", label = "CPU %" }]
          ]
          period  = 60
          region  = var.region
          title   = "CPU Utilization"
          view    = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, max = 100 }
          }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 1
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/EC2", "CPUCreditBalance", "InstanceId", var.gpu_instance_id, { stat = "Average", label = "Credit Balance" }],
            [".", "CPUCreditUsage", ".", ".", { stat = "Average", label = "Credit Usage" }]
          ]
          period  = 300
          region  = var.region
          title   = "CPU Credits"
          view    = "timeSeries"
          stacked = false
        }
      },

      # Status Checks
      {
        type   = "metric"
        x      = 16
        y      = 1
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/EC2", "StatusCheckFailed", "InstanceId", var.gpu_instance_id, { stat = "Maximum", label = "Any Failed", color = "#d62728" }],
            [".", "StatusCheckFailed_Instance", ".", ".", { stat = "Maximum", label = "Instance Failed", color = "#ff7f0e" }],
            [".", "StatusCheckFailed_System", ".", ".", { stat = "Maximum", label = "System Failed", color = "#9467bd" }]
          ]
          period  = 60
          region  = var.region
          title   = "Status Checks"
          view    = "timeSeries"
          stacked = false
        }
      },

      # Network
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/EC2", "NetworkIn", "InstanceId", var.gpu_instance_id, { stat = "Sum", label = "Bytes In" }],
            [".", "NetworkOut", ".", ".", { stat = "Sum", label = "Bytes Out" }]
          ]
          period  = 300
          region  = var.region
          title   = "Network Traffic"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 7
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/EC2", "NetworkPacketsIn", "InstanceId", var.gpu_instance_id, { stat = "Sum", label = "Packets In" }],
            [".", "NetworkPacketsOut", ".", ".", { stat = "Sum", label = "Packets Out" }]
          ]
          period  = 300
          region  = var.region
          title   = "Network Packets"
          view    = "timeSeries"
          stacked = false
        }
      },

      # Disk
      {
        type   = "metric"
        x      = 16
        y      = 7
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/EC2", "EBSReadBytes", "InstanceId", var.gpu_instance_id, { stat = "Sum", label = "Read Bytes" }],
            [".", "EBSWriteBytes", ".", ".", { stat = "Sum", label = "Write Bytes" }]
          ]
          period  = 300
          region  = var.region
          title   = "EBS Throughput"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 13
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/EC2", "EBSReadOps", "InstanceId", var.gpu_instance_id, { stat = "Sum", label = "Read Ops" }],
            [".", "EBSWriteOps", ".", ".", { stat = "Sum", label = "Write Ops" }]
          ]
          period  = 300
          region  = var.region
          title   = "EBS IOPS"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 13
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["AWS/EC2", "EBSIOBalance%", "InstanceId", var.gpu_instance_id, { stat = "Average", label = "I/O Balance %" }],
            [".", "EBSByteBalance%", ".", ".", { stat = "Average", label = "Byte Balance %" }]
          ]
          period  = 300
          region  = var.region
          title   = "EBS Burst Balance"
          view    = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, max = 100 }
          }
        }
      },

      # GPU Metrics (NVIDIA via CloudWatch Agent)
      {
        type   = "text"
        x      = 0
        y      = 19
        width  = 24
        height = 1
        properties = {
          markdown = "## GPU Metrics (requires CloudWatch Agent with NVIDIA plugin)"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 20
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["CWAgent", "nvidia_smi_utilization_gpu", "InstanceId", var.gpu_instance_id, "name", var.gpu_name, "index", var.gpu_index, "arch", var.gpu_arch, { stat = "Average", label = "GPU Utilization %" }]
          ]
          period  = 60
          region  = var.region
          title   = "GPU Utilization"
          view    = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, max = 100 }
          }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 20
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["CWAgent", "nvidia_smi_memory_used", "InstanceId", var.gpu_instance_id, "name", var.gpu_name, "index", var.gpu_index, "arch", var.gpu_arch, { stat = "Average", label = "Memory Used (MiB)" }],
            [".", "nvidia_smi_memory_total", ".", ".", ".", ".", ".", ".", ".", ".", { stat = "Average", label = "Memory Total (MiB)" }]
          ]
          period  = 60
          region  = var.region
          title   = "GPU Memory"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 20
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["CWAgent", "nvidia_smi_temperature_gpu", "InstanceId", var.gpu_instance_id, "name", var.gpu_name, "index", var.gpu_index, "arch", var.gpu_arch, { stat = "Average", label = "GPU Temp (°C)" }]
          ]
          period  = 60
          region  = var.region
          title   = "GPU Temperature"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 26
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["CWAgent", "nvidia_smi_power_draw", "InstanceId", var.gpu_instance_id, "name", var.gpu_name, "index", var.gpu_index, "arch", var.gpu_arch, { stat = "Average", label = "Power Draw (W)" }]
          ]
          period  = 60
          region  = var.region
          title   = "GPU Power Draw"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 26
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["CWAgent", "nvidia_smi_utilization_memory", "InstanceId", var.gpu_instance_id, "name", var.gpu_name, "index", var.gpu_index, "arch", var.gpu_arch, { stat = "Average", label = "Memory Controller %" }]
          ]
          period  = 60
          region  = var.region
          title   = "GPU Memory Controller Utilization"
          view    = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, max = 100 }
          }
        }
      },

      # System Metrics (via CloudWatch Agent)
      {
        type   = "text"
        x      = 0
        y      = 32
        width  = 24
        height = 1
        properties = {
          markdown = "## System Metrics (requires CloudWatch Agent)"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 33
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["CWAgent", "mem_used_percent", "InstanceId", var.gpu_instance_id, { stat = "Average", label = "Memory Used %" }]
          ]
          period  = 60
          region  = var.region
          title   = "System Memory"
          view    = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, max = 100 }
          }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 33
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["CWAgent", "disk_used_percent", "InstanceId", var.gpu_instance_id, "path", "/", "device", "nvme0n1p1", "fstype", "ext4", { stat = "Average", label = "Disk Used %" }]
          ]
          period  = 300
          region  = var.region
          title   = "Disk Usage"
          view    = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, max = 100 }
          }
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 33
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["CWAgent", "swap_used_percent", "InstanceId", var.gpu_instance_id, { stat = "Average", label = "Swap Used %" }]
          ]
          period  = 300
          region  = var.region
          title   = "Swap Usage"
          view    = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, max = 100 }
          }
        }
      },
    ]
  })
}

# ============================================
# Django Application Metrics Dashboard (Full)
# ============================================

resource "aws_cloudwatch_dashboard" "django" {
  dashboard_name = "${var.project_name}-${var.environment}-django-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # ---- Row 0: Header ----
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "# Django Application Metrics — ${var.project_name}-${var.environment}"
        }
      },

      # ============================================
      # Section: HTTP Overview
      # ============================================
      {
        type   = "text"
        x      = 0
        y      = 1
        width  = 24
        height = 1
        properties = {
          markdown = "## HTTP Overview"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "HttpRequestsTotal", { stat = "Maximum", label = "Requests" }],
            ["PhotoGear/Django", "HttpResponsesTotal", { stat = "Maximum", label = "Responses" }]
          ]
          period  = 60
          region  = var.region
          title   = "HTTP Requests & Responses Total"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 2
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "RequestsByMethod", "Method", "GET", { stat = "Maximum", label = "GET" }],
            ["PhotoGear/Django", "RequestsByMethod", "Method", "POST", { stat = "Maximum", label = "POST" }],
            ["PhotoGear/Django", "RequestsByMethod", "Method", "PUT", { stat = "Maximum", label = "PUT" }],
            ["PhotoGear/Django", "RequestsByMethod", "Method", "PATCH", { stat = "Maximum", label = "PATCH" }],
            ["PhotoGear/Django", "RequestsByMethod", "Method", "DELETE", { stat = "Maximum", label = "DELETE" }]
          ]
          period  = 60
          region  = var.region
          title   = "Requests by Method"
          view    = "timeSeries"
          stacked = true
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 2
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "RequestsByTransport", "Transport", "http", { stat = "Maximum", label = "HTTP" }]
          ]
          period  = 60
          region  = var.region
          title   = "Requests by Transport"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 8
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "AjaxRequestsTotal", { stat = "Maximum", label = "AJAX Requests" }]
          ]
          period  = 60
          region  = var.region
          title   = "AJAX Requests"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 8
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "StreamingResponsesTotal", { stat = "Maximum", label = "Streaming" }]
          ]
          period  = 60
          region  = var.region
          title   = "Streaming Responses"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 8
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "UnknownLatencyTotal", { stat = "Maximum", label = "Unknown Latency" }],
            ["PhotoGear/Django", "UnknownLatencyMiddlewaresTotal", { stat = "Maximum", label = "Unknown Latency (Middlewares)" }]
          ]
          period  = 60
          region  = var.region
          title   = "Unknown Latency Requests"
          view    = "timeSeries"
          stacked = false
        }
      },

      # ============================================
      # Section: Response Status Codes
      # ============================================
      {
        type   = "text"
        x      = 0
        y      = 14
        width  = 24
        height = 1
        properties = {
          markdown = "## Response Status Codes"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 15
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "200", { stat = "Maximum", label = "200 OK" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "201", { stat = "Maximum", label = "201 Created" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "302", { stat = "Maximum", label = "302 Found" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "400", { stat = "Maximum", label = "400 Bad Request" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "404", { stat = "Maximum", label = "404 Not Found" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "405", { stat = "Maximum", label = "405 Method Not Allowed" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "406", { stat = "Maximum", label = "406 Not Acceptable" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "500", { stat = "Maximum", label = "500 Internal Error" }]
          ]
          period  = 60
          region  = var.region
          title   = "All Response Status Codes"
          view    = "timeSeries"
          stacked = true
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 15
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "400", { stat = "Maximum", label = "400" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "404", { stat = "Maximum", label = "404" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "405", { stat = "Maximum", label = "405" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "406", { stat = "Maximum", label = "406" }],
            ["PhotoGear/Django", "ResponsesByStatus", "StatusCode", "500", { stat = "Maximum", label = "500" }]
          ]
          period  = 60
          region  = var.region
          title   = "Error Responses (4xx & 5xx)"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 21
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ResponsesByTemplate", "TemplateName", "None", { stat = "Maximum", label = "None (API)" }],
            ["PhotoGear/Django", "ResponsesByTemplate", "TemplateName", "drf_spectacular/swagger_ui.html", { stat = "Maximum", label = "Swagger UI" }]
          ]
          period  = 60
          region  = var.region
          title   = "Responses by Template"
          view    = "timeSeries"
          stacked = true
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 21
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ResponsesByCharset", "Charset", "utf-8", { stat = "Maximum", label = "UTF-8" }]
          ]
          period  = 60
          region  = var.region
          title   = "Responses by Charset"
          view    = "timeSeries"
          stacked = false
        }
      },

      # ============================================
      # Section: Request Latency
      # ============================================
      {
        type   = "text"
        x      = 0
        y      = 27
        width  = 24
        height = 1
        properties = {
          markdown = "## Request Latency"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 28
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "RequestLatencyAvg", { stat = "Average", label = "Average" }],
            ["PhotoGear/Django", "RequestLatencyP50", { stat = "Average", label = "p50" }],
            ["PhotoGear/Django", "RequestLatencyP90", { stat = "Average", label = "p90" }],
            ["PhotoGear/Django", "RequestLatencyP95", { stat = "Average", label = "p95" }],
            ["PhotoGear/Django", "RequestLatencyP99", { stat = "Average", label = "p99" }]
          ]
          period  = 60
          region  = var.region
          title   = "Request Latency Percentiles (ms)"
          view    = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, label = "ms" }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 28
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "RequestLatencyTotalSum", { stat = "Maximum", label = "Total Latency Sum (ms)" }],
            ["PhotoGear/Django", "RequestLatencyTotalCount", { stat = "Maximum", label = "Total Request Count" }]
          ]
          period  = 60
          region  = var.region
          title   = "Latency Sum & Request Count"
          view    = "timeSeries"
          stacked = false
        }
      },

      # ============================================
      # Section: Latency by View
      # ============================================
      {
        type   = "text"
        x      = 0
        y      = 34
        width  = 24
        height = 1
        properties = {
          markdown = "## Latency by View"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 35
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "LatencyByView", "View", "account-profile", "Method", "GET", { stat = "Average", label = "account-profile" }],
            ["PhotoGear/Django", "LatencyByView", "View", "job-management-list", "Method", "GET", { stat = "Average", label = "job-management-list" }],
            ["PhotoGear/Django", "LatencyByView", "View", "dashboard:stats", "Method", "GET", { stat = "Average", label = "dashboard:stats" }],
            ["PhotoGear/Django", "LatencyByView", "View", "dashboard:activities", "Method", "GET", { stat = "Average", label = "dashboard:activities" }],
            ["PhotoGear/Django", "LatencyByView", "View", "uploads:datasets-stats", "Method", "GET", { stat = "Average", label = "uploads:datasets-stats" }],
            ["PhotoGear/Django", "LatencyByView", "View", "product-list", "Method", "GET", { stat = "Average", label = "product-list" }]
          ]
          period  = 60
          region  = var.region
          title   = "Latency by View — GET (ms)"
          view    = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, label = "ms" }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 35
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "LatencyByView", "View", "uploads:multipart-sign", "Method", "POST", { stat = "Average", label = "multipart-sign" }],
            ["PhotoGear/Django", "LatencyByView", "View", "start-processing", "Method", "POST", { stat = "Average", label = "start-processing" }],
            ["PhotoGear/Django", "LatencyByView", "View", "ai-callback", "Method", "POST", { stat = "Average", label = "ai-callback" }],
            ["PhotoGear/Django", "LatencyByView", "View", "product-upload-init", "Method", "POST", { stat = "Average", label = "product-upload-init" }],
            ["PhotoGear/Django", "LatencyByView", "View", "product-upload-chunk", "Method", "POST", { stat = "Average", label = "product-upload-chunk" }],
            ["PhotoGear/Django", "LatencyByView", "View", "product-upload-complete", "Method", "POST", { stat = "Average", label = "product-upload-complete" }]
          ]
          period  = 60
          region  = var.region
          title   = "Latency by View — POST (ms)"
          view    = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, label = "ms" }
          }
        }
      },

      # ============================================
      # Section: Request Count by View
      # ============================================
      {
        type   = "text"
        x      = 0
        y      = 41
        width  = 24
        height = 1
        properties = {
          markdown = "## Request Count by View"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 42
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "RequestCountByView", "View", "api-root", "Method", "GET", { stat = "Maximum", label = "api-root" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "account-profile", "Method", "GET", { stat = "Maximum", label = "account-profile" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "job-management-list", "Method", "GET", { stat = "Maximum", label = "job-management-list" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "dashboard:stats", "Method", "GET", { stat = "Maximum", label = "dashboard:stats" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "dashboard:activities", "Method", "GET", { stat = "Maximum", label = "dashboard:activities" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "uploads:datasets-stats", "Method", "GET", { stat = "Maximum", label = "datasets-stats" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "product-list", "Method", "GET", { stat = "Maximum", label = "product-list" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "swagger-ui", "Method", "GET", { stat = "Maximum", label = "swagger-ui" }]
          ]
          period  = 60
          region  = var.region
          title   = "Request Count — GET Views"
          view    = "timeSeries"
          stacked = true
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 42
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "RequestCountByView", "View", "uploads:multipart-sign", "Method", "POST", { stat = "Maximum", label = "multipart-sign" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "start-processing", "Method", "POST", { stat = "Maximum", label = "start-processing" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "ai-callback", "Method", "POST", { stat = "Maximum", label = "ai-callback" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "product-upload-init", "Method", "POST", { stat = "Maximum", label = "upload-init" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "product-upload-chunk", "Method", "POST", { stat = "Maximum", label = "upload-chunk" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "product-upload-complete", "Method", "POST", { stat = "Maximum", label = "upload-complete" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "job-cancel", "Method", "POST", { stat = "Maximum", label = "job-cancel" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "job-retry", "Method", "POST", { stat = "Maximum", label = "job-retry" }]
          ]
          period  = 60
          region  = var.region
          title   = "Request Count — POST Views"
          view    = "timeSeries"
          stacked = true
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 48
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "RequestCountByView", "View", "uploads:dataset-delete", "Method", "DELETE", { stat = "Maximum", label = "dataset-delete" }],
            ["PhotoGear/Django", "RequestCountByView", "View", "job-delete", "Method", "DELETE", { stat = "Maximum", label = "job-delete" }]
          ]
          period  = 60
          region  = var.region
          title   = "Request Count — DELETE Views"
          view    = "timeSeries"
          stacked = true
        }
      },

      # ============================================
      # Section: Request & Response Body Size
      # ============================================
      {
        type   = "text"
        x      = 12
        y      = 48
        width  = 12
        height = 1
        properties = {
          markdown = "## Body Size"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 49
        width  = 6
        height = 5
        properties = {
          metrics = [
            ["PhotoGear/Django", "RequestBodyBytesAvg", { stat = "Average", label = "Avg Request Body" }],
            ["PhotoGear/Django", "ResponseBodyBytesAvg", { stat = "Average", label = "Avg Response Body" }]
          ]
          period  = 60
          region  = var.region
          title   = "Avg Body Size (Bytes)"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 18
        y      = 49
        width  = 6
        height = 5
        properties = {
          metrics = [
            ["PhotoGear/Django", "RequestBodyBytesTotal", { stat = "Maximum", label = "Total Request Bytes" }],
            ["PhotoGear/Django", "ResponseBodyBytesTotal", { stat = "Maximum", label = "Total Response Bytes" }]
          ]
          period  = 60
          region  = var.region
          title   = "Total Body Bytes"
          view    = "timeSeries"
          stacked = false
        }
      },

      # ============================================
      # Section: Exceptions
      # ============================================
      {
        type   = "text"
        x      = 0
        y      = 54
        width  = 24
        height = 1
        properties = {
          markdown = "## Exceptions"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 55
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ExceptionsByType", "Type", "Http404", { stat = "Sum", label = "Http404" }],
            ["PhotoGear/Django", "ExceptionsByType", "Type", "PermissionDenied", { stat = "Sum", label = "PermissionDenied" }],
            ["PhotoGear/Django", "ExceptionsByType", "Type", "ValidationError", { stat = "Sum", label = "ValidationError" }]
          ]
          period  = 60
          region  = var.region
          title   = "Exceptions by Type"
          view    = "timeSeries"
          stacked = true
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 55
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ExceptionsByView", "View", "ai-callback", { stat = "Sum", label = "ai-callback" }],
            ["PhotoGear/Django", "ExceptionsByView", "View", "job-cancel", { stat = "Sum", label = "job-cancel" }],
            ["PhotoGear/Django", "ExceptionsByView", "View", "start-processing", { stat = "Sum", label = "start-processing" }]
          ]
          period  = 60
          region  = var.region
          title   = "Exceptions by View"
          view    = "timeSeries"
          stacked = true
        }
      },

      # ============================================
      # Section: Process Metrics
      # ============================================
      {
        type   = "text"
        x      = 0
        y      = 61
        width  = 24
        height = 1
        properties = {
          markdown = "## Process Metrics"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 62
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ProcessResidentMemoryBytes", { stat = "Average", label = "Resident (RSS)" }],
            ["PhotoGear/Django", "ProcessVirtualMemoryBytes", { stat = "Average", label = "Virtual (VSZ)" }]
          ]
          period  = 60
          region  = var.region
          title   = "Process Memory (Bytes)"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 62
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ProcessCpuSecondsTotal", { stat = "Maximum", label = "CPU Seconds Total" }]
          ]
          period  = 60
          region  = var.region
          title   = "Process CPU Seconds"
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 62
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ProcessOpenFds", { stat = "Average", label = "Open FDs" }],
            ["PhotoGear/Django", "ProcessMaxFds", { stat = "Average", label = "Max FDs" }]
          ]
          period  = 60
          region  = var.region
          title   = "File Descriptors"
          view    = "timeSeries"
          stacked = false
        }
      },

      # ============================================
      # Section: Python GC
      # ============================================
      {
        type   = "text"
        x      = 0
        y      = 68
        width  = 24
        height = 1
        properties = {
          markdown = "## Python Garbage Collection"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 69
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "GcObjectsCollectedTotal", "Generation", "0", { stat = "Maximum", label = "Gen 0" }],
            ["PhotoGear/Django", "GcObjectsCollectedTotal", "Generation", "1", { stat = "Maximum", label = "Gen 1" }],
            ["PhotoGear/Django", "GcObjectsCollectedTotal", "Generation", "2", { stat = "Maximum", label = "Gen 2" }]
          ]
          period  = 60
          region  = var.region
          title   = "GC Objects Collected"
          view    = "timeSeries"
          stacked = true
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 69
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "GcObjectsUncollectableTotal", "Generation", "0", { stat = "Maximum", label = "Gen 0" }],
            ["PhotoGear/Django", "GcObjectsUncollectableTotal", "Generation", "1", { stat = "Maximum", label = "Gen 1" }],
            ["PhotoGear/Django", "GcObjectsUncollectableTotal", "Generation", "2", { stat = "Maximum", label = "Gen 2" }]
          ]
          period  = 60
          region  = var.region
          title   = "GC Objects Uncollectable"
          view    = "timeSeries"
          stacked = true
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 69
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "GcCollectionsTotal", "Generation", "0", { stat = "Maximum", label = "Gen 0" }],
            ["PhotoGear/Django", "GcCollectionsTotal", "Generation", "1", { stat = "Maximum", label = "Gen 1" }],
            ["PhotoGear/Django", "GcCollectionsTotal", "Generation", "2", { stat = "Maximum", label = "Gen 2" }]
          ]
          period  = 60
          region  = var.region
          title   = "GC Collections Count"
          view    = "timeSeries"
          stacked = true
        }
      },

      # ============================================
      # Section: Django Model Operations
      # ============================================
      {
        type   = "text"
        x      = 0
        y      = 75
        width  = 24
        height = 1
        properties = {
          markdown = "## Django Model Operations"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 76
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ModelInsertsTotal", { stat = "Sum" }]
          ]
          period  = 60
          region  = var.region
          title   = "Model Inserts"
          view    = "timeSeries"
          stacked = true
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 76
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ModelUpdatesTotal", { stat = "Sum" }]
          ]
          period  = 60
          region  = var.region
          title   = "Model Updates"
          view    = "timeSeries"
          stacked = true
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 76
        width  = 8
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "ModelDeletesTotal", { stat = "Sum" }]
          ]
          period  = 60
          region  = var.region
          title   = "Model Deletes"
          view    = "timeSeries"
          stacked = true
        }
      },

      # ============================================
      # Section: Migrations
      # ============================================
      {
        type   = "text"
        x      = 0
        y      = 82
        width  = 24
        height = 1
        properties = {
          markdown = "## Migrations"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 83
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "MigrationsApplied", { stat = "Maximum" }]
          ]
          period  = 300
          region  = var.region
          title   = "Migrations Applied"
          view    = "singleValue"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 83
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["PhotoGear/Django", "MigrationsUnapplied", { stat = "Maximum" }]
          ]
          period  = 300
          region  = var.region
          title   = "Migrations Unapplied"
          view    = "singleValue"
          stacked = false
        }
      },
    ]
  })
}
