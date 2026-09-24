import zipfile
import tarfile
import os
import mimetypes
import tempfile
import magic
from pathlib import Path
from django.core.cache import cache
from celery import shared_task
from apps.uploads.infrastructure.models import Image, Dataset
from apps.uploads.infrastructure.repositories import UploadRepository
from apps.uploads.domain.services import S3Service
from apps.uploads.domain.entities import UploadEntity
from apps.uploads.domain.constants import UploadStatusName
from smart_open import open as smart_open
from apps.uploads.domain.ainotification import DjangoChannelsNotificationService
from config.logging_config import get_logger

logger = get_logger(__name__)

try:
    import rarfile
except ImportError:
    rarfile = None


@shared_task
def process_archive_task(upload_id: str, s3_key: str):
    repo = UploadRepository()
    s3_service = S3Service()
    notifier = DjangoChannelsNotificationService()

    archive_entity = repo.get_by_id(upload_id)
    if not archive_entity:
        return "Archive record not found"

    dataset_id = str(archive_entity.dataset_id)
    extracted_count = 0
    metadata_count = 0

    from django.conf import settings as django_settings
    image_extensions = set(getattr(django_settings, 'DATASET_IMAGE_EXTENSIONS', [
        '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.webp', '.bmp', '.gif', '.dng',
    ]))
    metadata_extensions = set(getattr(django_settings, 'DATASET_METADATA_EXTENSIONS', [
        '.nav', '.obs', '.mrk', '.bin', '.pos', '.csv', '.txt', '.log',
        '.rtcm', '.ubx', '.rinex', '.json', '.xml',
    ]))
    all_allowed = image_extensions | metadata_extensions

    def _classify_file_type(ext):
        if ext in image_extensions:
            return 'IMAGE'
        if ext in metadata_extensions:
            return 'METADATA'
        return None

    def _guess_content_type(filename, ext, file_type):
        content_type, _ = mimetypes.guess_type(filename)
        if content_type:
            return content_type
        if file_type == 'METADATA':
            return 'application/octet-stream'
        content_type = f"image/{ext.lstrip('.')}"
        if ext == '.jpg':
            content_type = 'image/jpeg'
        return content_type

    def save_extracted_file(filename, file_data):
        nonlocal extracted_count, metadata_count

        if filename.startswith('__MACOSX') or filename.split('/')[-1].startswith('.'):
            return

        ext = Path(filename).suffix.lower()
        file_type = _classify_file_type(ext)
        if file_type is None:
            return

        if file_type == 'IMAGE':
            try:
                real_mime = magic.from_buffer(file_data[:2048], mime=True)
            except Exception:
                real_mime = ""

            valid_mimes = [
                'image/jpeg', 'image/png', 'image/tiff',
                'image/webp', 'image/bmp', 'image/gif',
                'image/x-adobe-dng',
            ]
            if real_mime and real_mime not in valid_mimes:
                return

        normalized_path = filename.replace('\\', '/')
        path_parts = [p for p in normalized_path.split('/') if p not in ['..', '.']]
        clean_filename = '/'.join(path_parts)
        if not clean_filename:
            return

        base_path = os.path.dirname(s3_key)
        subfolder = "extracted" if file_type == 'IMAGE' else "metadata"
        new_s3_key = f"{base_path}/{subfolder}/{upload_id}/{clean_filename}"

        content_type = _guess_content_type(clean_filename, ext, file_type)

        s3_service.upload_bytes(
            key=new_s3_key,
            file_content=file_data,
            content_type=content_type
        )

        new_entity = UploadEntity(
            id=None,
            user_id=archive_entity.user_id,
            organization_id=archive_entity.organization_id,
            dataset_id=archive_entity.dataset_id,
            dataset_name=archive_entity.dataset_name,
            batch_id=archive_entity.batch_id,
            file_name=clean_filename,
            file_path=new_s3_key,
            file_size=len(file_data),
            content_type=content_type,
            upload_status=UploadStatusName.COMPLETED,
            s3_key=new_s3_key,
            file_type=file_type,
            status=UploadStatusName.COMPLETED,
            parent_archive_id=archive_entity.id
        )
        repo.create(new_entity)
        if file_type == 'IMAGE':
            extracted_count += 1
        else:
            metadata_count += 1

    temp_file_path = None
    try:
        archive_ext = os.path.splitext(s3_key)[1].lower()
        logger.info(f"[ARCHIVE] Processing upload_id={upload_id}, s3_key={s3_key}, detected_ext='{archive_ext}'")

        with tempfile.NamedTemporaryFile(delete=False, suffix=archive_ext or '.zip') as temp_file:
            s3_service.s3_client.download_fileobj(s3_service.bucket_name, s3_key, temp_file)
            temp_file_path = temp_file.name

        file_size = os.path.getsize(temp_file_path)
        with open(temp_file_path, 'rb') as f:
            header_bytes = f.read(16)
            f.seek(-min(64, file_size), 2)
            tail_bytes = f.read()
        logger.info(
            f"[ARCHIVE] Downloaded from S3: size={file_size} bytes, "
            f"header(hex)={header_bytes.hex()}, tail(hex)={tail_bytes.hex()}, ext='{archive_ext}'"
        )

        # ZIP magic: 504b0304, RAR: 526172, TAR+GZ: 1f8b
        if not archive_ext or archive_ext not in ['.zip', '.tar', '.gz', '.tgz', '.rar']:
            if header_bytes[:4] == b'PK\x03\x04':
                archive_ext = '.zip'
                logger.info(f"[ARCHIVE] No valid ext, but ZIP magic detected — treating as .zip")
            elif header_bytes[:2] == b'\x1f\x8b':
                archive_ext = '.gz'
                logger.info(f"[ARCHIVE] No valid ext, but GZIP magic detected — treating as .gz")
            elif header_bytes[:3] == b'Rar':
                archive_ext = '.rar'
                logger.info(f"[ARCHIVE] No valid ext, but RAR magic detected — treating as .rar")
            else:
                logger.error(f"[ARCHIVE] Unknown format — header: {header_bytes[:16].hex()}")

        # --- Process ZIP ---
        if archive_ext == '.zip':
            try:
                with zipfile.ZipFile(temp_file_path, 'r') as zf:
                    for filename in zf.namelist():
                        if not filename.endswith('/'):
                            with zf.open(filename) as f:
                                save_extracted_file(filename, f.read())
            except zipfile.BadZipFile:
                raise ValueError("File is not a valid zip archive")

        # --- Process TAR/GZ ---
        elif archive_ext in ['.tar', '.gz', '.tgz', '.tar.gz']:
            try:
                with tarfile.open(name=temp_file_path, mode='r:*') as tf:
                    for member in tf.getmembers():
                        if member.isfile():
                            f = tf.extractfile(member)
                            if f:
                                save_extracted_file(member.name, f.read())
            except tarfile.ReadError:
                raise ValueError("File is not a valid tar archive")

        # --- Process RAR ---
        elif archive_ext == '.rar':
            if rarfile is None:
                raise Exception("RAR format not supported (rarfile library missing).")
            try:
                with rarfile.RarFile(temp_file_path) as rf:
                    for filename in rf.namelist():
                        if not filename.endswith('/'):
                            save_extracted_file(filename, rf.read(filename))
            except rarfile.Error:
                raise ValueError("File is not a valid rar archive")

        # --- Fallback (Treat as ZIP) ---
        else:
            try:
                with zipfile.ZipFile(temp_file_path, 'r') as zf:
                    for filename in zf.namelist():
                        if not filename.endswith('/'):
                            with zf.open(filename) as f:
                                save_extracted_file(filename, f.read())
            except zipfile.BadZipFile:
                raise Exception(f"Unsupported or corrupted archive format: {archive_ext}")

        # --- Validation ---
        if extracted_count == 0 and metadata_count == 0:
            error_msg = "No valid images or metadata files found in archive."
            repo.update_status(upload_id, UploadStatusName.FAILED)

            notifier.notify_frontend(dataset_id, "UPLOAD_FAILED", {
                "upload_id": upload_id,
                "status": UploadStatusName.FAILED,
                "error": error_msg
            })
            raise ValueError(error_msg)

        # --- Success ---
        repo.update_status(upload_id, UploadStatusName.COMPLETED)

        notifier.notify_frontend(
            dataset_id=dataset_id,
            message_type="UPLOAD_COMPLETED",
            payload={
                "upload_id": upload_id,
                "status": UploadStatusName.COMPLETED,
                "extracted_count": extracted_count,
                "metadata_count": metadata_count,
                "message": f"Extracted {extracted_count} images and {metadata_count} metadata files"
            }
        )

        return (
            f"Successfully extracted {extracted_count} images and "
            f"{metadata_count} metadata files from archive {upload_id}"
        )

    except Exception as e:
        print(f"Error extracting archive {upload_id}: {str(e)}")

        error_msg_raw = str(e)
        if "not a valid zip" in error_msg_raw.lower():
            user_error = "The uploaded file is corrupted or not a valid ZIP archive. Please verify the file and try again."
        elif "not a valid tar" in error_msg_raw.lower():
            user_error = "The uploaded file is corrupted or not a valid TAR archive. Please verify the file and try again."
        elif "not a valid rar" in error_msg_raw.lower():
            user_error = "The uploaded file is corrupted or not a valid RAR archive. Please verify the file and try again."
        elif "no valid images" in error_msg_raw.lower():
            user_error = "No valid images found in the archive. Ensure the ZIP contains supported image formats (TIFF, JPG, PNG)."
        elif "unsupported" in error_msg_raw.lower():
            user_error = f"Unsupported archive format. Please upload a ZIP, TAR.GZ, or RAR file."
        else:
            user_error = f"Failed to process archive: {error_msg_raw}"

        repo.update_status(upload_id, UploadStatusName.FAILED, error_message=user_error)


        try:
            ds_id = str(archive_entity.dataset_id) if archive_entity else "unknown"
            notifier.notify_frontend(
                dataset_id=ds_id,
                message_type="UPLOAD_FAILED",
                payload={
                    "upload_id": upload_id,
                    "status": UploadStatusName.FAILED,
                    "error": str(e)
                }
            )
        except Exception as notif_err:
            print(f"Failed to send failure notification: {notif_err}")

        return f"Failed: {str(e)}"

    finally:

        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass


@shared_task
def cleanup_stale_uploads_task():
    repo = UploadRepository()
    s3_service = S3Service()
    deleted_keys = repo.delete_old_pending_uploads(hours_limit=24)
    if not deleted_keys:
        return "No stale uploads found."
    count = 0
    for key in deleted_keys:
        if key:
            s3_service.delete_object(key)
            count += 1
    return f"Cleaned up {count} stale uploads."


@shared_task(bind=True, max_retries=3)
def create_dataset_archive_task(self, dataset_id, user_id, job_key):
    s3_service = S3Service()
    # [ ]
    notifier = DjangoChannelsNotificationService()

    cache.set(job_key, {'status': UploadStatusName.PROCESSING}, timeout=3600)


    notifier.notify_frontend(dataset_id, "EXPORT_STARTED", {"job_key": job_key})

    try:
        images = Image.objects.filter(dataset_id=dataset_id, status__name=UploadStatusName.COMPLETED)
        if not images.exists():
            raise ValueError("No completed files found for this dataset.")

        try:
            dataset = Dataset.objects.get(id=dataset_id)
            dataset_name = dataset.name.replace(" ", "_")
        except Dataset.DoesNotExist:
            dataset_name = "dataset"

        zip_filename = f"{dataset_name}_{dataset_id}.zip"
        zip_s3_key = f"exports/users/{user_id}/{zip_filename}"
        zip_s3_uri = f"s3://{s3_service.bucket_name}/{zip_s3_key}"

        transport_params = {'client': s3_service.s3_client}

        with smart_open(zip_s3_uri, 'wb', transport_params=transport_params) as s3_zip_stream:
            with zipfile.ZipFile(s3_zip_stream, 'w', zipfile.ZIP_DEFLATED) as zf:
                for img in images:
                    try:
                        source_s3_uri = f"s3://{s3_service.bucket_name}/{img.s3_key}"
                        with smart_open(source_s3_uri, 'rb', transport_params=transport_params) as s3_file_stream:
                            zf.writestr(img.file_name, s3_file_stream.read())
                    except Exception as e:
                        print(f"Skipping file {img.s3_key} in export: {e}")
                        continue

        download_url = s3_service.generate_presigned_download_url(key=zip_s3_key)

        result_data = {'status': UploadStatusName.COMPLETED, 'download_url': download_url, 'file_name': zip_filename}
        cache.set(job_key, result_data, timeout=3600)


        notifier.notify_frontend(dataset_id, "EXPORT_COMPLETED", result_data)

        return f"Export completed for dataset {dataset_id}"

    except Exception as e:
        error_msg = str(e)
        cache.set(job_key, {'status': UploadStatusName.FAILED, 'error': error_msg}, timeout=3600)


        notifier.notify_frontend(dataset_id, "EXPORT_FAILED", {"error": error_msg})


        return f"Export Failed: {error_msg}"
