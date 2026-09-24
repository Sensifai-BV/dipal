"""Serializers for Products API"""
from rest_framework import serializers
from products.models import Product


class ProductUploadInitSerializer(serializers.Serializer):
    """Initialize product upload (AI requesting presigned URL)"""
    job_id = serializers.UUIDField(required=True)
    dataset_id = serializers.UUIDField(required=True)
    product_type = serializers.ChoiceField(
        choices=Product.PRODUCT_TYPE_CHOICES,
        required=True
    )
    file_name = serializers.CharField(max_length=255, required=True)
    file_size = serializers.IntegerField(required=True, min_value=1)
    content_type = serializers.CharField(max_length=100, default='application/octet-stream')
    resolution_cm = serializers.FloatField(required=False, allow_null=True)
    bands = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_null=True
    )
    stats = serializers.JSONField(required=False, allow_null=True)


class ProductUploadInitResponseSerializer(serializers.Serializer):
    """Response for product upload initialization"""
    product_id = serializers.UUIDField()
    upload_id = serializers.UUIDField()
    s3_upload_id = serializers.CharField()
    s3_key = serializers.CharField()


class ProductChunkUploadSerializer(serializers.Serializer):
    """Request presigned URL for chunk upload"""
    upload_id = serializers.UUIDField(required=True)
    s3_upload_id = serializers.CharField(required=True)
    s3_key = serializers.CharField(required=True)
    part_number = serializers.IntegerField(required=True, min_value=1, max_value=10000)


class ProductChunkUploadResponseSerializer(serializers.Serializer):
    """Response with presigned URL for chunk upload"""
    url = serializers.URLField()
    part_number = serializers.IntegerField()


class ProductUploadCompleteSerializer(serializers.Serializer):
    """Complete product upload"""
    upload_id = serializers.UUIDField(required=True)
    s3_upload_id = serializers.CharField(required=True)
    s3_key = serializers.CharField(required=True)
    parts = serializers.ListField(
        child=serializers.DictField(),
        required=True
    )


class ProductUploadCompleteResponseSerializer(serializers.Serializer):
    """Response for completed upload"""
    product_id = serializers.UUIDField()
    dataset_id = serializers.UUIDField()
    s3_uri = serializers.CharField()
    status = serializers.CharField()


class ProductListSerializer(serializers.ModelSerializer):
    """List products with display names and categories"""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    category = serializers.CharField(source='get_category', read_only=True)
    dataset_name = serializers.CharField(source='dataset.name', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'dataset', 'dataset_name', 'job', 'type', 'type_display', 
            'category', 'uri', 'resolution_cm', 'bands', 'stats', 'created_at'
        ]
        read_only_fields = fields
