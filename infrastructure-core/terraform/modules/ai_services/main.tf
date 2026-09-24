data "aws_caller_identity" "current" {}

# ECR Repositories for AI services
resource "aws_ecr_repository" "ai_services" {
  for_each             = toset(["api-gateway", "calibration", "sfm", "orthomosaic-generation"])
  name                 = "${var.project_name}-${var.environment}-${each.key}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-${each.key}-ecr"
    Component = "AI-Services"
  })
}

resource "aws_ecr_lifecycle_policy" "ai_services" {
  for_each   = aws_ecr_repository.ai_services
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# CloudWatch Log Group for AI services
resource "aws_cloudwatch_log_group" "ai_services" {
  name              = "/ecs/${var.project_name}-${var.environment}-ai"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-services-logs"
    Component = "AI-Services"
  })
}

# Cloud Map Service Discovery
resource "aws_service_discovery_private_dns_namespace" "ai" {
  name        = "ai.${var.project_name}.local"
  description = "Service discovery for AI services"
  vpc         = var.vpc_id

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-discovery"
    Component = "AI-Services"
  })
}

resource "aws_service_discovery_service" "api_gateway" {
  name = "gateway"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.ai.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-gateway-discovery"
    Component = "AI-Services"
  })
}

resource "aws_service_discovery_service" "calibration" {
  name = "calibration"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.ai.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-calibration-discovery"
    Component = "AI-Services"
  })
}

resource "aws_service_discovery_service" "sfm" {
  name = "sfm"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.ai.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-sfm-discovery"
    Component = "AI-Services"
  })
}

resource "aws_service_discovery_service" "orthomosaic" {
  name = "orthomosaic"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.ai.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-orthomosaic-discovery"
    Component = "AI-Services"
  })
}
