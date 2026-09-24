"""
Example usage of the Dataset class with different storage drivers.

This module demonstrates how to use the PhotoGear dataset management system
with both local and S3 storage backends.
"""

from __future__ import annotations

import logging
from pathlib import Path

from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.factory import StorageDriverFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def example_local_storage():
    """
    Example using local filesystem storage.
    """
    logger.info("=" * 60)
    logger.info("Example: Local Storage")
    logger.info("=" * 60)

    # Create local storage driver
    driver = StorageDriverFactory.create(
        "local",
        {
            "base_path": Path("/tmp/photogear_storage"),
        },
    )

    # Connect to storage
    driver.connect()

    try:
        # Create dataset instance
        project_id = "test_project_001"
        dataset = Dataset(
            project_id=project_id,
            storage_driver=driver,
            temp_base_path=Path("/tmp/photogear"),
        )

        # Initialize workspace
        dataset.initialize_dataset()

        # Fetch images from storage
        images_path = dataset.fetch_images()
        logger.info(f"Images available at: {images_path}")

        # Create a new run
        run_path = dataset.create_run()
        logger.info(f"Processing run directory: {run_path}")
        logger.info(f"Current run ID: {dataset.current_run_id}")

        # Simulate processing - create some result files
        (run_path / "result.txt").write_text("Processing complete!")
        (run_path / "output").mkdir(exist_ok=True)
        (run_path / "output" / "data.bin").write_bytes(b"binary data")

        # Push results back to storage
        dataset.push_results()
        logger.info("Results pushed to storage successfully")

        # List available images
        images = dataset.list_images()
        logger.info(f"Available images: {images}")

        # Cleanup temporary files
        dataset.cleanup(keep_results=False)
        logger.info("Cleanup complete")

    finally:
        # Disconnect from storage
        driver.disconnect()


def example_s3_storage():
    """
    Example using AWS S3 storage.
    """
    logger.info("=" * 60)
    logger.info("Example: S3 Storage")
    logger.info("=" * 60)

    # Create S3 storage driver
    driver = StorageDriverFactory.create(
        "s3",
        {
            "bucket_name": "my-photogear-bucket",
            "region_name": "us-west-2",
            "prefix": "photogear",
        },
    )

    # Connect to S3
    driver.connect()

    try:
        # Create dataset instance
        project_id = "drone_survey_001"
        dataset = Dataset(
            project_id=project_id,
            storage_driver=driver,
        )

        # Initialize workspace
        dataset.initialize_dataset()

        # Fetch images from S3
        images_path = dataset.fetch_images()
        logger.info(f"Downloaded images to: {images_path}")

        # Create a new run
        run_path = dataset.create_run()
        logger.info(f"Processing run directory: {run_path}")

        # Simulate processing
        (run_path / "orthomosaic.tif").write_bytes(b"GeoTIFF data here")
        (run_path / "metadata.json").write_text('{"status": "complete"}')

        # Push results to S3
        dataset.push_results()
        logger.info("Results uploaded to S3")

        # Cleanup
        dataset.cleanup(keep_results=False)

    finally:
        driver.disconnect()


def example_from_environment():
    """
    Example using environment variables for configuration.

    Environment variables:
        STORAGE_DRIVER=local or s3
        STORAGE_BASE_PATH=/path/to/storage (for local)
        S3_BUCKET_NAME=bucket-name (for s3)
        AWS_REGION=us-west-2 (for s3)
    """
    logger.info("=" * 60)
    logger.info("Example: Environment-based Configuration")
    logger.info("=" * 60)

    # Create driver from environment
    driver = StorageDriverFactory.create_from_env()
    driver.connect()

    try:
        project_id = "env_project_001"
        dataset = Dataset(project_id=project_id, storage_driver=driver)

        dataset.initialize_dataset()
        images_path = dataset.fetch_images()

        logger.info(f"Images: {images_path}")
        logger.info(f"Available: {dataset.list_images()}")

    finally:
        driver.disconnect()


def example_multiple_runs():
    """
    Example demonstrating multiple processing runs.
    """
    logger.info("=" * 60)
    logger.info("Example: Multiple Runs")
    logger.info("=" * 60)

    driver = StorageDriverFactory.create(
        "local",
        {
            "base_path": Path("/tmp/photogear_storage"),
        },
    )
    driver.connect()

    try:
        project_id = "multi_run_project"
        dataset = Dataset(project_id=project_id, storage_driver=driver)

        dataset.initialize_dataset()
        dataset.fetch_images()

        # Run 1: Initial processing
        run1_path = dataset.create_run()
        logger.info(f"Run 1 path: {run1_path}")
        (run1_path / "result.txt").write_text("Run 1 results")
        dataset.push_results()

        # Run 2: Reprocessing with different parameters
        run2_path = dataset.create_run()
        logger.info(f"Run 2 path: {run2_path}")
        (run2_path / "result.txt").write_text("Run 2 results")
        dataset.push_results()

        # Run 3: Final processing
        run3_path = dataset.create_run()
        logger.info(f"Run 3 path: {run3_path}")
        (run3_path / "result.txt").write_text("Run 3 results")
        dataset.push_results()

        logger.info(f"Completed {dataset.current_run_id} runs")

        # Cleanup
        dataset.cleanup(keep_results=False)

    finally:
        driver.disconnect()


def example_workflow_integration():
    """
    Example showing integration with processing workflow.

    This simulates the actual PhotoGear orthomosaic generation workflow.
    """
    logger.info("=" * 60)
    logger.info("Example: Full Workflow Integration")
    logger.info("=" * 60)

    # Setup storage
    driver = StorageDriverFactory.create(
        "local",
        {
            "base_path": Path("/tmp/photogear_storage"),
        },
    )
    driver.connect()

    try:
        project_id = "workflow_project"
        dataset = Dataset(project_id=project_id, storage_driver=driver)

        # Step 1: Initialize and fetch images
        logger.info("Step 1: Fetching images from storage...")
        dataset.initialize_dataset()
        images_path = dataset.fetch_images()
        logger.info(f"  → Images ready at: {images_path}")

        # Step 2: Create processing run
        logger.info("Step 2: Creating processing run...")
        run_path = dataset.create_run()
        logger.info(f"  → Run directory: {run_path}")

        # Step 3: Simulate SFM processing
        logger.info("Step 3: Running SFM (Structure from Motion)...")
        sfm_output = run_path / "sfm"
        sfm_output.mkdir()
        (sfm_output / "sparse.ply").write_text("Point cloud data")
        (sfm_output / "cameras.json").write_text("{}")
        logger.info("  → SFM complete")

        # Step 4: Simulate dense reconstruction
        logger.info("Step 4: Running dense reconstruction...")
        dense_output = run_path / "dense"
        dense_output.mkdir()
        (dense_output / "dense.ply").write_text("Dense point cloud")
        logger.info("  → Dense reconstruction complete")

        # Step 5: Simulate orthomosaic generation
        logger.info("Step 5: Generating orthomosaic...")
        ortho_output = run_path / "orthomosaic"
        ortho_output.mkdir()
        (ortho_output / "orthomosaic.tif").write_bytes(b"GeoTIFF data")
        (ortho_output / "metadata.json").write_text('{"crs": "EPSG:4326"}')
        logger.info("  → Orthomosaic complete")

        # Step 6: Push results to storage
        logger.info("Step 6: Pushing results to storage...")
        dataset.push_results()
        logger.info("  → Results successfully uploaded")

        # Step 7: Cleanup
        logger.info("Step 7: Cleaning up temporary files...")
        dataset.cleanup(keep_results=False)
        logger.info("  → Cleanup complete")

        logger.info("Workflow completed successfully!")

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise
    finally:
        driver.disconnect()


if __name__ == "__main__":
    # Run examples
    print("\n")

    # Uncomment the examples you want to run:

    example_local_storage()
    # example_s3_storage()  # Requires AWS credentials
    # example_from_environment()
    # example_multiple_runs()
    # example_workflow_integration()

    print("\n")
    logger.info("All examples completed!")
