# : apps/uploads/Tasks/exporttask.py

import zipfile
import os
import tempfile
from django.core.cache import cache
from celery import shared_task
from apps.uploads.infrastructure.models import Image, Dataset
from apps.uploads.domain.services import S3Service
from apps.uploads.domain.ainotification import DjangoChannelsNotificationService
from apps.uploads.domain.constants import UploadStatusName


@shared_task
def create_dataset_archive_task(dataset_id, user_id, job_key):
    s3_service = S3Service()

    notifier = DjangoChannelsNotificationService()


    notifier.notify_frontend(
        dataset_id=dataset_id,
        message_type="EXPORT_STARTED",
        payload={"status": UploadStatusName.PROCESSING, "message": "Creating archive..."}
    )

    cache.set(job_key, {'status': UploadStatusName.PROCESSING}, timeout=3600)

    try:
        images = Image.objects.filter(dataset_id=dataset_id, status__name=UploadStatusName.COMPLETED)

        if not images.exists():
            error_msg = 'Dataset is empty or files not found'
            cache.set(job_key, {'status': UploadStatusName.FAILED, 'error': error_msg}, timeout=3600)


            notifier.notify_frontend(
                dataset_id=dataset_id,
                message_type="EXPORT_FAILED",
                payload={"error": error_msg}
            )
            return

        dataset_name = "dataset"
        try:
            dataset = Dataset.objects.get(id=dataset_id)
            dataset_name = dataset.name.replace(" ", "_")
        except Dataset.DoesNotExist:
            pass

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for img in images:
                    try:
                        file_content = s3_service.download_file(img.s3_key)
                        archive_name = img.file_name
                        zf.writestr(archive_name, file_content)
                    except Exception as e:
                        print(f"Error adding file {img.id} to archive: {e}")
                        continue

            temp_zip_path = temp_zip.name

        zip_s3_key = f"exports/users/{user_id}/{dataset_name}_{dataset_id}.zip"

        with open(temp_zip_path, 'rb') as f:
            s3_service.upload_bytes(zip_s3_key, f.read(), content_type='application/zip')

        os.remove(temp_zip_path)

        download_url = s3_service.generate_presigned_url(
            key=zip_s3_key,
            client_method='get_object'
        )

        cache.set(job_key, {
            'status': UploadStatusName.COMPLETED,
            'download_url': download_url
        }, timeout=3600)


        notifier.notify_frontend(
            dataset_id=dataset_id,
            message_type="EXPORT_COMPLETED",
            payload={
                "status": UploadStatusName.COMPLETED,
                "download_url": download_url,
                "file_name": f"{dataset_name}.zip"
            }
        )

    except Exception as e:
        error_msg = str(e)
        cache.set(job_key, {'status': UploadStatusName.FAILED, 'error': error_msg}, timeout=3600)


        notifier.notify_frontend(
            dataset_id=dataset_id,
            message_type="EXPORT_FAILED",
            payload={"error": error_msg}
        )

        if 'temp_zip_path' in locals() and os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
