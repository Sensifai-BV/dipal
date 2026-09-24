"""S3 Upload Client for uploading processing results"""
from __future__ import annotations

import boto3
from pathlib import Path
from typing import Dict, List

from .s3_settings import S3StorageSettings
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class S3ResultsUploader:
    """
    Handles uploading processing results to S3
    
    When USE_AWS_ROLE=true in environment, uses ECS Task Role / IAM Instance Profile
    for authentication (recommended for AWS deployments).
    Otherwise, uses explicit credentials from settings.
    """
    
    def __init__(self, settings: S3StorageSettings):
        self.settings = settings
        
        # Build client kwargs - only include credentials if explicitly set
        # When running on AWS (ECS), boto3 will automatically use the Task Role
        client_kwargs = {
            'region_name': settings.region_name
        }
        
        if settings.has_explicit_credentials:
            client_kwargs['aws_access_key_id'] = settings.access_key_id
            client_kwargs['aws_secret_access_key'] = settings.secret_access_key
            logger.info("S3ResultsUploader: Using explicit AWS credentials")
        else:
            # Let boto3 use ECS Task Role / IAM Instance Profile automatically
            logger.info("S3ResultsUploader: Using AWS IAM Role (ECS Task Role / Instance Profile)")
        
        self.s3_client = boto3.client('s3', **client_kwargs)
    
    def upload_file(
        self,
        local_path: Path | str,
        s3_key: str,
        bucket: str | None = None,
        extra_args: Dict | None = None
    ) -> str:
        """
        Upload a file to S3
        
        Args:
            local_path: Path to local file
            s3_key: S3 key (path in bucket)
            bucket: Bucket name (defaults to results_bucket)
            extra_args: Extra arguments for upload
            
        Returns:
            S3 URI (s3://bucket/key)
        """
        bucket = bucket or self.settings.results_bucket
        local_path = Path(local_path)
        
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")
        
        # Prepare extra args
        upload_args = extra_args or {}

        logger.info(f"Uploading {local_path} to s3://{bucket}/{s3_key}")
        
        try:
            self.s3_client.upload_file(
                str(local_path),
                bucket,
                s3_key,
                ExtraArgs=upload_args
            )
            
            s3_uri = f"s3://{bucket}/{s3_key}"
            logger.info(f"Successfully uploaded to {s3_uri}")
            return s3_uri
            
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            raise
    
    def upload_job_results(
        self,
        job_id: str,
        dataset_id: str,
        result_files: Dict[str, Path | str]
    ) -> Dict[str, str]:
        """
        Upload all result files for a job
        
        Args:
            job_id: Job ID
            dataset_id: Dataset ID
            result_files: Dict of {result_type: local_path}
                Example: {
                    'orthomosaic': '/path/to/orthomosaic.tif',
                    'dsm': '/path/to/dsm.tif',
                    'mesh': '/path/to/mesh.ply',
                }
        
        Returns:
            Dict of {result_type: s3_uri}
        """
        s3_uris = {}
        
        for result_type, local_path in result_files.items():
            if local_path is None:
                continue
                
            local_path = Path(local_path)
            if not local_path.exists():
                logger.warning(f"Result file not found: {local_path}")
                continue
            
            # S3 key structure: jobs/{dataset_id}/{job_id}/{result_type}/{filename}
            s3_key = f"jobs/{dataset_id}/{job_id}/{result_type}/{local_path.name}"
            
            try:
                s3_uri = self.upload_file(local_path, s3_key)
                s3_uris[result_type] = s3_uri
            except Exception as e:
                logger.error(f"Failed to upload {result_type}: {e}")
                # Continue with other files
        
        return s3_uris
    
    def generate_presigned_url(
        self,
        s3_uri: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate presigned URL for downloading
        
        Args:
            s3_uri: S3 URI (s3://bucket/key)
            expiration: URL expiration in seconds
            
        Returns:
            Presigned URL
        """
        # Parse s3://bucket/key
        if not s3_uri.startswith('s3://'):
            raise ValueError(f"Invalid S3 URI: {s3_uri}")
        
        parts = s3_uri[5:].split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        
        url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiration
        )
        
        return url
