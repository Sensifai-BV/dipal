import uuid
import magic
import mimetypes
import os
from ..domain.services import S3Service
from ..infrastructure.repositories import UploadRepository
from ..domain.entities import UploadEntity
from ..domain.constants import UploadStatusName
from apps.uploads.Tasks.tasks import process_archive_task
from config.logging_config import get_logger

logger = get_logger(__name__)


class InitiateMultipartUploadUseCase:
    def __init__(self):
        self.repo = UploadRepository()
        self.s3_service = S3Service()
        from ..infrastructure.models import Image
        self.image_model = Image

    def execute(self, user_id, organization_id, dataset_name, file_name, file_type, content_type, file_size, batch_id,
                dataset_id=None):
        
        logger.info(
            f"[USE-CASE:INIT] Starting multipart upload initialization - "
            f"file: {file_name}, size: {file_size}, type: {file_type}, user: {user_id}"
        )

        file_ext = os.path.splitext(file_name)[1].lower()
        logger.debug(f"[USE-CASE:INIT] File extension detected: {file_ext}")


        archive_extensions = {
            '.zip': 'application/zip',
            '.rar': 'application/vnd.rar',
            '.tar': 'application/x-tar',
            '.gz': 'application/gzip',
            '.tgz': 'application/x-gzip',
            '.7z': 'application/x-7z-compressed'
        }


        image_extensions = [
            '.jpg', '.jpeg', '.png', '.tiff', '.tif',
            '.webp', '.bmp', '.gif'
        ]


        if file_ext in archive_extensions:
            file_type = 'ARCHIVE'
            if not content_type or content_type == 'application/octet-stream':
                content_type = archive_extensions[file_ext]
            logger.info(f"[USE-CASE:INIT] Detected ARCHIVE type - content_type set to: {content_type}")

        elif file_ext in image_extensions:
            file_type = 'IMAGE'
            logger.info(f"[USE-CASE:INIT] Detected IMAGE type")

            if content_type == 'application/octet-stream' or not content_type:
                guessed_type, _ = mimetypes.guess_type(file_name)
                if guessed_type:
                    content_type = guessed_type
                logger.debug(f"[USE-CASE:INIT] Guessed content_type: {content_type}")

        else:
            logger.warning(f"[USE-CASE:INIT] Unknown file extension: {file_ext}, using provided type: {file_type}")
            pass

        if dataset_id:
            current_dataset_id = dataset_id
            logger.debug(f"[USE-CASE:INIT] Using existing dataset_id: {current_dataset_id}")
        else:
            logger.info(f"[USE-CASE:INIT] Creating/fetching dataset: {dataset_name}")
            dataset = self.repo.get_or_create_dataset(name=dataset_name, org_id=organization_id)
            current_dataset_id = dataset.id
            logger.info(f"[USE-CASE:INIT] Dataset resolved - dataset_id: {current_dataset_id}")

        logger.debug(f"[USE-CASE:INIT] Generating S3 key...")
        s3_key = self.s3_service.generate_s3_key(
            organization_id=organization_id,
            user_id=user_id,
            dataset_id=str(current_dataset_id),
            batch_id=str(batch_id),
            file_name=file_name
        )
        logger.info(f"[USE-CASE:INIT] S3 key generated: {s3_key}")

        logger.info(f"[USE-CASE:INIT] Calling S3Service.create_multipart_upload...")
        try:
            s3_upload_id = self.s3_service.create_multipart_upload(s3_key, content_type)
            logger.info(f"[USE-CASE:INIT] ✅ S3 multipart upload created - UploadId: {s3_upload_id}")
        except Exception as e:
            logger.error(f"[USE-CASE:INIT] ❌ Failed to create S3 multipart upload: {str(e)}", exc_info=True)
            raise

        new_upload = UploadEntity(
            id=None,
            user_id=user_id,
            organization_id=organization_id,
            dataset_id=current_dataset_id,
            dataset_name=dataset_name,
            batch_id=batch_id,
            file_name=file_name,
            file_path=s3_key,
            file_size=file_size,
            content_type=content_type,
            upload_status=UploadStatusName.PENDING,
            s3_key=s3_key,
            file_type=file_type,
            status=UploadStatusName.PENDING,
            parent_archive_id=None
        )
        
        logger.debug(f"[USE-CASE:INIT] Creating upload entity in database...")
        created_entity = self.repo.create(new_upload)
        logger.info(f"[USE-CASE:INIT] Upload entity created - upload_id: {created_entity.id}")

        logger.debug(f"[USE-CASE:INIT] Setting s3_upload_id in database...")
        self.repo.set_multipart_id(created_entity.id, s3_upload_id)
        logger.debug(f"[USE-CASE:INIT] s3_upload_id set successfully")

        created_entity.s3_upload_id = s3_upload_id
        
        logger.info(
            f"[USE-CASE:INIT] ✅ COMPLETE - upload_id: {created_entity.id}, "
            f"s3_upload_id: {s3_upload_id}, dataset_id: {current_dataset_id}"
        )
        return created_entity


class SignMultipartPartUseCase:
    def __init__(self):
        self.repo = UploadRepository()
        self.s3_service = S3Service()
        from ..infrastructure.models import Image
        self.image_model = Image

    def execute(self, upload_db_id, part_number):
        logger.info(f"[USE-CASE:SIGN] Generating presigned URL - upload_id: {upload_db_id}, part: {part_number}")
        
        try:
            image = self.image_model.objects.get(id=upload_db_id)
            logger.debug(
                f"[USE-CASE:SIGN] Upload found - file: {image.file_name}, "
                f"s3_key: {image.s3_key}, s3_upload_id: {image.s3_upload_id[:10] if image.s3_upload_id else 'None'}..."
            )
        except self.image_model.DoesNotExist:
            logger.error(f"[USE-CASE:SIGN] ❌ Upload not found: {upload_db_id}")
            raise ValueError("Upload not found")

        if not image.s3_upload_id:
            logger.error(
                f"[USE-CASE:SIGN] ❌ Upload {upload_db_id} has no s3_upload_id - "
                f"Not a valid multipart upload session"
            )
            raise ValueError("This is not a multipart upload session.")

        logger.debug(f"[USE-CASE:SIGN] Calling S3Service.generate_presigned_url_part...")
        try:
            url = self.s3_service.generate_presigned_url_part(
                key=image.s3_key,
                upload_id=image.s3_upload_id,
                part_number=part_number
            )
            logger.info(
                f"[USE-CASE:SIGN] ✅ Presigned URL generated - upload_id: {upload_db_id}, "
                f"part: {part_number}, URL length: {len(url)}"
            )
            logger.debug(f"[USE-CASE:SIGN] URL starts with: {url[:80]}...")
            return url
        except Exception as e:
            logger.error(
                f"[USE-CASE:SIGN] ❌ Failed to generate presigned URL - "
                f"upload_id: {upload_db_id}, part: {part_number}, error: {str(e)}",
                exc_info=True
            )
            raise


class CompleteMultipartUploadUseCase:
    def __init__(self):
        self.repo = UploadRepository()
        self.s3_service = S3Service()
        from ..infrastructure.models import Image
        self.image_model = Image

    def execute(self, upload_db_id, parts):
        """
        parts format: [{'PartNumber': 1, 'ETag': '...'}, ...]
        """
        logger.info(
            f"[USE-CASE:COMPLETE] Starting completion - upload_id: {upload_db_id}, "
            f"parts_count: {len(parts)}"
        )
        logger.debug(f"[USE-CASE:COMPLETE] Parts: {[p['PartNumber'] for p in parts]}")

        try:
            image = self.image_model.objects.get(id=upload_db_id)
            logger.debug(
                f"[USE-CASE:COMPLETE] Upload found - file: {image.file_name}, "
                f"type: {image.file_type}, s3_key: {image.s3_key}"
            )
        except self.image_model.DoesNotExist:
            logger.error(f"[USE-CASE:COMPLETE] ❌ Upload not found: {upload_db_id}")
            raise ValueError("Upload not found")

        logger.info(
            f"[USE-CASE:COMPLETE] Calling S3Service.complete_multipart_upload - "
            f"s3_upload_id: {image.s3_upload_id[:10]}..., parts: {len(parts)}"
        )
        try:
            self.s3_service.complete_multipart_upload(
                key=image.s3_key,
                upload_id=image.s3_upload_id,
                parts=parts
            )
            logger.info(f"[USE-CASE:COMPLETE] ✅ S3 multipart upload completed successfully")
        except Exception as e:
            logger.error(
                f"[USE-CASE:COMPLETE] ❌ S3 completion failed - "
                f"upload_id: {upload_db_id}, error: {str(e)}",
                exc_info=True
            )
            raise

        upload_entity = self.repo.get_by_id(upload_db_id)
        logger.debug(f"[USE-CASE:COMPLETE] Upload entity fetched - type: {upload_entity.file_type}")

        if upload_entity.file_type == 'ARCHIVE':
            logger.info(f"[USE-CASE:COMPLETE] File is ARCHIVE - starting processing pipeline")
            self.repo.update_status(upload_db_id, UploadStatusName.PROCESSING)
            logger.debug(f"[USE-CASE:COMPLETE] Status updated to PROCESSING")
            
            try:
                logger.debug(f"[USE-CASE:COMPLETE] Reading file header for MIME validation...")
                file_head_bytes = self.s3_service.read_object_head(upload_entity.s3_key, n_bytes=2048)
                mime_type = magic.from_buffer(file_head_bytes, mime=True)
                logger.info(f"[USE-CASE:COMPLETE] Detected MIME type: {mime_type}")

                allowed_archive_types = ['zip', 'rar', 'tar', 'gzip', '7z']
                is_valid_archive = any(t in mime_type for t in allowed_archive_types)


                if not is_valid_archive and mime_type == 'application/octet-stream':
                    file_ext = os.path.splitext(upload_entity.file_name)[1].lower()
                    valid_extensions = ['.zip', '.rar', '.tar', '.gz', '.tgz', '.7z']

                    if file_ext in valid_extensions:
                        is_valid_archive = True
                        logger.info(
                            f"[USE-CASE:COMPLETE] MIME is octet-stream but extension {file_ext} "
                            f"is valid - accepting as archive"
                        )

                if not is_valid_archive:
                    logger.error(
                        f"[USE-CASE:COMPLETE] ❌ Invalid archive MIME type: {mime_type} "
                        f"for file: {upload_entity.file_name}"
                    )
                    self.repo.update_status(upload_db_id, UploadStatusName.FAILED)
                    raise ValueError(f"File is flagged as Archive but has invalid mime: {mime_type}")

                logger.info(
                    f"[USE-CASE:COMPLETE] Archive validation passed - triggering Celery task "
                    f"process_archive_task"
                )
                process_archive_task.delay(upload_id=str(upload_entity.id), s3_key=upload_entity.s3_key)
                logger.info(
                    f"[USE-CASE:COMPLETE] ✅ Celery task dispatched - upload_id: {upload_entity.id}, "
                    f"task: process_archive_task"
                )

            except Exception as e:
                logger.error(
                    f"[USE-CASE:COMPLETE] ❌ Archive processing failed - "
                    f"upload_id: {upload_db_id}, error: {str(e)}",
                    exc_info=True
                )
                self.repo.update_status(upload_db_id, UploadStatusName.FAILED)
                raise RuntimeError(f"Failed to initiate archive processing: {str(e)}")

        else:
            logger.info(f"[USE-CASE:COMPLETE] File is not ARCHIVE - setting status to COMPLETED")
            self.repo.update_status(upload_db_id, UploadStatusName.COMPLETED)
            logger.debug(f"[USE-CASE:COMPLETE] Status updated to COMPLETED")

        final_entity = self.repo.get_by_id(upload_db_id)
        logger.info(
            f"[USE-CASE:COMPLETE] ✅ COMPLETE - upload_id: {upload_db_id}, "
            f"file: {final_entity.file_name}, final_status: {final_entity.status}"
        )
        return final_entity


# --------------------------------------------------
# ---------------Retry Uploads----------------------
# --------------------------------------------------
class AbortAndRetryMultipartUploadUseCase:
    def __init__(self):
        self.repo = UploadRepository()
        self.s3_service = S3Service()

    def execute(self, upload_db_id: uuid.UUID, user_id: int):

        existing_upload = self.repo.get_by_id(upload_db_id)
        if not existing_upload:
            raise ValueError(f"Upload with ID {upload_db_id} not found.")

        if existing_upload.user_id != user_id:
            raise PermissionError("You do not have permission to retry this upload.")

        if existing_upload.s3_upload_id:
            try:
                self.s3_service.abort_multipart_upload(
                    key=existing_upload.s3_key,
                    upload_id=existing_upload.s3_upload_id
                )
            except Exception:
                pass

        new_s3_upload_id = self.s3_service.create_multipart_upload(
            key=existing_upload.s3_key,
            content_type=existing_upload.content_type
        )

        self.repo.set_multipart_id(existing_upload.id, new_s3_upload_id)
        self.repo.update_status(existing_upload.id, UploadStatusName.PENDING)

        return {
            "upload_id": existing_upload.id,
            "s3_upload_id": new_s3_upload_id,
            "s3_key": existing_upload.s3_key,
            "message": "New multipart upload session initiated for retry."
        }


# --------------------------------------------------
class ProcessAICallbackUseCase:
    def __init__(self, ai_job_repo, notification_service):
        self.ai_job_repo = ai_job_repo
        self.notification_service = notification_service

    def execute(self, result_dto):
        job = self.ai_job_repo.get_by_id(result_dto.job_id)

        if not job:
            raise ValueError("AI Job not found")

        if result_dto.status == 'success':
            job.status = UploadStatusName.COMPLETED
            self.ai_job_repo.save_outputs(job, result_dto.outputs)
        else:
            job.status = UploadStatusName.FAILED

        self.ai_job_repo.update(job)

        self.notification_service.notify_frontend(
            dataset_id=job.dataset_id,
            message_type="AI_PROCESS_COMPLETED",
            payload={
                "job_id": job.id,
                "status": job.status,
                "result_files": [out.s3_key for out in result_dto.outputs]
            }
        )
