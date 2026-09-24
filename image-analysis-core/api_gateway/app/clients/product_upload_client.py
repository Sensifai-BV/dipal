"""
Product Upload Client - AI uploads processing results to Backend.

Replaces direct S3 upload. AI requests presigned URLs from Backend and uploads
results to Products table via multipart upload.
"""
from __future__ import annotations

import asyncio
import aiofiles
import httpx
from pathlib import Path
from typing import Dict
from pydantic_settings import BaseSettings, SettingsConfigDict

from chromatrace.tracer import trace_id_ctx
from infrastructure.logging import get_logger

logger = get_logger(__name__)


UPLOAD_CHUNK_TIMEOUT_SECONDS = 600
UPLOAD_CHUNK_MAX_RETRIES = 3
UPLOAD_CHUNK_RETRY_DELAY_SECONDS = 5.0
MAX_PARALLEL_CHUNK_UPLOADS = 4
BACKEND_REQUEST_MAX_RETRIES = 5
BACKEND_REQUEST_RETRY_DELAY_SECONDS = 3.0


class ProductUploadClientSettings(BaseSettings):
    """Product upload client configuration."""

    api_url: str
    api_secret_key: str
    chunk_timeout_seconds: int = UPLOAD_CHUNK_TIMEOUT_SECONDS
    chunk_max_retries: int = UPLOAD_CHUNK_MAX_RETRIES
    chunk_retry_delay_seconds: float = UPLOAD_CHUNK_RETRY_DELAY_SECONDS
    backend_max_retries: int = BACKEND_REQUEST_MAX_RETRIES
    backend_retry_delay_seconds: float = BACKEND_REQUEST_RETRY_DELAY_SECONDS

    model_config = SettingsConfigDict(
        extra="ignore",
        env_prefix="BACKEND_",
        env_file=".env",
        case_sensitive=False,
    )


class ProductUploadClient:
    """Client for uploading processing results to Backend Products API."""

    def __init__(self, settings: ProductUploadClientSettings | None = None):
        self.settings = settings or ProductUploadClientSettings()
        self.base_url = self.settings.api_url.rstrip('/')
        self.secret_key = self.settings.api_secret_key
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                'X-API-Secret-Key': self.secret_key,
                'Content-Type': 'application/json',
            },
            event_hooks={"request": [self._inject_trace_id]},
        )
        self._upload_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                self.settings.chunk_timeout_seconds,
                connect=30.0,
            ),
        )

    @staticmethod
    async def _inject_trace_id(request: httpx.Request) -> None:
        trace_id = trace_id_ctx.get()
        if trace_id:
            request.headers["X-Request-ID"] = trace_id

    async def _backend_post_with_retry(self, url: str, payload: dict) -> httpx.Response:
        """
        POST to the Django backend with retry on transient connection errors.

        Args:
            url: Full URL to POST to
            payload: JSON payload

        Returns:
            httpx.Response on success

        Raises:
            Exception: After all retries exhausted
        """
        max_retries = self.settings.backend_max_retries
        delay = self.settings.backend_retry_delay_seconds
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                response = await self._client.post(url, json=payload)
                return response
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(
                    f"Backend request attempt {attempt}/{max_retries} failed "
                    f"(url={url}): {e}"
                )
                if attempt < max_retries:
                    await asyncio.sleep(delay * attempt)

        raise Exception(
            f"Backend unreachable after {max_retries} attempts (url={url}): {last_error}"
        )

    async def upload_product(
        self,
        job_id: str,
        dataset_id: str,
        product_type: str,
        file_path: Path | str,
        resolution_cm: float | None = None,
        bands: list[str] | None = None,
        stats: dict | None = None,
        chunk_size: int = 500 * 1024 * 1024,
    ) -> Dict:
        """
        Upload a product file to Backend via multipart upload.

        Args:
            job_id: Processing job ID
            dataset_id: Dataset ID
            product_type: Type of product (orthomosaic, dsm, mesh, etc.)
            file_path: Path to file to upload
            resolution_cm: Product resolution in cm/pixel
            bands: List of spectral bands
            stats: Product statistics/metadata
            chunk_size: Size of each upload chunk (default 500MB)

        Returns:
            Dict with product upload result
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Product file not found: {file_path}")

        file_size = file_path.stat().st_size

        logger.info(
            f"Uploading product: type={product_type}, size={file_size/1024/1024:.1f}MB, "
            f"file={file_path.name}"
        )

        try:
            logger.info(
                f"[PRODUCT_UPLOAD] Initializing upload: job_id={job_id}, "
                f"dataset_id={dataset_id}, product_type={product_type}, "
                f"file_name={file_path.name}, file_size={file_size}"
            )
            init_response = await self._initialize_upload(
                job_id=job_id,
                dataset_id=dataset_id,
                product_type=product_type,
                file_name=file_path.name,
                file_size=file_size,
                resolution_cm=resolution_cm,
                bands=bands,
                stats=stats,
            )

            product_id = init_response['product_id']
            upload_id = init_response['upload_id']
            s3_upload_id = init_response['s3_upload_id']
            s3_key = init_response['s3_key']

            logger.info(
                f"[PRODUCT_UPLOAD] Upload initialized: product_id={product_id}, "
                f"upload_id={upload_id}, s3_key={s3_key}"
            )

            total_chunks = (file_size + chunk_size - 1) // chunk_size

            presigned_urls = await self._prefetch_chunk_urls(
                upload_id=upload_id,
                s3_upload_id=s3_upload_id,
                s3_key=s3_key,
                total_chunks=total_chunks,
            )

            chunks: list[tuple[int, bytes]] = []
            async with aiofiles.open(file_path, 'rb') as f:
                for part_number in range(1, total_chunks + 1):
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    chunks.append((part_number, chunk))

            semaphore = asyncio.Semaphore(MAX_PARALLEL_CHUNK_UPLOADS)

            async def _upload_one(part_number: int, chunk: bytes) -> dict:
                async with semaphore:
                    etag = await self._upload_chunk(
                        presigned_urls[part_number], chunk
                    )
                    logger.debug(
                        f"Uploaded chunk {part_number}/{total_chunks} "
                        f"({len(chunk)/1024/1024:.1f}MB)"
                    )
                    return {'PartNumber': part_number, 'ETag': etag}

            uploaded_parts = await asyncio.gather(
                *[_upload_one(pn, ch) for pn, ch in chunks]
            )
            uploaded_parts_sorted = sorted(uploaded_parts, key=lambda p: p['PartNumber'])

            complete_response = await self._complete_upload(
                upload_id=upload_id,
                s3_upload_id=s3_upload_id,
                s3_key=s3_key,
                parts=list(uploaded_parts_sorted),
            )

            logger.info(
                f"Product uploaded successfully: product_id={complete_response['product_id']}, "
                f"s3_uri={complete_response['s3_uri']}"
            )

            return complete_response

        except Exception as e:
            logger.error(f"Failed to upload product {product_type}: {e}", exc_info=True)
            raise

    async def _initialize_upload(
        self,
        job_id: str,
        dataset_id: str,
        product_type: str,
        file_name: str,
        file_size: int,
        resolution_cm: float | None,
        bands: list[str] | None,
        stats: dict | None,
    ) -> Dict:
        """Initialize product upload."""
        url = f"{self.base_url}/v1/api/products/upload/init/"

        payload = {
            'job_id': job_id,
            'dataset_id': dataset_id,
            'product_type': product_type,
            'file_name': file_name,
            'file_size': file_size,
            'resolution_cm': resolution_cm,
            'bands': bands,
            'stats': stats,
        }

        logger.info(
            f"[PRODUCT_UPLOAD] Init request: POST {url}, "
            f"payload keys={list(payload.keys())}, "
            f"job_id={payload.get('job_id')}, dataset_id={payload.get('dataset_id')}, "
            f"product_type={payload.get('product_type')}"
        )
        response = await self._backend_post_with_retry(url, payload)
        if response.status_code != 200:
            logger.error(
                f"[PRODUCT_UPLOAD] Init failed: status={response.status_code}, "
                f"body={response.text[:500]}, url={url}"
            )
            raise Exception(f"Failed to initialize upload: {response.status_code} - {response.text}")

        return response.json()

    async def _prefetch_chunk_urls(
        self,
        upload_id: str,
        s3_upload_id: str,
        s3_key: str,
        total_chunks: int,
    ) -> dict[int, str]:
        """
        Pre-fetch presigned URLs for all chunks in parallel.

        Args:
            upload_id: Upload identifier
            s3_upload_id: S3 multipart upload ID
            s3_key: S3 object key
            total_chunks: Total number of chunks

        Returns:
            Mapping of part_number → presigned URL
        """
        async def _fetch_one(part_number: int) -> tuple[int, str]:
            resp = await self._get_chunk_url(
                upload_id=upload_id,
                s3_upload_id=s3_upload_id,
                s3_key=s3_key,
                part_number=part_number,
            )
            return part_number, resp['url']

        results = await asyncio.gather(
            *[_fetch_one(pn) for pn in range(1, total_chunks + 1)]
        )
        return dict(results)

    async def _get_chunk_url(
        self,
        upload_id: str,
        s3_upload_id: str,
        s3_key: str,
        part_number: int,
    ) -> Dict:
        """Get presigned URL for chunk upload."""
        url = f"{self.base_url}/v1/api/products/upload/chunk/"

        payload = {
            'upload_id': upload_id,
            's3_upload_id': s3_upload_id,
            's3_key': s3_key,
            'part_number': part_number,
        }

        response = await self._backend_post_with_retry(url, payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get chunk URL: {response.status_code} - {response.text}")

        return response.json()

    async def _upload_chunk(self, presigned_url: str, chunk: bytes) -> str:
        """
        Upload chunk to presigned URL with timeout and retry.

        Args:
            presigned_url: S3 presigned URL for chunk upload
            chunk: Raw bytes to upload

        Returns:
            ETag string from S3 response
        """
        chunk_size_mb = len(chunk) / 1024 / 1024
        last_error = None

        for attempt in range(1, self.settings.chunk_max_retries + 1):
            try:
                response = await self._upload_client.put(
                    presigned_url, content=chunk
                )
                if response.status_code not in [200, 201]:
                    raise Exception(
                        f"Failed to upload chunk: {response.status_code} - {response.text}"
                    )

                etag = response.headers.get('ETag', '').strip('"')
                return etag

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(
                    f"Chunk upload attempt {attempt}/{self.settings.chunk_max_retries} "
                    f"failed ({chunk_size_mb:.1f}MB): {e}"
                )
                if attempt < self.settings.chunk_max_retries:
                    await asyncio.sleep(self.settings.chunk_retry_delay_seconds)

        raise Exception(
            f"Chunk upload failed after {self.settings.chunk_max_retries} attempts "
            f"({chunk_size_mb:.1f}MB): {last_error}"
        )

    async def _complete_upload(
        self,
        upload_id: str,
        s3_upload_id: str,
        s3_key: str,
        parts: list[dict],
    ) -> Dict:
        """Complete multipart upload."""
        url = f"{self.base_url}/v1/api/products/upload/complete/"

        payload = {
            'upload_id': upload_id,
            's3_upload_id': s3_upload_id,
            's3_key': s3_key,
            'parts': parts,
        }

        response = await self._backend_post_with_retry(url, payload)
        if response.status_code != 200:
            raise Exception(f"Failed to complete upload: {response.status_code} - {response.text}")

        return response.json()

    async def close(self):
        """Close the underlying HTTP clients."""
        await self._client.aclose()
        await self._upload_client.aclose()
