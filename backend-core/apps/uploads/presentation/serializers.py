import re
import requests
from urllib.parse import urlparse, parse_qs
from rest_framework import serializers
from ..infrastructure.models import UploadStatus, AIProcessingJob, AIResultFile, Dataset, Image


# --------------------------------------------------------
# 1. Start AI Job Serializers (NEW)
# --------------------------------------------------------

class DatasetImagesManifestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = [
            'id',
            'file_name',
            's3_key',
            'file_size',
            'file_type',
            'batch_id'
        ]
class StartAIRequestSerializer(serializers.Serializer):
    dataset_id = serializers.UUIDField(help_text="UUID of the dataset to process")
    type = serializers.CharField(max_length=50, help_text="Type of AI job (e.g. DETECTION)")

class AIProcessingJobSimpleSerializer(serializers.ModelSerializer):
    status = serializers.CharField(source='status.name', read_only=True)

    class Meta:
        model = AIProcessingJob
        fields = ['id', 'type', 'status', 'created_at']

# --------------------------------------------------------
# 2. AI Callback Serializers (EXISTING - Restored)
# --------------------------------------------------------

class AIResultFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIResultFile
        fields = ['file_name', 's3_key', 'file_type']

class AICallbackInputSerializer(serializers.Serializer):
    job_id = serializers.UUIDField()
    status = serializers.SlugRelatedField(
        queryset=UploadStatus.objects.all(),
        slug_field='name'
    )
    files = AIResultFileSerializer(many=True, required=False)
    error_message = serializers.CharField(required=False, allow_null=True)

    def validate_status(self, value):
        return value

class AICallbackResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    job_id = serializers.UUIDField()

# --------------------------------------------------------
# 3. Dataset & Image Serializers
# --------------------------------------------------------

class DatasetSerializer(serializers.ModelSerializer):
    ai_jobs = AIProcessingJobSimpleSerializer(many=True, read_only=True)

    class Meta:
        model = Dataset
        fields = ['id', 'name', 'created_at', 'ai_jobs']

class ImageSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    dataset_id = serializers.UUIDField(read_only=True)
    dataset_name = serializers.CharField(read_only=True)
    batch_id = serializers.UUIDField(read_only=True)
    file_name = serializers.CharField(read_only=True)
    file_type = serializers.CharField(read_only=True)
    status = serializers.CharField(source='upload_status', read_only=True)
    s3_key = serializers.CharField(read_only=True)
    file_size = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    width = serializers.IntegerField(read_only=True)
    height = serializers.IntegerField(read_only=True)

class DatasetStatsSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    total_files = serializers.IntegerField()
    total_size = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()
    status = serializers.CharField(default='Unknown')
    error_message = serializers.CharField(allow_null=True, default=None)

class UploadStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadStatus
        fields = ['id', 'name', 'label']

# --------------------------------------------------------
# 4. Upload & Presigned URL Serializers
# --------------------------------------------------------

class GeneratePresignedUrlRequestSerializer(serializers.Serializer):
    dataset_name = serializers.CharField(max_length=255, required=False)
    dataset_id = serializers.UUIDField(required=False)
    batch_id = serializers.UUIDField()
    file_name = serializers.CharField(max_length=255)
    file_type = serializers.ChoiceField(choices=[('IMAGE', 'Image'), ('ARCHIVE', 'Archive (Zip)')])
    content_type = serializers.CharField(max_length=100)
    file_size = serializers.IntegerField(min_value=1)
    retry_upload_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, data):
        if not data.get('dataset_name') and not data.get('dataset_id') and not data.get('retry_upload_id'):
            raise serializers.ValidationError("Either 'dataset_name' or 'dataset_id' must be provided.")
        return data

class PresignedUrlResponseSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()
    dataset_id = serializers.UUIDField()
    url = serializers.URLField()
    fields = serializers.DictField()
    s3_key = serializers.CharField()
    expires_in = serializers.IntegerField()

class ConfirmUploadSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField(required=True)
    s3_key = serializers.CharField(required=True)
    checksum = serializers.CharField(required=False, allow_blank=True)
    file_size = serializers.IntegerField(required=False, allow_null=True)

# --------------------------------------------------------
# 5. Multipart Upload Serializers
# --------------------------------------------------------

class InitMultipartRequestSerializer(serializers.Serializer):
    dataset_name = serializers.CharField(required=False, allow_blank=True)
    dataset_id = serializers.UUIDField(required=False)
    batch_id = serializers.UUIDField(required=True)
    file_name = serializers.CharField()
    file_type = serializers.ChoiceField(choices=['ARCHIVE'], default='ARCHIVE')
    content_type = serializers.CharField()
    file_size = serializers.IntegerField()

    def validate(self, data):
        if not data.get('dataset_name') and not data.get('dataset_id'):
            raise serializers.ValidationError("Either 'dataset_name' or 'dataset_id' must be provided.")
        return data

class InitMultipartResponseSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()
    s3_upload_id = serializers.CharField()
    s3_key = serializers.CharField()

class SignPartRequestSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()
    part_number = serializers.IntegerField(min_value=1, max_value=10000)

class SignPartResponseSerializer(serializers.Serializer):
    url = serializers.URLField()

class PartItemSerializer(serializers.Serializer):
    PartNumber = serializers.IntegerField()
    ETag = serializers.CharField()

class CompleteMultipartRequestSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()
    parts = serializers.ListField(child=PartItemSerializer())

class RetryMultipartUploadRequestSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()


class UploadFromUrlRequestSerializer(serializers.Serializer):
    dataset_name = serializers.CharField(
        required=True,
        max_length=255,
        help_text="Name of the dataset (Backend will create it or find existing one)."
    )
    file_url = serializers.URLField(
        required=True,
        help_text="The direct (presigned) URL to the file."
    )
    file_name = serializers.CharField(required=False, max_length=255)
    dataset_id = serializers.CharField(required=False, allow_null=True)
    batch_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_file_url(self, value):

        if not value.startswith('https://'):
            raise serializers.ValidationError("URL must be secure (HTTPS).")

        parsed = urlparse(value)
        domain = parsed.netloc.lower()
        query_params = parsed.query

        if 'Signature' not in query_params and 'X-Amz-Signature' not in query_params:
            raise serializers.ValidationError(
                "The provided URL does not appear to be a valid Presigned URL (missing Signature)."
            )

        allowed_domains = [
            'amazonaws.com',
            'digitaloceanspaces.com',
            'storage.googleapis.com',
            'minio'
        ]
        if not any(domain.endswith(d) for d in allowed_domains):
            raise serializers.ValidationError(f"Domain not allowed. Allowed: {allowed_domains}")

        try:
            with requests.get(value, stream=True, allow_redirects=True, timeout=10) as response:
                if response.status_code == 403:
                    raise serializers.ValidationError("Access Denied to file URL (Expired or Invalid).")
                elif response.status_code >= 400:
                    raise serializers.ValidationError(f"File URL is not accessible. Status: {response.status_code}")

                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > 10 * 1024 * 1024 * 1024:  # 10GB Limit
                    raise serializers.ValidationError("File is too large (Max 10GB).")
        except requests.RequestException:
            raise serializers.ValidationError("Could not connect to the file URL.")

        return value

class UploadFromUrlResponseSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()
    status = serializers.CharField()
    message = serializers.CharField()
