"""Unit tests for PresignedUrlStorageDriver."""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import shutil
import sys

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from infrastructure.storage.drivers.presigned_url import PresignedUrlStorageDriver


class TestPresignedUrlDriverInit(unittest.TestCase):
    """Tests for PresignedUrlStorageDriver initialization."""

    def test_default_init(self):
        driver = PresignedUrlStorageDriver()
        self.assertEqual(driver.project_urls, {})
        self.assertEqual(driver.timeout, 300)
        self.assertFalse(driver._connected)

    def test_custom_init(self):
        urls = {"p1": {"download_url": "https://dl", "upload_url": "https://ul"}}
        driver = PresignedUrlStorageDriver(project_urls=urls, timeout=60)
        self.assertEqual(driver.project_urls, urls)
        self.assertEqual(driver.timeout, 60)


class TestPresignedUrlDriverConnect(unittest.TestCase):
    """Tests for connect / disconnect."""

    def test_connect(self):
        driver = PresignedUrlStorageDriver()
        driver.connect()
        self.assertTrue(driver._connected)

    def test_disconnect(self):
        driver = PresignedUrlStorageDriver()
        driver.connect()
        driver.disconnect()
        self.assertFalse(driver._connected)


class TestPresignedUrlDriverGetUrls(unittest.TestCase):
    """Tests for _get_project_urls."""

    def test_known_project(self):
        urls = {"p1": {"download_url": "https://dl"}}
        driver = PresignedUrlStorageDriver(project_urls=urls)
        result = driver._get_project_urls("p1")
        self.assertEqual(result["download_url"], "https://dl")

    def test_unknown_project(self):
        driver = PresignedUrlStorageDriver()
        with self.assertRaises(ValueError):
            driver._get_project_urls("missing")


class TestPresignedUrlDriverParseUrls(unittest.TestCase):
    """Tests for _parse_image_urls."""

    def setUp(self):
        self.driver = PresignedUrlStorageDriver()

    def test_parse_images_key(self):
        data = {"images": [{"url": "https://a", "filename": "1.jpg"}]}
        result = self.driver._parse_image_urls(data)
        self.assertEqual(len(result), 1)

    def test_parse_urls_key(self):
        data = {"urls": ["https://a", "https://b"]}
        result = self.driver._parse_image_urls(data)
        self.assertEqual(len(result), 2)

    def test_parse_files_key(self):
        data = {"files": [{"url": "https://a", "name": "1.jpg"}]}
        result = self.driver._parse_image_urls(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["filename"], "1.jpg")

    def test_parse_nested_data(self):
        data = {"data": {"images": ["https://a"]}}
        result = self.driver._parse_image_urls(data)
        self.assertEqual(len(result), 1)

    def test_parse_fallback_list(self):
        data = {"custom_key": ["https://a", "https://b"]}
        result = self.driver._parse_image_urls(data)
        self.assertEqual(len(result), 2)

    def test_parse_empty(self):
        data = {"info": "no images"}
        result = self.driver._parse_image_urls(data)
        self.assertEqual(result, [])


class TestPresignedUrlDriverFilename(unittest.TestCase):
    """Tests for _extract_filename_from_url."""

    def setUp(self):
        self.driver = PresignedUrlStorageDriver()

    def test_simple_url(self):
        result = self.driver._extract_filename_from_url(
            "https://bucket.s3.amazonaws.com/images/photo.jpg"
        )
        self.assertEqual(result, "photo.jpg")

    def test_url_with_params(self):
        result = self.driver._extract_filename_from_url(
            "https://bucket.s3.amazonaws.com/img.tif?X-Amz-Algorithm=AWS4"
        )
        self.assertEqual(result, "img.tif")

    def test_no_filename(self):
        result = self.driver._extract_filename_from_url("https://example.com/")
        self.assertIn("image_", result)
        self.assertTrue(result.endswith(".jpg"))


class TestPresignedUrlDriverFetch(unittest.TestCase):
    """Tests for fetch_images."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_not_connected(self):
        driver = PresignedUrlStorageDriver(
            project_urls={"p1": {"download_url": "https://dl"}}
        )
        with self.assertRaises(ConnectionError):
            driver.fetch_images("p1", Path(self.tmpdir))

    def test_fetch_with_direct_images(self):
        urls = {
            "p1": {
                "images": [
                    {"url": "https://example.com/1.jpg", "filename": "1.jpg"},
                ],
            }
        }
        driver = PresignedUrlStorageDriver(project_urls=urls)
        driver.connect()

        mock_response = MagicMock()
        mock_response.content = b"fake-image-data"
        mock_response.raise_for_status = MagicMock()

        driver.session = MagicMock()
        driver.session.get.return_value = mock_response

        result = driver.fetch_images("p1", Path(self.tmpdir))
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].exists())

    def test_fetch_skip_existing(self):
        urls = {
            "p1": {
                "images": [
                    {"url": "https://example.com/1.jpg", "filename": "1.jpg"},
                ],
            }
        }
        driver = PresignedUrlStorageDriver(project_urls=urls)
        driver.connect()

        existing_file = Path(self.tmpdir) / "1.jpg"
        existing_file.write_bytes(b"existing-data")

        result = driver.fetch_images("p1", Path(self.tmpdir))
        self.assertEqual(len(result), 1)

    def test_fetch_no_images(self):
        urls = {"p1": {"download_url": "https://dl"}}
        driver = PresignedUrlStorageDriver(project_urls=urls)
        driver.connect()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"info": "nothing"}

        driver.session = MagicMock()
        driver.session.get.return_value = mock_resp

        with self.assertRaises(FileNotFoundError):
            driver.fetch_images("p1", Path(self.tmpdir))


class TestPresignedUrlDriverPush(unittest.TestCase):
    """Tests for push_results."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_not_connected(self):
        driver = PresignedUrlStorageDriver(
            project_urls={"p1": {"upload_url": "https://ul"}}
        )
        with self.assertRaises(ConnectionError):
            driver.push_results("p1", Path(self.tmpdir), run_id=1)

    def test_source_not_exists(self):
        driver = PresignedUrlStorageDriver(
            project_urls={"p1": {"upload_url": "https://ul"}}
        )
        driver.connect()
        with self.assertRaises(FileNotFoundError):
            driver.push_results("p1", Path("/nonexistent/path"), run_id=1)

    def test_push_single_file(self):
        urls = {"p1": {"upload_url": "https://ul"}}
        driver = PresignedUrlStorageDriver(project_urls=urls)
        driver.connect()

        test_file = Path(self.tmpdir) / "result.tif"
        test_file.write_bytes(b"tiff-data")

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        driver.session = MagicMock()
        driver.session.post.return_value = mock_resp

        driver.push_results("p1", test_file, run_id=1)
        driver.session.post.assert_called_once()

    def test_push_directory(self):
        urls = {"p1": {"upload_url": "https://ul"}}
        driver = PresignedUrlStorageDriver(project_urls=urls)
        driver.connect()

        (Path(self.tmpdir) / "a.tif").write_bytes(b"data1")
        (Path(self.tmpdir) / "b.tif").write_bytes(b"data2")

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        driver.session = MagicMock()
        driver.session.post.return_value = mock_resp

        driver.push_results("p1", Path(self.tmpdir), run_id=1)
        self.assertEqual(driver.session.post.call_count, 2)

    def test_push_empty_dir(self):
        urls = {"p1": {"upload_url": "https://ul"}}
        driver = PresignedUrlStorageDriver(project_urls=urls)
        driver.connect()

        empty = Path(self.tmpdir) / "empty"
        empty.mkdir()

        driver.session = MagicMock()
        driver.push_results("p1", empty, run_id=1)


class TestPresignedUrlDriverContentType(unittest.TestCase):
    """Tests for _get_content_type."""

    def test_content_type_tif(self):
        driver = PresignedUrlStorageDriver()
        ct = driver._get_content_type(Path("image.tif"))
        self.assertIn("tif", ct.lower())

    def test_content_type_jpg(self):
        driver = PresignedUrlStorageDriver()
        ct = driver._get_content_type(Path("photo.jpg"))
        self.assertIn("image", ct.lower())


if __name__ == "__main__":
    unittest.main()
