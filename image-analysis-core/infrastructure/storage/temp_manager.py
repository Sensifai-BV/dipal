"""Temporary storage manager for job processing"""
from __future__ import annotations

import shutil
from pathlib import Path
from datetime import datetime, timedelta

from .s3_settings import TempStorageSettings
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class TempStorageManager:
    """Manages temporary storage for processing jobs"""
    
    def __init__(self, settings: TempStorageSettings):
        self.settings = settings
        self.base_path = Path(settings.base_path)
        self.cleanup_days = settings.cleanup_days
        
        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def get_job_dir(self, job_id: str) -> Path:
        """
        Get/create temp directory for a job
        
        Args:
            job_id: Job ID
            
        Returns:
            Path to job directory
        """
        job_dir = self.base_path / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Touch a .timestamp file to track last access
        timestamp_file = job_dir / ".timestamp"
        timestamp_file.touch()
        
        logger.info(f"Job directory: {job_dir}")
        return job_dir
    
    def get_subdirectory(self, job_id: str, subdir: str) -> Path:
        """
        Get/create subdirectory within job folder
        
        Args:
            job_id: Job ID
            subdir: Subdirectory name (e.g., 'calibration', 'sfm', 'orthomosaic')
            
        Returns:
            Path to subdirectory
        """
        job_dir = self.get_job_dir(job_id)
        sub_path = job_dir / subdir
        sub_path.mkdir(parents=True, exist_ok=True)
        return sub_path
    
    def get_service_job_dir(self, job_id: str, service_name: str) -> Path:
        """
        Get/create service-specific job directory following new structure:
        temp/jobs/{service}/{job_id}_{service}/
        
        Args:
            job_id: Job ID
            service_name: Service name ('sfm', 'orthomosaic', 'radiometric')
            
        Returns:
            Path to service job directory
        """
        service_dir = self.base_path / "jobs" / service_name / f"{job_id}_{service_name}"
        service_dir.mkdir(parents=True, exist_ok=True)
        
        # Touch a .timestamp file to track last access
        timestamp_file = service_dir / ".timestamp"
        timestamp_file.touch()
        
        logger.info(f"Service job directory ({service_name}): {service_dir}")
        return service_dir
    
    def get_dataset_dir(self, dataset_id: str) -> Path:
        """
        Get/create shared dataset directory for images
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Path to dataset directory
        """
        dataset_dir = self.base_path / "datasets" / dataset_id
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        # Touch timestamp to track last access
        timestamp_file = dataset_dir / ".timestamp"
        timestamp_file.touch()
        
        logger.info(f"Dataset directory: {dataset_dir}")
        return dataset_dir
    
    def get_dataset_images_dir(self, dataset_id: str) -> Path:
        """
        Get/create images directory for a dataset
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Path to dataset images directory
        """
        dataset_dir = self.get_dataset_dir(dataset_id)
        images_dir = dataset_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        return images_dir
    
    def dataset_images_exist(self, dataset_id: str) -> bool:
        """
        Check if dataset images already exist locally
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            True if images directory exists and contains files
        """
        images_dir = self.base_path / "datasets" / dataset_id / "images"
        if not images_dir.exists():
            return False
        
        # Check if directory has any image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
        for file in images_dir.rglob('*'):
            if file.is_file() and file.suffix.lower() in image_extensions:
                return True
        
        return False
    
    def cleanup_old_jobs(self, dry_run: bool = False) -> int:
        """
        Clean up job folders not updated in cleanup_days
        
        Args:
            dry_run: If True, only log what would be deleted
            
        Returns:
            Number of directories cleaned up
        """
        jobs_dir = self.base_path / "jobs"
        if not jobs_dir.exists():
            return 0
        
        cleanup_count = 0
        cutoff_time = datetime.now() - timedelta(days=self.cleanup_days)
        
        for job_dir in jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue
            
            # Check timestamp file
            timestamp_file = job_dir / ".timestamp"
            
            if timestamp_file.exists():
                last_modified = datetime.fromtimestamp(timestamp_file.stat().st_mtime)
            else:
                # Use directory modification time as fallback
                last_modified = datetime.fromtimestamp(job_dir.stat().st_mtime)
            
            if last_modified < cutoff_time:
                if dry_run:
                    logger.info(f"[DRY RUN] Would delete: {job_dir} (last modified: {last_modified})")
                else:
                    logger.info(f"Deleting old job directory: {job_dir} (last modified: {last_modified})")
                    try:
                        shutil.rmtree(job_dir)
                        cleanup_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {job_dir}: {e}")
        
        if not dry_run and cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} old job directories")
        
        return cleanup_count
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a specific job directory
        
        Args:
            job_id: Job ID
            
        Returns:
            True if deleted, False if not found
        """
        job_dir = self.base_path / "jobs" / job_id
        
        if not job_dir.exists():
            logger.warning(f"Job directory not found: {job_dir}")
            return False
        
        try:
            logger.info(f"Deleting job directory: {job_dir}")
            shutil.rmtree(job_dir)
            return True
        except Exception as e:
            logger.error(f"Failed to delete job directory {job_dir}: {e}")
            return False
    
    def update_job_timestamp(self, job_id: str):
        """
        Update the timestamp for a job to keep it alive
        
        Args:
            job_id: Job ID
        """
        job_dir = self.base_path / "jobs" / job_id
        if job_dir.exists():
            timestamp_file = job_dir / ".timestamp"
            timestamp_file.touch()
