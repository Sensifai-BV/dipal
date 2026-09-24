import requests
import boto3
from django.conf import settings
from ...domain.interfaces import AIServiceClient, StorageService
from ...domain.entities import ProcessingTask

class HttpAIServiceClient(AIServiceClient):
    def trigger_processing(self, task: ProcessingTask) -> bool:
        url = f"{settings.AI_SERVICE_URL}/v1/api/process"
        payload = {
            "task_id": task.id,
            "s3_key": task.image_s3_key,
            "type": task.task_type,
            "callback_url": settings.WEBHOOK_CALLBACK_URL
        }
        try:
            # Timeout is crucial to prevent hanging
            response = requests.post(url, json=payload, timeout=5)
            return response.status_code == 202 or response.status_code == 200
        except requests.RequestException:
            return False

class S3StorageService(StorageService):
    def __init__(self):
        # Build client kwargs - only include credentials if explicitly set
        # When USE_AWS_ROLE=true, boto3 will automatically use ECS Task Role
        client_kwargs = {
            'endpoint_url': settings.AWS_S3_ENDPOINT_URL  # For MinIO compatibility in Dev
        }
        
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
            client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
        
        self.s3 = boto3.client('s3', **client_kwargs)
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME

    def check_file_exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except:
            return False
