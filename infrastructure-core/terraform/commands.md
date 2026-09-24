### Verify IAM User Permissions

```bash
# List SQS queues
aws sqs list-queues 

# Describe EFS filesystem
aws efs describe-file-systems 

# List S3 buckets
aws s3 ls 
```

## 2. SQS Queue Testing

### Get Queue URLs

```bash
# Get all AI queue URLs
aws sqs list-queues --queue-name-prefix photogear-production-ai 

# Get specific queue URL
CALIBRATION_QUEUE_URL=$(terraform output -raw ai_calibration_queue_url)
SFM_QUEUE_URL=$(terraform output -raw ai_sfm_queue_url)
ORTHOMOSAIC_QUEUE_URL=$(terraform output -raw ai_orthomosaic_queue_url)

CALIBRATION_DLQ_URL=$(terraform output -raw ai_calibration_dlq_url)
SFM_DLQ_URL=$(terraform output -raw ai_sfm_dlq_url)
ORTHOMOSAIC_DLQ_URL=$(terraform output -raw ai_orthomosaic_dlq_url)
```

### Send Test Messages

```bash
# Send message to calibration queue
aws sqs send-message \
  --queue-url $CALIBRATION_QUEUE_URL \
  --message-body '{"task":"calibration","image":"test.jpg"}' \
  

# Send message to SFM queue
aws sqs send-message \
  --queue-url $SFM_QUEUE_URL \
  --message-body '{"task":"sfm","project":"test-project"}' \
  

# Send message to orthomosaic queue
aws sqs send-message \
  --queue-url $ORTHOMOSAIC_QUEUE_URL \
  --message-body '{"task":"orthomosaic","tiles":["tile1","tile2"]}' \
  
```

### Receive and Delete Messages

```bash
# Receive message from calibration queue
aws sqs receive-message \
  --queue-url $CALIBRATION_QUEUE_URL \
  --max-number-of-messages 1 \
  

# Delete message (use receipt handle from above)
aws sqs delete-message \
  --queue-url $CALIBRATION_QUEUE_URL \
  --receipt-handle "RECEIPT_HANDLE_HERE" \
  
```

### Check Queue Attributes

```bash
# Get queue attributes
aws sqs get-queue-attributes \
  --queue-url $CALIBRATION_QUEUE_URL \
  --attribute-names All \
  

# Check approximate message count
aws sqs get-queue-attributes \
  --queue-url $CALIBRATION_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages 
  
```

### Test Dead Letter Queue (DLQ)

```bash
# Send a message and receive it 4 times (maxReceiveCount=3, so 4th time goes to DLQ)
MESSAGE_ID=$(aws sqs send-message --queue-url $CALIBRATION_QUEUE_URL --message-body "test-dlq"  --query 'MessageId' --output text)

# Receive without deleting (repeat 4 times)
for i in {1..4}; do
  aws sqs receive-message --queue-url $CALIBRATION_QUEUE_URL --visibility-timeout 1 
  sleep 2
done

# Check DLQ for the message
aws sqs receive-message \
  --queue-url $CALIBRATION_DLQ_URL \
  
```

### Purge Queue (Development Only)

```bash
# WARNING: This deletes all messages in the queue
aws sqs purge-queue --queue-url $CALIBRATION_QUEUE_URL 
```

## 3. S3 Bucket Testing

### Get Bucket Name

```bash
# Get bucket name from Terraform output
AI_BUCKET=$(terraform output -raw ai_dev_bucket_name)
echo $AI_BUCKET
```

### Upload Test Files

```bash
# Create a test file
echo "Test data for AI development" > test-file.txt

# Upload to S3
aws s3 cp test-file.txt s3://$AI_BUCKET/test-file.txt 

# Upload with metadata
aws s3 cp test-file.txt s3://$AI_BUCKET/data/test-file.txt \
  --metadata project=test,type=calibration \
  
```

### List Objects

```bash
# List all objects
aws s3 ls s3://$AI_BUCKET/ --recursive 

# List with details
aws s3api list-objects-v2 \
  --bucket $AI_BUCKET \
  
```

### Download Objects

```bash
# Download single file
aws s3 cp s3://$AI_BUCKET/test-file.txt downloaded-file.txt 

# Download directory
aws s3 sync s3://$AI_BUCKET/data/ ./local-data/ 
```

### Test Versioning

```bash
# List object versions
aws s3api list-object-versions \
  --bucket $AI_BUCKET \
  --prefix test-file.txt \
  

# Upload new version
echo "Updated content" > test-file.txt
aws s3 cp test-file.txt s3://$AI_BUCKET/test-file.txt 

# List versions again
aws s3api list-object-versions \
  --bucket $AI_BUCKET \
  --prefix test-file.txt \
  
```

### Verify Encryption

```bash
# Check server-side encryption
aws s3api head-object \
  --bucket $AI_BUCKET \
  --key test-file.txt \
   \
  --query 'ServerSideEncryption'
```

### Delete Objects

```bash
# Delete single object
aws s3 rm s3://$AI_BUCKET/test-file.txt 

# Delete all objects (WARNING: Use with caution)
aws s3 rm s3://$AI_BUCKET/ --recursive 
```

## 4. EFS Filesystem Testing

### Get EFS Information

```bash
# Get EFS ID from Terraform output
EFS_ID=$(terraform output -raw ai_efs_id)
EFS_DNS=$(terraform output -raw ai_efs_dns_name)

echo "EFS ID: $EFS_ID"
echo "EFS DNS: $EFS_DNS"
```

### Describe EFS Filesystem

```bash
# Get filesystem details
aws efs describe-file-systems \
  --file-system-id $EFS_ID \
  

# Get mount targets
aws efs describe-mount-targets \
  --file-system-id $EFS_ID \
  

# Get lifecycle policy
aws efs describe-lifecycle-configuration \
  --file-system-id $EFS_ID \
  
```

### Mount EFS (From EC2 or ECS Task)

```bash
# Install NFS client (on Amazon Linux 2)
sudo yum install -y amazon-efs-utils

# Create mount point
sudo mkdir -p /mnt/efs

# Mount using DNS name
sudo mount -t efs -o tls $EFS_ID:/ /mnt/efs

# Or mount using DNS name directly
sudo mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport $EFS_DNS:/ /mnt/efs

# Verify mount
df -h | grep efs
```

### Test EFS Read/Write

```bash
# Write test file
echo "EFS test data" | sudo tee /mnt/efs/test.txt

# Read test file
cat /mnt/efs/test.txt

# Create directory structure
sudo mkdir -p /mnt/efs/calibration /mnt/efs/sfm /mnt/efs/orthomosaic

# Set permissions
sudo chmod -R 755 /mnt/efs/
```

### Add to /etc/fstab (Persistent Mount)

```bash
# Add to fstab for automatic mounting
echo "$EFS_ID:/ /mnt/efs efs _netdev,tls,iam 0 0" | sudo tee -a /etc/fstab

# Test fstab entry
sudo mount -a
```

## 5. Integration Testing

### End-to-End Workflow Test

```bash
# 1. Upload raw data to S3
aws s3 cp raw-images.zip s3://$AI_BUCKET/raw/raw-images.zip 

# 2. Send calibration task to SQS
aws sqs send-message \
  --queue-url $CALIBRATION_QUEUE_URL \
  --message-body "{\"input\":\"s3://$AI_BUCKET/raw/raw-images.zip\",\"output\":\"s3://$AI_BUCKET/processed/\"}" \
  

# 3. Process would run and write to EFS (simulated)
echo "Processing complete" | sudo tee /mnt/efs/calibration/result.txt

# 4. Upload results to S3
aws s3 cp /mnt/efs/calibration/result.txt s3://$AI_BUCKET/processed/result.txt 

# 5. Verify results
aws s3 ls s3://$AI_BUCKET/processed/ 
```

### Queue to S3 to EFS Pipeline

```bash
# Send multiple tasks
for i in {1..5}; do
  aws sqs send-message \
    --queue-url $SFM_QUEUE_URL \
    --message-body "{\"task_id\":\"$i\",\"input\":\"s3://$AI_BUCKET/input/task-$i.zip\"}" \
    
done

# Check queue depth
aws sqs get-queue-attributes \
  --queue-url $SFM_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages \
  
```

## 6. Monitoring and Troubleshooting

### CloudWatch Metrics

```bash
# Get EFS metrics (burst credit balance)
aws cloudwatch get-metric-statistics \
  --namespace AWS/EFS \
  --metric-name BurstCreditBalance \
  --dimensions Name=FileSystemId,Value=$EFS_ID \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average

# Get SQS metrics (approximate number of messages)
QUEUE_NAME="photogear-production-ai-calibration-queue"
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfMessagesVisible \
  --dimensions Name=QueueName,Value=$QUEUE_NAME \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

### Check Resource Tags

```bash
# Check EFS tags
aws efs describe-tags --file-system-id $EFS_ID

# Check SQS tags
aws sqs list-queue-tags --queue-url $CALIBRATION_QUEUE_URL 

# Check S3 tags
aws s3api get-bucket-tagging --bucket $AI_BUCKET 
```

### Troubleshooting Commands

```bash
# Check IAM user permissions
aws iam list-user-policies --user-name photogear-production-aidev
aws iam get-user-policy --user-name photogear-production-aidev --policy-name photogear-production-aidev-policy

# Check security group for EFS
aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=photogear-production-ai-efs-sg" \
  --query 'SecurityGroups[0].{GroupId:GroupId,Ingress:IpPermissions,Egress:IpPermissionsEgress}'

# Test network connectivity to EFS mount targets
MOUNT_TARGET_IP=$(aws efs describe-mount-targets --file-system-id $EFS_ID --query 'MountTargets[0].IpAddress' --output text)
nc -zv $MOUNT_TARGET_IP 2049
```

## 7. Cleanup Test Resources

```bash
# Purge all SQS queues
aws sqs purge-queue --queue-url $CALIBRATION_QUEUE_URL 
aws sqs purge-queue --queue-url $SFM_QUEUE_URL 
aws sqs purge-queue --queue-url $ORTHOMOSAIC_QUEUE_URL 
aws sqs purge-queue --queue-url $CALIBRATION_DLQ_URL 
aws sqs purge-queue --queue-url $SFM_DLQ_URL 
aws sqs purge-queue --queue-url $ORTHOMOSAIC_DLQ_URL 

# Delete all test files from S3
aws s3 rm s3://$AI_BUCKET/test-file.txt 
aws s3 rm s3://$AI_BUCKET/ --recursive --include "test-*" 

# Clean EFS test data
sudo rm -rf /mnt/efs/test*
```

## Notes

- All commands use the `` flag to use the IAM user credentials
- Replace placeholder values (RECEIPT_HANDLE_HERE, etc.) with actual values from command outputs
- EFS mount commands should be run from an EC2 instance or ECS task within the VPC
- For production use, consider implementing proper error handling and logging
- Monitor CloudWatch metrics regularly to track resource usage and costs
