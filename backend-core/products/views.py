"""Views for Product Upload API (for AI to upload processing results)"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from django.conf import settings
import uuid

from products.models import Product
from products.serializers import (
    ProductUploadInitSerializer,
    ProductUploadInitResponseSerializer,
    ProductChunkUploadSerializer,
    ProductChunkUploadResponseSerializer,
    ProductUploadCompleteSerializer,
    ProductUploadCompleteResponseSerializer,
    ProductListSerializer,
)
# geo_utils is available but footprint extraction not enabled yet
# from products.geo_utils import (
#     extract_footprint_from_s3,
#     GEOSPATIAL_PRODUCT_TYPES,
# )
from apps.uploads.domain.services import S3Service
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.uploads.infrastructure.models import Dataset

from utils.permissions import IsAIService
from config.logging_config import get_logger

logger = get_logger(__name__)


# Temporary storage for multipart upload metadata
# In production, use Redis or database
UPLOAD_SESSIONS = {}


class ProductUploadInitView(APIView):
    """
    Initialize product upload for AI processing results.
    AI calls this to get multipart upload credentials.
    """
    authentication_classes = []
    permission_classes = [IsAIService]
    
    @extend_schema(
        summary="Initialize Product Upload",
        description="AI calls this to start uploading a processing result",
        request=ProductUploadInitSerializer,
        responses={200: ProductUploadInitResponseSerializer},
        tags=['AI Product Upload']
    )
    def post(self, request):
        logger.info(
            f"[PRODUCT_INIT] Received upload init: "
            f"data={dict(request.data)}"
        )
        serializer = ProductUploadInitSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(
                f"[PRODUCT_INIT] Validation failed: errors={serializer.errors}, "
                f"data={dict(request.data)}"
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        
        try:
            # Get job and dataset
            job = ProcessingJob.objects.get(id=data['job_id'])
            dataset = Dataset.objects.get(id=data['dataset_id'])
            
            # Use get_or_create to prevent duplicates when job is rerun
            # If product already exists for this job+type combination, reuse it
            product, created = Product.objects.get_or_create(
                dataset=dataset,
                job=job,
                type=data['product_type'],
                defaults={
                    'uri': '',  # Will be set on completion
                    'resolution_cm': data.get('resolution_cm'),
                    'bands': data.get('bands'),
                    'stats': data.get('stats', {}),
                }
            )
            
            if not created:
                # Product already exists - update it for rerun
                logger.info(
                    f"Product already exists for job {job.id}, type {data['product_type']}. "
                    f"Reusing product_id={product.id} (likely a rerun)"
                )
                # Update mutable fields
                product.resolution_cm = data.get('resolution_cm') or product.resolution_cm
                product.bands = data.get('bands') or product.bands
                product.stats = data.get('stats', {}) or product.stats
                product.uri = ''  # Reset URI for new upload
                product.save()
            else:
                logger.info(f"Created new product: product_id={product.id}, type={data['product_type']}")
            
            # Generate S3 key for product
            # Structure: products/{dataset_id}/{job_id}/{product_type}/{filename}
            s3_key = f"products/{dataset.id}/{job.id}/{data['product_type']}/{data['file_name']}"
            
            # Initialize S3 multipart upload
            s3_service = S3Service()
            s3_upload_id = s3_service.create_multipart_upload(
                key=s3_key,
                content_type=data.get('content_type', 'application/octet-stream')
            )
            
            # Store upload session info (in production, use Redis/database)
            upload_id = str(uuid.uuid4())
            UPLOAD_SESSIONS[upload_id] = {
                'product_id': str(product.id),
                's3_upload_id': s3_upload_id,
                's3_key': s3_key,
                'dataset_id': str(dataset.id),
                'job_id': str(job.id),
            }
            
            logger.info(
                f"Product upload initialized: product_id={product.id}, "
                f"type={data['product_type']}, s3_key={s3_key}"
            )
            
            return Response({
                'product_id': str(product.id),
                'upload_id': upload_id,
                's3_upload_id': s3_upload_id,
                's3_key': s3_key,
            }, status=status.HTTP_200_OK)
            
        except ProcessingJob.DoesNotExist:
            return Response(
                {"error": "Job not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Dataset.DoesNotExist:
            return Response(
                {"error": "Dataset not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error initializing product upload: {e}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductChunkUploadView(APIView):
    """
    Get presigned URL for uploading a chunk of product data.
    """
    authentication_classes = []
    permission_classes = [IsAIService]
    
    @extend_schema(
        summary="Get Presigned URL for Chunk Upload",
        description="AI calls this for each chunk to get upload URL",
        request=ProductChunkUploadSerializer,
        responses={200: ProductChunkUploadResponseSerializer},
        tags=['AI Product Upload']
    )
    def post(self, request):
        serializer = ProductChunkUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            # Verify upload session exists
            upload_id = str(data['upload_id'])
            if upload_id not in UPLOAD_SESSIONS:
                return Response(
                    {"error": "Upload session not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Generate presigned URL for this part
            s3_service = S3Service()
            presigned_url = s3_service.generate_presigned_url_part(
                key=data['s3_key'],
                upload_id=data['s3_upload_id'],
                part_number=data['part_number'],
                expires_in=3600
            )
            
            return Response({
                'url': presigned_url,
                'part_number': data['part_number'],
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductUploadCompleteView(APIView):
    """
    Complete product upload after all chunks uploaded.
    """
    authentication_classes = []
    permission_classes = [IsAIService]
    
    @extend_schema(
        summary="Complete Product Upload",
        description="AI calls this after all chunks uploaded",
        request=ProductUploadCompleteSerializer,
        responses={200: ProductUploadCompleteResponseSerializer},
        tags=['AI Product Upload']
    )
    def post(self, request):
        serializer = ProductUploadCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            # Get upload session
            upload_id = str(data['upload_id'])
            if upload_id not in UPLOAD_SESSIONS:
                return Response(
                    {"error": "Upload session not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            session = UPLOAD_SESSIONS[upload_id]
            
            # Complete S3 multipart upload
            s3_service = S3Service()
            s3_service.complete_multipart_upload(
                key=data['s3_key'],
                upload_id=data['s3_upload_id'],
                parts=data['parts']
            )
            
            # Update product with S3 URI
            product_id = session['product_id']
            product = Product.objects.get(id=product_id)
            product.uri = data['s3_key']
            
            # TODO: Extract footprint for geospatial products (orthomosaic, dsm, dem, hillshade)
            # Footprint extraction is implemented in geo_utils.py but not enabled yet
            # product.footprint = extract_footprint_from_s3(s3_key, bucket)
            
            product.save()
            
            # Clean up session
            del UPLOAD_SESSIONS[upload_id]
            
            logger.info(
                f"Product upload completed: product_id={product_id}, "
                f"type={product.type}, s3_key={data['s3_key']}"
            )
            
            return Response({
                'product_id': str(product.id),
                'dataset_id': str(product.dataset_id),
                's3_uri': f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{data['s3_key']}",
                'status': 'completed',
            }, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error completing product upload: {e}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductUploadAbortView(APIView):
    """
    Abort an in-progress multipart upload.
    
    Call this if chunk upload fails or needs to be cancelled.
    This cleans up:
    - S3 multipart upload (prevents orphaned parts)
    - Upload session
    - Partially created Product record
    """
    authentication_classes = []
    permission_classes = [IsAIService]
    
    @extend_schema(
        summary="Abort Product Upload",
        description="Abort an in-progress multipart upload and clean up resources",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "upload_id": {"type": "string", "description": "Upload session ID"},
                    "s3_upload_id": {"type": "string", "description": "S3 multipart upload ID"},
                    "s3_key": {"type": "string", "description": "S3 object key"},
                },
                "required": ["upload_id", "s3_upload_id", "s3_key"]
            }
        },
        responses={200: {"type": "object", "properties": {"status": {"type": "string"}}}},
        tags=['AI Product Upload']
    )
    def post(self, request):
        upload_id = request.data.get('upload_id')
        s3_upload_id = request.data.get('s3_upload_id')
        s3_key = request.data.get('s3_key')
        
        if not all([upload_id, s3_upload_id, s3_key]):
            return Response(
                {"error": "upload_id, s3_upload_id, and s3_key are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Abort S3 multipart upload
            s3_service = S3Service()
            try:
                s3_service.abort_multipart_upload(
                    key=s3_key,
                    upload_id=s3_upload_id,
                )
                logger.info(f"Aborted S3 multipart upload: {s3_key}")
            except Exception as e:
                logger.warning(f"Failed to abort S3 multipart upload: {e}")
            
            # Clean up upload session
            upload_id_str = str(upload_id)
            if upload_id_str in UPLOAD_SESSIONS:
                session = UPLOAD_SESSIONS[upload_id_str]
                
                # Delete partially created product
                try:
                    product_id = session.get('product_id')
                    if product_id:
                        Product.objects.filter(id=product_id).delete()
                        logger.info(f"Deleted partial product: {product_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete partial product: {e}")
                
                del UPLOAD_SESSIONS[upload_id_str]
                logger.info(f"Cleaned up upload session: {upload_id}")
            
            return Response({
                'status': 'aborted',
                'message': 'Upload aborted and resources cleaned up',
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error aborting upload: {e}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
