from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .base import StorageDriver
from infrastructure.logging import get_logger
from infrastructure.storage.s3_settings import S3StorageSettings, AWSSettings

logger = get_logger(__name__)

MAX_DOWNLOAD_WORKERS = 8


class S3StorageDriver(StorageDriver):
    """
    AWS S3 storage driver.

    Manages files in AWS S3 bucket. Suitable for production deployments.
    Can use shared S3StorageSettings or custom configuration.
    
    When USE_AWS_ROLE=true in environment, uses ECS Task Role / IAM Instance Profile
    for authentication (recommended for AWS deployments).
    Otherwise, uses explicit credentials from settings or environment variables.
    """

    def __init__(
        self,
        bucket_name: str | None = None,
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        prefix: str = "photogear",
        settings: S3StorageSettings | None = None,
    ):
        """
        Initialize S3 storage driver.

        Args:
            bucket_name: Name of the S3 bucket (overrides settings)
            region_name: AWS region (defaults to settings or 'us-east-1')
            aws_access_key_id: AWS access key (defaults to settings, ignored if USE_AWS_ROLE=true)
            aws_secret_access_key: AWS secret key (defaults to settings, ignored if USE_AWS_ROLE=true)
            prefix: Prefix for all S3 keys (default: "photogear")
            settings: Shared S3StorageSettings instance
        """
        # Check if we should use AWS IAM Role instead of explicit credentials
        aws_settings = AWSSettings()
        self.use_aws_role = aws_settings.use_aws_role
        
        # Use settings if provided, otherwise use params
        if settings:
            self.bucket_name = bucket_name or settings.raw_images_bucket
            self.region_name = region_name or settings.region_name
            # Only use credentials if NOT using AWS role
            if not self.use_aws_role and settings.has_explicit_credentials:
                self.aws_access_key_id = aws_access_key_id or settings.access_key_id
                self.aws_secret_access_key = aws_secret_access_key or settings.secret_access_key
            else:
                self.aws_access_key_id = None
                self.aws_secret_access_key = None
        else:
            self.bucket_name = bucket_name
            self.region_name = region_name or "us-east-1"
            # Only use credentials if NOT using AWS role
            if not self.use_aws_role:
                self.aws_access_key_id = aws_access_key_id
                self.aws_secret_access_key = aws_secret_access_key
            else:
                self.aws_access_key_id = None
                self.aws_secret_access_key = None
        
        self.prefix = prefix.strip("/")
        self.s3_client = None
        self._connected = False

    def connect(self) -> None:
        """
        Establish connection to S3.
        
        When USE_AWS_ROLE=true, boto3 will automatically use ECS Task Role
        or IAM Instance Profile for authentication.
        """
        try:
            session_kwargs = {
                "region_name": self.region_name,
            }

            if self.aws_access_key_id and self.aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = self.aws_access_key_id
                session_kwargs["aws_secret_access_key"] = self.aws_secret_access_key
                logger.info("S3StorageDriver: Using explicit AWS credentials")
            else:
                # Let boto3 use ECS Task Role / IAM Instance Profile automatically
                logger.info("S3StorageDriver: Using AWS IAM Role (ECS Task Role / Instance Profile)")

            session = boto3.Session(**session_kwargs)
            self.s3_client = session.client("s3")

            # Test connection by checking if bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)  # type: ignore

            self._connected = True
            logger.info(f"Connected to S3 bucket: {self.bucket_name}")

        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise ConnectionError(
                "AWS credentials not found. Please configure AWS credentials.",
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                logger.error(f"Bucket {self.bucket_name} does not exist")
                raise ConnectionError(f"S3 bucket '{self.bucket_name}' not found")
            elif error_code == "403":
                logger.error(f"Access denied to bucket {self.bucket_name}")
                raise ConnectionError(
                    f"Access denied to S3 bucket '{self.bucket_name}'",
                )
            else:
                logger.error(f"Failed to connect to S3: {e}")
                raise ConnectionError(f"Failed to connect to S3: {e}")

    def disconnect(self) -> None:
        """
        Close S3 connection.
        """
        self.s3_client = None
        self._connected = False
        logger.info("Disconnected from S3")

    def _get_s3_key(self, project_id: str, *parts: str) -> str:
        """
        Construct S3 key with proper prefix.

        Args:
            project_id: Project identifier
            *parts: Additional path parts

        Returns:
            Full S3 key
        """
        key_parts = [self.prefix, project_id] + list(parts)
        return "/".join(key_parts)

    def fetch_images(self, project_id: str, destination_path: Path) -> list[Path]:
        """
        Download images from S3 to destination.

        Args:
            project_id: Unique identifier for the project
            destination_path: Local path where images should be downloaded

        Returns:
            List of paths to downloaded images
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        destination_path.mkdir(parents=True, exist_ok=True)

        # List all objects in the images folder
        prefix = self._get_s3_key(project_id, "images") + "/"
        downloaded_images = []

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")  # type: ignore
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            image_extensions = {
                ".jpg",
                ".jpeg",
                ".png",
                ".tif",
                ".tiff",
                ".JPG",
                ".JPEG",
                ".PNG",
                ".TIF",
                ".TIFF",
            }

            image_keys: list[tuple[str, str]] = []

            for page in pages:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    key = obj["Key"]
                    if key.endswith("/"):
                        continue

                    filename = Path(key).name
                    if Path(filename).suffix in image_extensions:
                        image_keys.append((key, filename))

            if not image_keys:
                raise FileNotFoundError(
                    f"No images found for project {project_id} in S3",
                )

            logger.info(f"Found {len(image_keys)} images to download in parallel")

            def _download_one(key: str, filename: str) -> Path:
                local_file = destination_path / filename
                self.s3_client.download_file(  # type: ignore
                    Bucket=self.bucket_name,
                    Key=key,
                    Filename=str(local_file),
                )
                logger.debug(f"Downloaded {key} to {local_file}")
                return local_file

            downloaded_images: list[Path] = []
            with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS) as executor:
                futures = {
                    executor.submit(_download_one, key, fname): key
                    for key, fname in image_keys
                }
                for future in as_completed(futures):
                    downloaded_images.append(future.result())

            logger.info(
                f"Fetched {len(downloaded_images)} images for project {project_id} from S3",
            )
            return downloaded_images

        except ClientError as e:
            logger.error(f"Failed to fetch images from S3: {e}")
            raise OSError(f"Failed to fetch images from S3: {e}")

    def push_results(self, project_id: str, source_path: Path, run_id: int) -> None:
        """
        Upload processing results to S3.

        Args:
            project_id: Unique identifier for the project
            source_path: Local path containing results to upload
            run_id: Run identifier
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        if not source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")

        try:
            if source_path.is_file():
                # Upload single file
                key = self._get_s3_key(project_id, f"run_{run_id}", source_path.name)
                self.s3_client.upload_file(  # type: ignore
                    Filename=str(source_path),
                    Bucket=self.bucket_name,
                    Key=key,
                )
                logger.info(f"Uploaded file {source_path.name} to S3")

            elif source_path.is_dir():
                # Upload directory contents
                uploaded_count = 0
                for file_path in source_path.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(source_path)
                        key = self._get_s3_key(
                            project_id,
                            f"run_{run_id}",
                            str(rel_path),
                        )

                        self.s3_client.upload_file(  # type: ignore
                            Filename=str(file_path),
                            Bucket=self.bucket_name,
                            Key=key,
                        )
                        uploaded_count += 1
                        logger.debug(f"Uploaded {file_path} to S3 as {key}")

                logger.info(
                    f"Uploaded {uploaded_count} files for project {project_id}, run {run_id} to S3",
                )

        except ClientError as e:
            logger.error(f"Failed to push results to S3: {e}")
            raise OSError(f"Failed to push results to S3: {e}")

    def fetch_auxiliary_files(
        self,
        project_id: str,
        destination_path: Path,
    ) -> list[Path]:
        """
        Download PPK/GNSS auxiliary files (.nav, .obs, .bin, .mrk) from S3.

        Searches two S3 prefixes:
          1. ``{prefix}/{project_id}/images/`` — for datasets where all files
             (images + PPK) were uploaded into the same folder.
          2. ``{prefix}/{project_id}/ppk/``    — dedicated PPK folder.

        Files are saved flat into ``destination_path`` (the dataset root so that
        ``geo_register()`` can find the ``.MRK`` file with ``workspace.glob("*.MRK")``).

        Args:
            project_id: Unique identifier for the project
            destination_path: Local directory where auxiliary files should be saved

        Returns:
            List of paths to downloaded auxiliary files (empty if none found)
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        destination_path.mkdir(parents=True, exist_ok=True)

        ppk_extensions = {
            ".nav", ".NAV",
            ".obs", ".OBS",
            ".bin", ".BIN",
            ".mrk", ".MRK",
        }

        search_prefixes = [
            self._get_s3_key(project_id, "images") + "/",
            self._get_s3_key(project_id, "ppk") + "/",
        ]

        aux_keys: list[tuple[str, str]] = []

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")  # type: ignore
            for search_prefix in search_prefixes:
                pages = paginator.paginate(Bucket=self.bucket_name, Prefix=search_prefix)
                for page in pages:
                    if "Contents" not in page:
                        continue
                    for obj in page["Contents"]:
                        key = obj["Key"]
                        if key.endswith("/"):
                            continue
                        filename = Path(key).name
                        if Path(filename).suffix in ppk_extensions:
                            aux_keys.append((key, filename))

            if not aux_keys:
                logger.debug(
                    f"No PPK auxiliary files found for project {project_id} "
                    f"under images/ or ppk/ prefixes"
                )
                return []

            logger.info(
                f"Found {len(aux_keys)} PPK auxiliary file(s) to download "
                f"for project {project_id}"
            )

            def _download_one(key: str, filename: str) -> Path:
                local_file = destination_path / filename
                self.s3_client.download_file(  # type: ignore
                    Bucket=self.bucket_name,
                    Key=key,
                    Filename=str(local_file),
                )
                logger.debug(f"Downloaded auxiliary file {key} → {local_file}")
                return local_file

            downloaded: list[Path] = []
            with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS) as executor:
                futures = {
                    executor.submit(_download_one, key, fname): key
                    for key, fname in aux_keys
                }
                for future in as_completed(futures):
                    downloaded.append(future.result())

            logger.info(
                f"Downloaded {len(downloaded)} PPK auxiliary file(s) "
                f"for project {project_id}"
            )
            return downloaded

        except ClientError as e:
            logger.warning(
                f"Failed to fetch auxiliary files from S3 for project {project_id}: {e} "
                "(non-fatal — pipeline will continue without PPK data)"
            )
            return []

    def list_images(self, project_id: str) -> list[str]:
        """
        List available images for a project in S3.

        Args:
            project_id: Unique identifier for the project

        Returns:
            List of image filenames
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        prefix = self._get_s3_key(project_id, "images") + "/"
        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".tif",
            ".tiff",
            ".JPG",
            ".JPEG",
            ".PNG",
            ".TIF",
            ".TIFF",
        }
        images = []

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")  # type: ignore
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            for page in pages:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    key = obj["Key"]
                    if key.endswith("/"):
                        continue

                    filename = Path(key).name
                    if Path(filename).suffix in image_extensions:
                        images.append(filename)

            return sorted(images)

        except ClientError as e:
            logger.error(f"Failed to list images from S3: {e}")
            return []

    def exists(self, path: str) -> bool:
        """
        Check if a path exists in S3.

        Args:
            path: Path to check (relative to prefix)

        Returns:
            True if path exists, False otherwise
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        key = f"{self.prefix}/{path}".strip("/")

        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)  # type: ignore
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                logger.error(f"Error checking existence in S3: {e}")
                raise

    def delete_project(self, project_id: str) -> None:
        """
        Delete all data for a project in S3.

        Args:
            project_id: Unique identifier for the project
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        prefix = self._get_s3_key(project_id) + "/"

        try:
            # List all objects with the project prefix
            paginator = self.s3_client.get_paginator("list_objects_v2")  # type: ignore
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            objects_to_delete = []
            for page in pages:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    objects_to_delete.append({"Key": obj["Key"]})

            # Delete objects in batches of 1000 (S3 limit)
            if objects_to_delete:
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i : i + 1000]
                    self.s3_client.delete_objects(  # type: ignore
                        Bucket=self.bucket_name,
                        Delete={"Objects": batch},
                    )

                logger.info(
                    f"Deleted {len(objects_to_delete)} objects for project {project_id} from S3",
                )
            else:
                logger.warning(f"No objects found for project {project_id} in S3")

        except ClientError as e:
            logger.error(f"Failed to delete project from S3: {e}")
            raise OSError(f"Failed to delete project from S3: {e}")
