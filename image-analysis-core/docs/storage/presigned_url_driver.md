# Presigned URL Storage Driver

## Overview

The `PresignedUrlStorageDriver` is a storage driver implementation for PhotoGear that works with S3 presigned URLs. This driver is ideal for scenarios where:

- Direct S3 access is not available or desired
- An API gateway manages access to S3 resources
- You want to use temporary, scoped access URLs
- Security policies require presigned URLs for data access

## How It Works

### Download Workflow

1. **GET Request**: The driver makes a GET request to a presigned URL endpoint
2. **JSON Response**: The endpoint returns a JSON response containing a list of presigned URLs for images
3. **Download Images**: Each image is downloaded individually using its presigned URL
4. **Local Storage**: Images are saved to the local workspace

### Upload Workflow

1. **Collect Files**: The driver collects all files from the results directory
2. **POST Request**: Each file is uploaded via POST request to the presigned upload URL
3. **Metadata**: File path and project information are included in the upload

## Supported JSON Response Formats

The driver automatically handles multiple JSON response formats for the download endpoint:

### Format 1: Detailed Image Info
```json
{
  "images": [
    {
      "url": "https://s3.amazonaws.com/bucket/image1.jpg?AWSAccessKeyId=...",
      "filename": "DJI_001.jpg"
    },
    {
      "url": "https://s3.amazonaws.com/bucket/image2.jpg?AWSAccessKeyId=...",
      "filename": "DJI_002.jpg"
    }
  ]
}
```

### Format 2: Simple URL List
```json
{
  "urls": [
    "https://s3.amazonaws.com/bucket/image1.jpg?AWSAccessKeyId=...",
    "https://s3.amazonaws.com/bucket/image2.jpg?AWSAccessKeyId=..."
  ]
}
```

### Format 3: Files with 'name' Field
```json
{
  "files": [
    {
      "url": "https://s3.amazonaws.com/bucket/image1.jpg?AWSAccessKeyId=...",
      "name": "DJI_001.jpg"
    }
  ]
}
```

### Format 4: Nested Data Structure
```json
{
  "status": "success",
  "data": {
    "images": [
      {
        "url": "https://s3.amazonaws.com/bucket/image1.jpg?AWSAccessKeyId=..."
      }
    ]
  }
}
```

## Usage

### Basic Usage

```python
from pathlib import Path
from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.presigned_url import PresignedUrlStorageDriver

# Create driver
driver = PresignedUrlStorageDriver(timeout=300)
driver.connect()

# Set project-specific URLs
driver.set_project_urls(
    project_id="my_project",
    download_url="https://api.example.com/projects/my_project/images/download",
    upload_url="https://api.example.com/projects/my_project/results/upload"
)

# Use with Dataset
dataset = Dataset(
    project_id="my_project",
    storage_driver=driver,
    temp_base_path=Path("/tmp/photogear")
)

# Initialize and fetch images
dataset.initialize_dataset()
images_path = dataset.fetch_images()

# Process and upload results
run_path = dataset.create_run()
# ... do processing ...
dataset.push_results()

# Cleanup
dataset.cleanup()
driver.disconnect()
```

### Using StorageDriverFactory

```python
from infrastructure.storage.drivers.factory import StorageDriverFactory

# Create driver using factory
driver = StorageDriverFactory.create(
    "presigned_url",
    {"timeout": 300}
)

driver.connect()

# Set URLs for project
driver.set_project_urls(
    project_id="my_project",
    download_url="https://...",
    upload_url="https://..."
)

# Use as normal...
```

### Multiple Projects

```python
# Create driver
driver = PresignedUrlStorageDriver()
driver.connect()

# Configure multiple projects
driver.set_project_urls(
    project_id="project_1",
    download_url="https://api.example.com/projects/project_1/images/download",
    upload_url="https://api.example.com/projects/project_1/results/upload"
)

driver.set_project_urls(
    project_id="project_2",
    download_url="https://api.example.com/projects/project_2/images/download",
    upload_url="https://api.example.com/projects/project_2/results/upload"
)

# Use with different projects
dataset1 = Dataset(project_id="project_1", storage_driver=driver)
dataset2 = Dataset(project_id="project_2", storage_driver=driver)
```

### Dynamic URL Provider Pattern

For applications where URLs need to be generated dynamically:

```python
class PresignedUrlService:
    """Service to fetch presigned URLs from API Gateway."""

    def __init__(self, api_base_url: str, api_key: str):
        self.api_base_url = api_base_url
        self.api_key = api_key

    def get_download_url(self, project_id: str) -> str:
        """Request a presigned URL for downloading images."""
        import requests
        response = requests.post(
            f"{self.api_base_url}/presigned-urls/download",
            json={"project_id": project_id},
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()["url"]

    def get_upload_url(self, project_id: str, run_id: int) -> str:
        """Request a presigned URL for uploading results."""
        import requests
        response = requests.post(
            f"{self.api_base_url}/presigned-urls/upload",
            json={"project_id": project_id, "run_id": run_id},
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()["url"]

# Usage
url_service = PresignedUrlService(
    api_base_url="https://api.photogear.example.com",
    api_key="your-api-key"
)

driver = PresignedUrlStorageDriver()
driver.connect()

# Get URLs dynamically
download_url = url_service.get_download_url("my_project")
upload_url = url_service.get_upload_url("my_project", run_id=1)

driver.set_project_urls(
    project_id="my_project",
    download_url=download_url,
    upload_url=upload_url
)
```

## Configuration

### Constructor Parameters

- `project_urls` (dict, optional): Pre-configured URLs for projects. Format:
  ```python
  {
      "project_id": {
          "download_url": "https://...",
          "upload_url": "https://..."
      }
  }
  ```
- `timeout` (int, optional): HTTP request timeout in seconds. Default: 300

### Environment Variables

When using `StorageDriverFactory.create_from_env()`:

```bash
export STORAGE_DRIVER=presigned_url
export PRESIGNED_URL_TIMEOUT=300  # optional, defaults to 300
```

Note: Project URLs must still be set via `set_project_urls()` as they are project-specific.

## API Methods

### `connect()`
Establish connection and initialize HTTP session.

### `disconnect()`
Close HTTP session and cleanup.

### `set_project_urls(project_id, download_url, upload_url)`
Configure presigned URLs for a specific project.

### `fetch_images(project_id, destination_path)`
Download images using presigned URLs.

**Returns**: List of downloaded image paths

**Raises**:
- `ConnectionError`: If driver not connected
- `ValueError`: If project URLs not configured
- `FileNotFoundError`: If no images found
- `IOError`: If download fails

### `push_results(project_id, source_path, run_id)`
Upload results using presigned URLs.

**Raises**:
- `ConnectionError`: If driver not connected
- `ValueError`: If project URLs not configured
- `FileNotFoundError`: If source path doesn't exist
- `IOError`: If upload fails

### `list_images(project_id)`
List available images without downloading.

**Returns**: List of image filenames

## Limitations

- **exists()**: Not supported, always returns `False`
- **delete_project()**: Not supported, raises `NotImplementedError`
  - Deletion must be handled through the API that generates the presigned URLs

## Security Considerations

1. **URL Expiration**: Presigned URLs typically have an expiration time. Ensure URLs are refreshed before they expire.

2. **HTTPS Only**: Always use HTTPS URLs for secure transmission.

3. **URL Storage**: Don't log or store presigned URLs permanently as they contain embedded credentials.

4. **Timeout**: Set appropriate timeout values to prevent hanging on slow connections.

## Integration with API Gateway

The presigned URL driver is designed to work with an API Gateway that provides presigned URL endpoints:

### Expected API Gateway Endpoints

#### Download Endpoint
```
GET /projects/{project_id}/images/download
```

**Response**:
```json
{
  "images": [
    {
      "url": "presigned-s3-url-1",
      "filename": "image1.jpg"
    }
  ]
}
```

#### Upload Endpoint
```
POST /projects/{project_id}/results/upload
```

**Request** (multipart/form-data):
- `file`: File binary data
- `project_id`: Project identifier
- `run_id`: Run identifier
- `path`: Relative file path

**Response**:
```json
{
  "status": "success",
  "message": "File uploaded"
}
```

## Error Handling

The driver includes comprehensive error handling:

- Network errors are logged and converted to `IOError`
- JSON parsing errors are caught and reported
- Failed individual image downloads don't stop the entire batch
- Meaningful error messages help debug issues

## Logging

The driver uses Python's `logging` module. Enable debug logging to see detailed information:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

Log messages include:
- Connection status
- URL configuration
- Download/upload progress
- Individual file operations
- Errors and warnings

## Testing

Example test setup:

```python
import unittest
from unittest.mock import Mock, patch
from infrastructure.storage.drivers.presigned_url import PresignedUrlStorageDriver

class TestPresignedUrlDriver(unittest.TestCase):
    def test_fetch_images(self):
        driver = PresignedUrlStorageDriver()
        driver.connect()

        # Mock HTTP responses
        with patch.object(driver.session, 'get') as mock_get:
            # Mock the list endpoint
            mock_get.return_value.json.return_value = {
                "images": [
                    {"url": "http://example.com/img1.jpg", "filename": "img1.jpg"}
                ]
            }
            mock_get.return_value.content = b"fake image data"

            driver.set_project_urls(
                "test_project",
                "http://example.com/download",
                "http://example.com/upload"
            )

            images = driver.fetch_images("test_project", Path("/tmp/test"))
            self.assertEqual(len(images), 1)
```

## Comparison with Other Drivers

| Feature | Local | S3 | Presigned URL |
|---------|-------|-----|---------------|
| Direct S3 Access | ❌ | ✅ | ❌ |
| API Gateway Compatible | ❌ | ❌ | ✅ |
| Temporary Access | ❌ | ❌ | ✅ |
| AWS Credentials Required | ❌ | ✅ | ❌ |
| Delete Support | ✅ | ✅ | ❌ |
| Exists Check | ✅ | ✅ | ❌ |
| Setup Complexity | Low | Medium | Low |

## Troubleshooting

### "No URLs configured for project"
- Make sure to call `set_project_urls()` before using fetch/push methods

### "Failed to fetch images: Invalid response format"
- Check that the download endpoint returns JSON in one of the supported formats
- Enable debug logging to see the actual response

### "Request timeout"
- Increase the timeout parameter
- Check network connectivity to the API gateway

### "Failed to download any images"
- Verify the presigned URLs are valid and not expired
- Check that the URLs are accessible from your network
- Ensure the URLs point to actual image files

## Future Enhancements

Potential improvements for future versions:

1. **Batch Upload**: Support for multipart batch uploads
2. **Progress Callbacks**: Report download/upload progress
3. **Retry Logic**: Automatic retry on transient failures
4. **Caching**: Cache presigned URLs until expiration
5. **Async Operations**: Support for asynchronous downloads/uploads
