# Allow ECS tasks to communicate with AI Gateway on port 8080 (self-referencing)
resource "aws_security_group_rule" "ecs_internal_8080" {
  type                     = "ingress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  source_security_group_id = var.ecs_security_group_id
  security_group_id        = var.ecs_security_group_id
  description              = "AI Gateway from ECS tasks"
}

# Security Group for Batch GPU instances
resource "aws_security_group" "batch" {
  name        = "${var.project_name}-${var.environment}-batch-sg"
  description = "Security group for AWS Batch GPU instances"
  vpc_id      = var.vpc_id

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-batch-sg"
    Component = "AI-Services"
  })
}

# Allow EFS access from Batch instances
resource "aws_security_group_rule" "efs_from_batch" {
  type                     = "ingress"
  from_port                = 2049
  to_port                  = 2049
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.batch.id
  security_group_id        = var.efs_security_group_id
  description              = "NFS from Batch GPU instances"
}
