"""Unit tests for ProductUploadClient."""
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from api_gateway.app.clients.product_upload_client import (
    ProductUploadClient,
    ProductUploadClientSettings,
    UPLOAD_CHUNK_TIMEOUT_SECONDS,
    UPLOAD_CHUNK_MAX_RETRIES,
    UPLOAD_CHUNK_RETRY_DELAY_SECONDS,
)


def _make_response(status_code=200, json_data=None, text="", headers=None):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    resp.headers = headers or {}
    return resp


class TestProductUploadClientSettings(unittest.TestCase):
    """Tests for ProductUploadClientSettings."""

    def test_defaults(self):
        s = ProductUploadClientSettings(
            api_url="http://backend:8000",
            api_secret_key="secret123",
            _env_file=None,
        )
        self.assertEqual(s.api_url, "http://backend:8000")
        self.assertEqual(s.api_secret_key, "secret123")
        self.assertEqual(s.chunk_timeout_seconds, UPLOAD_CHUNK_TIMEOUT_SECONDS)
        self.assertEqual(s.chunk_max_retries, UPLOAD_CHUNK_MAX_RETRIES)
        self.assertAlmostEqual(s.chunk_retry_delay_seconds, UPLOAD_CHUNK_RETRY_DELAY_SECONDS)

    def test_custom_values(self):
        s = ProductUploadClientSettings(
            api_url="http://custom:9000",
            api_secret_key="key",
            chunk_timeout_seconds=30,
            chunk_max_retries=5,
            chunk_retry_delay_seconds=1.0,
            _env_file=None,
        )
        self.assertEqual(s.chunk_timeout_seconds, 30)
        self.assertEqual(s.chunk_max_retries, 5)


class TestProductUploadClientInit(unittest.TestCase):
    """Tests for ProductUploadClient initialization."""

    def test_init_with_settings(self):
        settings = ProductUploadClientSettings(
            api_url="http://backend:8000/",
            api_secret_key="secret",
            _env_file=None,
        )
        client = ProductUploadClient(settings)
        self.assertEqual(client.base_url, "http://backend:8000")
        self.assertEqual(client.secret_key, "secret")

    def test_init_strips_trailing_slash(self):
        settings = ProductUploadClientSettings(
            api_url="http://host:8000///",
            api_secret_key="key",
            _env_file=None,
        )
        client = ProductUploadClient(settings)
        self.assertFalse(client.base_url.endswith("/"))


class TestProductUploadClientUpload(unittest.IsolatedAsyncioTestCase):
    """Tests for upload_product method."""

    def setUp(self):
        settings = ProductUploadClientSettings(
            api_url="http://backend:8000",
            api_secret_key="secret",
            chunk_max_retries=1,
            chunk_retry_delay_seconds=0.0,
            _env_file=None,
        )
        self.client = ProductUploadClient(settings)
        self.tmp = Path(tempfile.mktemp(suffix=".tif"))
        self.tmp.write_bytes(b"\x00" * 100)

    def tearDown(self):
        self.tmp.unlink(missing_ok=True)

    async def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            await self.client.upload_product(
                job_id="j1", dataset_id="d1", product_type="orthomosaic",
                file_path=Path("/tmp/nonexistent_xyz_56789.tif"),
            )

    @patch("api_gateway.app.clients.product_upload_client.aiofiles.open")
    async def test_upload_success(self, mock_aiofiles):
        init_resp = _make_response(status_code=200, json_data={
            "product_id": "p1", "upload_id": "u1", "s3_upload_id": "s1", "s3_key": "k1",
        })
        chunk_url_resp = _make_response(status_code=200, json_data={"url": "http://s3/presigned"})
        complete_resp = _make_response(status_code=200, json_data={
            "product_id": "p1", "s3_uri": "s3://bucket/key",
        })
        upload_resp = _make_response(status_code=200, headers={"ETag": '"abc123"'})

        self.client._client.post = AsyncMock(
            side_effect=[init_resp, chunk_url_resp, complete_resp]
        )
        self.client._upload_client.put = AsyncMock(return_value=upload_resp)

        mock_file = AsyncMock()
        mock_file.read = AsyncMock(side_effect=[b"\x00" * 100, b""])
        mock_aiofiles.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await self.client.upload_product(
            job_id="j1", dataset_id="d1", product_type="orthomosaic",
            file_path=self.tmp,
        )
        self.assertEqual(result["product_id"], "p1")

    async def test_init_upload_failure(self):
        fail_resp = _make_response(status_code=500, text="Internal Server Error")
        self.client._client.post = AsyncMock(return_value=fail_resp)

        with self.assertRaises(Exception):
            await self.client.upload_product(
                job_id="j1", dataset_id="d1", product_type="dsm",
                file_path=self.tmp,
            )


class TestProductUploadClientChunk(unittest.IsolatedAsyncioTestCase):
    """Tests for _upload_chunk with retries."""

    def setUp(self):
        settings = ProductUploadClientSettings(
            api_url="http://backend:8000",
            api_secret_key="secret",
            chunk_max_retries=2,
            chunk_retry_delay_seconds=0.0,
            _env_file=None,
        )
        self.client = ProductUploadClient(settings)

    async def test_chunk_upload_success(self):
        resp = _make_response(status_code=200, headers={"ETag": '"etag123"'})
        self.client._upload_client.put = AsyncMock(return_value=resp)

        etag = await self.client._upload_chunk("http://s3/url", b"data")
        self.assertEqual(etag, "etag123")

    async def test_chunk_upload_retry_then_fail(self):
        self.client._upload_client.put = AsyncMock(
            side_effect=httpx.ConnectError("connection error")
        )

        with self.assertRaises(Exception):
            await self.client._upload_chunk("http://s3/url", b"data")


class TestProductUploadClientHelpers(unittest.IsolatedAsyncioTestCase):
    """Tests for _get_chunk_url and _complete_upload."""

    def setUp(self):
        settings = ProductUploadClientSettings(
            api_url="http://backend:8000",
            api_secret_key="secret",
            _env_file=None,
        )
        self.client = ProductUploadClient(settings)

    async def test_get_chunk_url_success(self):
        resp = _make_response(status_code=200, json_data={"url": "http://s3/presigned"})
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client._get_chunk_url("u1", "s1", "k1", 1)
        self.assertEqual(result["url"], "http://s3/presigned")

    async def test_get_chunk_url_failure(self):
        resp = _make_response(status_code=500, text="error")
        self.client._client.post = AsyncMock(return_value=resp)

        with self.assertRaises(Exception):
            await self.client._get_chunk_url("u1", "s1", "k1", 1)

    async def test_complete_upload_success(self):
        resp = _make_response(status_code=200, json_data={"product_id": "p1", "s3_uri": "s3://b/k"})
        self.client._client.post = AsyncMock(return_value=resp)

        result = await self.client._complete_upload("u1", "s1", "k1", [])
        self.assertEqual(result["product_id"], "p1")


if __name__ == "__main__":
    unittest.main()
