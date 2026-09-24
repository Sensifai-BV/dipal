# PhotoGear Production Infrastructure

Production-ready AWS infrastructure for deploying Django backend to ECS Fargate with automated CI/CD via GitLab webhooks.

## Architecture Overview

This infrastructure deploys a complete production environment with:

- **Compute**: ECS Fargate cluster with auto-scaling and circuit breaker rollback
- **Load Balancing**: Application Load Balancer with HTTPS support for public API access
- **Database**: RDS PostgreSQL with automated backups
- **Cache**: ElastiCache Redis for Celery broker and caching
- **Storage**: S3 bucket with KMS encryption for media files
- **Container Registry**: ECR for Docker images with lifecycle policies
- **CI/CD**: GitLab webhook → API Gateway → Lambda → S3 → CodePipeline → CodeBuild → ECS
- **Networking**: VPC with public/private subnets, NAT Gateway, and VPC endpoints
- **Security**: Security groups, IAM roles with least privilege, encryption at rest
- **Monitoring**: CloudWatch dashboards, alarms, and log aggregation

### Data Flow

```
GitLab Push Event
    ↓
GitLab Webhook (with API key)
    ↓
API Gateway
    ↓
Lambda (validates webhook, uploads metadata)
    ↓
S3 Artifact Bucket (source.zip)
    ↓
EventBridge (triggers on S3 upload)
    ↓
CodePipeline
    ↓
CodeBuild (clones repo, builds Docker image)
    ↓
ECR (pushes image with commit hash + latest tags)
    ↓
ECS Fargate (deploys with circuit breaker)
    ↓
Application Running (with health checks)
```

## Prerequisites

Before deploying, ensure you have:

1. **AWS CLI** configured with appropriate credentials
   ```bash
   aws configure
   ```

2. **Terraform** >= 1.0 installed
   ```bash
   terraform version
   ```

3. **Docker** installed (for building initial image)
   ```bash
   docker version
   ```

4. **Git** access to the backend repository
   ```bash
   git clone https://gitlab.eclipse.org/eclipse-research-labs/spade-project/opencall-2/dipal/backend-core.git
   ```

5. **AWS Account** with permissions to create:
   - VPC, Subnets, NAT Gateway
   - RDS, ElastiCache
   - ECS, ECR
   - S3, KMS
   - Lambda, API Gateway
   - CodePipeline, CodeBuild
   - IAM roles and policies
   - Secrets Manager, SSM Parameter Store
   - CloudWatch

## Project Structure

```
.
├── terraform/
│   ├── modules/
│   │   ├── networking/      # VPC, subnets, NAT gateway
│   │   ├── security/        # Security groups, IAM roles
│   │   ├── load_balancer/   # Application Load Balancer
│   │   ├── database/        # RDS PostgreSQL
│   │   ├── cache/           # ElastiCache Redis
│   │   ├── storage/         # S3 buckets, ECR
│   │   ├── compute/         # ECS cluster, tasks, service
│   │   ├── cicd/            # Lambda, API Gateway, CodePipeline
│   │   └── monitoring/      # CloudWatch alarms and dashboard
│   ├── main.tf              # Root module configuration
│   ├── variables.tf         # Variable definitions
│   ├── outputs.tf           # Output values
│   ├── providers.tf         # Provider configuration
│   ├── terraform.tfvars     # Variable values (safe to commit)
│   └── terraform.tfvars.secret.example  # Secret template
├── buildspec.yml            # CodeBuild build specification
└── README.md                # This file
```

## Deployment Steps

### Step 1: Initialize Terraform

```bash
cd terraform
terraform init
```

### Step 2: Review and Customize Variables

Edit `terraform.tfvars` if needed:

```hcl
# Key variables you might want to adjust
db_instance_class      = "db.t3.micro"     # Increase for production
redis_node_type        = "cache.t3.micro"  # Increase for production
ecs_task_cpu          = "256"              # Increase if needed
ecs_task_memory       = "512"              # Increase if needed
db_multi_az           = false              # Set true for HA
db_deletion_protection = true              # Keep true for production
```

### Step 3: Plan Infrastructure

```bash
terraform plan -out=tfplan
```

Review the plan carefully to understand what will be created.

### Step 4: Deploy Infrastructure

```bash
terraform apply tfplan
```

This will take approximately 10-15 minutes to create all resources.

### Step 5: Retrieve Outputs

```bash
terraform output
```

Save important outputs:
- `webhook_url` - For GitLab configuration
- `ecr_repository_url` - For Docker image push
- `db_endpoint` - Database connection string
- `redis_endpoint` - Redis connection string

### Step 6: Update Secrets

Update the following secrets in AWS Secrets Manager:

```bash
# Django SECRET_KEY
aws secretsmanager update-secret \
  --secret-id photogear/production/secret-key \
  --secret-string "$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" \
  --region eu-north-1

# AWS credentials for S3 access from Django
aws secretsmanager update-secret \
  --secret-id photogear/production/aws-access-key-id \
  --secret-string "YOUR_AWS_ACCESS_KEY_ID" \
  --region eu-north-1

aws secretsmanager update-secret \
  --secret-id photogear/production/aws-secret-access-key \
  --secret-string "YOUR_AWS_SECRET_ACCESS_KEY" \
  --region eu-north-1

# AI Service API Key
aws secretsmanager update-secret \
  --secret-id photogear/production/ai-service-secret-key \
  --secret-string "YOUR_AI_SERVICE_API_KEY" \
  --region eu-north-1
```

### Step 7: Update SSM Parameters

```bash
# Allowed hosts (comma-separated)
aws ssm put-parameter \
  --name /photogear/production/allowed-hosts \
  --value "yourdomain.com,www.yourdomain.com" \
  --type String \
  --overwrite \
  --region eu-north-1

# CORS allowed origins (comma-separated)
aws ssm put-parameter \
  --name /photogear/production/cors-allowed-origins \
  --value "https://yourdomain.com,https://www.yourdomain.com" \
  --type String \
  --overwrite \
  --region eu-north-1
```

### Step 8: Build and Push Initial Docker Image

```bash
# Get ECR repository URL from terraform output
ECR_URL=$(terraform output -raw ecr_repository_url)

# Clone the backend repository
git clone https://gitlab.eclipse.org/eclipse-research-labs/spade-project/opencall-2/dipal/backend-core.git
cd backend-core

# Login to ECR
aws ecr get-login-password --region eu-north-1 | \
  docker login --username AWS --password-stdin $ECR_URL

# Build Docker image
docker build -t $ECR_URL:latest .

# Push to ECR
docker push $ECR_URL:latest

cd ..
```

### Step 9: Update ECS Service

After pushing the initial image, update the ECS service to pull it:

```bash
# Force new deployment
aws ecs update-service \
  --cluster photogear-production-cluster \
  --service photogear-production-service \
  --force-new-deployment \
  --region eu-north-1
```

### Step 10: Configure GitLab Webhook

1. Get the webhook API key:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id $(terraform output -raw webhook_api_key_secret_arn) \
     --query SecretString \
     --output text \
     --region eu-north-1
   ```

2. In GitLab, navigate to your repository:
   - Settings → Webhooks → Add webhook

3. Configure the webhook:
   - **URL**: `<webhook_url from terraform output>`
   - **Secret Token**: Leave empty
   - **Custom Headers**: Add header
     - Key: `x-api-key`
     - Value: `<API key from step 1>`
   - **Trigger**: Select "Push events"
   - **SSL verification**: Enable

4. Click "Add webhook" and test it

### Step 11: Copy buildspec.yml to Your Repository

Copy the `buildspec.yml` file to the root of your backend repository:

```bash
cp buildspec.yml backend-core/
cd backend-core
git add buildspec.yml
git commit -m "Add CodeBuild buildspec"
git push
```

This push will trigger the CI/CD pipeline!

## Accessing the Backend API

After deployment, the backend API is accessible via the Application Load Balancer:

```bash
# Get the backend URL
terraform output backend_url_https

# Test the API health endpoint
curl -k https://$(terraform output -raw alb_dns_name)/

# Or use HTTP (will redirect to HTTPS)
curl -L http://$(terraform output -raw alb_dns_name)/
```

The URL will look like: `https://photogear-production-alb-123456789.eu-north-1.elb.amazonaws.com`

**Important**: Update your Django configuration to include the ALB DNS name:

```bash
# Update ALLOWED_HOSTS to include the ALB DNS name
ALB_DNS=$(terraform output -raw alb_dns_name)
aws ssm put-parameter \
  --name /photogear/production/allowed-hosts \
  --value "localhost,127.0.0.1,$ALB_DNS" \
  --type String \
  --overwrite \
  --region eu-north-1

# Update CORS_ALLOWED_ORIGINS for frontend access
aws ssm put-parameter \
  --name /photogear/production/cors-allowed-origins \
  --value "http://localhost:3000,https://$ALB_DNS" \
  --type String \
  --overwrite \
  --region eu-north-1
```

**Note about HTTPS**: The ALB uses a self-signed certificate when no custom domain is configured. Browsers will show a security warning. For production use:

1. Register a custom domain (e.g., api.photogear.com)
2. Create an ACM certificate for your domain in AWS Certificate Manager
3. Add the certificate ARN to `terraform.tfvars`:
   ```hcl
   alb_certificate_arn = "arn:aws:acm:eu-north-1:123456789:certificate/xxxxx"
   ```
4. Create a Route53 A record pointing to the ALB:
   ```bash
   aws route53 change-resource-record-sets \
     --hosted-zone-id YOUR_ZONE_ID \
     --change-batch file://dns-change.json
   ```

## Monitoring and Troubleshooting

### View CloudWatch Dashboard

```bash
# Get dashboard URL
echo "https://console.aws.amazon.com/cloudwatch/home?region=eu-north-1#dashboards:name=$(terraform output -raw cloudwatch_dashboard_name)"
```

### Check ECS Service Status

```bash
aws ecs describe-services \
  --cluster photogear-production-cluster \
  --services photogear-production-service \
  --region eu-north-1
```

### View ECS Task Logs

```bash
# Get the latest task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster photogear-production-cluster \
  --service-name photogear-production-service \
  --region eu-north-1 \
  --query 'taskArns[0]' \
  --output text)

# View logs
aws logs tail /ecs/photogear-production --follow --region eu-north-1
```

### Check CodePipeline Status

```bash
aws codepipeline get-pipeline-state \
  --name photogear-production-pipeline \
  --region eu-north-1
```

### View CodeBuild Logs

```bash
# Get the latest build ID
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name photogear-production-build \
  --region eu-north-1 \
  --query 'ids[0]' \
  --output text)

# View build logs
aws logs tail /aws/codebuild/photogear-production --follow --region eu-north-1
```

### Debug Failed Deployments

If a deployment fails, check:

1. **ECS Circuit Breaker**: The circuit breaker will automatically roll back failed deployments
   ```bash
   aws ecs describe-services \
     --cluster photogear-production-cluster \
     --services photogear-production-service \
     --query 'services[0].deployments' \
     --region eu-north-1
   ```

2. **Health Check**: Ensure your `/health/` endpoint returns 200
   ```bash
   # SSH into task (if exec enabled)
   aws ecs execute-command \
     --cluster photogear-production-cluster \
     --task <task-id> \
     --container backend \
     --command "/bin/bash" \
     --interactive \
     --region eu-north-1
   ```

3. **Environment Variables**: Verify all secrets are populated
   ```bash
   # Check task definition
   aws ecs describe-task-definition \
     --task-definition photogear-production-task \
     --region eu-north-1
   ```

### Common Issues

**Issue**: ECS tasks fail to start
- **Solution**: Check CloudWatch logs, verify environment variables are set correctly

**Issue**: Database connection errors
- **Solution**: Verify security groups allow traffic from ECS to RDS on port 5432

**Issue**: Pipeline doesn't trigger on push
- **Solution**: Verify GitLab webhook configuration and API key

**Issue**: CodeBuild fails to clone repository
- **Solution**: Check if repository is public or configure GitLab credentials

**Issue**: Docker build fails
- **Solution**: Check buildspec.yml syntax and Dockerfile in your repository

## Costs Estimation

Approximate monthly costs (eu-north-1):

| Service | Configuration | Estimated Cost |
|---------|--------------|----------------|
| ECS Fargate | 1 task (256 CPU, 512 MB) | $10-15 |
| RDS PostgreSQL | db.t3.micro, 20GB | $15-20 |
| ElastiCache Redis | cache.t3.micro | $12-15 |
| Application Load Balancer | 1 ALB + data transfer | $16-25 |
| NAT Gateway | 1 gateway + data transfer | $35-50 |
| S3 | Storage + requests | $5-10 |
| ECR | Image storage | $1-2 |
| CloudWatch | Logs + metrics | $5-10 |
| Other | Lambda, API Gateway, etc. | $2-5 |
| **Total** | | **~$101-152/month** |

To reduce costs:
- Use Single NAT Gateway (already configured)
- Enable S3 lifecycle policies (already configured)
- Use t3.micro instances (already configured)
- Set up budget alerts

## Security Best Practices

This infrastructure implements:

- ✅ Encryption at rest (RDS, S3, ElastiCache)
- ✅ Encryption in transit (HTTPS, TLS)
- ✅ Secrets stored in AWS Secrets Manager
- ✅ Configuration in SSM Parameter Store
- ✅ IAM roles with least privilege
- ✅ Security groups restricting access
- ✅ Private subnets for compute/database
- ✅ VPC endpoints for S3
- ✅ API key authentication for webhooks
- ✅ Container image scanning
- ✅ CloudWatch logging enabled

Additional recommendations:
- Enable AWS GuardDuty
- Set up AWS WAF for API Gateway
- Configure AWS Config for compliance
- Enable AWS CloudTrail for auditing
- Use AWS Systems Manager Session Manager instead of SSH

## Maintenance

### Backup Strategy

- **RDS**: Automated daily backups (7-day retention)
- **S3**: Versioning enabled with lifecycle policies
- **ECR**: Keep last 10 images

### Update Infrastructure

```bash
# Pull latest changes
git pull

# Plan changes
terraform plan -out=tfplan

# Apply changes
terraform apply tfplan
```

### Scale Up/Down

Edit `terraform.tfvars`:

```hcl
# Increase resources
db_instance_class = "db.t3.small"
redis_node_type   = "cache.t3.small"
ecs_task_cpu      = "512"
ecs_task_memory   = "1024"
ecs_desired_count = 2
```

Then apply:

```bash
terraform apply
```

### Disaster Recovery

1. **Database**: Restore from automated backup
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier photogear-production-db-restored \
     --db-snapshot-identifier <snapshot-id>
   ```

2. **S3**: Restore from version history
   ```bash
   aws s3api list-object-versions --bucket photogear-production-app-data
   ```

3. **Full Infrastructure**: Re-run `terraform apply`

## Cleanup

To destroy all resources:

```bash
# Disable deletion protection first
terraform apply -var="db_deletion_protection=false"

# Destroy all resources
terraform destroy

# Note: Some resources may need manual deletion:
# - S3 buckets with contents
# - ECR images
# - CloudWatch log groups
```

## Support and Contributing

For issues or questions:
1. Check CloudWatch logs
2. Review this README
3. Check Terraform documentation

## License

This infrastructure code is provided as-is for the PhotoGear project.
