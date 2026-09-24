import boto3
import requests
from botocore.exceptions import ClientError
from django.conf import settings
import uuid
from urllib.parse import urlparse
from config.logging_config import get_logger

logger = get_logger(__name__)

class S3Service:
    def __init__(self):
        self.aws_access_key_id = settings.AWS_ACCESS_KEY_ID
        self.aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY
        self.region_name = settings.AWS_S3_REGION_NAME
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        logger.info(f"Initializing S3Service - Region: {self.region_name}, Bucket: {self.bucket_name}")
        
        # Build client kwargs - only include credentials if explicitly set
        # When USE_AWS_ROLE=true, boto3 will automatically use ECS Task Role
        client_kwargs = {
            'endpoint_url': settings.AWS_S3_ENDPOINT_URL,
            'region_name': self.region_name,
            'config': boto3.session.Config(signature_version='s3v4')
        }
        
        if self.aws_access_key_id and self.aws_secret_access_key:
            client_kwargs['aws_access_key_id'] = self.aws_access_key_id
            client_kwargs['aws_secret_access_key'] = self.aws_secret_access_key
            logger.info("S3Service: Using explicit AWS credentials")
        else:
            logger.info("S3Service: Using AWS IAM Role (ECS Task Role / Instance Profile)")
        
        self.s3_client = boto3.client('s3', **client_kwargs)
        logger.debug(f"S3 client created with endpoint: {settings.AWS_S3_ENDPOINT_URL}")

        try:
            logger.debug(f"Checking if bucket '{self.bucket_name}' exists...")
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Successfully connected to S3 bucket '{self.bucket_name}'")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                logger.warning(f"Bucket '{self.bucket_name}' not found. Creating it...")
                try:
                    if self.region_name and self.region_name != 'us-east-1':
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region_name}
                        )
                    else:
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Bucket '{self.bucket_name}' created successfully.")
                except Exception as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
            else:
                logger.error(f"S3 connection error: {e}")

    def _get_client_and_bucket(self):
        """Helper to get the raw client and bucket name for advanced operations."""
        return self.s3_client, self.bucket_name

    # ---------------------------------------------------------
    # Cross-Bucket Copy Logic (NEW)
    # ---------------------------------------------------------

    def copy_from_presigned_url(self, source_url, destination_key):
        """
        Downloads a file from a presigned URL to a temp file, then uploads to our S3.
        Uses iter_content for reliable streaming (handles content-encoding properly).
        """
        import tempfile
        import os
        import zipfile

        logger.info(f"Starting copy from presigned URL to S3 key: {destination_key}")
        temp_path = None
        try:
            with requests.get(source_url, stream=True, timeout=300) as response:
                response.raise_for_status()

                content_type = response.headers.get('content-type', 'application/octet-stream')
                content_length = response.headers.get('content-length', 'unknown')
                content_encoding = response.headers.get('content-encoding', 'none')
                logger.info(
                    f"[COPY_URL] Response: status={response.status_code}, "
                    f"content-type={content_type}, content-length={content_length}, "
                    f"content-encoding={content_encoding}"
                )

                with tempfile.NamedTemporaryFile(delete=False, suffix='.download') as tmp:
                    temp_path = tmp.name
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
                        if chunk:
                            tmp.write(chunk)
                            downloaded += len(chunk)
                    tmp.flush()
                    os.fsync(tmp.fileno())

            file_size = os.path.getsize(temp_path)
            logger.info(f"[COPY_URL] Downloaded {file_size} bytes to temp file (iter_content total: {downloaded})")

            with open(temp_path, 'rb') as f:
                header_bytes = f.read(16)
                f.seek(-min(64, file_size), 2)
                tail_bytes = f.read()
                logger.info(
                    f"[COPY_URL] File header(hex): {header_bytes.hex()}, "
                    f"tail(hex): {tail_bytes.hex()}"
                )

            if header_bytes[:4] == b'PK\x03\x04':
                if not zipfile.is_zipfile(temp_path):
                    logger.error(
                        f"[COPY_URL] ZIP header detected but file is NOT a valid ZIP! "
                        f"size={file_size}, content-length={content_length}"
                    )
                else:
                    logger.info(f"[COPY_URL] ZIP validation passed")

            with open(temp_path, 'rb') as f:
                self.s3_client.upload_fileobj(
                    Fileobj=f,
                    Bucket=self.bucket_name,
                    Key=destination_key,
                    ExtraArgs={'ContentType': content_type}
                )

            logger.info(f"[COPY_URL] Successfully uploaded {file_size} bytes to S3: {destination_key}")
            return destination_key

        except requests.RequestException as e:
            logger.error(f"Failed to download from presigned URL: {str(e)}")
            raise Exception(f"Failed to download from Source Presigned URL: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to upload to S3 bucket '{self.bucket_name}': {str(e)}")
            raise Exception(f"Failed to upload to Internal S3: {str(e)}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _parse_s3_url(self, url):
        parsed = urlparse(url)

        if parsed.scheme == 's3':
            # Format: s3://bucket/key
            bucket = parsed.netloc
            key = parsed.path.lstrip('/')
        elif parsed.scheme == 'https':
            # Format: https://bucket.s3.amazonaws.com/key
            # Or: https://s3.region.amazonaws.com/bucket/key
            if parsed.netloc.startswith('s3.'):
                # Path-style: /bucket/key
                parts = parsed.path.lstrip('/').split('/', 1)
                bucket = parts[0]
                key = parts[1]
            else:
                # Virtual-hosted style: bucket.s3...
                bucket = parsed.netloc.split('.')[0]
                key = parsed.path.lstrip('/')
        else:
            raise ValueError("Invalid S3 URL scheme")

        return bucket, key

    # ---------------------------------------------------------
    # Key Generation & Basic Helpers
    # ---------------------------------------------------------

    def generate_s3_key(self, organization_id: int, user_id: int, dataset_id: str, batch_id: str,
                        file_name: str) -> str:
        """
        Generates a highly structured S3 key for optimal organization.
        """
        random_prefix = uuid.uuid4().hex[:8]
        clean_filename = "".join(c if c.isalnum() or c in ('.', '_', '-') else '_' for c in file_name)

        key = (
            f"orgs/{organization_id}/"
            f"users/{user_id}/"
            f"datasets/{dataset_id}/"
            f"batches/{batch_id}/"
            f"{random_prefix}_{clean_filename}"
        )
        return key

    # ---------------------------------------------------------
    # Multipart Upload Methods
    # ---------------------------------------------------------

    def create_multipart_upload(self, key: str, content_type: str) -> str:
        """Initiates a multipart upload and returns the UploadId."""
        logger.info(
            f"[S3:CREATE-MULTIPART] Starting multipart upload creation - "
            f"key: {key}, content_type: {content_type}, bucket: {self.bucket_name}"
        )
        try:
            response = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                ContentType=content_type
            )
            upload_id = response['UploadId']
            logger.info(
                f"[S3:CREATE-MULTIPART] ✅ SUCCESS - UploadId: {upload_id}, key: {key}"
            )
            logger.debug(f"[S3:CREATE-MULTIPART] Full response: {response}")
            return upload_id
        except Exception as e:
            logger.error(
                f"[S3:CREATE-MULTIPART] ❌ FAILED - key: {key}, bucket: {self.bucket_name}, "
                f"error: {str(e)}",
                exc_info=True
            )
            raise

    def generate_presigned_url_part(self, key: str, upload_id: str, part_number: int, expires_in=3600) -> str:
        """
        Generates a presigned URL for uploading a specific part.
        """
        logger.info(
            f"[S3:PRESIGNED-PART] Generating presigned URL - part: {part_number}, "
            f"upload_id: {upload_id[:10]}..., expires_in: {expires_in}s"
        )
        logger.debug(f"[S3:PRESIGNED-PART] Key: {key}, bucket: {self.bucket_name}")
        
        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod='upload_part',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key,
                    'UploadId': upload_id,
                    'PartNumber': part_number
                },
                ExpiresIn=expires_in
            )
            logger.info(
                f"[S3:PRESIGNED-PART] ✅ SUCCESS - Generated URL for part {part_number}, "
                f"length: {len(url)}"
            )
            logger.debug(f"[S3:PRESIGNED-PART] URL preview: {url[:100]}...")
            return url
        except Exception as e:
            logger.error(
                f"[S3:PRESIGNED-PART] ❌ FAILED - part: {part_number}, "
                f"upload_id: {upload_id[:10]}..., key: {key}, error: {str(e)}",
                exc_info=True
            )
            raise

    def complete_multipart_upload(self, key: str, upload_id: str, parts: list):
        """
        Completes the multipart upload by assembling the parts.
        parts format: [{'PartNumber': 1, 'ETag': '...'}, ...]
        """
        logger.info(
            f"[S3:COMPLETE-MULTIPART] Starting completion - "
            f"upload_id: {upload_id[:10]}..., parts_count: {len(parts)}, key: {key}"
        )
        logger.debug(f"[S3:COMPLETE-MULTIPART] Parts summary: {[p['PartNumber'] for p in parts]}")
        logger.debug(f"[S3:COMPLETE-MULTIPART] Bucket: {self.bucket_name}")
        
        try:
            response = self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            logger.info(
                f"[S3:COMPLETE-MULTIPART] ✅ SUCCESS - File assembled in S3, key: {key}"
            )
            logger.debug(f"[S3:COMPLETE-MULTIPART] Response ETag: {response.get('ETag', 'N/A')}")
            logger.debug(f"[S3:COMPLETE-MULTIPART] Response Location: {response.get('Location', 'N/A')}")
        except Exception as e:
            logger.error(
                f"[S3:COMPLETE-MULTIPART] ❌ FAILED - "
                f"upload_id: {upload_id[:10]}..., key: {key}, parts: {len(parts)}, "
                f"error: {str(e)}",
                exc_info=True
            )
            logger.error(
                f"[S3:COMPLETE-MULTIPART] This usually means: \n"
                f"  1. Parts not uploaded to S3 (frontend didn't PUT chunks)\n"
                f"  2. Invalid ETags in parts list\n"
                f"  3. Missing parts (gaps in part numbers)\n"
                f"  4. Upload expired or was aborted"
            )
            raise

    def abort_multipart_upload(self, key: str, upload_id: str):
        """Aborts a multipart upload, freeing up S3 resources."""
        logger.warning(f"Aborting multipart upload {upload_id[:8]}... for key: {key}")
        try:
            self.s3_client.abort_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                UploadId=upload_id
            )
            logger.info(f"Multipart upload aborted successfully")
        except self.s3_client.exceptions.NoSuchUpload:
            logger.debug(f"Upload {upload_id[:8]}... already aborted or doesn't exist")

    # ---------------------------------------------------------
    # Single Object / Stream Methods
    # ---------------------------------------------------------

    def upload_fileobj(self, fileobj, key: str, content_type: str):
        """
        Uploads a file-like object directly to S3 using boto3's transfer manager.
        """
        logger.info(f"Uploading file object to S3 key: {key}, content_type: {content_type}")
        self.s3_client.upload_fileobj(
            fileobj,
            self.bucket_name,
            key,
            ExtraArgs={'ContentType': content_type}
        )
        logger.info(f"File object uploaded successfully to: {key}")

    def upload_bytes(self, key: str, file_content: bytes, content_type: str):
        """
        Uploads raw bytes directly to S3 using put_object.
        Required for uploading extracted files from archives.
        """
        logger.info(f"Uploading {len(file_content)} bytes to S3 key: {key}, content_type: {content_type}")
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_content,
                ContentType=content_type
            )
            logger.info(f"Successfully uploaded {len(file_content)} bytes to: {key}")
        except Exception as e:
            logger.error(f"Error uploading bytes to S3 key {key}: {str(e)}")
            raise e

    def download_file_stream(self, key):
        """Downloads a file from S3 and returns the streaming body."""
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
        return response['Body']

    def download_file(self, key: str) -> bytes:
        """
        Downloads a file from S3 and returns it as bytes.
        Required for processing certain archive types (like tar/rar) in memory.
        """
        logger.info(f"Downloading file from S3 key: {key}")
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            file_data = response['Body'].read()
            logger.info(f"Successfully downloaded {len(file_data)} bytes from: {key}")
            return file_data
        except Exception as e:
            logger.error(f"Error downloading file from S3 key {key}: {str(e)}")
            raise e

    def generate_presigned_download_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generates a presigned URL for downloading a file (GET request).
        """
        logger.debug(f"Generating presigned download URL for key: {key}, expires_in: {expires_in}s")
        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=expires_in
            )
            logger.debug(f"Presigned download URL generated successfully for: {key}")
            return url
        except Exception as e:
            logger.error(f"Error generating presigned download URL for key {key}: {str(e)}")
            raise Exception(f"Error generating presigned download URL: {str(e)}")

    def read_object_head(self, s3_key: str, n_bytes: int = 2048) -> bytes:
        """
        Reads the first n_bytes of an object from S3.
        Used for magic number validation.
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Range=f'bytes=0-{n_bytes-1}'
            )
            return response['Body'].read()
        except Exception as e:
            raise Exception(f"Error reading object head from S3: {str(e)}")

    def delete_object(self, s3_key: str):
        logger.info(f"Deleting S3 object: {s3_key}")
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Successfully deleted S3 object: {s3_key}")
        except Exception as e:
            logger.error(f"Error deleting S3 object {s3_key}: {str(e)}")

    def list_files(self, prefix='', max_keys=1000):
        logger.debug(f"Listing S3 files with prefix: '{prefix}', max_keys: {max_keys}")
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            files = response.get('Contents', [])
            logger.info(f"Found {len(files)} files with prefix '{prefix}'")
            return files
        except Exception as e:
            logger.error(f"Error listing S3 files with prefix '{prefix}': {e}")
            return []
