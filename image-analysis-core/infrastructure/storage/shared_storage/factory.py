"""Factory for creating shared storage backends via dependency injection."""
from __future__ import annotations

from infrastructure.logging import get_logger
from infrastructure.storage.s3_settings import TempStorageSettings

from .base import SharedStorageBackend
from .efs_storage import EFSSharedStorage
from .local_storage import LocalSharedStorage
from .settings import EFSSettings, SharedStorageSettings

logger = get_logger(__name__)


class SharedStorageFactory:
    """
    Create the appropriate shared storage backend from configuration.

    Reads SHARED_STORAGE_MODE from env:
      - 'local': LocalSharedStorage (Docker volume / host dir)
      - 'efs': EFSSharedStorage (AWS EFS mount)
    """

    @staticmethod
    def create(
        shared_settings: SharedStorageSettings | None = None,
        temp_settings: TempStorageSettings | None = None,
        efs_settings: EFSSettings | None = None,
    ) -> SharedStorageBackend:
        """
        Create a shared storage backend based on configuration.

        Args:
            shared_settings: Storage mode configuration
            temp_settings: Local temp path settings
            efs_settings: EFS-specific settings

        Returns:
            Configured SharedStorageBackend instance

        Raises:
            ValueError: If mode is not 'local' or 'efs'
        """
        shared_settings = shared_settings or SharedStorageSettings()
        mode = shared_settings.mode.lower()

        if mode == "local":
            temp_settings = temp_settings or TempStorageSettings()
            logger.info(f"Using local shared storage at {temp_settings.base_path}")
            return LocalSharedStorage(settings=temp_settings)

        if mode == "efs":
            efs_settings = efs_settings or EFSSettings()
            logger.info(
                f"Using EFS shared storage: fs={efs_settings.file_system_id}, "
                f"mount={efs_settings.mount_point}"
            )
            return EFSSharedStorage(settings=efs_settings)

        raise ValueError(
            f"Unknown SHARED_STORAGE_MODE: '{mode}'. Must be 'local' or 'efs'."
        )


__all__ = ["SharedStorageFactory"]
