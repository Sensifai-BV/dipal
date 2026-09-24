"""Unit tests for Dataset class and StorageDriverFactory."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.factory import StorageDriverFactory
from infrastructure.storage.drivers.base import StorageDriver


class TestDatasetInit(unittest.TestCase):
    """Tests for Dataset initialization."""

    def test_init_defaults(self):
        mock_driver = MagicMock()
        ds = Dataset("proj1", mock_driver)
        self.assertEqual(ds.project_id, "proj1")
        self.assertEqual(ds.storage_driver, mock_driver)
        self.assertEqual(ds.temp_base_path, Path("/app/data/temp"))
        self.assertIsNone(ds._current_run_id)

    def test_init_custom_base_path(self):
        mock_driver = MagicMock()
        ds = Dataset("proj1", mock_driver, temp_base_path=Path("/tmp/custom"))
        self.assertEqual(ds.temp_base_path, Path("/tmp/custom"))


class TestDatasetWorkspace(unittest.TestCase):
    """Tests for Dataset workspace operations."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.mock_driver = MagicMock()
        self.ds = Dataset("proj1", self.mock_driver, temp_base_path=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_initialize_dataset(self):
        self.ds.initialize_dataset()
        self.assertTrue(self.ds.project_temp_path.exists())
        self.assertTrue(self.ds.images_path.exists())

    def test_create_run(self):
        self.ds.initialize_dataset()
        run_path = self.ds.create_run()
        self.assertTrue(run_path.exists())
        self.assertEqual(self.ds._current_run_id, 1)

    def test_create_multiple_runs(self):
        self.ds.initialize_dataset()
        self.ds.create_run()
        self.ds.create_run()
        self.assertEqual(self.ds._current_run_id, 2)

    def test_get_run_path_current(self):
        self.ds.initialize_dataset()
        expected = self.ds.create_run()
        self.assertEqual(self.ds.get_run_path(), expected)

    def test_get_run_path_specific(self):
        self.ds.initialize_dataset()
        path = self.ds.get_run_path(5)
        self.assertTrue(str(path).endswith("run_5"))

    def test_get_run_path_no_current(self):
        with self.assertRaises(ValueError):
            self.ds.get_run_path()

    def test_get_images_path(self):
        self.assertEqual(self.ds.get_images_path(), self.ds.images_path)

    def test_current_run_id(self):
        self.assertIsNone(self.ds.current_run_id)
        self.ds.initialize_dataset()
        self.ds.create_run()
        self.assertEqual(self.ds.current_run_id, 1)

    def test_list_images(self):
        self.mock_driver.list_images.return_value = ["a.jpg", "b.tif"]
        result = self.ds.list_images()
        self.assertEqual(result, ["a.jpg", "b.tif"])
        self.mock_driver.list_images.assert_called_once_with("proj1")


class TestDatasetFetch(unittest.TestCase):
    """Tests for Dataset.fetch_images."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.mock_driver = MagicMock()
        self.ds = Dataset("proj1", self.mock_driver, temp_base_path=self.tmpdir)
        self.ds.initialize_dataset()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_fetch_images_downloads(self):
        self.mock_driver.fetch_images.return_value = [Path("a.jpg")]
        result = self.ds.fetch_images()
        self.assertEqual(result, self.ds.images_path)
        self.mock_driver.fetch_images.assert_called_once()

    def test_fetch_images_skip_if_local(self):
        (self.ds.images_path / "existing.jpg").write_text("fake")
        result = self.ds.fetch_images()
        self.assertEqual(result, self.ds.images_path)
        self.mock_driver.fetch_images.assert_not_called()

    def test_fetch_images_download_if_no_images(self):
        (self.ds.images_path / "readme.txt").write_text("text")
        self.mock_driver.fetch_images.return_value = [Path("a.jpg")]
        self.ds.fetch_images()
        self.mock_driver.fetch_images.assert_called_once()


class TestDatasetPushResults(unittest.TestCase):
    """Tests for Dataset.push_results."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.mock_driver = MagicMock()
        self.ds = Dataset("proj1", self.mock_driver, temp_base_path=self.tmpdir)
        self.ds.initialize_dataset()
        self.ds.create_run()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_push_results_current_run(self):
        self.ds.push_results()
        self.mock_driver.push_results.assert_called_once()

    def test_push_results_custom_path(self):
        p = self.tmpdir / "custom"
        p.mkdir()
        self.ds.push_results(source_path=p, run_id=99)
        self.mock_driver.push_results.assert_called_once_with(
            project_id="proj1", source_path=p, run_id=99,
        )

    def test_push_results_no_current_run(self):
        ds = Dataset("proj2", self.mock_driver, temp_base_path=self.tmpdir)
        with self.assertRaises(ValueError):
            ds.push_results()


class TestDatasetCleanup(unittest.TestCase):
    """Tests for Dataset.cleanup."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.mock_driver = MagicMock()
        self.ds = Dataset("proj1", self.mock_driver, temp_base_path=self.tmpdir)
        self.ds.initialize_dataset()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cleanup_all(self):
        self.ds.cleanup()
        self.assertFalse(self.ds.project_temp_path.exists())

    def test_cleanup_keep_results(self):
        (self.ds.images_path / "img.jpg").write_text("fake")
        run_dir = self.ds.create_run()
        (run_dir / "result.tif").write_text("result")
        self.ds.cleanup(keep_results=True)
        self.assertFalse(self.ds.images_path.exists())
        self.assertTrue(run_dir.exists())


class TestStorageDriverFactory(unittest.TestCase):
    """Tests for StorageDriverFactory."""

    def test_create_local(self):
        tmpdir = tempfile.mkdtemp()
        try:
            driver = StorageDriverFactory.create("local", {"base_path": tmpdir})
            self.assertIsNotNone(driver)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_create_unsupported(self):
        with self.assertRaises(ValueError):
            StorageDriverFactory.create("ftp", {})

    def test_create_invalid_config(self):
        with self.assertRaises(ValueError):
            StorageDriverFactory.create("local", {"nonexistent_param": True})

    @patch("infrastructure.storage.drivers.factory.StorageDriverSettings")
    def test_create_from_env_local(self, mock_settings_cls):
        mock_settings_cls.return_value = MagicMock(
            driver="local", base_path="/tmp/store"
        )
        driver = StorageDriverFactory.create_from_env("local")
        self.assertIsNotNone(driver)

    @patch("infrastructure.storage.drivers.factory.StorageDriverSettings")
    @patch("infrastructure.storage.drivers.factory.S3StorageDriver")
    def test_create_from_env_s3_with_role(self, mock_s3, mock_settings_cls):
        mock_settings_cls.return_value = MagicMock(
            driver="s3", bucket_name="bucket", region="us-east-1",
            prefix="pg", use_aws_role=True,
        )
        mock_s3.return_value = MagicMock()
        StorageDriverFactory.create_from_env("s3")

    @patch("infrastructure.storage.drivers.factory.StorageDriverSettings")
    @patch("infrastructure.storage.drivers.factory.S3StorageDriver")
    def test_create_from_env_s3_with_creds(self, mock_s3, mock_settings_cls):
        mock_settings_cls.return_value = MagicMock(
            driver="s3", bucket_name="bucket", region="us-east-1",
            prefix="pg", use_aws_role=False,
            access_key_id="K", secret_access_key="S",
        )
        mock_s3.return_value = MagicMock()
        StorageDriverFactory.create_from_env("s3")

    @patch("infrastructure.storage.drivers.factory.StorageDriverSettings")
    def test_create_from_env_s3_no_bucket(self, mock_settings_cls):
        mock_settings_cls.return_value = MagicMock(
            driver="s3", bucket_name="",
        )
        with self.assertRaises(ValueError):
            StorageDriverFactory.create_from_env("s3")

    @patch("infrastructure.storage.drivers.factory.StorageDriverSettings")
    def test_create_from_env_presigned(self, mock_settings_cls):
        mock_settings_cls.return_value = MagicMock(
            driver="presigned_url", presigned_url_timeout=300,
        )
        driver = StorageDriverFactory.create_from_env("presigned_url")
        self.assertIsNotNone(driver)

    @patch("infrastructure.storage.drivers.factory.StorageDriverSettings")
    def test_create_from_env_unknown(self, mock_settings_cls):
        mock_settings_cls.return_value = MagicMock(driver="ftp")
        with self.assertRaises(ValueError):
            StorageDriverFactory.create_from_env("ftp")

    def test_register_driver(self):
        class CustomDriver(StorageDriver):
            def connect(self): pass
            def disconnect(self): pass
            def fetch_images(self, project_id, destination_path): pass
            def push_results(self, project_id, source_path, run_id): pass
        StorageDriverFactory.register_driver("custom", CustomDriver)
        self.assertIn("custom", StorageDriverFactory._drivers)
        del StorageDriverFactory._drivers["custom"]

    def test_register_driver_invalid(self):
        with self.assertRaises(TypeError):
            StorageDriverFactory.register_driver("bad", dict)


if __name__ == "__main__":
    unittest.main()
