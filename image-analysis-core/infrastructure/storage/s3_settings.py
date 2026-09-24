"""S3 Storage Configuration and Settings"""
from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Any


class AWSSettings(BaseSettings):
    """
    AWS Base Configuration
    
    When use_aws_role=true, boto3 will automatically use ECS Task Role 
    or IAM Instance Profile for authentication.
    This is the recommended approach for AWS environments.
    
    When use_aws_role=false (default), explicit credentials from environment
    variables will be used (for local development).
    """
    
    # Flag to indicate if we should use AWS role instead of explicit credentials
    # When True, credentials are ignored and boto3 uses ECS Task Role / IAM Instance Profile
    use_aws_role: bool = False
    
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


class S3StorageSettings(BaseSettings):
    """
    S3 Storage Configuration
    
    When USE_AWS_ROLE=true, the access_key_id and secret_access_key will be None,
    and boto3 will automatically use ECS Task Role or IAM Instance Profile.
    This is the recommended approach for AWS environments.
    
    When USE_AWS_ROLE=false (default), explicit credentials from environment
    variables will be used (for local development).
    """
    
    # AWS credentials - can be None when using AWS role
    access_key_id: str | None = None
    secret_access_key: str | None = None
    region_name: str

    # Multiple buckets for different purposes
    raw_images_bucket: str
    ai_bucket: str
    results_bucket: str
    
    # Flag to indicate if we should use AWS role instead of explicit credentials
    use_aws_role: bool = False
    
    model_config = SettingsConfigDict(
        env_prefix="AWS_S3_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )
    
    @model_validator(mode='before')
    @classmethod
    def check_aws_role(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Check USE_AWS_ROLE and clear credentials if using AWS role."""
        raw = data.get('use_aws_role')
        if raw is None:
            try:
                use_role = AWSSettings().use_aws_role
            except Exception:
                use_role = False
        elif isinstance(raw, bool):
            use_role = raw
        else:
            use_role = str(raw).strip().lower() in ('true', '1', 'yes')
        
        if use_role:
            data['use_aws_role'] = True
            data['access_key_id'] = None
            data['secret_access_key'] = None
        
        return data
    
    @property
    def has_explicit_credentials(self) -> bool:
        """Check if explicit credentials are configured"""
        return bool(self.access_key_id and self.secret_access_key)


class StorageDriverSettings(BaseSettings):
    """
    Storage Driver Configuration
    
    Used by StorageDriverFactory to create storage drivers from environment.
    """
    
    # Storage driver type: 'local', 's3', or 'presigned_url'
    driver: str = "local"
    
    # Local storage settings
    base_path: str = "/tmp/photogear_storage"
    
    # S3 settings
    bucket_name: str | None = None
    region: str = "us-east-1"
    prefix: str = "photogear"
    access_key_id: str | None = None
    secret_access_key: str | None = None
    
    # AWS role setting (shared with AWSSettings)
    use_aws_role: bool = False
    
    # Presigned URL settings
    presigned_url_timeout: int = 300
    
    model_config = SettingsConfigDict(
        env_prefix="STORAGE_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )
    
    @model_validator(mode='before')
    @classmethod
    def check_aws_role(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Check USE_AWS_ROLE and clear credentials if using AWS role"""
        use_role = data.get('use_aws_role')
        if use_role is None:
            try:
                aws_settings = AWSSettings()
                use_role = aws_settings.use_aws_role
            except Exception:
                use_role = False
        
        if use_role:
            data['use_aws_role'] = True
            data['access_key_id'] = None
            data['secret_access_key'] = None
        
        return data
    
    @property
    def has_explicit_credentials(self) -> bool:
        """Check if explicit credentials are configured"""
        return bool(self.access_key_id and self.secret_access_key)


class TempStorageSettings(BaseSettings):
    """Temporary storage configuration"""
    
    base_path: str = "/app/data/temp"
    cleanup_days: int = 1
    
    model_config = SettingsConfigDict(
        env_prefix="TEMP_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )
