from celery import shared_task
from django.utils import timezone
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.infra.services.ai_client import AIGatewayClient
from apps.jobs.processing_stages import JobStatus, ProcessingStage
from apps.uploads.infrastructure.models import Dataset
import logging
import boto3
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task
def process_drone_imagery(job_db_id, starting_stage=None):
    """
    Celery task to submit processing job to AI Gateway
    
    Args:
        job_db_id: Job ID in database
        starting_stage: Optional stage to resume from (e.g., 'sfm', 'orthomosaic_generation')
    
    This task:
    1. Gets the job from database
    2. Generates presigned URL for dataset download
    3. Calls AI Gateway to start processing (optionally resuming from a specific stage)
    4. Updates job status with AI Gateway's job_id
    """
    try:
        job = ProcessingJob.objects.select_related('dataset').get(id=job_db_id)
        
        if job.status in (JobStatus.CANCELLED, JobStatus.COMPLETED, JobStatus.FAILED):
            logger.info(
                f"Job {job_db_id} is already {job.status} — skipping dispatch to AI Gateway"
            )
            return
        
        # Update status to processing
        job.status = JobStatus.PROCESSING
        job.stage = ProcessingStage.QUEUED
        job.progress = 0
        job.started_at = timezone.now()
        job.save()
        
        logger.info(f"Processing job {job.id} for dataset {job.dataset.name}")
        
        image_urls = generate_dataset_image_urls(job.dataset)
        
        if not image_urls:
            raise Exception(f"No images found for dataset {job.dataset.id}")
        
        logger.info(f"Generated {len(image_urls)} presigned URLs for dataset {job.dataset.id}")
        
        metadata_urls = generate_dataset_metadata_urls(job.dataset)
        logger.info(f"Generated {len(metadata_urls)} metadata presigned URLs for dataset {job.dataset.id}")
        
        parameters = {
            "resolution_gsd": job.resolution_gsd,
            "radiometric_calibration": job.radiometric_calibration,
            "analysis_mode": job.analysis_mode,
            "calibration": {
                "enabled": job.radiometric_calibration
            },
            "sfm": {
                "resolution_gsd": job.resolution_gsd
            },
            "orthomosaic": {
                "generate_cog": True,
                "resolution_gsd": job.resolution_gsd
            },
            "metadata_urls": metadata_urls,
        }
        
        # Call AI Gateway with list of image URLs
        ai_client = AIGatewayClient()
        ai_response = ai_client.start_processing_job(
            job_id=str(job.id),
            dataset_id=str(job.dataset.id),
            download_url=image_urls,  # Now a list of presigned URLs
            parameters=parameters,
            starting_stage=starting_stage  # Pass starting_stage for resume capability
        )
        
        # Store AI Gateway's job_id in metadata or a new field
        # For now, we can add a field or use notes/metadata
        job.stage = 'sfm'
        job.progress = 5
        job.save()
        
        logger.info(f"Job {job.id} submitted to AI Gateway. AI job_id: {ai_response.get('job_id')}")
        
    except ProcessingJob.DoesNotExist:
        logger.error(f"Job {job_db_id} not found.")
    except Exception as e:
        logger.error(f"Failed to process job {job_db_id}: {e}", exc_info=True)
        try:
            job = ProcessingJob.objects.get(id=job_db_id)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'error_message', 'completed_at'])
        except ProcessingJob.DoesNotExist:
            logger.error(f"Job {job_db_id} not found when updating failure status.")


def generate_dataset_image_urls(dataset: Dataset, expiration: int = 3600) -> list:
    """
    Generate presigned URLs for all images in a dataset
    
    Args:
        dataset: Dataset object
        expiration: URL expiration in seconds (default 1 hour)
        
    Returns:
        List of presigned URLs for dataset images
    """
    from apps.uploads.infrastructure.models import Image
    
    bucket = settings.AWS_S3_RAW_IMAGES_BUCKET  # Use RAW images bucket, not STORAGE bucket
    
    if not bucket:
        logger.error(
            f"AWS_S3_RAW_IMAGES_BUCKET is not set (got {bucket!r}). "
            f"Falling back to AWS_STORAGE_BUCKET_NAME={settings.AWS_STORAGE_BUCKET_NAME!r}"
        )
        bucket = settings.AWS_STORAGE_BUCKET_NAME
    
    if not bucket:
        logger.error("No S3 bucket configured. Cannot generate presigned URLs.")
        return []
    
    # Build client kwargs - only include credentials if explicitly set
    # When USE_AWS_ROLE=true, boto3 will automatically use ECS Task Role
    client_kwargs = {
        'region_name': settings.AWS_S3_REGION_NAME,
        'config': boto3.session.Config(signature_version='s3v4'),
    }
    
    # Only pass endpoint_url if explicitly set (passing None causes botocore errors)
    if settings.AWS_S3_ENDPOINT_URL:
        client_kwargs['endpoint_url'] = settings.AWS_S3_ENDPOINT_URL
    
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
        client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
    
    # Initialize S3 client
    s3_client = boto3.client('s3', **client_kwargs)
    
    logger.info(f"S3 client configured - bucket: {bucket}, region: {settings.AWS_S3_REGION_NAME}, endpoint: {settings.AWS_S3_ENDPOINT_URL}")
    
    # Get all IMAGE type files for this dataset
    images = Image.objects.filter(
        dataset_id=dataset.id,
        file_type='IMAGE'
    ).values_list('s3_key', 'file_name')
    
    if not images:
        logger.warning(f"No images found for dataset {dataset.id}")
        return []
    
    # Generate presigned URLs for each image
    presigned_urls = []
    for s3_key, file_name in images:
        if not s3_key:
            logger.warning(f"Skipping image with empty s3_key (file_name={file_name}) in dataset {dataset.id}")
            continue
        try:
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': s3_key},
                ExpiresIn=expiration
            )
            presigned_urls.append({
                'url': presigned_url,
                'filename': file_name
            })
        except Exception as e:
            logger.error(
                f"Failed to generate presigned URL for {s3_key}: {e} "
                f"(bucket={bucket!r}, region={settings.AWS_S3_REGION_NAME!r})",
                exc_info=True
            )
            continue
    
    logger.info(f"Generated {len(presigned_urls)} presigned URLs for dataset {dataset.id}")
    return presigned_urls


def generate_dataset_metadata_urls(dataset: Dataset, expiration: int = 3600) -> list:
    """
    Generate presigned URLs for all metadata files in a dataset.

    Args:
        dataset: Dataset object
        expiration: URL expiration in seconds (default 1 hour)

    Returns:
        List of dicts with presigned URL and filename for each metadata file
    """
    from apps.uploads.infrastructure.models import Image

    bucket = settings.AWS_S3_RAW_IMAGES_BUCKET
    if not bucket:
        bucket = settings.AWS_STORAGE_BUCKET_NAME
    if not bucket:
        return []

    client_kwargs = {
        'region_name': settings.AWS_S3_REGION_NAME,
        'config': boto3.session.Config(signature_version='s3v4'),
    }
    if settings.AWS_S3_ENDPOINT_URL:
        client_kwargs['endpoint_url'] = settings.AWS_S3_ENDPOINT_URL
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
        client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY

    s3_client = boto3.client('s3', **client_kwargs)

    metadata_files = Image.objects.filter(
        dataset_id=dataset.id,
        file_type='METADATA'
    ).values_list('s3_key', 'file_name')

    if not metadata_files:
        logger.info(f"No metadata files found for dataset {dataset.id}")
        return []

    presigned_urls = []
    for s3_key, file_name in metadata_files:
        if not s3_key:
            continue
        try:
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': s3_key},
                ExpiresIn=expiration
            )
            presigned_urls.append({
                'url': presigned_url,
                'filename': file_name,
            })
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for metadata {s3_key}: {e}")
            continue

    logger.info(f"Generated {len(presigned_urls)} metadata presigned URLs for dataset {dataset.id}")
    return presigned_urls
