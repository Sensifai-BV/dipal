from celery import shared_task
from ..infrastructure.repositories import UploadRepository
from ..domain.services import S3Service
from ..domain.constants import UploadStatusName
from apps.uploads.Tasks.tasks import process_archive_task
from apps.uploads.domain.ainotification import DjangoChannelsNotificationService
from config.logging_config import get_logger

logger = get_logger(__name__)


@shared_task
def download_and_process_url_task(upload_id: str, file_url: str, s3_key: str):
    """Download file from presigned URL and queue archive processing."""
    repo = UploadRepository()
    s3_service = S3Service()
    notifier = DjangoChannelsNotificationService()

    upload_entity = repo.get_by_id(upload_id)
    dataset_id = str(upload_entity.dataset_id) if upload_entity else "unknown"

    logger.info(f"[URL_TASK] Starting download: upload_id={upload_id}, dataset_id={dataset_id}")

    try:
        notifier.notify_frontend(dataset_id, 'DOWNLOAD_STARTED', {
            "upload_id": upload_id,
            "message": "Starting S3 import..."
        })

        repo.update_status(upload_id, UploadStatusName.DOWNLOADING)

        s3_service.copy_from_presigned_url(
            source_url=file_url,
            destination_key=s3_key,
        )

        logger.info(f"[URL_TASK] Download complete for upload_id={upload_id}, fetching file size")

        try:
            head = s3_service.s3_client.head_object(Bucket=s3_service.bucket_name, Key=s3_key)
            file_size = head.get('ContentLength', 0)
            repo.update_status(upload_id, UploadStatusName.PENDING, file_size=file_size)
            logger.info(f"[URL_TASK] File size: {file_size} bytes for upload_id={upload_id}")
        except Exception as e:
            logger.warning(f"[URL_TASK] Could not fetch file size for upload_id={upload_id}: {e}")

        repo.update_status(upload_id, UploadStatusName.PROCESSING)

        notifier.notify_frontend(dataset_id, 'DOWNLOAD_COMPLETED', {
            "upload_id": upload_id,
            "message": "Import finished. Queuing for extraction..."
        })

        logger.info(f"[URL_TASK] Queuing archive processing for upload_id={upload_id}")
        process_archive_task.delay(upload_id=upload_id, s3_key=s3_key)

    except Exception as e:
        logger.error(f"[URL_TASK] Failed to import from URL: upload_id={upload_id}, error={e}", exc_info=True)

        error_msg_raw = str(e)
        if "download from Source" in error_msg_raw or "Failed to download" in error_msg_raw:
            user_error = "Failed to download the file from the provided URL. The link may have expired or is inaccessible."
        elif "upload to Internal" in error_msg_raw:
            user_error = "Failed to store the downloaded file. Please try again later."
        else:
            user_error = f"Import failed: {error_msg_raw}"

        repo.update_status(upload_id, UploadStatusName.FAILED, error_message=user_error)

        notifier.notify_frontend(dataset_id, 'DOWNLOAD_FAILED', {
            "upload_id": upload_id,
            "error": str(e),
            "message": "Failed to import file from S3"
        })
