"""Tests for all HTTP clients: Backend, SFM, Orthomosaic, Calibration, ProductUpload."""
import unittest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

import httpx

from api_gateway.app.clients.backend_client import BackendClient, BackendClientSettings
from api_gateway.app.clients.sfm_client import SFMClient, SFMClientSettings
from api_gateway.app.clients.orthomosaic_client import OrthomosaicClient, OrthomosaicClientSettings
from api_gateway.app.clients.calibration_client import CalibrationClient, CalibrationClientSettings
from api_gateway.app.clients.product_upload_client import ProductUploadClient, ProductUploadClientSettings


def _make_response(status_code=200, json_data=None, text="", headers=None):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    resp.headers = headers or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    return resp


class TestBackendClient(unittest.IsolatedAsyncioTestCase):
    """Tests for BackendClient."""

    def setUp(self):
        self.settings = BackendClientSettings(
            api_url="http://backend:8000",
            callback_endpoint="/v1/api/jobs/ai-callback/",
            api_secret_key="test-secret-key-1234567890",
            callback_max_retries=1,
            callback_base_delay=0.0,
        )
        self.client = BackendClient(self.settings)

    def test_callback_url_construction(self):
        """Test callback URL is built correctly."""
        self.assertEqual(
            self.client.callback_url,
            "http://backend:8000/v1/api/jobs/ai-callback/",
        )

    async def test_send_progress_update_success(self):
        """Test successful progress update."""
        resp = _make_response(status_code=200)
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client.send_progress_update(
            job_id="j-1", progress=50.0, current_stage="sfm", message="processing"
        )
        self.assertTrue(result)

    async def test_send_progress_update_failure(self):
        """Test progress update with non-200 response."""
        resp = _make_response(status_code=500, text="server error")
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client.send_progress_update(
            job_id="j-2", progress=50.0, current_stage="sfm"
        )
        self.assertFalse(result)

    async def test_send_completion(self):
        """Test sending completion callback."""
        resp = _make_response(status_code=200)
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client.send_completion(
            job_id="j-3",
            dataset_id="ds-1",
            outputs={"ortho": "s3://bucket/ortho.tif"},
        )
        self.assertTrue(result)

    async def test_send_failure(self):
        """Test sending failure callback."""
        resp = _make_response(status_code=200)
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client.send_failure(
            job_id="j-4", error_message="processing failed"
        )
        self.assertTrue(result)

    async def test_send_callback_exception(self):
        """Test callback when connection raises exception."""
        self.client._client.post = AsyncMock(
            side_effect=ConnectionError("network down")
        )

        result = await self.client.send_failure(
            job_id="j-5", error_message="test"
        )
        self.assertFalse(result)


class TestSFMClient(unittest.IsolatedAsyncioTestCase):
    """Tests for SFMClient."""

    def setUp(self):
        self.settings = SFMClientSettings(
            address="http://sfm:8002",
            timeout_seconds=5,
            max_retries=2,
            retry_delay_seconds=0.01,
        )
        self.client = SFMClient(self.settings)

    async def test_run_sfm_success(self):
        """Test successful SFM job submission."""
        resp = _make_response(status_code=200, json_data={"job_id": "sfm-1", "status": "running"})
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client.run_sfm(
            job_id="sfm-1", dataset_id="ds-1", download_url="https://example.com/data.zip"
        )
        self.assertEqual(result["job_id"], "sfm-1")

    async def test_run_sfm_all_retries_fail(self):
        """Test SFM service unavailable after all retries."""
        self.client._client.post = AsyncMock(
            side_effect=httpx.ConnectError("refused")
        )

        with self.assertRaises(Exception) as ctx:
            await self.client.run_sfm(
                job_id="sfm-fail", dataset_id="ds-1", download_url="http://example.com"
            )
        self.assertIn("unavailable", str(ctx.exception))

    async def test_get_job_status(self):
        """Test getting SFM job status."""
        resp = _make_response(status_code=200, json_data={"status": "completed"})
        self.client._client.get = AsyncMock(return_value=resp)

        result = await self.client.get_job_status("sfm-1")
        self.assertEqual(result["status"], "completed")

    async def test_cancel_job(self):
        """Test cancelling SFM job."""
        resp = _make_response(status_code=200, json_data={"cancelled": True})
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client.cancel_job("sfm-1")
        self.assertTrue(result["cancelled"])

    async def test_get_result(self):
        """Test getting SFM job result."""
        resp = _make_response(status_code=200, json_data={"result": "path/output"})
        self.client._client.get = AsyncMock(return_value=resp)

        result = await self.client.get_result("sfm-1")
        self.assertEqual(result["result"], "path/output")

    async def test_legacy_methods(self):
        """Test legacy backward-compat methods."""
        resp = _make_response(status_code=200, json_data={"status": "ok"}, text="ok")
        self.client._client.post = AsyncMock(return_value=resp)
        self.client._client.get = AsyncMock(return_value=resp)

        result = await self.client.initialize_dataset()
        self.assertEqual(result, "ok")

        result = await self.client.job_status("j1")
        self.assertEqual(result["status"], "ok")


class TestOrthomosaicClient(unittest.IsolatedAsyncioTestCase):
    """Tests for OrthomosaicClient."""

    def setUp(self):
        self.settings = OrthomosaicClientSettings(
            address="http://ortho:8003",
            timeout_seconds=5,
            max_retries=2,
            retry_delay_seconds=0.01,
        )
        self.client = OrthomosaicClient(self.settings)

    async def test_run_orthomosaic_success(self):
        """Test successful orthomosaic job submission."""
        resp = _make_response(status_code=200, json_data={"job_id": "ortho-1", "status": "running"})
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client.run_orthomosaic(
            job_id="ortho-1", dataset_id="ds-1", dataset_path="/data/ds-1"
        )
        self.assertEqual(result["job_id"], "ortho-1")

    async def test_run_orthomosaic_retries_exhausted(self):
        """Test orthomosaic retries exhausted."""
        self.client._client.post = AsyncMock(
            side_effect=httpx.ConnectError("refused")
        )

        with self.assertRaises(Exception) as ctx:
            await self.client.run_orthomosaic(
                job_id="o-fail", dataset_id="ds-1", dataset_path="/data"
            )
        self.assertIn("unavailable", str(ctx.exception))

    async def test_get_job_status(self):
        """Test getting orthomosaic job status."""
        resp = _make_response(status_code=200, json_data={"status": "completed"})
        self.client._client.get = AsyncMock(return_value=resp)

        result = await self.client.get_job_status("ortho-1")
        self.assertEqual(result["status"], "completed")

    async def test_cancel_job(self):
        """Test cancelling orthomosaic job."""
        resp = _make_response(status_code=200, json_data={"cancelled": True})
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client.cancel_job("ortho-1")
        self.assertTrue(result["cancelled"])


class TestCalibrationClient(unittest.IsolatedAsyncioTestCase):
    """Tests for CalibrationClient."""

    def setUp(self):
        self.settings = CalibrationClientSettings(
            address="http://calib:8004",
            timeout_seconds=5,
            max_retries=2,
            retry_delay_seconds=0.01,
        )
        self.client = CalibrationClient(self.settings)

    async def test_run_calibration_success(self):
        """Test successful calibration job submission."""
        resp = _make_response(status_code=200, json_data={"job_id": "cal-1", "status": "running"})
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client.run_calibration(
            job_id="cal-1", dataset_id="ds-1", download_url="https://example.com/data.zip"
        )
        self.assertEqual(result["job_id"], "cal-1")

    async def test_run_calibration_retries_exhausted(self):
        """Test calibration retries exhausted."""
        self.client._client.post = AsyncMock(
            side_effect=httpx.ConnectError("refused")
        )

        with self.assertRaises(Exception) as ctx:
            await self.client.run_calibration(
                job_id="c-fail", dataset_id="ds-1", download_url="http://example.com"
            )
        self.assertIn("unavailable", str(ctx.exception))

    async def test_get_job_status(self):
        """Test getting calibration job status."""
        resp = _make_response(status_code=200, json_data={"status": "completed"})
        self.client._client.get = AsyncMock(return_value=resp)

        result = await self.client.get_job_status("cal-1")
        self.assertEqual(result["status"], "completed")

    async def test_cancel_job(self):
        """Test cancelling calibration job."""
        resp = _make_response(status_code=200, json_data={"cancelled": True})
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client.cancel_job("cal-1")
        self.assertTrue(result["cancelled"])

    async def test_get_result(self):
        """Test getting calibration result."""
        resp = _make_response(status_code=200, json_data={"calibrated": True})
        self.client._client.get = AsyncMock(return_value=resp)

        result = await self.client.get_result("cal-1")
        self.assertTrue(result["calibrated"])


class TestProductUploadClient(unittest.IsolatedAsyncioTestCase):
    """Tests for ProductUploadClient."""

    def setUp(self):
        self.settings = ProductUploadClientSettings(
            api_url="http://backend:8000",
            api_secret_key="test-secret-key-1234567890",
            chunk_timeout_seconds=10,
            chunk_max_retries=2,
            chunk_retry_delay_seconds=0.01,
        )
        self.client = ProductUploadClient(settings=self.settings)

    def test_base_url_construction(self):
        """Test base URL trailing slash removal."""
        self.assertEqual(self.client.base_url, "http://backend:8000")

    async def test_initialize_upload(self):
        """Test initializing product upload."""
        resp = _make_response(
            status_code=200,
            json_data={"product_id": "p1", "upload_id": "u1", "s3_upload_id": "su1", "s3_key": "k1"},
        )
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client._initialize_upload(
            job_id="j1", dataset_id="ds1", product_type="orthomosaic",
            file_name="ortho.tif", file_size=1000,
            resolution_cm=2.5, bands=["R", "G", "B"], stats={"mean": 128},
        )
        self.assertEqual(result["product_id"], "p1")

    async def test_initialize_upload_failure(self):
        """Test init upload failure handling."""
        resp = _make_response(status_code=400, text="bad request")
        self.client._client.post = AsyncMock(return_value=resp)

        with self.assertRaises(Exception) as ctx:
            await self.client._initialize_upload(
                job_id="j1", dataset_id="ds1", product_type="orthomosaic",
                file_name="ortho.tif", file_size=1000,
                resolution_cm=None, bands=None, stats=None,
            )
        self.assertIn("Failed to initialize", str(ctx.exception))

    async def test_upload_chunk_success(self):
        """Test uploading a chunk to presigned URL."""
        resp = _make_response(status_code=200, headers={"ETag": '"abc123"'})
        self.client._upload_client.put = AsyncMock(return_value=resp)

        etag = await self.client._upload_chunk("https://s3.example.com/chunk", b"data")
        self.assertEqual(etag, "abc123")

    async def test_upload_chunk_retry(self):
        """Test chunk upload retry on timeout."""
        ok_resp = _make_response(status_code=200, headers={"ETag": '"ok"'})
        self.client._upload_client.put = AsyncMock(
            side_effect=[httpx.TimeoutException("timeout"), ok_resp]
        )

        etag = await self.client._upload_chunk("https://s3.example.com/chunk", b"data")
        self.assertEqual(etag, "ok")

    async def test_complete_upload(self):
        """Test completing multipart upload."""
        resp = _make_response(
            status_code=200,
            json_data={"product_id": "pp1", "s3_uri": "s3://bucket/key"},
        )
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client._complete_upload(
            upload_id="u1", s3_upload_id="su1", s3_key="k1",
            parts=[{"PartNumber": 1, "ETag": "abc"}],
        )
        self.assertEqual(result["s3_uri"], "s3://bucket/key")

    async def test_upload_product_file_not_found(self):
        """Test upload_product with nonexistent file."""
        with self.assertRaises(FileNotFoundError):
            await self.client.upload_product(
                job_id="j1", dataset_id="ds1", product_type="ortho",
                file_path="/nonexistent/file.tif",
            )


if __name__ == "__main__":
    unittest.main()
