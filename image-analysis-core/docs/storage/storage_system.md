# PhotoGear Storage System Documentation

## Overview

The PhotoGear storage system provides a flexible and extensible architecture for managing image datasets and processing results across different storage backends (local filesystem, AWS S3, etc.).

## Architecture

### Components

1. **Storage Drivers** - Abstract interface for different storage backends
2. **Dataset Manager** - High-level API for dataset operations
3. **Factory Pattern** - Easy creation of storage driver instances

### Directory Structure

```
infrastructure/storage/
├── __init__.py
├── dataset.py                 # Dataset manager class
├── example_usage.py           # Usage examples
├── drivers/
│   ├── __init__.py
│   ├── base.py               # Abstract storage driver interface
│   ├── local.py              # Local filesystem implementation
│   ├── s3.py                 # AWS S3 implementation
│   └── factory.py            # Factory for creating drivers
```

## Dataset Workflow

### Typical Processing Flow

```
1. User creates project with project_id
2. User uploads images to storage (images folder)
3. Processing pipeline starts:
   a. Create Dataset instance with storage driver
   b. Initialize dataset workspace
   c. Fetch images from storage to temp directory
   d. Create run directory (run_1, run_2, etc.)
   e. Process images (SFM, orthomosaic, etc.)
   f. Push results back to storage
   g. Cleanup temporary files
```

### Temporary Directory Structure

```
/tmp/photogear/{project_id}/
├── images/              # Fetched from storage
│   ├── image001.jpg
│   ├── image002.jpg
│   └── ...
├── run_1/              # First processing run
│   ├── sfm/
│   ├── dense/
│   └── orthomosaic/
├── run_2/              # Second processing run (reprocessing)
│   └── ...
└── run_3/              # Third processing run
    └── ...
```

### Storage Structure

#### Local Storage
```
{base_path}/{project_id}/
├── images/             # Original images
│   ├── image001.jpg
│   └── ...
├── run_1/             # Results from run 1
│   ├── sfm/
│   ├── dense/
│   └── orthomosaic/
├── run_2/             # Results from run 2
│   └── ...
```

#### S3 Storage
```
s3://{bucket}/{prefix}/{project_id}/
├── images/             # Original images
│   ├── image001.jpg
│   └── ...
├── run_1/             # Results from run 1
│   ├── sfm/
│   ├── dense/
│   └── orthomosaic/
├── run_2/             # Results from run 2
│   └── ...
```

## Usage

### 1. Basic Usage with Local Storage

```python
from pathlib import Path
from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.factory import StorageDriverFactory

# Create local storage driver
driver = StorageDriverFactory.create('local', {
    'base_path': Path('/mnt/storage')
})

# Connect to storage
driver.connect()

# Create dataset
dataset = Dataset(
    project_id="my_project_001",
    storage_driver=driver
)

# Initialize workspace
dataset.initialize_dataset()

# Fetch images
images_path = dataset.fetch_images()
print(f"Images ready at: {images_path}")

# Create processing run
run_path = dataset.create_run()
print(f"Processing in: {run_path}")

# ... do processing ...

# Push results
dataset.push_results()

# Cleanup
dataset.cleanup()

# Disconnect
driver.disconnect()
```

### 2. Using AWS S3 Storage

```python
from infrastructure.storage.drivers.factory import StorageDriverFactory
from infrastructure.storage.dataset import Dataset

# Create S3 driver
driver = StorageDriverFactory.create('s3', {
    'bucket_name': 'my-photogear-bucket',
    'region_name': 'us-west-2',
    'aws_access_key_id': 'YOUR_ACCESS_KEY',      # Optional, uses env vars
    'aws_secret_access_key': 'YOUR_SECRET_KEY',  # Optional, uses env vars
    'prefix': 'photogear'
})

driver.connect()

dataset = Dataset(
    project_id="drone_survey_001",
    storage_driver=driver
)

# Same workflow as local storage
dataset.initialize_dataset()
images_path = dataset.fetch_images()
run_path = dataset.create_run()

# ... processing ...

dataset.push_results()
dataset.cleanup()
driver.disconnect()
```

### 3. Using Environment Variables

```python
import os
from infrastructure.storage.drivers.factory import StorageDriverFactory

# Set environment variables
os.environ['STORAGE_DRIVER'] = 's3'
os.environ['S3_BUCKET_NAME'] = 'my-bucket'
os.environ['AWS_REGION'] = 'us-west-2'

# Create driver from environment
driver = StorageDriverFactory.create_from_env()
driver.connect()

# Use driver with dataset...
```

### 4. Multiple Processing Runs

```python
dataset = Dataset(project_id="project_001", storage_driver=driver)
dataset.initialize_dataset()
dataset.fetch_images()

# Run 1
run1_path = dataset.create_run()  # Creates run_1
# ... process ...
dataset.push_results()

# Run 2 (reprocessing with different parameters)
run2_path = dataset.create_run()  # Creates run_2
# ... process ...
dataset.push_results()

# Run 3
run3_path = dataset.create_run()  # Creates run_3
# ... process ...
dataset.push_results()

print(f"Completed {dataset.current_run_id} runs")
```

## Storage Driver API

### Abstract Interface (`StorageDriver`)

All storage drivers must implement:

- `connect()` - Establish connection to storage
- `disconnect()` - Close connection
- `fetch_images(project_id, destination_path)` - Download images
- `push_results(project_id, source_path, run_id)` - Upload results
- `list_images(project_id)` - List available images
- `exists(path)` - Check if path exists
- `delete_project(project_id)` - Delete all project data

### LocalStorageDriver

**Parameters:**
- `base_path` (Path): Root directory for storage

**Example:**
```python
from pathlib import Path
from infrastructure.storage.drivers.local import LocalStorageDriver

driver = LocalStorageDriver(base_path=Path('/mnt/storage'))
driver.connect()
```

### S3StorageDriver

**Parameters:**
- `bucket_name` (str): S3 bucket name
- `region_name` (str, optional): AWS region (default: 'us-east-1')
- `aws_access_key_id` (str, optional): AWS access key
- `aws_secret_access_key` (str, optional): AWS secret key
- `prefix` (str): Prefix for S3 keys (default: 'photogear')

**Example:**
```python
from infrastructure.storage.drivers.s3 import S3StorageDriver

driver = S3StorageDriver(
    bucket_name='my-bucket',
    region_name='us-west-2',
    prefix='photogear'
)
driver.connect()
```

## Dataset API

### Initialization

```python
Dataset(
    project_id: str,
    storage_driver: StorageDriver,
    temp_base_path: Optional[Path] = None  # defaults to /tmp/photogear
)
```

### Methods

#### `initialize_dataset()`
Creates the workspace directory structure.

```python
dataset.initialize_dataset()
```

#### `fetch_images() -> Path`
Downloads images from storage to local workspace.

```python
images_path = dataset.fetch_images()
```

#### `create_run() -> Path`
Creates a new run directory (run_1, run_2, etc.).

```python
run_path = dataset.create_run()
```

#### `get_run_path(run_id: Optional[int] = None) -> Path`
Gets path to a specific run directory.

```python
# Get current run path
current_path = dataset.get_run_path()

# Get specific run path
run2_path = dataset.get_run_path(run_id=2)
```

#### `push_results(source_path: Optional[Path] = None, run_id: Optional[int] = None)`
Uploads results to storage.

```python
# Push current run results
dataset.push_results()

# Push specific directory
dataset.push_results(source_path=Path('/tmp/results'), run_id=5)
```

#### `cleanup(keep_results: bool = False)`
Cleans up temporary workspace.

```python
# Remove everything
dataset.cleanup()

# Keep run results, only remove images
dataset.cleanup(keep_results=True)
```

#### `list_images() -> List[str]`
Lists available images for the project.

```python
images = dataset.list_images()
print(f"Found {len(images)} images")
```

#### `get_images_path() -> Path`
Returns path to images directory.

```python
images_path = dataset.get_images_path()
```

### Properties

#### `current_run_id` (Optional[int])
Current run identifier.

```python
run_id = dataset.current_run_id
```

#### `current_run_path` (Optional[Path])
Current run directory path.

```python
run_path = dataset.current_run_path
```

## Environment Variables

### Storage Driver Selection
- `STORAGE_DRIVER`: 'local' or 's3' (default: 'local')

### Local Storage
- `STORAGE_BASE_PATH`: Base path for local storage (default: '/tmp/photogear_storage')

### S3 Storage
- `S3_BUCKET_NAME`: S3 bucket name (required for S3)
- `AWS_REGION`: AWS region (default: 'us-east-1')
- `AWS_ACCESS_KEY_ID`: AWS access key (optional, uses AWS SDK default chain)
- `AWS_SECRET_ACCESS_KEY`: AWS secret key (optional, uses AWS SDK default chain)
- `S3_PREFIX`: Prefix for S3 keys (default: 'photogear')

## Integration with Services

### Orthomosaic Generation Service

```python
from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.factory import StorageDriverFactory

def process_orthomosaic(project_id: str):
    """Process orthomosaic for a project."""

    # Create storage driver from environment
    driver = StorageDriverFactory.create_from_env()
    driver.connect()

    try:
        # Create dataset
        dataset = Dataset(project_id=project_id, storage_driver=driver)
        dataset.initialize_dataset()

        # Fetch images
        images_path = dataset.fetch_images()

        # Create run
        run_path = dataset.create_run()

        # Run SFM
        sfm_output = run_sfm(images_path, run_path / "sfm")

        # Generate orthomosaic
        ortho_output = generate_orthomosaic(
            sfm_output,
            run_path / "orthomosaic"
        )

        # Push results
        dataset.push_results()

        # Cleanup
        dataset.cleanup()

        return {
            'status': 'success',
            'run_id': dataset.current_run_id,
            'output': str(ortho_output)
        }

    finally:
        driver.disconnect()
```

### API Gateway Integration

```python
from fastapi import APIRouter, HTTPException
from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.factory import StorageDriverFactory

router = APIRouter()

@router.post("/projects/{project_id}/process")
async def process_project(project_id: str):
    """Start processing pipeline for a project."""

    driver = StorageDriverFactory.create_from_env()
    driver.connect()

    try:
        dataset = Dataset(project_id=project_id, storage_driver=driver)

        # Check if images exist
        images = dataset.list_images()
        if not images:
            raise HTTPException(
                status_code=404,
                detail=f"No images found for project {project_id}"
            )

        # Initialize and start processing
        dataset.initialize_dataset()
        images_path = dataset.fetch_images()
        run_path = dataset.create_run()

        # Queue processing job...

        return {
            'project_id': project_id,
            'run_id': dataset.current_run_id,
            'image_count': len(images),
            'status': 'processing'
        }

    finally:
        driver.disconnect()
```

## Error Handling

```python
from infrastructure.storage.dataset import Dataset

try:
    dataset = Dataset(project_id="test", storage_driver=driver)
    dataset.fetch_images()

except FileNotFoundError as e:
    # No images found for project
    print(f"Images not found: {e}")

except ConnectionError as e:
    # Storage connection failed
    print(f"Connection error: {e}")

except IOError as e:
    # Upload/download failed
    print(f"I/O error: {e}")

except Exception as e:
    # Other errors
    print(f"Unexpected error: {e}")
```

## Best Practices

1. **Always use context managers or try/finally blocks**
   ```python
   driver.connect()
   try:
       # ... operations ...
   finally:
       driver.disconnect()
   ```

2. **Use environment variables for configuration**
   ```python
   driver = StorageDriverFactory.create_from_env()
   ```

3. **Cleanup temporary files after processing**
   ```python
   dataset.push_results()
   dataset.cleanup()
   ```

4. **Handle errors gracefully**
   ```python
   try:
       dataset.fetch_images()
   except FileNotFoundError:
       logger.error("Images not found")
       # Handle appropriately
   ```

5. **Use appropriate storage driver for environment**
   - Development/Testing: `LocalStorageDriver`
   - Production: `S3StorageDriver`

## Extending the System

### Creating a Custom Storage Driver

```python
from infrastructure.storage.drivers.base import StorageDriver
from pathlib import Path
from typing import List

class CustomStorageDriver(StorageDriver):
    """Custom storage driver implementation."""

    def __init__(self, custom_param: str):
        self.custom_param = custom_param
        self._connected = False

    def connect(self) -> None:
        # Implement connection logic
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def fetch_images(self, project_id: str, destination_path: Path) -> List[Path]:
        # Implement fetch logic
        pass

    def push_results(self, project_id: str, source_path: Path, run_id: int) -> None:
        # Implement push logic
        pass

    def list_images(self, project_id: str) -> List[str]:
        # Implement list logic
        pass

    def exists(self, path: str) -> bool:
        # Implement exists logic
        pass

    def delete_project(self, project_id: str) -> None:
        # Implement delete logic
        pass

# Register with factory
from infrastructure.storage.drivers.factory import StorageDriverFactory

StorageDriverFactory.register_driver('custom', CustomStorageDriver)

# Use it
driver = StorageDriverFactory.create('custom', {'custom_param': 'value'})
```

## Troubleshooting

### Images not found
- Verify project_id is correct
- Check storage backend has images in `{project_id}/images/` folder
- Verify storage driver connection is successful

### S3 connection failed
- Check AWS credentials are configured
- Verify bucket exists and is accessible
- Check IAM permissions for the bucket
- Verify region is correct

### Upload/download slow
- For S3: Consider using multipart upload for large files
- Check network bandwidth
- Consider compression for large datasets

### Permission errors
- Check filesystem permissions (local storage)
- Check IAM policies (S3 storage)
- Verify write access to temp directories

## Performance Considerations

- Large datasets: Consider parallel upload/download
- Network latency: Use regional S3 buckets
- Disk space: Monitor temp directory space
- Cleanup: Always cleanup after processing to free space

## Security

- Never hardcode AWS credentials
- Use IAM roles when running on AWS infrastructure
- Use environment variables or AWS credential chain
- Restrict S3 bucket access with appropriate policies
- Consider encryption for sensitive data
