"""Tests for storage drivers, temp manager, and settings."""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta

from infrastructure.storage.drivers.local import LocalStorageDriver
from infrastructure.storage.temp_manager import TempStorageManager
from infrastructure.storage.s3_settings import (
    AWSSettings,
    S3StorageSettings,
    StorageDriverSettings,
    TempStorageSettings,
)


class TestLocalStorageDriver(unittest.TestCase):
    """Tests for LocalStorageDriver."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.driver = LocalStorageDriver(base_path=Path(self.tmpdir))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_connect(self):
        """Test connecting creates base directory."""
        self.driver.connect()
        self.assertTrue(self.driver._connected)
        self.assertTrue(Path(self.tmpdir).exists())

    def test_disconnect(self):
        """Test disconnecting sets connected to False."""
        self.driver.connect()
        self.driver.disconnect()
        self.assertFalse(self.driver._connected)

    def test_fetch_images_not_connected(self):
        """Test fetching images without connecting raises error."""
        with self.assertRaises(ConnectionError):
            self.driver.fetch_images("proj-1", Path("/tmp/dest"))

    def test_fetch_images_success(self):
        """Test fetching images copies them to destination."""
        self.driver.connect()
        proj_dir = Path(self.tmpdir) / "proj-1" / "images"
        proj_dir.mkdir(parents=True)
        (proj_dir / "img1.jpg").write_bytes(b"fake-jpeg")
        (proj_dir / "img2.tif").write_bytes(b"fake-tiff")
        (proj_dir / "readme.txt").write_text("not an image")

        dest = Path(self.tmpdir) / "output"
        images = self.driver.fetch_images("proj-1", dest)
        self.assertEqual(len(images), 2)
        self.assertTrue(all(p.exists() for p in images))

    def test_fetch_images_no_directory(self):
        """Test fetching images from nonexistent directory."""
        self.driver.connect()
        with self.assertRaises(FileNotFoundError):
            self.driver.fetch_images("nonexistent", Path("/tmp/dest"))

    def test_push_results_file(self):
        """Test pushing a single file."""
        self.driver.connect()
        src = Path(self.tmpdir) / "result.txt"
        src.write_text("result data")
        self.driver.push_results("proj-1", src, run_id=1)
        dest = Path(self.tmpdir) / "proj-1" / "run_1" / "result.txt"
        self.assertTrue(dest.exists())

    def test_push_results_directory(self):
        """Test pushing a directory of results."""
        self.driver.connect()
        src_dir = Path(self.tmpdir) / "src_results"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("a")
        sub = src_dir / "sub"
        sub.mkdir()
        (sub / "file2.txt").write_text("b")

        self.driver.push_results("proj-1", src_dir, run_id=2)
        dest = Path(self.tmpdir) / "proj-1" / "run_2"
        self.assertTrue((dest / "file1.txt").exists())
        self.assertTrue((dest / "sub" / "file2.txt").exists())

    def test_push_results_not_connected(self):
        """Test push results without connecting raises error."""
        with self.assertRaises(ConnectionError):
            self.driver.push_results("proj-1", Path("/tmp/file"), 1)

    def test_push_results_nonexistent_source(self):
        """Test push results with nonexistent source."""
        self.driver.connect()
        with self.assertRaises(FileNotFoundError):
            self.driver.push_results("proj-1", Path("/nonexistent"), 1)

    def test_list_images(self):
        """Test listing images for a project."""
        self.driver.connect()
        proj_dir = Path(self.tmpdir) / "proj-1" / "images"
        proj_dir.mkdir(parents=True)
        (proj_dir / "a.jpg").write_bytes(b"")
        (proj_dir / "b.png").write_bytes(b"")
        (proj_dir / "c.txt").write_text("")

        images = self.driver.list_images("proj-1")
        self.assertEqual(len(images), 2)
        self.assertIn("a.jpg", images)

    def test_list_images_empty(self):
        """Test listing images for nonexistent project."""
        self.driver.connect()
        images = self.driver.list_images("nonexistent")
        self.assertEqual(images, [])

    def test_list_images_not_connected(self):
        """Test listing images without connecting."""
        with self.assertRaises(ConnectionError):
            self.driver.list_images("proj-1")

    def test_exists(self):
        """Test checking if path exists."""
        self.driver.connect()
        (Path(self.tmpdir) / "testfile.txt").write_text("x")
        self.assertTrue(self.driver.exists("testfile.txt"))
        self.assertFalse(self.driver.exists("nonexistent.txt"))

    def test_delete_project(self):
        """Test deleting a project."""
        self.driver.connect()
        proj_dir = Path(self.tmpdir) / "proj-1"
        proj_dir.mkdir()
        (proj_dir / "data.txt").write_text("data")
        self.driver.delete_project("proj-1")
        self.assertFalse(proj_dir.exists())

    def test_delete_project_nonexistent(self):
        """Test deleting nonexistent project (should not raise)."""
        self.driver.connect()
        self.driver.delete_project("nonexistent")

    def test_delete_project_not_connected(self):
        """Test deleting project without connecting."""
        with self.assertRaises(ConnectionError):
            self.driver.delete_project("proj-1")


class TestS3StorageDriver(unittest.TestCase):
    """Tests for S3StorageDriver with mocked boto3."""

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    @patch("infrastructure.storage.drivers.s3.boto3")
    def test_connect_success(self, mock_boto3, mock_aws_settings):
        """Test successful S3 connection."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver

        driver = S3StorageDriver(
            bucket_name="test-bucket",
            region_name="us-east-1",
            aws_access_key_id="AKID",
            aws_secret_access_key="SECRET",
        )

        mock_client = MagicMock()
        mock_boto3.Session.return_value.client.return_value = mock_client

        driver.connect()
        self.assertTrue(driver._connected)
        mock_client.head_bucket.assert_called_with(Bucket="test-bucket")

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    @patch("infrastructure.storage.drivers.s3.boto3")
    def test_connect_bucket_not_found(self, mock_boto3, mock_aws_settings):
        """Test connection failure when bucket doesn't exist."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver
        from botocore.exceptions import ClientError

        driver = S3StorageDriver(
            bucket_name="nonexistent", region_name="us-east-1"
        )

        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadBucket"
        )
        mock_boto3.Session.return_value.client.return_value = mock_client

        with self.assertRaises(ConnectionError):
            driver.connect()

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    @patch("infrastructure.storage.drivers.s3.boto3")
    def test_connect_access_denied(self, mock_boto3, mock_aws_settings):
        """Test connection failure with access denied."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver
        from botocore.exceptions import ClientError

        driver = S3StorageDriver(
            bucket_name="restricted", region_name="us-east-1"
        )

        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "403"}}, "HeadBucket"
        )
        mock_boto3.Session.return_value.client.return_value = mock_client

        with self.assertRaises(ConnectionError):
            driver.connect()

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_disconnect(self, mock_aws_settings):
        """Test S3 disconnect."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver

        driver = S3StorageDriver(bucket_name="test", region_name="us-east-1")
        driver._connected = True
        driver.s3_client = MagicMock()
        driver.disconnect()
        self.assertFalse(driver._connected)
        self.assertIsNone(driver.s3_client)

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_get_s3_key(self, mock_aws_settings):
        """Test S3 key construction."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver

        driver = S3StorageDriver(
            bucket_name="test", region_name="us-east-1", prefix="photogear"
        )
        key = driver._get_s3_key("proj-1", "images", "img.jpg")
        self.assertEqual(key, "photogear/proj-1/images/img.jpg")

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_fetch_images_not_connected(self, mock_aws_settings):
        """Test fetch images when not connected."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver

        driver = S3StorageDriver(bucket_name="test", region_name="us-east-1")
        with self.assertRaises(ConnectionError):
            driver.fetch_images("proj-1", Path("/tmp/dest"))

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_exists_true(self, mock_aws_settings):
        """Test exists returns True for existing object."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver

        driver = S3StorageDriver(bucket_name="test", region_name="us-east-1")
        driver._connected = True
        driver.s3_client = MagicMock()
        driver.s3_client.head_object.return_value = {}

        self.assertTrue(driver.exists("proj-1/file.txt"))

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_exists_false(self, mock_aws_settings):
        """Test exists returns False for nonexistent object."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver
        from botocore.exceptions import ClientError

        driver = S3StorageDriver(bucket_name="test", region_name="us-east-1")
        driver._connected = True
        driver.s3_client = MagicMock()
        driver.s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )

        self.assertFalse(driver.exists("nonexistent.txt"))

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_list_images_not_connected(self, mock_aws_settings):
        """Test list images when not connected."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver

        driver = S3StorageDriver(bucket_name="test", region_name="us-east-1")
        with self.assertRaises(ConnectionError):
            driver.list_images("proj-1")

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_push_results_not_connected(self, mock_aws_settings):
        """Test push results when not connected."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver

        driver = S3StorageDriver(bucket_name="test", region_name="us-east-1")
        with self.assertRaises(ConnectionError):
            driver.push_results("proj-1", Path("/tmp/src"), 1)

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_delete_project_not_connected(self, mock_aws_settings):
        """Test delete project when not connected."""
        mock_aws_settings.return_value.use_aws_role = False
        from infrastructure.storage.drivers.s3 import S3StorageDriver

        driver = S3StorageDriver(bucket_name="test", region_name="us-east-1")
        with self.assertRaises(ConnectionError):
            driver.delete_project("proj-1")

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_use_aws_role(self, mock_aws_settings):
        """Test that AWS role mode clears credentials."""
        mock_aws_settings.return_value.use_aws_role = True
        from infrastructure.storage.drivers.s3 import S3StorageDriver

        driver = S3StorageDriver(
            bucket_name="test",
            region_name="us-east-1",
            aws_access_key_id="AKID",
            aws_secret_access_key="SECRET",
        )
        self.assertIsNone(driver.aws_access_key_id)
        self.assertIsNone(driver.aws_secret_access_key)


class TestTempStorageManager(unittest.TestCase):
    """Tests for TempStorageManager."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.settings = TempStorageSettings(
            base_path=self.tmpdir, cleanup_days=1
        )
        self.manager = TempStorageManager(self.settings)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_job_dir(self):
        """Test creating/getting job directory."""
        job_dir = self.manager.get_job_dir("job-1")
        self.assertTrue(job_dir.exists())
        self.assertTrue((job_dir / ".timestamp").exists())

    def test_get_subdirectory(self):
        """Test creating subdirectory within job folder."""
        sub = self.manager.get_subdirectory("job-1", "sfm")
        self.assertTrue(sub.exists())
        self.assertTrue(sub.name == "sfm")

    def test_get_service_job_dir(self):
        """Test service-specific job directory."""
        sdir = self.manager.get_service_job_dir("job-1", "sfm")
        self.assertTrue(sdir.exists())
        self.assertIn("sfm", str(sdir))
        self.assertTrue((sdir / ".timestamp").exists())

    def test_get_dataset_dir(self):
        """Test getting dataset directory."""
        ds_dir = self.manager.get_dataset_dir("ds-1")
        self.assertTrue(ds_dir.exists())
        self.assertIn("datasets", str(ds_dir))

    def test_get_dataset_images_dir(self):
        """Test getting dataset images directory."""
        img_dir = self.manager.get_dataset_images_dir("ds-1")
        self.assertTrue(img_dir.exists())
        self.assertEqual(img_dir.name, "images")

    def test_dataset_images_exist_false(self):
        """Test dataset images don't exist."""
        self.assertFalse(self.manager.dataset_images_exist("ds-nonexist"))

    def test_dataset_images_exist_true(self):
        """Test dataset images exist."""
        img_dir = self.manager.get_dataset_images_dir("ds-1")
        (img_dir / "test.jpg").write_bytes(b"fake")
        self.assertTrue(self.manager.dataset_images_exist("ds-1"))

    def test_dataset_images_exist_empty_dir(self):
        """Test dataset images dir exists but empty."""
        self.manager.get_dataset_images_dir("ds-empty")
        self.assertFalse(self.manager.dataset_images_exist("ds-empty"))

    def test_delete_job(self):
        """Test deleting a job directory."""
        self.manager.get_job_dir("del-job")
        result = self.manager.delete_job("del-job")
        self.assertTrue(result)
        self.assertFalse(
            (Path(self.tmpdir) / "jobs" / "del-job").exists()
        )

    def test_delete_job_nonexistent(self):
        """Test deleting nonexistent job."""
        result = self.manager.delete_job("nonexistent")
        self.assertFalse(result)

    def test_update_job_timestamp(self):
        """Test updating job timestamp."""
        job_dir = self.manager.get_job_dir("ts-job")
        ts_file = job_dir / ".timestamp"
        import time
        old_mtime = ts_file.stat().st_mtime
        time.sleep(0.05)
        self.manager.update_job_timestamp("ts-job")
        new_mtime = ts_file.stat().st_mtime
        self.assertGreater(new_mtime, old_mtime)

    def test_cleanup_old_jobs(self):
        """Test cleaning up old job directories."""
        job_dir = self.manager.get_job_dir("old-job")
        ts_file = job_dir / ".timestamp"
        old_time = datetime.now() - timedelta(days=5)
        import os
        os.utime(ts_file, (old_time.timestamp(), old_time.timestamp()))
        count = self.manager.cleanup_old_jobs()
        self.assertEqual(count, 1)
        self.assertFalse(job_dir.exists())

    def test_cleanup_preserves_recent(self):
        """Test cleanup preserves recent jobs."""
        self.manager.get_job_dir("recent-job")
        count = self.manager.cleanup_old_jobs()
        self.assertEqual(count, 0)

    def test_cleanup_dry_run(self):
        """Test cleanup dry run doesn't delete."""
        job_dir = self.manager.get_job_dir("dry-job")
        ts_file = job_dir / ".timestamp"
        old_time = datetime.now() - timedelta(days=5)
        import os
        os.utime(ts_file, (old_time.timestamp(), old_time.timestamp()))
        count = self.manager.cleanup_old_jobs(dry_run=True)
        self.assertEqual(count, 0)
        self.assertTrue(job_dir.exists())


class TestS3Settings(unittest.TestCase):
    """Tests for S3 storage settings."""

    @patch.dict("os.environ", {
        "AWS_S3_ACCESS_KEY_ID": "test-key",
        "AWS_S3_SECRET_ACCESS_KEY": "test-secret",
        "AWS_S3_REGION_NAME": "us-west-2",
        "AWS_S3_RAW_IMAGES_BUCKET": "raw-imgs",
        "AWS_S3_AI_BUCKET": "ai-data",
        "AWS_S3_RESULTS_BUCKET": "results",
        "USE_AWS_ROLE": "false",
    }, clear=False)
    def test_s3_settings_from_env(self):
        """Test S3 settings loaded from environment."""
        settings = S3StorageSettings(
            access_key_id="test-key",
            secret_access_key="test-secret",
            region_name="us-west-2",
            raw_images_bucket="raw-imgs",
            ai_bucket="ai-data",
            results_bucket="results",
            use_aws_role=False,
        )
        self.assertEqual(settings.region_name, "us-west-2")
        self.assertTrue(settings.has_explicit_credentials)

    def test_s3_settings_no_credentials(self):
        """Test S3 settings without credentials."""
        settings = S3StorageSettings(
            region_name="us-east-1",
            raw_images_bucket="raw",
            ai_bucket="ai",
            results_bucket="res",
            access_key_id=None,
            secret_access_key=None,
        )
        self.assertFalse(settings.has_explicit_credentials)

    def test_temp_storage_settings_defaults(self):
        """Test TempStorageSettings default values."""
        settings = TempStorageSettings()
        self.assertEqual(settings.base_path, "/app/data/temp")
        self.assertEqual(settings.cleanup_days, 1)

    def test_storage_driver_settings_defaults(self):
        """Test StorageDriverSettings default values."""
        with patch.dict("os.environ", {}, clear=True):
            settings = StorageDriverSettings(_env_file=None)
            self.assertEqual(settings.driver, "local")
            self.assertFalse(settings.has_explicit_credentials)


if __name__ == "__main__":
    unittest.main()
