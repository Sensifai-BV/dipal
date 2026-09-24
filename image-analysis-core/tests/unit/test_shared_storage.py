"""Unit tests for infrastructure/storage/shared_storage (local, EFS, factory, settings)."""
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import sys

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from infrastructure.storage.shared_storage.settings import (
    SharedStorageSettings,
    EFSSettings,
)
from infrastructure.storage.shared_storage.local_storage import LocalSharedStorage
from infrastructure.storage.shared_storage.factory import SharedStorageFactory


class TestSharedStorageSettings(unittest.TestCase):
    """Tests for SharedStorageSettings."""

    def test_default_mode(self):
        s = SharedStorageSettings(_env_file=None)
        self.assertEqual(s.mode, "local")


class TestEFSSettings(unittest.TestCase):
    """Tests for EFSSettings."""

    def test_defaults(self):
        s = EFSSettings(_env_file=None)
        self.assertEqual(s.mount_point, "/app/data/temp")
        self.assertEqual(s.aws_region, "eu-north-1")
        self.assertEqual(s.file_system_id, "")


class TestLocalSharedStorage(unittest.TestCase):
    """Tests for LocalSharedStorage."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from infrastructure.storage.s3_settings import TempStorageSettings

        self.settings = TempStorageSettings(
            base_path=self.tmpdir, cleanup_after_days=7, _env_file=None
        )
        self.storage = LocalSharedStorage(settings=self.settings)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_base_path(self):
        self.assertEqual(self.storage.get_base_path(), Path(self.tmpdir))

    def test_get_dataset_path(self):
        p = self.storage.get_dataset_path("ds1")
        self.assertEqual(p, Path(self.tmpdir) / "datasets" / "ds1")

    def test_get_job_workspace(self):
        p = self.storage.get_job_workspace("j1", "sfm")
        self.assertEqual(p, Path(self.tmpdir) / "jobs" / "sfm" / "j1")

    def test_ensure_directory(self):
        p = Path(self.tmpdir) / "a" / "b" / "c"
        result = self.storage.ensure_directory(p)
        self.assertTrue(p.exists())
        self.assertEqual(result, p)

    def test_cleanup_job(self):
        job_dir = Path(self.tmpdir) / "jobs" / "sfm" / "j1"
        job_dir.mkdir(parents=True)
        (job_dir / "data.txt").write_text("test")
        self.storage.cleanup_job("j1")
        self.assertFalse(job_dir.exists())

    def test_cleanup_job_no_jobs_dir(self):
        self.storage.cleanup_job("j999")

    def test_cleanup_dataset(self):
        ds_dir = Path(self.tmpdir) / "datasets" / "ds1"
        ds_dir.mkdir(parents=True)
        (ds_dir / "img.jpg").write_text("x")
        self.storage.cleanup_dataset("ds1")
        self.assertFalse(ds_dir.exists())

    def test_cleanup_dataset_not_exists(self):
        self.storage.cleanup_dataset("missing")

    def test_cleanup_stale(self):
        old_dir = Path(self.tmpdir) / "datasets" / "old"
        old_dir.mkdir(parents=True)
        old_time = time.time() - (10 * 86400)
        os.utime(old_dir, (old_time, old_time))

        new_dir = Path(self.tmpdir) / "datasets" / "new"
        new_dir.mkdir(parents=True)

        cleaned = self.storage.cleanup_stale(max_age_days=5)
        self.assertGreater(len(cleaned), 0)
        self.assertTrue(new_dir.exists())

    def test_cleanup_stale_empty(self):
        cleaned = self.storage.cleanup_stale(max_age_days=1)
        self.assertEqual(cleaned, [])

    def test_get_disk_usage(self):
        usage = self.storage.get_disk_usage()
        self.assertIn("total", usage)
        self.assertIn("used", usage)
        self.assertIn("free", usage)
        self.assertIn("percent_used", usage)
        self.assertGreater(usage["total"], 0)

    def test_is_healthy(self):
        self.assertTrue(self.storage.is_healthy())

    def test_is_healthy_failure(self):
        self.storage._base_path = Path("/nonexistent/path/xyz123")
        self.assertFalse(self.storage.is_healthy())


class TestEFSSharedStorage(unittest.TestCase):
    """Tests for EFSSharedStorage."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.settings = EFSSettings(
            mount_point=self.tmpdir,
            file_system_id="fs-test123",
            _env_file=None,
        )
        from infrastructure.storage.shared_storage.efs_storage import EFSSharedStorage
        self.storage = EFSSharedStorage(settings=self.settings)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_base_path(self):
        self.assertEqual(self.storage.get_base_path(), Path(self.tmpdir))

    def test_get_dataset_path(self):
        p = self.storage.get_dataset_path("ds1")
        self.assertEqual(p, Path(self.tmpdir) / "datasets" / "ds1")

    def test_get_job_workspace(self):
        p = self.storage.get_job_workspace("j1", "sfm")
        self.assertEqual(p, Path(self.tmpdir) / "jobs" / "sfm" / "j1")

    def test_ensure_directory(self):
        p = Path(self.tmpdir) / "x" / "y"
        self.storage.ensure_directory(p)
        self.assertTrue(p.exists())

    def test_cleanup_job(self):
        job_dir = Path(self.tmpdir) / "jobs" / "ortho" / "j1"
        job_dir.mkdir(parents=True)
        self.storage.cleanup_job("j1")
        self.assertFalse(job_dir.exists())

    def test_cleanup_dataset(self):
        ds = Path(self.tmpdir) / "datasets" / "ds2"
        ds.mkdir(parents=True)
        self.storage.cleanup_dataset("ds2")
        self.assertFalse(ds.exists())

    def test_cleanup_stale(self):
        old = Path(self.tmpdir) / "datasets" / "old"
        old.mkdir(parents=True)
        old_time = time.time() - (20 * 86400)
        os.utime(old, (old_time, old_time))
        cleaned = self.storage.cleanup_stale(max_age_days=10)
        self.assertGreater(len(cleaned), 0)

    def test_get_disk_usage_no_api(self):
        self.storage._settings = EFSSettings(
            mount_point=self.tmpdir, file_system_id="", _env_file=None
        )
        usage = self.storage.get_disk_usage()
        self.assertIn("total", usage)

    @patch("boto3.client")
    def test_get_efs_metrics(self, mock_boto):
        mock_efs = MagicMock()
        mock_efs.describe_file_systems.return_value = {
            "FileSystems": [{
                "SizeInBytes": {"Value": 1_000_000},
                "LifeCycleState": "available",
                "PerformanceMode": "generalPurpose",
                "ThroughputMode": "bursting",
            }]
        }
        self.storage._efs_client = mock_efs
        metrics = self.storage._get_efs_metrics()
        self.assertEqual(metrics["used"], 1_000_000)
        self.assertEqual(metrics["lifecycle_state"], "available")

    @patch("boto3.client")
    def test_describe_filesystem(self, mock_boto):
        mock_efs = MagicMock()
        mock_efs.describe_file_systems.return_value = {
            "FileSystems": [{"FileSystemId": "fs-test123"}]
        }
        self.storage._efs_client = mock_efs
        result = self.storage.describe_filesystem()
        self.assertEqual(result["FileSystemId"], "fs-test123")

    def test_describe_filesystem_no_id(self):
        self.storage._settings = EFSSettings(
            mount_point=self.tmpdir, file_system_id="", _env_file=None
        )
        with self.assertRaises(ValueError):
            self.storage.describe_filesystem()

    def test_is_healthy_local_ok(self):
        self.storage._settings = EFSSettings(
            mount_point=self.tmpdir, file_system_id="", _env_file=None
        )
        self.assertTrue(self.storage.is_healthy())

    @patch("boto3.client")
    def test_is_healthy_with_api(self, mock_boto):
        mock_efs = MagicMock()
        mock_efs.describe_file_systems.return_value = {
            "FileSystems": [{"LifeCycleState": "available"}]
        }
        self.storage._efs_client = mock_efs
        self.assertTrue(self.storage.is_healthy())


class TestSharedStorageFactory(unittest.TestCase):
    """Tests for SharedStorageFactory."""

    def test_create_local(self):
        from infrastructure.storage.s3_settings import TempStorageSettings

        tmpdir = tempfile.mkdtemp()
        try:
            shared_settings = SharedStorageSettings(mode="local", _env_file=None)
            temp_settings = TempStorageSettings(base_path=tmpdir, _env_file=None)
            storage = SharedStorageFactory.create(
                shared_settings=shared_settings, temp_settings=temp_settings
            )
            self.assertIsInstance(storage, LocalSharedStorage)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_create_efs(self):
        from infrastructure.storage.shared_storage.efs_storage import EFSSharedStorage

        shared_settings = SharedStorageSettings(mode="efs", _env_file=None)
        efs_settings = EFSSettings(mount_point="/tmp/efs_test", _env_file=None)
        storage = SharedStorageFactory.create(
            shared_settings=shared_settings, efs_settings=efs_settings
        )
        self.assertIsInstance(storage, EFSSharedStorage)

    def test_create_invalid_mode(self):
        shared_settings = SharedStorageSettings(mode="gcs", _env_file=None)
        with self.assertRaises(ValueError):
            SharedStorageFactory.create(shared_settings=shared_settings)


if __name__ == "__main__":
    unittest.main()
