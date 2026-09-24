"""Shared storage settings for EFS and local modes."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SharedStorageSettings(BaseSettings):
    """
    Shared storage configuration supporting local and EFS modes.

    Args:
        mode: Storage mode — 'local' or 'efs'

    When mode='local': uses TEMP_BASE_PATH as root directory.
    When mode='efs': uses EFS mount point (same path interface).
    """

    mode: str = "local"

    model_config = SettingsConfigDict(
        env_prefix="SHARED_STORAGE_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


class EFSSettings(BaseSettings):
    """
    AWS EFS configuration for managed shared storage.

    Args:
        file_system_id: EFS filesystem ID (e.g., fs-0123456789abcdef0)
        mount_point: Local mount path for EFS
        aws_region: AWS region for EFS API calls
        access_key_id: AWS access key for EFS management APIs
        secret_access_key: AWS secret key for EFS management APIs
    """

    file_system_id: str = ""
    mount_point: str = "/app/data/temp"
    aws_region: str = "eu-north-1"
    access_key_id: str = ""
    secret_access_key: str = ""

    model_config = SettingsConfigDict(
        env_prefix="EFS_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


__all__ = ["SharedStorageSettings", "EFSSettings"]
