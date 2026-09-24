from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from requests.exceptions import RequestException

from .base import StorageDriver
from infrastructure.logging import get_logger

logger = get_logger(__name__)

MAX_DOWNLOAD_WORKERS = 8


class PresignedUrlStorageDriver(StorageDriver):
    """
    Presigned URL storage driver.

    Works with S3 presigned URLs to fetch and upload data.
    Suitable for scenarios where direct S3 access is not available,
    but presigned URLs are provided by an API gateway.

    Expected workflow:
    1. Download: GET request to download_url returns JSON with list of image URLs
    2. Each image URL is a presigned URL that can be downloaded directly
    3. Upload: POST/PUT files to upload_url with file data
    """

    def __init__(
        self,
        project_urls: dict[str, dict[str, str]] | None = None,
        timeout: int = 300,
    ):
        """
        Initialize presigned URL storage driver.

        Args:
            project_urls: Dictionary mapping project_id to URLs.
                         Format: {
                             'project_id': {
                                 'download_url': 'https://...',
                                 'upload_url': 'https://...'
                             }
                         }
            timeout: Request timeout in seconds (default: 300)
        """
        self.project_urls = project_urls or {}
        self.timeout = timeout
        self._connected = False
        self.session = requests.Session()

    def connect(self) -> None:
        """
        Establish connection (validate session).
        """
        try:
            # Test that we can make requests
            self.session.headers.update(
                {
                    "User-Agent": "PhotoGear-PresignedUrl-Driver/1.0",
                },
            )
            self._connected = True
            logger.info("Connected to presigned URL storage")
        except Exception as e:
            logger.error(f"Failed to initialize session: {e}")
            raise ConnectionError(f"Cannot initialize HTTP session: {e}")

    def disconnect(self) -> None:
        """
        Close connection and cleanup session.
        """
        self.session.close()
        self._connected = False
        logger.info("Disconnected from presigned URL storage")

    def _get_project_urls(self, project_id: str) -> dict[str, str]:
        """
        Get URLs for a project.

        Args:
            project_id: Project identifier

        Returns:
            Dictionary with download_url and upload_url

        Raises:
            ValueError: If project URLs not configured
        """
        if project_id not in self.project_urls:
            raise ValueError(
                f"No URLs configured for project {project_id}. "
                f"Call set_project_urls() first.",
            )
        return self.project_urls[project_id]

    def fetch_images(self, project_id: str, destination_path: Path) -> list[Path]:
        """
        Fetch images using presigned URLs.

        Workflow:
        1. If 'images' list is directly provided in project_urls, use it
        2. Otherwise, GET request to download_url
        3. Parse JSON response to get list of image URLs
        4. Download each image URL to destination_path

        Expected JSON response format:
        {
            "images": [
                {
                    "url": "https://presigned-url-1",
                    "filename": "image1.jpg"
                },
                ...
            ]
        }

        Alternative format (simple list of URLs):
        {
            "urls": ["https://presigned-url-1", "https://presigned-url-2", ...]
        }

        Args:
            project_id: Unique identifier for the project
            destination_path: Local path where images should be downloaded

        Returns:
            List of paths to downloaded images

        Raises:
            ConnectionError: If not connected
            ValueError: If project URLs not configured
            FileNotFoundError: If no images found
            IOError: If download fails
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        urls = self._get_project_urls(project_id)
        
        destination_path.mkdir(parents=True, exist_ok=True)

        try:
            # Check if images list is provided directly
            if "images" in urls and isinstance(urls["images"], list):
                logger.info(f"Using directly provided image list with {len(urls['images'])} images")
                image_urls = urls["images"]
            else:
                # Get list of image URLs from download_url
                download_url = urls["download_url"]
                logger.info(f"Fetching image list from {download_url}")
                response = self.session.get(download_url, timeout=self.timeout)
                response.raise_for_status()

                # Parse JSON response
                data = response.json()

                # Handle different response formats
                image_urls = self._parse_image_urls(data)

            if not image_urls:
                raise FileNotFoundError(
                    f"No images found for project {project_id}",
                )

            logger.info(f"Found {len(image_urls)} images to download")

            # Download each image
            logger.info("Starting parallel image download...")
            downloaded_images: list[Path] = []
            total = len(image_urls)

            def _download_one(idx: int, image_info) -> Path | None:
                """Download a single image (runs in thread pool)."""
                filename = f"unknown_{idx}.jpg"
                url = ""
                try:
                    if isinstance(image_info, dict):
                        url = image_info["url"]
                        filename = image_info.get(
                            "filename",
                        ) or self._extract_filename_from_url(url)
                    else:
                        url = image_info
                        filename = self._extract_filename_from_url(url)

                    local_file = destination_path / filename
                    local_file.parent.mkdir(parents=True, exist_ok=True)

                    if local_file.exists() and local_file.stat().st_size > 0:
                        logger.debug(f"Image {idx}/{total} already exists: {filename}, skipping download")
                        return local_file

                    logger.debug(f"Downloading image {idx}/{total}: {filename}")
                    img_response = self.session.get(url, timeout=self.timeout)
                    img_response.raise_for_status()

                    local_file.write_bytes(img_response.content)
                    logger.debug(f"Downloaded {filename} ({len(img_response.content)} bytes)")
                    return local_file

                except Exception as e:
                    logger.warning(f"Failed to download image {filename}: {e}", exc_info=True)
                    return None

            with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS) as executor:
                futures = {
                    executor.submit(_download_one, idx, info): idx
                    for idx, info in enumerate(image_urls, 1)
                }
                done_count = 0
                for future in as_completed(futures):
                    result = future.result()
                    if result is not None:
                        downloaded_images.append(result)
                    done_count += 1
                    if done_count % 50 == 0:
                        logger.info(f"Downloaded {done_count}/{total} images...")

            if not downloaded_images:
                raise FileNotFoundError(
                    f"Failed to download any images for project {project_id}",
                )

            logger.info(
                f"Successfully fetched {len(downloaded_images)} images for project {project_id}",
            )
            return downloaded_images

        except RequestException as e:
            logger.error(f"Failed to fetch images: {e}")
            raise OSError(f"Failed to fetch images: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse image list response: {e}")
            raise OSError(f"Invalid response format: {e}")

    def _parse_image_urls(self, data: dict[str, Any]) -> list[dict[str, str] | str]:
        """
        Parse image URLs from various JSON response formats.

        Supports multiple formats:
        - {"images": [{"url": "...", "filename": "..."}, ...]}
        - {"urls": ["url1", "url2", ...]}
        - {"files": [{"url": "...", "name": "..."}, ...]}
        - {"data": {"images": [...]}}

        Args:
            data: JSON response data

        Returns:
            List of image URLs (either dict with url/filename or plain URLs)
        """
        # Try different keys and formats
        if "images" in data:
            return data["images"]
        elif "urls" in data:
            return data["urls"]
        elif "files" in data:
            # Normalize 'name' to 'filename'
            return [
                {"url": f["url"], "filename": f.get("name") or f.get("filename")}  # type: ignore
                if isinstance(f, dict)
                else f
                for f in data["files"]
            ]
        elif "data" in data and isinstance(data["data"], dict):
            return self._parse_image_urls(data["data"])
        else:
            # Try to find any key that contains a list
            for key, value in data.items():
                if isinstance(value, list) and value:
                    return value

        return []

    def _extract_filename_from_url(self, url: str) -> str:
        """
        Extract filename from URL.

        Args:
            url: URL string

        Returns:
            Extracted filename or generated name
        """
        parsed = urlparse(url)
        path = parsed.path
        filename = Path(path).name

        # If no filename in URL, generate one
        if not filename or "." not in filename:
            import hashlib

            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"image_{url_hash}.jpg"

        return filename

    def push_results(self, project_id: str, source_path: Path, run_id: int) -> None:
        """
        Upload processing results using presigned URLs.

        Workflow:
        1. Collect all files from source_path
        2. For each file, POST/PUT to upload_url with file data

        The upload_url should accept multipart/form-data or direct binary upload.
        Files are uploaded with their relative paths preserved.

        Args:
            project_id: Unique identifier for the project
            source_path: Local path containing results to upload
            run_id: Run identifier

        Raises:
            ConnectionError: If not connected
            ValueError: If project URLs not configured
            FileNotFoundError: If source path doesn't exist
            IOError: If upload fails
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        if not source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")

        urls = self._get_project_urls(project_id)
        upload_url = urls["upload_url"]

        try:
            files_to_upload = []

            if source_path.is_file():
                files_to_upload.append((source_path, source_path.name))
            elif source_path.is_dir():
                for file_path in source_path.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(source_path)
                        files_to_upload.append((file_path, str(rel_path)))

            if not files_to_upload:
                logger.warning(f"No files found to upload in {source_path}")
                return

            logger.info(f"Uploading {len(files_to_upload)} files for run {run_id}")

            # Upload each file
            uploaded_count = 0
            for file_path, rel_path in files_to_upload:  # type: ignore
                try:
                    # Prepare file for upload
                    with open(file_path, "rb") as f:
                        files = {
                            "file": (rel_path, f, self._get_content_type(file_path)),
                        }
                        data = {
                            "project_id": project_id,
                            "run_id": run_id,
                            "path": rel_path,
                        }

                        logger.debug(f"Uploading {rel_path}")
                        response = self.session.post(
                            upload_url,
                            files=files,  # type: ignore
                            data=data,
                            timeout=self.timeout,
                        )
                        response.raise_for_status()

                        uploaded_count += 1
                        logger.debug(f"Uploaded {rel_path}")

                except Exception as e:
                    logger.warning(f"Failed to upload {rel_path}: {e}")
                    continue

            if uploaded_count == 0:
                raise OSError("Failed to upload any files")

            logger.info(
                f"Successfully uploaded {uploaded_count}/{len(files_to_upload)} files "
                f"for project {project_id}, run {run_id}",
            )

        except RequestException as e:
            logger.error(f"Failed to push results: {e}")
            raise OSError(f"Failed to push results: {e}")

    def _get_content_type(self, file_path: Path) -> str:
        """
        Get content type for a file.

        Args:
            file_path: Path to file

        Returns:
            Content type string
        """
        import mimetypes

        content_type, _ = mimetypes.guess_type(str(file_path))
        return content_type or "application/octet-stream"

    def list_images(self, project_id: str) -> list[str]:
        """
        List available images for a project.

        Makes a GET request to download_url and extracts filenames
        without downloading the actual images.

        Args:
            project_id: Unique identifier for the project

        Returns:
            List of image filenames
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        try:
            urls = self._get_project_urls(project_id)
            download_url = urls["download_url"]

            response = self.session.get(download_url, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            image_urls = self._parse_image_urls(data)

            filenames = []
            for image_info in image_urls:
                if isinstance(image_info, dict):
                    filename = image_info.get(
                        "filename",
                    ) or self._extract_filename_from_url(
                        image_info["url"],
                    )
                else:
                    filename = self._extract_filename_from_url(image_info)
                filenames.append(filename)

            return sorted(filenames)

        except Exception as e:
            logger.error(f"Failed to list images: {e}")
            return []

    def exists(self, path: str) -> bool:
        """
        Check if a path exists.

        Note: This operation is not well-supported with presigned URLs
        as they don't provide a direct way to check existence.

        Args:
            path: Path to check

        Returns:
            False (not supported)
        """
        logger.warning("exists() operation not supported for presigned URL driver")
        return False

    def delete_project(self, project_id: str) -> None:
        """
        Delete all data for a project.

        Note: This operation is not supported with presigned URLs
        as they typically provide read/write access only.

        Args:
            project_id: Unique identifier for the project

        Raises:
            NotImplementedError: Always raised as operation not supported
        """
        raise NotImplementedError(
            "delete_project() not supported for presigned URL driver. "
            "Deletion must be handled through the API that generates the URLs.",
        )
