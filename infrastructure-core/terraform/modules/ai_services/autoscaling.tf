# Auto-scaling: 0/1 scaling for Calibration and Orthomosaic based on SQS queue depth

# --- Calibration ---
resource "aws_appautoscaling_target" "calibration" {
  max_capacity       = 1
  min_capacity       = 0
  resource_id        = "service/${var.ecs_cluster_name}/${aws_ecs_service.calibration.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "calibration_scale_up" {
  name               = "${var.project_name}-${var.environment}-calibration-scale-up"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.calibration.resource_id
  scalable_dimension = aws_appautoscaling_target.calibration.scalable_dimension
  service_namespace  = aws_appautoscaling_target.calibration.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ExactCapacity"
    cooldown                = 60
    metric_aggregation_type = "Maximum"

    step_adjustment {
      scaling_adjustment          = 1
      metric_interval_lower_bound = 0
    }
  }
}

resource "aws_appautoscaling_policy" "calibration_scale_down" {
  name               = "${var.project_name}-${var.environment}-calibration-scale-down"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.calibration.resource_id
  scalable_dimension = aws_appautoscaling_target.calibration.scalable_dimension
  service_namespace  = aws_appautoscaling_target.calibration.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ExactCapacity"
    cooldown                = 300
    metric_aggregation_type = "Maximum"

    step_adjustment {
      scaling_adjustment          = 0
      metric_interval_upper_bound = 0
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "calibration_queue_has_messages" {
  alarm_name          = "${var.project_name}-${var.environment}-calibration-queue-not-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0

  dimensions = {
    QueueName = var.calibration_queue_name
  }

  alarm_actions = [aws_appautoscaling_policy.calibration_scale_up.arn]

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-calibration-queue-alarm"
    Component = "AI-Services"
  })
}

resource "aws_cloudwatch_metric_alarm" "calibration_queue_empty" {
  alarm_name          = "${var.project_name}-${var.environment}-calibration-queue-empty"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 5
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0

  dimensions = {
    QueueName = var.calibration_queue_name
  }

  alarm_actions = [aws_appautoscaling_policy.calibration_scale_down.arn]

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-calibration-queue-empty-alarm"
    Component = "AI-Services"
  })
}

# --- Orthomosaic ---
resource "aws_appautoscaling_target" "orthomosaic" {
  max_capacity       = 1
  min_capacity       = 0
  resource_id        = "service/${var.ecs_cluster_name}/${aws_ecs_service.orthomosaic.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "orthomosaic_scale_up" {
  name               = "${var.project_name}-${var.environment}-orthomosaic-scale-up"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.orthomosaic.resource_id
  scalable_dimension = aws_appautoscaling_target.orthomosaic.scalable_dimension
  service_namespace  = aws_appautoscaling_target.orthomosaic.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ExactCapacity"
    cooldown                = 60
    metric_aggregation_type = "Maximum"

    step_adjustment {
      scaling_adjustment          = 1
      metric_interval_lower_bound = 0
    }
  }
}

resource "aws_appautoscaling_policy" "orthomosaic_scale_down" {
  name               = "${var.project_name}-${var.environment}-orthomosaic-scale-down"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.orthomosaic.resource_id
  scalable_dimension = aws_appautoscaling_target.orthomosaic.scalable_dimension
  service_namespace  = aws_appautoscaling_target.orthomosaic.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ExactCapacity"
    cooldown                = 300
    metric_aggregation_type = "Maximum"

    step_adjustment {
      scaling_adjustment          = 0
      metric_interval_upper_bound = 0
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "orthomosaic_queue_has_messages" {
  alarm_name          = "${var.project_name}-${var.environment}-orthomosaic-queue-not-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0

  dimensions = {
    QueueName = var.orthomosaic_queue_name
  }

  alarm_actions = [aws_appautoscaling_policy.orthomosaic_scale_up.arn]

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-orthomosaic-queue-alarm"
    Component = "AI-Services"
  })
}

resource "aws_cloudwatch_metric_alarm" "orthomosaic_queue_empty" {
  alarm_name          = "${var.project_name}-${var.environment}-orthomosaic-queue-empty"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 5
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0

  dimensions = {
    QueueName = var.orthomosaic_queue_name
  }

  alarm_actions = [aws_appautoscaling_policy.orthomosaic_scale_down.arn]

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-orthomosaic-queue-empty-alarm"
    Component = "AI-Services"
  })
}
