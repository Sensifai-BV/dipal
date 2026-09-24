# Quick Start Guide

This is a condensed guide to get your infrastructure up and running quickly. For full details, see [README.md](README.md).

## Prerequisites Checklist

- [ ] AWS CLI configured: `aws configure`
- [ ] Terraform installed: `terraform --version`
- [ ] Docker installed: `docker --version`

## Deployment in 5 Steps

### 1. Initialize Terraform

```bash
cd terraform
terraform init
```

### 2. Deploy Infrastructure

```bash
terraform plan -out=tfplan
terraform apply tfplan
```

**Wait ~10-15 minutes for deployment to complete.**

### 3. Save Important Outputs

```bash
# Save these values - you'll need them!
terraform output ecr_repository_url
terraform output webhook_url
terraform output backend_url_https
terraform output db_endpoint
terraform output redis_endpoint

# Get the webhook API key
aws secretsmanager get-secret-value \
  --secret-id $(terraform output -raw webhook_api_key_secret_arn) \
  --query SecretString --output text --region eu-north-1
```

### 4. Update Secrets

```bash
# Generate and set Django secret key
aws secretsmanager update-secret \
  --secret-id photogear/production/secret-key \
  --secret-string "$(openssl rand -base64 50)" \
  --region eu-north-1

# Set AWS credentials for S3 access
aws secretsmanager update-secret \
  --secret-id photogear/production/aws-access-key-id \
  --secret-string "YOUR_AWS_ACCESS_KEY_ID" \
  --region eu-north-1

aws secretsmanager update-secret \
  --secret-id photogear/production/aws-secret-access-key \
  --secret-string "YOUR_AWS_SECRET_ACCESS_KEY" \
  --region eu-north-1

# Set AI service key
aws secretsmanager update-secret \
  --secret-id photogear/production/ai-service-secret-key \
  --secret-string "YOUR_AI_SERVICE_API_KEY" \
  --region eu-north-1

# Update allowed hosts (include ALB DNS name)
ALB_DNS=$(terraform output -raw alb_dns_name)
aws ssm put-parameter \
  --name /photogear/production/allowed-hosts \
  --value "localhost,127.0.0.1,$ALB_DNS" \
  --type String --overwrite --region eu-north-1

# Update CORS origins (include ALB DNS name)
aws ssm put-parameter \
  --name /photogear/production/cors-allowed-origins \
  --value "http://localhost:3000,https://$ALB_DNS" \
  --type String --overwrite --region eu-north-1
```

### 5. Build and Deploy Initial Image

```bash
# Get ECR URL from output
ECR_URL=$(cd terraform && terraform output -raw ecr_repository_url)

# Clone your backend repo
git clone https://gitlab.eclipse.org/eclipse-research-labs/spade-project/opencall-2/dipal/backend-core.git
cd backend-core

# Copy buildspec.yml to repo
cp ../buildspec.yml .

# Login to ECR
aws ecr get-login-password --region eu-north-1 | \
  docker login --username AWS --password-stdin $ECR_URL

# Build and push
docker build -t $ECR_URL:latest .
docker push $ECR_URL:latest

# Force ECS deployment
aws ecs update-service \
  --cluster photogear-production-cluster \
  --service photogear-production-service \
  --force-new-deployment \
  --region eu-north-1

# Commit buildspec.yml to trigger CI/CD
git add buildspec.yml
git commit -m "Add buildspec for automated builds"
git push
```

## Configure GitLab Webhook

1. In GitLab: **Settings** → **Webhooks** → **Add webhook**
2. Enter:
   - **URL**: `<webhook_url from terraform output>`
   - **Custom Header**: Key: `x-api-key`, Value: `<API key from step 3>`
   - **Trigger**: ✓ Push events
3. Click **Add webhook**
4. Test the webhook

**Done!** Now every push to your repository will automatically build and deploy to ECS.

## Verify Deployment

```bash
# Check ECS service
aws ecs describe-services \
  --cluster photogear-production-cluster \
  --services photogear-production-service \
  --region eu-north-1

# View logs
aws logs tail /ecs/photogear-production --follow --region eu-north-1

# Check pipeline
aws codepipeline get-pipeline-state \
  --name photogear-production-pipeline \
  --region eu-north-1
```

## Access Your Backend

Your backend API is now publicly accessible via the Application Load Balancer:

```bash
# Get backend URL
cd terraform
terraform output backend_url_https

# Test the API
curl -k https://$(terraform output -raw alb_dns_name)/
```

The URL will be something like: `https://photogear-production-alb-123456789.eu-north-1.elb.amazonaws.com`

**Note**: The `-k` flag bypasses SSL verification (self-signed certificate). For production, configure a custom domain with ACM certificate.

**For your frontend**: Use the `alb_dns_name` output to configure your frontend's API endpoint.

## Access Monitoring

```bash
# Open CloudWatch Dashboard
DASHBOARD=$(cd terraform && terraform output -raw cloudwatch_dashboard_name)
echo "https://console.aws.amazon.com/cloudwatch/home?region=eu-north-1#dashboards:name=$DASHBOARD"
```

## Troubleshooting

**ECS tasks not starting?**
```bash
# Check logs
aws logs tail /ecs/photogear-production --follow --region eu-north-1
```

**Database connection issues?**
```bash
# Verify DB endpoint
cd terraform && terraform output db_endpoint
```

**Pipeline not triggering?**
- Verify webhook is configured in GitLab
- Check API key is correct
- View Lambda logs: `aws logs tail /aws/lambda/photogear-production-webhook-processor --follow`

## Next Steps

- [ ] Set up custom domain name
- [ ] Configure SSL/TLS certificate
- [ ] Set up automated backups schedule
- [ ] Configure CloudWatch alarms notifications
- [ ] Review and adjust resource sizes based on load
- [ ] Set up AWS Budgets for cost monitoring

For detailed information, see [README.md](README.md).
