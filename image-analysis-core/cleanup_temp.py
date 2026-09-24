#!/usr/bin/env python3
"""
Cleanup script for temporary job directories
Run this as a cronjob to clean up old job folders

Usage:
    python cleanup_temp.py [--dry-run]

Cron example (run daily at 2 AM):
    0 2 * * * cd /app && python cleanup_temp.py >> /var/log/temp_cleanup.log 2>&1
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from infrastructure.storage.temp_manager import TempStorageManager
from infrastructure.storage.s3_settings import TempStorageSettings
from infrastructure.logging import get_logger, configure_logging

# Configure logging for standalone script
configure_logging(application_level="Production", enable_file_logging=True)
logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Clean up old temporary job directories')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only show what would be deleted, without actually deleting'
    )
    
    args = parser.parse_args()
    
    try:
        # Load settings from .env
        settings = TempStorageSettings()
        manager = TempStorageManager(settings)
        
        logger.info("="*60)
        logger.info("Starting temp directory cleanup")
        logger.info(f"Base path: {settings.base_path}")
        logger.info(f"Cleanup threshold: {settings.cleanup_days} day(s)")
        logger.info(f"Dry run: {args.dry_run}")
        logger.info("="*60)
        
        # Run cleanup
        cleaned_count = manager.cleanup_old_jobs(dry_run=args.dry_run)
        
        logger.info("="*60)
        if args.dry_run:
            logger.info(f"Dry run completed. {cleaned_count} directories would be deleted")
        else:
            logger.info(f"Cleanup completed. {cleaned_count} directories deleted")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
