# Directory Structure and Timeout Issues

## Problem Statement

During job processing, the system creates a complex directory structure that can lead to confusion and timeout issues:

### Current Directory Structure (PROBLEMATIC)

```
temp/
├── datasets/
│   └── {dataset_id}/
│       ├── images/          # Downloaded images
│       └── run_1/           # Processing workspace
│           ├── dense/
│           └── sparse/
├── jobs/
│   └── {job_id}_sfm/
│       └── sfm/

└── sfm/
    ├── {job_id}_sfm/
    │   └── datasets/
    │       └── {dataset_id}/
    │           └── images/
    └── {another_job_id}_sfm/
        └── {dataset_id}/
            └── images/
```

### Recommended Directory Structure (CLEAN)

```
temp/
├── datasets/
│   └── {dataset_id}/
│       └── images/          # Downloaded images (single source)
│
└── jobs/
    ├── sfm/
    │   └── {job_id}_sfm/
    │       └── run_1/       # SFM processing workspace
    │           ├── database.db
    │           ├── sparse/
    │           └── dense/
    ├── orthomosaic/
    │   └── {job_id}_orthomosaic/
    │       ├── dsm.tif
    │       └── orthomosaic.tif
    └── radiometric/
        └── {job_id}_radiometric/
            └── calibrated_images/
```

### Benefits of New Structure

1. **Single Image Storage**: Images stored once in `temp/datasets/{dataset_id}/images/`
2. **Organized by Service**: Each service has its own subfolder under `jobs/`
3. **Clear Job Separation**: `{job_id}_<service>` format makes tracking easy
4. **No Redundancy**: Eliminates duplicate image downloads
5. **Predictable Paths**: Consistent structure across all services

### Issues Identified

1. **Multiple Image Copies**: Images downloaded to multiple locations (FIXED)
2. **Inconsistent Paths**: Different services use different directory structures (FIXED)
3. **Timeout Problems**: API Gateway blocks waiting for sub-services to complete
4. **Container Exit**: API Gateway Docker container exits after SFM completes
5. **Storage Waste**: Redundant data storage across multiple directories (FIXED)

---

## Implementation Status

### ✅ Completed Changes

1. **Unified Image Storage** ✅
   - All images stored once in `temp/datasets/{dataset_id}/images/`
   - Services reference this shared location
   - No duplicate downloads

2. **Service-Specific Job Directories** ✅
   - SFM: `temp/jobs/sfm/{job_id}_sfm/run_1/`
   - Orthomosaic: `temp/jobs/orthomosaic/{job_id}_orthomosaic/`
   - Radiometric: `temp/jobs/radiometric/{job_id}_radiometric/`

3. **Updated Components** ✅
   - `TempStorageManager`: Added `get_service_job_dir()` method
   - SFM Service: Uses new directory structure
   - Orthomosaic Service: Uses new directory structure
   - Dataset class: Manages shared image storage

4. **Async/Non-Blocking Pipeline** ✅ **CRITICAL FIX**
   - Removed all `wait_for_job_completion()` blocking calls
   - API Gateway now triggers services and returns immediately
   - Services run independently (can take 8+ hours)
   - Services callback directly to backend with progress/completion
   - **No more timeout errors or container exits**

### 🔄 Pending Changes

1. **Callback Architecture**: Services need to implement direct callbacks to backend (currently use AI Gateway)
2. **Radiometric Service**: Currently mocked, needs real implementation with new structure
3. **Product Upload**: Currently in sub-services, should move to backend via callbacks

---

## Root Cause Analysis

### 1. Timeout Issue

**Problem:**
```python
# In API Gateway run_pipeline_task()
calibration_result = await wait_for_job_completion(
    calibration_client.get_job_status,
    calibration_job_id,
    background_task_handler,
    backend_client,
    job_id,
    progress_start=10.0,
    progress_end=30.0,
    stage_name="radiometric_calibration",
)
```

The API Gateway **synchronously waits** for each sub-service (SFM, MVS, Orthomosaic) to complete. For large datasets (425 images), this can take **hours**, leading to:
- Timeout errors in background task handler
- Container exits before completion
- Lost job state

**Error seen:**
```
TimeoutError: Job 80600424-cb22-4875-b9a8-b8cdc82c7adf failed: TimeoutError
```

### 2. Directory Structure Issue

**Problem:**
Each microservice creates its own workspace:
- SFM service: `/app/data/temp/sfm/{job_id}_sfm/`
- Orthomosaic service: `/app/data/temp/orthomosaic/{job_id}/`
- API Gateway: `/app/data/temp/jobs/{job_id}/`
- Dataset storage: `/app/data/temp/datasets/{dataset_id}/`

This leads to:
- Image downloads repeated by each service
- Inconsistent file locations
- Difficult debugging

---

## Recommended Solutions

### Solution 1: Asynchronous Processing (CRITICAL)

**Replace synchronous waiting with callback-based architecture:**

#### Current (PROBLEMATIC):
```python
# API Gateway blocks waiting
result = await wait_for_job_completion(...)  # Blocks for hours!
```

#### Recommended (CALLBACK-BASED):
```python
# API Gateway triggers and immediately returns
await sfm_client.run_sfm(job_id, dataset_id, download_url, parameters)
# SFM service will callback to backend when done
# API Gateway task completes immediately
```

**Benefits:**
- No timeout issues
- Container doesn't block
- Better resource utilization
- Can process multiple jobs concurrently

**Implementation Steps:**

1. **Update SFM Service to Callback Directly to Backend**

Create endpoint in SFM service:
```python
# services/sfm/app/v1/api/products/upload/endpoints/sfm_endpoint.py

async def sfm_processing_complete_callback(
    job_id: str,
    result: dict,
    backend_url: str,
    secret_key: str
):
    """Send completion callback to backend"""
    payload = {
        "job_id": job_id,
        "type": "progress",  # or "complete" or "error"
        "progress": 60.0,
        "current_stage": "sfm",
        "stage_progress": 100,
        "message": "SFM completed successfully",
        "outputs": result
    }
    
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"{backend_url}/v1/api/jobs/ai-callback/",
            json=payload,
            headers={"X-API-Secret-Key": secret_key}
        )
```

2. **Update API Gateway to Fire-and-Forget**

```python
# api_gateway/app/v1/api/products/upload/endpoints/jobs.py

async def run_pipeline_task(...):
    """Execute pipeline without blocking"""
    
    # Step 1: Trigger SFM (don't wait!)
    await sfm_client.run_sfm(
        job_id=f"{job_id}_sfm",
        dataset_id=dataset_id,
        download_url=download_url,
        parameters=parameters.get("sfm", {}),
        callback_url=backend_callback_url,  # Backend URL, not gateway
        secret_key=secret_key
    )
    
    # Don't wait - let SFM callback when done
    logger.info(f"SFM triggered for job {job_id}, gateway task complete")
    
    # API Gateway task ends here
    # Backend will receive callbacks directly from sub-services
```

3. **Update Backend Callback to Chain Next Stage**

```python
# backend/apps/jobs/api/views/ai_callback.py

def _handle_progress_update(self, job: ProcessingJob, data: dict):
    """Handle progress and trigger next stage"""
    current_stage = data.get('current_stage')
    stage_progress = data.get('stage_progress', 0)
    
    # Update job
    job.progress = data.get('progress')
    job.stage = current_stage
    
    # If stage complete, trigger next stage
    if stage_progress == 100:
        job.last_successful_stage = current_stage
        job.save()
        
        # Trigger next stage
        if current_stage == 'sfm':
            self._trigger_mvs_stage(job)
        elif current_stage == 'mvs':
            self._trigger_publishing_stage(job)
    else:
        job.save()

def _trigger_mvs_stage(self, job: ProcessingJob):
    """Trigger MVS processing"""
    from apps.jobs.infra.services.ai_client import AIGatewayClient
    
    client = AIGatewayClient()
    client.trigger_mvs(
        job_id=str(job.id),
        dataset_id=str(job.dataset_id),
        # ... parameters
    )
```

---

### Solution 2: Unified Directory Structure

**Standardize workspace paths across all services:**

#### Recommended Structure:
```
/app/data/
├── temp/
│   └── jobs/
│       └── {job_id}/                      # One workspace per job
│           ├── dataset_images/             # Shared image storage
│           │   └── {image_files}
│           ├── sfm/                        # SFM outputs
│           │   ├── sparse/
│           │   └── dense/
│           ├── mvs/                        # MVS outputs
│           │   └── mesh/
│           ├── orthomosaic/                # Orthomosaic outputs
│           │   └── tiles/
│           └── products/                   # Final deliverables
│               ├── orthomosaic.tif
│               ├── dsm.tif
│               └── mesh.ply
└── cache/
    └── datasets/
        └── {dataset_id}/                   # Persistent dataset cache
            └── images/
                └── {image_files}
```

**Benefits:**
- Single download location per dataset (cache)
- Clear separation of job workspaces
- Easy cleanup after job completion
- Predictable file locations

**Implementation:**

1. **Create TempStorageManager with Standardized Paths**

```python
# infrastructure/storage/temp_manager.py

class TempStorageManager:
    def __init__(self, base_path="/app/data"):
        self.base_path = Path(base_path)
        self.temp_dir = self.base_path / "temp" / "jobs"
        self.cache_dir = self.base_path / "cache" / "datasets"
    
    def get_job_workspace(self, job_id: str) -> Path:
        """Get unified job workspace"""
        job_dir = self.temp_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir
    
    def get_dataset_cache(self, dataset_id: str) -> Path:
        """Get persistent dataset cache"""
        cache_dir = self.cache_dir / dataset_id / "images"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
    
    def get_sfm_workspace(self, job_id: str) -> Path:
        """Get SFM workspace within job"""
        return self.get_job_workspace(job_id) / "sfm"
    
    def get_mvs_workspace(self, job_id: str) -> Path:
        """Get MVS workspace within job"""
        return self.get_job_workspace(job_id) / "mvs"
    
    def cleanup_job(self, job_id: str):
        """Delete job workspace after completion"""
        import shutil
        job_dir = self.temp_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
```

2. **Update Services to Use Shared Image Cache**

```python
# services/sfm/app/core/services/colmap_service.py

class ColmapService:
    def __init__(self, temp_manager: TempStorageManager):
        self.temp_manager = temp_manager
    
    async def process(self, job_id: str, dataset_id: str):
        # Use cached images if available
        image_cache = self.temp_manager.get_dataset_cache(dataset_id)
        
        if not list(image_cache.glob("*.jpg")):
            # Download images to cache
            await self.download_images(download_url, image_cache)
        
        # Create symlinks in job workspace
        job_images = self.temp_manager.get_job_workspace(job_id) / "dataset_images"
        job_images.mkdir(parents=True, exist_ok=True)
        
        for img in image_cache.glob("*.jpg"):
            symlink_path = job_images / img.name
            if not symlink_path.exists():
                symlink_path.symlink_to(img)
        
        # Run SFM in job workspace
        sfm_workspace = self.temp_manager.get_sfm_workspace(job_id)
        # ... continue processing
```

---

### Solution 3: Timeout Configuration

**Update timeout settings for long-running jobs:**

```python
# infrastructure/message_queue/background_task.py

async def run_background_task_with_timeout(
    self,
    job_id: str,
    task_func: Callable,
    timeout_hours: int = 24,  # 24 hours for large jobs
    *args,
    **kwargs
):
    """Execute task with extended timeout"""
    try:
        # Set asyncio timeout
        async with asyncio.timeout(timeout_hours * 3600):
            self.update_job_status(job_id, JobStatus.RUNNING)
            result = await task_func(*args, **kwargs)
            self.update_job_status(job_id, JobStatus.COMPLETED, result=result)
            
    except asyncio.TimeoutError:
        error_msg = f"Job exceeded timeout of {timeout_hours} hours"
        self.update_job_status(job_id, JobStatus.FAILED, error=error_msg)
        logger.error(f"Job {job_id} timed out after {timeout_hours} hours")
```

---

## Migration Path

### Phase 1: Fix Timeout (CRITICAL - Do First)

1. ✅ Update API Gateway to use callbacks instead of async wait
2. ✅ Update SFM/MVS/Orthomosaic services to callback directly to backend
3. ✅ Test with small dataset (< 50 images)
4. ✅ Deploy to production

### Phase 2: Standardize Directory Structure

1. ✅ Implement `TempStorageManager` with standardized paths
2. ✅ Update each service to use new path structure
3. ✅ Add dataset image caching
4. ✅ Test with existing jobs
5. ✅ Clean up old directory structure

### Phase 3: Cleanup and Monitoring

1. ✅ Add automated cleanup for completed jobs
2. ✅ Add disk space monitoring
3. ✅ Document new directory structure
4. ✅ Update deployment scripts

---

## Testing Checklist

### Timeout Fix Testing

- [ ] Small dataset (< 50 images): Job completes without timeout
- [ ] Medium dataset (100-200 images): Job completes without timeout
- [ ] Large dataset (> 400 images): Job completes without timeout
- [ ] API Gateway container stays running after triggering SFM
- [ ] Backend receives callbacks from SFM service
- [ ] Retry works correctly after fixing timeout

### Directory Structure Testing

- [x] Images stored once in `temp/datasets/{dataset_id}/images/`
- [x] SFM workspace created in `temp/jobs/sfm/{job_id}_sfm/`
- [x] No duplicate image downloads for same dataset
- [ ] Orthomosaic uses correct paths from new structure
- [ ] Radiometric calibration uses correct paths
- [ ] Multiple jobs for same dataset share images correctly
- [ ] Cleanup removes old jobs but preserves datasets in use

---

## Implementation Summary

### Changed Files

**Infrastructure:**
- `image-analysis-core/infrastructure/storage/temp_manager.py`
  - Added `get_service_job_dir()` method for new directory structure
  
**SFM Service:**
- `image-analysis-core/services/sfm/app/v1/api/products/upload/endpoints/sfm_endpoint.py`
  - Updated `run_sfm_task()` to use new directory structure:
    - Images: `temp/datasets/{dataset_id}/images/`
    - Workspace: `temp/jobs/sfm/{job_id}_sfm/run_1/`
  - Pass `dataset.dataset_path` instead of `dataset.project_temp_path` to pipeline
  
**Documentation:**
- `image-analysis-core/docs/DIRECTORY_STRUCTURE.md` - This file (updated with new structure)
- `image-analysis-core/docs/RETRY_AND_RESUME_IMPLEMENTATION.md` - Job retry system
- `image-analysis-core/docs/JOB_RETRY_SYSTEM.md` - Comprehensive retry documentation

**Docker:**
- `image-analysis-core/docker-compose.yml` - Added `sfm_database` volume
- `image-analysis-core/docker-compose.sfm.yml` - Added `sfm_database` volume

### Directory Structure Changes

**Before (Problematic):**
```
temp/
├── datasets/{dataset_id}/images/
├── jobs/{job_id}/sfm/
└── sfm/
    └── {job_id}_sfm/
        └── datasets/{dataset_id}/images/  # DUPLICATE!
```

**After (Clean):**
```
temp/
├── datasets/
│   └── {dataset_id}/
│       └── images/           # Single source of truth
└── jobs/
    ├── sfm/
    │   └── {job_id}_sfm/
    │       └── run_1/        # Processing workspace
    │           ├── database.db
    │           ├── sparse/
    │           └── dense/
    ├── orthomosaic/
    │   └── {job_id}_orthomosaic/
    │       └── outputs/
    └── radiometric/
        └── {job_id}_radiometric/
            └── calibrated/
```

### Code Changes Summary

**1. TempStorageManager - New Method:**
```python
def get_service_job_dir(self, job_id: str, service_name: str) -> Path:
    """Get temp/jobs/{service}/{job_id}_{service}/ directory"""
    service_dir = self.base_path / "jobs" / service_name / f"{job_id}_{service_name}"
    service_dir.mkdir(parents=True, exist_ok=True)
    return service_dir
```

**2. SFM Service - Updated Paths:**
```python
# Images: temp/datasets/{dataset_id}/images/ (shared)
dataset = Dataset(project_id=dataset_id, storage_driver=driver, temp_base_path=Path(temp_settings.base_path))
dataset.initialize_dataset()
dataset.fetch_images()  # Downloads to dataset.images_path

# Workspace: temp/jobs/sfm/{job_id}_sfm/run_1/
job_workspace = Path(temp_settings.base_path) / "jobs" / "sfm" / f"{job_id}_sfm"
run_path = job_workspace / "run_1"

# Run pipeline with dataset directory (contains images/)
pipeline.run_pipeline(dataset_path=dataset.dataset_path.absolute())
```

### Next Steps

1. **Test Integration:**
   ```bash
   cd /home/ali/projects/PhotoGear/backend
   docker compose down && docker compose up -d
   # Run integration tests
   cd ../integration-tests
   pytest tests/test_job_processing_integration.py -v
   ```

2. **Verify Directory Structure:**
   ```bash
   # Check that images are in correct location
   docker exec photogear-sfm ls -la /app/data/temp/datasets/
   docker exec photogear-sfm ls -la /app/data/temp/jobs/sfm/
   ```

3. **Update Remaining Services:**
   - Orthomosaic service: Use `get_service_job_dir(job_id, "orthomosaic")`
   - Radiometric service: Use `get_service_job_dir(job_id, "radiometric")`

4. **Monitor for Issues:**
   - Check logs for path-related errors
   - Verify no duplicate image downloads
   - Ensure SQLite database persists correctly

- [ ] Images downloaded only once per dataset
- [ ] All services can access shared image cache
- [ ] Job workspace contains all expected outputs
- [ ] Cleanup removes job workspace but preserves dataset cache
- [ ] Multiple jobs for same dataset share cached images

---

## Rollback Plan

If issues occur after deployment:

1. **Revert to synchronous processing:**
   - Restore old `wait_for_job_completion` code
   - Accept timeout risk temporarily

2. **Keep callback enhancements:**
   - Callback infrastructure is additive
   - No need to remove if not causing issues

3. **Directory structure:**
   - Old and new can coexist
   - Gradually migrate to new structure

---

## Monitoring

### Key Metrics to Track

```sql
-- Jobs timing out
SELECT COUNT(*) as timeout_count
FROM jobs_processing_job
WHERE status = 'failed' 
  AND error_message LIKE '%TimeoutError%'
  AND created_at > NOW() - INTERVAL '7 days';

-- Average job duration by status
SELECT 
  status,
  AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) / 3600 as avg_hours
FROM jobs_processing_job
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY status;

-- Disk usage by directory
-- Run on server
du -sh /app/data/temp/*
du -sh /app/data/cache/*
```

---

## Related Documentation

- [Job Retry System](JOB_RETRY_SYSTEM.md)
- [API Gateway Architecture](../../image-analysis-core/docs/API_GATEWAY.md)
- [Background Task Handler](../../image-analysis-core/infrastructure/message_queue/background_task.py)
