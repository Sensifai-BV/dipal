import uuid
from typing import Optional, List
from django.db import transaction
from django.db.models import Count, Sum, Q, Case, When, Value, CharField, Subquery, OuterRef
from ..infrastructure.models import Image, Dataset, UploadStatus
from ..domain.entities import UploadEntity
from ..domain.constants import UploadStatusName
from config.logging_config import get_logger

logger = get_logger(__name__)

class UploadRepository:

    # ---------------------------------------------------------
    # Helper: Convert Django Model -> Domain Entity
    # ---------------------------------------------------------
    @staticmethod
    def model_to_entity(model: Image) -> UploadEntity:
        
        status_name = model.status.name if model.status else UploadStatusName.PENDING
        
        return UploadEntity(
            id=model.id,
            user_id=model.user_id,
            organization_id=model.dataset.org_id if model.dataset else None,
            dataset_id=model.dataset_id,
            dataset_name=model.dataset.name if model.dataset else None,
            batch_id=model.batch_id,
            file_name=model.file_name,
            file_path=model.s3_key,
            file_size=model.file_size,
            content_type=model.content_type,
            upload_status=status_name,  
            s3_key=model.s3_key,
            file_type=model.file_type,
            status=status_name,         
            parent_archive_id=model.parent_image_id,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    # ---------------------------------------------------------
    # Dataset: Resolve by name OR create new
    # ---------------------------------------------------------
    @staticmethod
    def get_or_create_dataset(name: str, org_id: int) -> Dataset:
        dataset, _ = Dataset.objects.get_or_create(
            name=name,
            org_id=org_id,
            defaults={}
        )
        return dataset

    # ---------------------------------------------------------
    # Create Upload Record
    # ---------------------------------------------------------
    @staticmethod
    def create(entity: UploadEntity) -> UploadEntity:
        logger.debug(
            f"[REPO:CREATE] Creating upload record - file: {entity.file_name}, "
            f"dataset: {entity.dataset_id}, status: {entity.upload_status}"
        )
      
        try:
            status_obj = UploadStatus.objects.get(name=entity.upload_status)
            logger.debug(f"[REPO:CREATE] Status object found: {status_obj.name}")
        except UploadStatus.DoesNotExist:
            logger.warning(
                f"[REPO:CREATE] Status '{entity.upload_status}' not found, creating new status"
            )
            status_obj, _ = UploadStatus.objects.get_or_create(
                name=entity.upload_status, 
                defaults={'label': entity.upload_status.capitalize()}
            )

        image = Image.objects.create(
            user_id=entity.user_id,
            dataset_id=entity.dataset_id,
            batch_id=entity.batch_id,
            file_name=entity.file_name,
            file_size=entity.file_size,
            content_type=entity.content_type,
            status=status_obj,  
            s3_key=entity.s3_key,
            file_type=entity.file_type,
            parent_image_id=entity.parent_archive_id
        )
        logger.info(
            f"[REPO:CREATE] ✅ Upload record created - id: {image.id}, "
            f"file: {entity.file_name}, s3_key: {entity.s3_key}"
        )
        return UploadRepository.model_to_entity(image)
    # ---------------------------------------------------------
    # Get Upload by ID
    # ---------------------------------------------------------
    @staticmethod
    def get_by_id(upload_id: uuid.UUID) -> Optional[UploadEntity]:
        try:
            image = Image.objects.get(id=upload_id)
            return UploadRepository.model_to_entity(image)
        except Image.DoesNotExist:
            return None

    # ---------------------------------------------------------
    # Update status (PROCESSING / COMPLETED / FAILED)
    # ---------------------------------------------------------
    @staticmethod
    def update_status(upload_id: uuid.UUID, status_name: str, file_size: Optional[int] = None, error_message: Optional[str] = None) -> UploadEntity:
        """
        Updates the status. Finds the UploadStatus object by name first.
        """
        logger.info(f"[REPO:UPDATE-STATUS] Updating status - upload_id: {upload_id}, new_status: {status_name}")
        
        try:
            status_obj = UploadStatus.objects.get(name=status_name)
            logger.debug(f"[REPO:UPDATE-STATUS] Status object found: {status_obj.name}")
        except UploadStatus.DoesNotExist:
            logger.error(f"[REPO:UPDATE-STATUS] ❌ Status '{status_name}' does not exist in database")
            raise ValueError(f"Status with name '{status_name}' does not exist in DB.")

        with transaction.atomic():
            image = Image.objects.select_for_update().get(id=upload_id)
            old_status = image.status.name if image.status else 'N/A'
            logger.debug(
                f"[REPO:UPDATE-STATUS] Upload found - file: {image.file_name}, "
                f"old_status: {old_status}, new_status: {status_name}"
            )
            
            image.status = status_obj  
            if file_size is not None:
                logger.debug(f"[REPO:UPDATE-STATUS] Updating file_size to: {file_size}")
                image.file_size = file_size
            if error_message is not None:
                image.error_message = error_message
            elif status_name != UploadStatusName.FAILED:
                image.error_message = None
            image.save()
            
        logger.info(
            f"[REPO:UPDATE-STATUS] ✅ Status updated - upload_id: {upload_id}, "
            f"{old_status} -> {status_name}"
        )
        return UploadRepository.model_to_entity(image)

    # ---------------------------------------------------------
    # List uploads of a user
    # ---------------------------------------------------------
    @staticmethod
    def get_user_uploads(
        user_id: int,
        dataset_id: Optional[uuid.UUID] = None,
        batch_id: Optional[uuid.UUID] = None,
        file_type: Optional[str] = None
    ) -> List[UploadEntity]:
        
       
        queryset = Image.objects.select_related('status', 'dataset').filter(user_id=user_id)

        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        if file_type:
            queryset = queryset.filter(file_type=file_type)

        queryset = queryset.order_by('-created_at')

        return [UploadRepository.model_to_entity(img) for img in queryset]

    # ---------------------------------------------------------
    # Dataset Stats for user
    # ---------------------------------------------------------
    @staticmethod
    def get_datasets_stats(user_id: int) -> List[dict]:
        
        qs = Dataset.objects.filter(org__users__id=user_id).distinct()

        failed_error_subquery = Image.objects.filter(
            dataset_id=OuterRef('id'),
            file_type='ARCHIVE',
            status__name=UploadStatusName.FAILED,
            error_message__isnull=False,
        ).order_by('-updated_at').values('error_message')[:1]

        stats = qs.annotate(
            total_files=Count('images', filter=Q(images__file_type='IMAGE')),
            total_size=Sum('images__file_size', filter=Q(images__file_type='ARCHIVE')),
            
            processing_count=Count('images', filter=Q(
                images__file_type='ARCHIVE',
                images__status__name__in=[
                    UploadStatusName.PROCESSING, UploadStatusName.PENDING, UploadStatusName.DOWNLOADING
                ]
            )),
            failed_count=Count('images', filter=Q(
                images__file_type='ARCHIVE',
                images__status__name=UploadStatusName.FAILED
            ))
        ).annotate(
            status=Case(
                When(processing_count__gt=0, then=Value(UploadStatusName.PROCESSING)),
                When(failed_count__gt=0, then=Value(UploadStatusName.FAILED)),
                default=Value(UploadStatusName.COMPLETED),
                output_field=CharField(),
            ),
            error_message=Subquery(failed_error_subquery),
        ).values(
            'id',
            'name',
            'total_files',
            'total_size',
            'created_at',
            'status',
            'error_message',
        ).order_by('-created_at')

        return list(stats)

    def set_multipart_id(self, upload_id: uuid.UUID, s3_upload_id: str):
        logger.debug(
            f"[REPO:SET-MULTIPART-ID] Setting s3_upload_id - "
            f"upload_id: {upload_id}, s3_upload_id: {s3_upload_id[:10]}..."
        )
        try:
            image = Image.objects.get(id=upload_id)
            logger.debug(f"[REPO:SET-MULTIPART-ID] Upload found - file: {image.file_name}")
            image.s3_upload_id = s3_upload_id
            image.save()
            logger.info(
                f"[REPO:SET-MULTIPART-ID] ✅ s3_upload_id set - upload_id: {upload_id}, "
                f"s3_upload_id: {s3_upload_id[:10]}..."
            )
        except Image.DoesNotExist:
            logger.error(f"[REPO:SET-MULTIPART-ID] ❌ Upload not found: {upload_id}")
            pass

    @staticmethod
    def get_dataset_archive_status(dataset_id: uuid.UUID) -> Optional[dict]:
        """
        Finds the Image record with file_type='ARCHIVE' for the given dataset_id
        and returns its status details.
        """
        try:
            image = Image.objects.select_related('status').filter(
                dataset_id=dataset_id,
                file_type=Image.FileType.ARCHIVE
            ).order_by('-created_at').first()

            if not image:
                return None

            return {
                'upload_id': image.id,
                'file_name': image.file_name,
                'status': image.status.name,
                'status_label': image.status.label,
                's3_key': image.s3_key,
                'updated_at': image.updated_at
            }
        except Exception as e:
            return None