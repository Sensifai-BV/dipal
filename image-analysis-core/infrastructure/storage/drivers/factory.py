from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import StorageDriver
from .local import LocalStorageDriver
from .presigned_url import PresignedUrlStorageDriver
from .s3 import S3StorageDriver
from infrastructure.logging import get_logger
from infrastructure.storage.s3_settings import StorageDriverSettings

logger = get_logger(__name__)


class StorageDriverFactory:
    """
    Factory class for creating storage driver instances.

    Supports creation of different storage drivers based on configuration.
    """

    _drivers: dict[str, type[StorageDriver]] = {
        "local": LocalStorageDriver,
        "s3": S3StorageDriver,
        "presigned_url": PresignedUrlStorageDriver,
    }

    @classmethod
    def create(cls, driver_type: str, config: dict[str, Any]) -> StorageDriver:
        """
        Create a storage driver instance.

        Args:
            driver_type: Type of driver to create ('local' or 's3')
            config: Configuration dictionary for the driver

        Returns:
            Initialized storage driver instance

        Raises:
            ValueError: If driver_type is not supported

        Examples:
            # Create local driver
            >>> driver = StorageDriverFactory.create('local', {
            ...     'base_path': '/mnt/storage'
            ... })

            # Create S3 driver
            >>> driver = StorageDriverFactory.create('s3', {
            ...     'bucket_name': 'my-bucket',
            ...     'region_name': 'us-west-2',
            ...     'prefix': 'photogear'
            ... })
        """
        driver_type = driver_type.lower()

        if driver_type not in cls._drivers:
            raise ValueError(
                f"Unsupported driver type: {driver_type}. "
                f"Supported types: {', '.join(cls._drivers.keys())}",
            )

        driver_class = cls._drivers[driver_type]

        try:
            driver = driver_class(**config)
            logger.info(f"Created {driver_type} storage driver")
            return driver
        except TypeError as e:
            logger.error(f"Invalid configuration for {driver_type} driver: {e}")
            raise ValueError(f"Invalid configuration for {driver_type} driver: {e}")

    @classmethod
    def create_from_env(cls, driver_type: str | None = None) -> StorageDriver:
        """
        Create a storage driver from environment variables using pydantic settings.

        Args:
            driver_type: Type of driver to create. If None, reads from
                        STORAGE_DRIVER env var (defaults to 'local')

        Environment Variables (via StorageDriverSettings):
            STORAGE_DRIVER: Type of storage driver ('local', 's3', or 'presigned_url')

            For Local Driver:
                STORAGE_BASE_PATH: Base path for local storage

            For S3 Driver:
                STORAGE_BUCKET_NAME: S3 bucket name
                STORAGE_REGION: AWS region (optional, defaults to 'us-east-1')
                USE_AWS_ROLE: When 'true', uses ECS Task Role / IAM Instance Profile
                              instead of explicit credentials (recommended for AWS deployments)
                STORAGE_ACCESS_KEY_ID: AWS access key (ignored when USE_AWS_ROLE=true)
                STORAGE_SECRET_ACCESS_KEY: AWS secret key (ignored when USE_AWS_ROLE=true)
                STORAGE_PREFIX: Prefix for S3 keys (optional, defaults to 'photogear')

            For Presigned URL Driver:
                STORAGE_PRESIGNED_URL_TIMEOUT: Request timeout in seconds (optional, defaults to 300)
                Note: Project URLs must be set via set_project_urls() method

        Returns:
            Initialized storage driver instance
        """
        # Load settings from environment using pydantic
        settings = StorageDriverSettings()
        
        if driver_type is None:
            driver_type = settings.driver

        driver_type = driver_type.lower()

        if driver_type == "local":
            config: dict[str, Any] = {"base_path": Path(settings.base_path)}

        elif driver_type == "s3":
            if not settings.bucket_name:
                raise ValueError(
                    "STORAGE_BUCKET_NAME environment variable is required for S3 driver",
                )
            
            if settings.use_aws_role:
                # Let boto3 use ECS Task Role / IAM Instance Profile automatically
                config = {
                    "bucket_name": settings.bucket_name,
                    "region_name": settings.region,
                    "prefix": settings.prefix,
                    # aws_access_key_id and aws_secret_access_key intentionally omitted
                }
                logger.info("StorageDriverFactory: Creating S3 driver with AWS IAM Role")
            else:
                # Use explicit credentials for local development
                config = {
                    "bucket_name": settings.bucket_name,
                    "region_name": settings.region,
                    "aws_access_key_id": settings.access_key_id,
                    "aws_secret_access_key": settings.secret_access_key,
                    "prefix": settings.prefix,
                }
                logger.info("StorageDriverFactory: Creating S3 driver with explicit credentials")

        elif driver_type == "presigned_url":
            config = {
                "timeout": settings.presigned_url_timeout,
            }

        else:
            raise ValueError(f"Unsupported driver type: {driver_type}")

        return cls.create(driver_type, config)

    @classmethod
    def register_driver(cls, name: str, driver_class: type[StorageDriver]) -> None:
        """
        Register a custom storage driver.

        Args:
            name: Name for the driver
            driver_class: Driver class (must inherit from StorageDriver)

        Raises:
            TypeError: If driver_class doesn't inherit from StorageDriver
        """
        if not issubclass(driver_class, StorageDriver):
            raise TypeError(f"{driver_class} must inherit from StorageDriver")

        cls._drivers[name.lower()] = driver_class
        logger.info(f"Registered custom storage driver: {name}")
