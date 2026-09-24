import uuid
from ..domain.entities import UploadEntity
from ..domain.services import S3Service
from ..domain.constants import UploadStatusName
from ..infrastructure.repositories import UploadRepository


class StartUploadFromUrlUseCase:
    def __init__(self):
        self.repo = UploadRepository()
        self.s3_service = S3Service()

    def execute(self, user_id, organization_id, dataset_name, file_url, file_name, batch_id, dataset_id=None):

        if dataset_id:
            current_dataset_id = dataset_id
        elif dataset_name:
            dataset = self.repo.get_or_create_dataset(name=dataset_name, org_id=organization_id)
            current_dataset_id = dataset.id
        else:
            raise ValueError("Dataset Name or ID is required.")

        if not file_name:
            file_name = file_url.split('/')[-1]
            if not file_name or len(file_name) > 200:
                file_name = f"import_{uuid.uuid4().hex[:8]}.zip"

        s3_key = self.s3_service.generate_s3_key(
            organization_id=organization_id,
            user_id=user_id,
            dataset_id=str(current_dataset_id),
            batch_id=str(batch_id) if batch_id else str(uuid.uuid4()),
            file_name=file_name
        )

        new_upload = UploadEntity(
            id=None,
            user_id=user_id,
            organization_id=organization_id,
            dataset_id=current_dataset_id,
            dataset_name=dataset_name,
            batch_id=batch_id,
            file_name=file_name,
            file_path=s3_key,
            file_size=0,
            content_type='application/zip',
            upload_status=UploadStatusName.DOWNLOADING,
            s3_key=s3_key,
            file_type='ARCHIVE',
            status=UploadStatusName.DOWNLOADING,
            parent_archive_id=None
        )

        created_entity = self.repo.create(new_upload)

        return created_entity
