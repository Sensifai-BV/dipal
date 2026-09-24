# CloudWatch Log Group for Telegram Lambda
resource "aws_cloudwatch_log_group" "telegram_lambda" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-telegram-notifier"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-telegram-notifier-logs"
    }
  )
}

# Package Lambda function
data "archive_file" "telegram_lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda/telegram_notifier.zip"

  source {
    content  = file("${path.module}/lambda/telegram_notifier.py")
    filename = "telegram_notifier.py"
  }
}

# Telegram Notifier Lambda Function
resource "aws_lambda_function" "telegram_notifier" {
  filename         = data.archive_file.telegram_lambda_zip.output_path
  function_name    = "${var.project_name}-${var.environment}-telegram-notifier"
  role             = var.telegram_lambda_role_arn
  handler          = "telegram_notifier.handler"
  source_code_hash = data.archive_file.telegram_lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 30

  environment {
    variables = {
      TELEGRAM_SECRET_ARN = var.telegram_secret_arn
      PROJECT_NAME        = var.project_name
      ENVIRONMENT         = var.environment
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-telegram-notifier"
    }
  )
}

# EventBridge Rule: Backend Pipeline State Changes
resource "aws_cloudwatch_event_rule" "backend_pipeline" {
  name        = "${var.project_name}-${var.environment}-backend-pipeline-notifications"
  description = "Trigger Telegram notifications for backend pipeline state changes"

  event_pattern = jsonencode({
    source      = ["aws.codepipeline"]
    detail-type = ["CodePipeline Pipeline Execution State Change"]
    detail = {
      pipeline = [var.backend_pipeline_name]
      state    = ["STARTED", "SUCCEEDED", "FAILED"]
    }
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-backend-pipeline-notifications"
    }
  )
}

resource "aws_cloudwatch_event_target" "backend_pipeline" {
  rule     = aws_cloudwatch_event_rule.backend_pipeline.name
  arn      = aws_lambda_function.telegram_notifier.arn
  role_arn = null
}

resource "aws_lambda_permission" "backend_pipeline" {
  statement_id  = "AllowBackendPipelineEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.backend_pipeline.arn
}

# EventBridge Rule: Frontend Pipeline State Changes
resource "aws_cloudwatch_event_rule" "frontend_pipeline" {
  name        = "${var.project_name}-${var.environment}-frontend-pipeline-notifications"
  description = "Trigger Telegram notifications for frontend pipeline state changes"

  event_pattern = jsonencode({
    source      = ["aws.codepipeline"]
    detail-type = ["CodePipeline Pipeline Execution State Change"]
    detail = {
      pipeline = [var.frontend_pipeline_name]
      state    = ["STARTED", "SUCCEEDED", "FAILED"]
    }
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-pipeline-notifications"
    }
  )
}

resource "aws_cloudwatch_event_target" "frontend_pipeline" {
  rule     = aws_cloudwatch_event_rule.frontend_pipeline.name
  arn      = aws_lambda_function.telegram_notifier.arn
  role_arn = null
}

resource "aws_lambda_permission" "frontend_pipeline" {
  statement_id  = "AllowFrontendPipelineEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.frontend_pipeline.arn
}

# EventBridge Rule: Backend Build State Changes
resource "aws_cloudwatch_event_rule" "backend_build" {
  name        = "${var.project_name}-${var.environment}-backend-build-notifications"
  description = "Trigger Telegram notifications for backend build state changes"

  event_pattern = jsonencode({
    source      = ["aws.codebuild"]
    detail-type = ["CodeBuild Build State Change"]
    detail = {
      "project-name" = [var.backend_build_project]
      "build-status" = ["IN_PROGRESS", "SUCCEEDED", "FAILED"]
    }
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-backend-build-notifications"
    }
  )
}

resource "aws_cloudwatch_event_target" "backend_build" {
  rule     = aws_cloudwatch_event_rule.backend_build.name
  arn      = aws_lambda_function.telegram_notifier.arn
  role_arn = null
}

resource "aws_lambda_permission" "backend_build" {
  statement_id  = "AllowBackendBuildEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.backend_build.arn
}

# EventBridge Rule: Frontend Build State Changes
resource "aws_cloudwatch_event_rule" "frontend_build" {
  name        = "${var.project_name}-${var.environment}-frontend-build-notifications"
  description = "Trigger Telegram notifications for frontend build state changes"

  event_pattern = jsonencode({
    source      = ["aws.codebuild"]
    detail-type = ["CodeBuild Build State Change"]
    detail = {
      "project-name" = [var.frontend_build_project]
      "build-status" = ["IN_PROGRESS", "SUCCEEDED", "FAILED"]
    }
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-build-notifications"
    }
  )
}

resource "aws_cloudwatch_event_target" "frontend_build" {
  rule     = aws_cloudwatch_event_rule.frontend_build.name
  arn      = aws_lambda_function.telegram_notifier.arn
  role_arn = null
}

resource "aws_lambda_permission" "frontend_build" {
  statement_id  = "AllowFrontendBuildEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_notifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.frontend_build.arn
}
