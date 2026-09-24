"""
Test script for PresignedUrlStorageDriver.

This script tests the basic functionality of the presigned URL driver
using mocked HTTP responses.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import Mock, patch

from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.presigned_url import PresignedUrlStorageDriver

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def test_basic_functionality():
    """Test basic driver functionality."""
    logger.info("=" * 60)
    logger.info("Test: Basic Driver Functionality")
    logger.info("=" * 60)

    driver = PresignedUrlStorageDriver(
        timeout=30,
        project_urls={
            "test_project": {
                "download_url": "https://example.com/download",
                "upload_url": "https://example.com/upload",
            },
        },
    )
    driver.connect()

    logger.info("✓ Driver created and URLs configured")

    # Test that URLs are stored
    urls = driver._get_project_urls("test_project")
    assert urls["download_url"] == "https://example.com/download"
    assert urls["upload_url"] == "https://example.com/upload"

    logger.info("✓ Project URLs retrieved correctly")

    driver.disconnect()
    logger.info("✓ Test passed!")


def test_json_parsing():
    """Test JSON response parsing for different formats."""
    logger.info("=" * 60)
    logger.info("Test: JSON Response Parsing")
    logger.info("=" * 60)

    driver = PresignedUrlStorageDriver()

    # Test Format 1: images with url and filename
    format1 = {
        "images": [
            {"url": "https://example.com/img1.jpg", "filename": "img1.jpg"},
            {"url": "https://example.com/img2.jpg", "filename": "img2.jpg"},
        ],
    }
    result1 = driver._parse_image_urls(format1)
    assert len(result1) == 2
    assert result1[0]["filename"] == "img1.jpg"
    logger.info("✓ Format 1 (images array) parsed correctly")

    # Test Format 2: simple urls array
    format2 = {
        "urls": [
            "https://example.com/img1.jpg",
            "https://example.com/img2.jpg",
        ],
    }
    result2 = driver._parse_image_urls(format2)
    assert len(result2) == 2
    logger.info("✓ Format 2 (urls array) parsed correctly")

    # Test Format 3: files with name
    format3 = {
        "files": [
            {"url": "https://example.com/img1.jpg", "name": "img1.jpg"},
        ],
    }
    result3 = driver._parse_image_urls(format3)
    assert len(result3) == 1
    logger.info("✓ Format 3 (files with name) parsed correctly")

    # Test Format 4: nested data
    format4 = {
        "status": "success",
        "data": {
            "images": [
                {"url": "https://example.com/img1.jpg"},
            ],
        },
    }
    result4 = driver._parse_image_urls(format4)
    assert len(result4) == 1
    logger.info("✓ Format 4 (nested data) parsed correctly")

    logger.info("✓ All JSON formats parsed correctly!")


def test_filename_extraction():
    """Test filename extraction from URLs."""
    logger.info("=" * 60)
    logger.info("Test: Filename Extraction")
    logger.info("=" * 60)

    driver = PresignedUrlStorageDriver()

    # Test URL with clear filename
    url1 = "https://bucket.s3.amazonaws.com/path/to/image1.jpg?signature=xyz"
    filename1 = driver._extract_filename_from_url(url1)
    assert filename1 == "image1.jpg"
    logger.info(f"✓ Extracted '{filename1}' from URL with query params")

    # Test URL with path
    url2 = "https://example.com/images/DJI_001.TIF"
    filename2 = driver._extract_filename_from_url(url2)
    assert filename2 == "DJI_001.TIF"
    logger.info(f"✓ Extracted '{filename2}' from simple path")

    # Test URL without filename (generates hash)
    url3 = "https://example.com/getimage?id=123"
    filename3 = driver._extract_filename_from_url(url3)
    assert filename3.startswith("image_")
    assert filename3.endswith(".jpg")
    logger.info(f"✓ Generated '{filename3}' for URL without filename")

    logger.info("✓ Filename extraction works correctly!")


def test_mocked_fetch_images():
    """Test fetch_images with mocked HTTP responses."""
    logger.info("=" * 60)
    logger.info("Test: Fetch Images (Mocked)")
    logger.info("=" * 60)

    driver = PresignedUrlStorageDriver(
        timeout=30,
        project_urls={
            "test_project": {
                "download_url": "https://example.com/download",
                "upload_url": "https://example.com/upload",
            },
        },
    )
    driver.connect()

    # Create temporary directory for testing
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        dest_path = Path(tmpdir) / "images"

        # Mock the HTTP requests
        with patch.object(driver.session, "get") as mock_get:
            # First call: get list of images
            list_response = Mock()
            list_response.json.return_value = {
                "images": [
                    {"url": "https://example.com/img1.jpg", "filename": "img1.jpg"},
                    {"url": "https://example.com/img2.jpg", "filename": "img2.jpg"},
                ],
            }
            list_response.raise_for_status = Mock()

            # Subsequent calls: download images
            img_response = Mock()
            img_response.content = b"fake image data"
            img_response.raise_for_status = Mock()

            # Configure mock to return different responses
            mock_get.side_effect = [list_response, img_response, img_response]

            # Fetch images
            images = driver.fetch_images("test_project", dest_path)

            # Verify results
            assert len(images) == 2
            assert images[0].name == "img1.jpg"
            assert images[1].name == "img2.jpg"
            assert images[0].read_bytes() == b"fake image data"

            logger.info(f"✓ Fetched {len(images)} images successfully")
            logger.info(f"✓ Images saved to {dest_path}")

    driver.disconnect()
    logger.info("✓ Test passed!")


def test_mocked_push_results():
    """Test push_results with mocked HTTP responses."""
    logger.info("=" * 60)
    logger.info("Test: Push Results (Mocked)")
    logger.info("=" * 60)

    driver = PresignedUrlStorageDriver(
        timeout=30,
        project_urls={
            "test_project": {
                "download_url": "https://example.com/download",
                "upload_url": "https://example.com/upload",
            },
        },
    )
    driver.connect()

    # Create temporary directory with test files
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / "results"
        source_path.mkdir()

        # Create some test files
        (source_path / "result.txt").write_text("test result")
        (source_path / "output").mkdir()
        (source_path / "output" / "data.bin").write_bytes(b"binary data")

        # Mock the HTTP requests
        with patch.object(driver.session, "post") as mock_post:
            post_response = Mock()
            post_response.raise_for_status = Mock()
            mock_post.return_value = post_response

            # Push results
            driver.push_results("test_project", source_path, run_id=1)

            # Verify that POST was called
            assert mock_post.call_count == 2  # 2 files
            logger.info("✓ Uploaded 2 files successfully")

    driver.disconnect()
    logger.info("✓ Test passed!")


def test_list_images():
    """Test list_images functionality."""
    logger.info("=" * 60)
    logger.info("Test: List Images (Mocked)")
    logger.info("=" * 60)

    driver = PresignedUrlStorageDriver(
        timeout=30,
        project_urls={
            "test_project": {
                "download_url": "https://example.com/download",
                "upload_url": "https://example.com/upload",
            },
        },
    )
    driver.connect()

    # Mock the HTTP request
    with patch.object(driver.session, "get") as mock_get:
        response = Mock()
        response.json.return_value = {
            "images": [
                {"url": "https://example.com/img1.jpg", "filename": "DJI_001.jpg"},
                {"url": "https://example.com/img2.jpg", "filename": "DJI_002.jpg"},
                {"url": "https://example.com/img3.jpg", "filename": "DJI_003.jpg"},
            ],
        }
        response.raise_for_status = Mock()
        mock_get.return_value = response

        # List images
        images = driver.list_images("test_project")

        assert len(images) == 3
        assert "DJI_001.jpg" in images
        assert "DJI_002.jpg" in images
        assert "DJI_003.jpg" in images

        logger.info(f"✓ Listed {len(images)} images: {images}")

    driver.disconnect()
    logger.info("✓ Test passed!")


def test_integration_with_dataset():
    """Test integration with Dataset class."""
    logger.info("=" * 60)
    logger.info("Test: Integration with Dataset")
    logger.info("=" * 60)

    driver = PresignedUrlStorageDriver(
        timeout=30,
        project_urls={
            "test_project": {
                "download_url": "https://example.com/download",
                "upload_url": "https://example.com/upload",
            },
        },
    )
    driver.connect()

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dataset
        dataset = Dataset(
            project_id="test_project",
            storage_driver=driver,
            temp_base_path=Path(tmpdir),
        )

        # Initialize
        dataset.initialize_dataset()
        logger.info("✓ Dataset initialized")

        # Create run
        run_path = dataset.create_run()
        assert run_path.exists()
        logger.info(f"✓ Run directory created: {run_path}")

        # Get run path
        retrieved_path = dataset.get_run_path()
        assert retrieved_path == run_path
        logger.info("✓ Run path retrieved correctly")

        # Create some files
        (run_path / "result.txt").write_text("test")

        # Mock push_results
        with patch.object(driver, "push_results") as mock_push:
            dataset.push_results()
            mock_push.assert_called_once()
            logger.info("✓ Push results called correctly")

    driver.disconnect()
    logger.info("✓ Test passed!")


def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("RUNNING ALL TESTS FOR PRESIGNED URL DRIVER")
    logger.info("=" * 60 + "\n")

    try:
        test_basic_functionality()
        print()

        test_json_parsing()
        print()

        test_filename_extraction()
        print()

        test_mocked_fetch_images()
        print()

        test_mocked_push_results()
        print()

        test_list_images()
        print()

        test_integration_with_dataset()
        print()

        logger.info("=" * 60)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("=" * 60)

    except AssertionError as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
