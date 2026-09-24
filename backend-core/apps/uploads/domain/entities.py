from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import uuid

@dataclass
class UploadEntity:
    id: Optional[uuid.UUID]
    user_id: int
    organization_id: Optional[int]
    dataset_id: uuid.UUID
    dataset_name: Optional[str]
    batch_id: Optional[uuid.UUID]
    file_name: str
    file_path: str
    file_size: Optional[int]
    content_type: str
    upload_status: str
    s3_key: str
    file_type: str
    status: str 
    parent_archive_id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class PresignedUrlEntity:
    upload_id: uuid.UUID      
    dataset_id: uuid.UUID     
    url: str
    fields: dict
    s3_key: str
    expires_in: int

@dataclass
class AIOutputMetadata:
    file_name: str
    s3_key: str
    file_type: str

@dataclass
class AICompletionResult:
    job_id: str
    status: str # 'success' or 'failed'
    outputs: List[AIOutputMetadata]
    error_message: str = None
