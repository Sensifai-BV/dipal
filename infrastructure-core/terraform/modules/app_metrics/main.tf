# CloudWatch Log Group for Metrics Collector Lambda
resource "aws_cloudwatch_log_group" "metrics_collector" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-metrics-collector"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-metrics-collector-logs"
    }
  )
}

# Package Lambda function
data "archive_file" "metrics_collector_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda/metrics_collector.zip"

  source {
    content  = file("${path.module}/lambda/metrics_collector.py")
    filename = "metrics_collector.py"
  }
}

# Metrics Collector Lambda Function
resource "aws_lambda_function" "metrics_collector" {
  filename         = data.archive_file.metrics_collector_zip.output_path
  function_name    = "${var.project_name}-${var.environment}-metrics-collector"
  role             = var.lambda_role_arn
  handler          = "metrics_collector.handler"
  source_code_hash = data.archive_file.metrics_collector_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 30

  environment {
    variables = {
      METRICS_URL  = var.metrics_url
      CW_NAMESPACE = "PhotoGear/Django"
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-metrics-collector"
    }
  )
}

# EventBridge Schedule Rule - Run every 1 minute
resource "aws_cloudwatch_event_rule" "metrics_schedule" {
  name                = "${var.project_name}-${var.environment}-metrics-collector-schedule"
  description         = "Trigger metrics collector Lambda every minute"
  schedule_expression = "rate(1 minute)"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-metrics-collector-schedule"
    }
  )
}

resource "aws_cloudwatch_event_target" "metrics_schedule" {
  rule = aws_cloudwatch_event_rule.metrics_schedule.name
  arn  = aws_lambda_function.metrics_collector.arn
}

resource "aws_lambda_permission" "metrics_schedule" {
  statement_id  = "AllowEventBridgeSchedule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.metrics_collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.metrics_schedule.arn
}
