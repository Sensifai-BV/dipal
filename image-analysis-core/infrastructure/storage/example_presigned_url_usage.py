"""
Example usage of the PresignedUrlStorageDriver.

This demonstrates how to use the presigned URL driver to fetch images
and upload results using S3 presigned URLs.
"""

from __future__ import annotations

import logging
from pathlib import Path

from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.factory import StorageDriverFactory
from infrastructure.storage.drivers.presigned_url import PresignedUrlStorageDriver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def example_presigned_url_storage():
    """
    Example using presigned URL storage.

    This example shows how to:
    1. Create a presigned URL driver
    2. Configure it with project-specific URLs
    3. Fetch images from presigned URLs
    4. Upload results using presigned URLs
    """
    logger.info("=" * 60)
    logger.info("Example: Presigned URL Storage")
    logger.info("=" * 60)

    project_id = "test_project_002"

    # Set presigned URLs for the project
    # These URLs would typically be obtained from an API gateway
    download_url = "https://api.example.com/projects/test_project_002/images/download"
    upload_url = "https://api.example.com/projects/test_project_002/results/upload"

    # driver.set_project_urls(
    #     project_id=project_id,
    #     download_url=download_url,
    #     upload_url=upload_url,
    # )
    # Create presigned URL storage driver
    driver = StorageDriverFactory.create(
        "presigned_url",
        {
            "timeout": 300,  # 5 minutes timeout
            "project_urls": {
                project_id: {
                    "download_url": download_url,
                    "upload_url": upload_url,
                },
            },
        },
    )

    # Connect to storage
    driver.connect()

    try:
        # Create dataset instance
        dataset = Dataset(
            project_id=project_id,
            storage_driver=driver,
            temp_base_path=Path("/tmp/photogear"),
        )

        # Initialize workspace
        dataset.initialize_dataset()

        # Fetch images from presigned URLs
        logger.info("Fetching images using presigned URLs...")
        images_path = dataset.fetch_images()
        logger.info(f"Images available at: {images_path}")

        # Create a new run
        run_path = dataset.create_run()
        logger.info(f"Processing run directory: {run_path}")

        # Simulate processing - create some result files
        (run_path / "result.txt").write_text("Processing complete!")
        (run_path / "output").mkdir(exist_ok=True)
        (run_path / "output" / "data.bin").write_bytes(b"binary data")

        # Push results using presigned URLs
        logger.info("Pushing results using presigned URLs...")
        dataset.push_results()
        logger.info("Results pushed successfully")

        # List available images
        images = driver.list_images(project_id)
        logger.info(f"Available images: {images}")

        # Cleanup temporary files
        dataset.cleanup(keep_results=False)
        logger.info("Cleanup complete")

    finally:
        # Disconnect from storage
        driver.disconnect()


def example_presigned_url_with_custom_response_format():
    """
    Example showing how the driver handles different JSON response formats.

    The driver can automatically parse different response formats:
    1. {"images": [{"url": "...", "filename": "..."}, ...]}
    2. {"urls": ["url1", "url2", ...]}
    3. {"files": [{"url": "...", "name": "..."}, ...]}
    4. {"data": {"images": [...]}}
    """
    logger.info("=" * 60)
    logger.info("Example: Custom Response Format Handling")
    logger.info("=" * 60)

    # The driver automatically detects and parses these formats:

    # Format 1: Detailed image info
    example_response_1 = {
        "images": [
            {
                "url": "https://s3.amazonaws.com/bucket/image1.jpg?signature=...",
                "filename": "DJI_001.jpg",
            },
            {
                "url": "https://s3.amazonaws.com/bucket/image2.jpg?signature=...",
                "filename": "DJI_002.jpg",
            },
        ],
    }

    # Format 2: Simple URL list
    example_response_2 = {
        "urls": [
            "https://s3.amazonaws.com/bucket/image1.jpg?signature=...",
            "https://s3.amazonaws.com/bucket/image2.jpg?signature=...",
        ],
    }

    # Format 3: Files with 'name' instead of 'filename'
    example_response_3 = {
        "files": [
            {
                "url": "https://s3.amazonaws.com/bucket/image1.jpg?signature=...",
                "name": "DJI_001.jpg",
            },
        ],
    }

    # Format 4: Nested data structure
    example_response_4 = {
        "status": "success",
        "data": {
            "images": [
                {"url": "https://s3.amazonaws.com/bucket/image1.jpg?signature=..."},
            ],
        },
    }

    logger.info("The driver automatically handles all these response formats!")
    logger.info(f"Example response 1: {example_response_1}")
    logger.info(f"Example response 2: {example_response_2}")
    logger.info(f"Example response 3: {example_response_3}")
    logger.info(f"Example response 4: {example_response_4}")


def example_with_url_provider():
    """
    Example using a URL provider pattern.

    In a real application, you might have a service that generates
    presigned URLs dynamically for each project.
    """
    logger.info("=" * 60)
    logger.info("Example: Dynamic URL Provider Pattern")
    logger.info("=" * 60)

    class PresignedUrlProvider:
        """Service that generates presigned URLs for projects."""

        def __init__(self, api_base_url: str):
            self.api_base_url = api_base_url

        def get_download_url(self, project_id: str) -> str:
            """Get presigned URL for downloading project images."""
            return f"{self.api_base_url}/projects/{project_id}/images/download"

        def get_upload_url(self, project_id: str, run_id: int) -> str:
            """Get presigned URL for uploading run results."""
            return f"{self.api_base_url}/projects/{project_id}/runs/{run_id}/upload"

    # Initialize the URL provider
    url_provider = PresignedUrlProvider(
        api_base_url="https://api.photogear.example.com",
    )

    # Create driver
    project_id = "demo_project"

    # Get URLs from provider and configure driver
    download_url = url_provider.get_download_url(project_id)
    upload_url = url_provider.get_upload_url(project_id, run_id=1)

    driver = PresignedUrlStorageDriver(
        timeout=300,
        project_urls={
            project_id: {
                "download_url": download_url,
                "upload_url": upload_url,
            },
        },
    )
    driver.connect()

    try:
        logger.info(f"Configured URLs for project {project_id}")
        logger.info(f"Download URL: {download_url}")
        logger.info(f"Upload URL: {upload_url}")

        # Now use the driver with Dataset as normal
        Dataset(
            project_id=project_id,
            storage_driver=driver,
        )

        logger.info("Driver is ready to fetch/push data!")

    finally:
        driver.disconnect()


if __name__ == "__main__":
    # Run examples
    logger.info("Running Presigned URL Storage Driver Examples\n")

    # Note: These examples won't actually run without real presigned URLs
    # They are for demonstration purposes only

    example_presigned_url_with_custom_response_format()
    logger.info("\n")

    example_with_url_provider()
    logger.info("\n")

    # To run the actual example, you would need real presigned URLs:
    # example_presigned_url_storage()
