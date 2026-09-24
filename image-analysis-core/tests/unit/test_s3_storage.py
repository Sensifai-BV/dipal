"""Unit tests for S3 storage driver and S3 results uploader."""
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import sys

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from infrastructure.storage.drivers.s3 import S3StorageDriver
from infrastructure.storage.s3_uploader import S3ResultsUploader


class TestS3StorageDriverInit(unittest.TestCase):
    """Tests for S3StorageDriver initialization."""

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_init_with_explicit_creds(self, mock_aws):
        mock_aws.return_value = MagicMock(use_aws_role=False)
        driver = S3StorageDriver(
            bucket_name="my-bucket",
            region_name="eu-west-1",
            aws_access_key_id="AKID",
            aws_secret_access_key="SECRET",
        )
        self.assertEqual(driver.bucket_name, "my-bucket")
        self.assertEqual(driver.region_name, "eu-west-1")
        self.assertEqual(driver.aws_access_key_id, "AKID")
        self.assertFalse(driver._connected)

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_init_with_aws_role(self, mock_aws):
        mock_aws.return_value = MagicMock(use_aws_role=True)
        driver = S3StorageDriver(
            bucket_name="my-bucket",
            aws_access_key_id="AKID",
            aws_secret_access_key="SECRET",
        )
        self.assertIsNone(driver.aws_access_key_id)
        self.assertIsNone(driver.aws_secret_access_key)

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_init_with_settings(self, mock_aws):
        mock_aws.return_value = MagicMock(use_aws_role=False)
        mock_settings = MagicMock(
            raw_images_bucket="settings-bucket",
            region_name="us-west-2",
            has_explicit_credentials=True,
            access_key_id="S_AKID",
            secret_access_key="S_SECRET",
        )
        driver = S3StorageDriver(settings=mock_settings)
        self.assertEqual(driver.bucket_name, "settings-bucket")
        self.assertEqual(driver.aws_access_key_id, "S_AKID")


class TestS3StorageDriverConnect(unittest.TestCase):
    """Tests for S3StorageDriver connect/disconnect."""

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    @patch("infrastructure.storage.drivers.s3.boto3")
    def test_connect_success(self, mock_boto, mock_aws):
        mock_aws.return_value = MagicMock(use_aws_role=False)
        mock_session = MagicMock()
        mock_boto.Session.return_value = mock_session

        driver = S3StorageDriver(
            bucket_name="bucket", aws_access_key_id="K", aws_secret_access_key="S"
        )
        driver.connect()
        self.assertTrue(driver._connected)
        mock_session.client.return_value.head_bucket.assert_called_once()

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    @patch("infrastructure.storage.drivers.s3.boto3")
    def test_connect_no_credentials(self, mock_boto, mock_aws):
        from botocore.exceptions import NoCredentialsError
        mock_aws.return_value = MagicMock(use_aws_role=False)
        mock_boto.Session.return_value.client.return_value.head_bucket.side_effect = (
            NoCredentialsError()
        )
        driver = S3StorageDriver(bucket_name="bucket")
        with self.assertRaises(ConnectionError):
            driver.connect()

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    @patch("infrastructure.storage.drivers.s3.boto3")
    def test_connect_bucket_not_found(self, mock_boto, mock_aws):
        from botocore.exceptions import ClientError
        mock_aws.return_value = MagicMock(use_aws_role=False)
        err = ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket")
        mock_boto.Session.return_value.client.return_value.head_bucket.side_effect = err
        driver = S3StorageDriver(bucket_name="missing")
        with self.assertRaises(ConnectionError):
            driver.connect()

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    @patch("infrastructure.storage.drivers.s3.boto3")
    def test_connect_access_denied(self, mock_boto, mock_aws):
        from botocore.exceptions import ClientError
        mock_aws.return_value = MagicMock(use_aws_role=False)
        err = ClientError({"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadBucket")
        mock_boto.Session.return_value.client.return_value.head_bucket.side_effect = err
        driver = S3StorageDriver(bucket_name="forbidden")
        with self.assertRaises(ConnectionError):
            driver.connect()

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    @patch("infrastructure.storage.drivers.s3.boto3")
    def test_connect_other_error(self, mock_boto, mock_aws):
        from botocore.exceptions import ClientError
        mock_aws.return_value = MagicMock(use_aws_role=False)
        err = ClientError({"Error": {"Code": "500", "Message": "Server Error"}}, "HeadBucket")
        mock_boto.Session.return_value.client.return_value.head_bucket.side_effect = err
        driver = S3StorageDriver(bucket_name="error")
        with self.assertRaises(ConnectionError):
            driver.connect()

    @patch("infrastructure.storage.drivers.s3.AWSSettings")
    def test_disconnect(self, mock_aws):
        mock_aws.return_value = MagicMock(use_aws_role=False)
        driver = S3StorageDriver(bucket_name="bucket")
        driver._connected = True
        driver.s3_client = MagicMock()
        driver.disconnect()
        self.assertFalse(driver._connected)
        self.assertIsNone(driver.s3_client)


class TestS3StorageDriverOperations(unittest.TestCase):
    """Tests for S3StorageDriver operations (fetch, push, list, exists, delete)."""

    def _make_connected_driver(self):
        with patch("infrastructure.storage.drivers.s3.AWSSettings") as mock_aws:
            mock_aws.return_value = MagicMock(use_aws_role=False)
            driver = S3StorageDriver(bucket_name="bucket")
        driver._connected = True
        driver.s3_client = MagicMock()
        return driver

    def test_get_s3_key(self):
        driver = self._make_connected_driver()
        key = driver._get_s3_key("proj1", "images", "test.jpg")
        self.assertEqual(key, "photogear/proj1/images/test.jpg")

    def test_fetch_images_not_connected(self):
        with patch("infrastructure.storage.drivers.s3.AWSSettings") as mock_aws:
            mock_aws.return_value = MagicMock(use_aws_role=False)
            driver = S3StorageDriver(bucket_name="bucket")
        with self.assertRaises(ConnectionError):
            driver.fetch_images("proj", Path("/tmp/out"))

    def test_fetch_images_success(self):
        driver = self._make_connected_driver()
        tmpdir = Path(tempfile.mkdtemp())
        try:
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [
                {"Contents": [
                    {"Key": "photogear/proj/images/img1.jpg"},
                    {"Key": "photogear/proj/images/img2.tif"},
                    {"Key": "photogear/proj/images/"},
                    {"Key": "photogear/proj/images/readme.txt"},
                ]}
            ]
            driver.s3_client.get_paginator.return_value = mock_paginator

            result = driver.fetch_images("proj", tmpdir)
            self.assertEqual(len(result), 2)
            self.assertEqual(driver.s3_client.download_file.call_count, 2)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_fetch_images_no_images(self):
        driver = self._make_connected_driver()
        tmpdir = Path(tempfile.mkdtemp())
        try:
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [{"Contents": []}]
            driver.s3_client.get_paginator.return_value = mock_paginator
            with self.assertRaises(FileNotFoundError):
                driver.fetch_images("proj", tmpdir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_push_results_not_connected(self):
        with patch("infrastructure.storage.drivers.s3.AWSSettings") as mock_aws:
            mock_aws.return_value = MagicMock(use_aws_role=False)
            driver = S3StorageDriver(bucket_name="bucket")
        with self.assertRaises(ConnectionError):
            driver.push_results("proj", Path("/tmp"), 1)

    def test_push_results_source_not_found(self):
        driver = self._make_connected_driver()
        with self.assertRaises(FileNotFoundError):
            driver.push_results("proj", Path("/nonexistent"), 1)

    def test_push_results_single_file(self):
        driver = self._make_connected_driver()
        tmpdir = Path(tempfile.mkdtemp())
        try:
            f = tmpdir / "result.tif"
            f.write_text("data")
            driver.push_results("proj", f, 1)
            driver.s3_client.upload_file.assert_called_once()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_push_results_directory(self):
        driver = self._make_connected_driver()
        tmpdir = Path(tempfile.mkdtemp())
        try:
            (tmpdir / "a.tif").write_text("a")
            (tmpdir / "b.tif").write_text("b")
            driver.push_results("proj", tmpdir, 1)
            self.assertEqual(driver.s3_client.upload_file.call_count, 2)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_list_images_not_connected(self):
        with patch("infrastructure.storage.drivers.s3.AWSSettings") as mock_aws:
            mock_aws.return_value = MagicMock(use_aws_role=False)
            driver = S3StorageDriver(bucket_name="bucket")
        with self.assertRaises(ConnectionError):
            driver.list_images("proj")

    def test_list_images_success(self):
        driver = self._make_connected_driver()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Contents": [
                {"Key": "photogear/proj/images/b.jpg"},
                {"Key": "photogear/proj/images/a.tif"},
            ]}
        ]
        driver.s3_client.get_paginator.return_value = mock_paginator
        result = driver.list_images("proj")
        self.assertEqual(result, ["a.tif", "b.jpg"])

    def test_list_images_client_error(self):
        from botocore.exceptions import ClientError
        driver = self._make_connected_driver()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "err"}}, "List"
        )
        driver.s3_client.get_paginator.return_value = mock_paginator
        result = driver.list_images("proj")
        self.assertEqual(result, [])

    def test_exists_true(self):
        driver = self._make_connected_driver()
        result = driver.exists("proj/images/test.jpg")
        self.assertTrue(result)

    def test_exists_false(self):
        from botocore.exceptions import ClientError
        driver = self._make_connected_driver()
        driver.s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )
        result = driver.exists("proj/images/missing.jpg")
        self.assertFalse(result)

    def test_exists_other_error(self):
        from botocore.exceptions import ClientError
        driver = self._make_connected_driver()
        driver.s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "err"}}, "HeadObject"
        )
        with self.assertRaises(ClientError):
            driver.exists("proj/images/test.jpg")

    def test_delete_project_not_connected(self):
        with patch("infrastructure.storage.drivers.s3.AWSSettings") as mock_aws:
            mock_aws.return_value = MagicMock(use_aws_role=False)
            driver = S3StorageDriver(bucket_name="bucket")
        with self.assertRaises(ConnectionError):
            driver.delete_project("proj")

    def test_delete_project_success(self):
        driver = self._make_connected_driver()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Contents": [
                {"Key": "photogear/proj/images/a.jpg"},
                {"Key": "photogear/proj/images/b.jpg"},
            ]}
        ]
        driver.s3_client.get_paginator.return_value = mock_paginator
        driver.delete_project("proj")
        driver.s3_client.delete_objects.assert_called_once()

    def test_delete_project_no_objects(self):
        driver = self._make_connected_driver()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{}]
        driver.s3_client.get_paginator.return_value = mock_paginator
        driver.delete_project("proj")
        driver.s3_client.delete_objects.assert_not_called()


class TestS3ResultsUploader(unittest.TestCase):
    """Tests for S3ResultsUploader."""

    @patch("infrastructure.storage.s3_uploader.boto3")
    def _make_uploader(self, mock_boto):
        mock_settings = MagicMock(
            region_name="us-east-1",
            has_explicit_credentials=True,
            access_key_id="AKID",
            secret_access_key="SECRET",
            results_bucket="results-bucket",
        )
        uploader = S3ResultsUploader(mock_settings)
        uploader.s3_client = MagicMock()
        return uploader

    def test_upload_file_success(self):
        uploader = self._make_uploader()
        tmpdir = Path(tempfile.mkdtemp())
        try:
            f = tmpdir / "result.tif"
            f.write_text("data")
            uri = uploader.upload_file(f, "test/result.tif")
            self.assertEqual(uri, "s3://results-bucket/test/result.tif")
            uploader.s3_client.upload_file.assert_called_once()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_upload_file_not_found(self):
        uploader = self._make_uploader()
        with self.assertRaises(FileNotFoundError):
            uploader.upload_file(Path("/nonexistent"), "key")

    def test_upload_file_custom_bucket(self):
        uploader = self._make_uploader()
        tmpdir = Path(tempfile.mkdtemp())
        try:
            f = tmpdir / "a.tif"
            f.write_text("data")
            uri = uploader.upload_file(f, "k", bucket="custom")
            self.assertEqual(uri, "s3://custom/k")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_upload_job_results(self):
        uploader = self._make_uploader()
        tmpdir = Path(tempfile.mkdtemp())
        try:
            (tmpdir / "ortho.tif").write_text("ortho")
            (tmpdir / "dsm.tif").write_text("dsm")
            result_files = {
                "orthomosaic": tmpdir / "ortho.tif",
                "dsm": tmpdir / "dsm.tif",
                "missing": tmpdir / "nope.tif",
                "null": None,
            }
            uris = uploader.upload_job_results("job1", "ds1", result_files)
            self.assertIn("orthomosaic", uris)
            self.assertIn("dsm", uris)
            self.assertNotIn("missing", uris)
            self.assertNotIn("null", uris)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_generate_presigned_url(self):
        uploader = self._make_uploader()
        uploader.s3_client.generate_presigned_url.return_value = "https://signed.url"
        url = uploader.generate_presigned_url("s3://bucket/key/file.tif")
        self.assertEqual(url, "https://signed.url")

    def test_generate_presigned_url_invalid(self):
        uploader = self._make_uploader()
        with self.assertRaises(ValueError):
            uploader.generate_presigned_url("not-s3-uri")

    @patch("infrastructure.storage.s3_uploader.boto3")
    def test_init_with_role(self, mock_boto):
        mock_settings = MagicMock(
            region_name="us-east-1",
            has_explicit_credentials=False,
            results_bucket="results-bucket",
        )
        uploader = S3ResultsUploader(mock_settings)
        self.assertIsNotNone(uploader.s3_client)


if __name__ == "__main__":
    unittest.main()
