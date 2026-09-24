# Job Retry and Resume Implementation

## Overview

This document describes the implementation of job retry and resume functionality across the PhotoGear system, allowing failed jobs to be retried from their last successful checkpoint rather than restarting from the beginning.

## Architecture

### Components Involved

1. **Backend (Django REST Framework)**
   - ProcessingJob model with retry tracking fields
   - Retry endpoint: `POST /v1/api/jobs/{job_id}/retry/`
   - AI callback handler for tracking stage completion

2. **AI Gateway (FastAPI)**
   - Modified job pipeline to accept `starting_stage` parameter
   - Stage skipping logic for resume capability
   - Preserved data from previous runs (SFM database persistence)

3. **SFM Service (COLMAP)**
   - SQLite database persisted in Docker volume
   - Allows resuming from checkpoint without reprocessing

## Implementation Details

### 1. Database Schema (Backend)

Added fields to `ProcessingJob` model:

```python
retry_count = models.IntegerField(default=0)
last_successful_stage = models.CharField(max_length=50, null=True, blank=True)
original_job_id = models.UUIDField(null=True, blank=True)
can_retry = models.BooleanField(default=True)
```

**Migration**: `backend/apps/jobs/migrations/0003_add_retry_fields.py`

### 2. Retry Endpoint (Backend)

**Endpoint**: `POST /v1/api/jobs/{job_id}/retry/`

**Query Parameters**:
- `force_restart` (boolean, optional, default: false)
  - `false`: Resume from last successful stage
  - `true`: Restart from beginning

**Logic**:
1. Validates job can be retried (failed status, retry limit not exceeded)
2. Determines resume stage from `last_successful_stage`
3. Creates new job with retry metadata
4. Sends request to AI Gateway with `starting_stage` parameter

**Stage Resume Mapping**:
- Last successful: `queued` → Resume from: `sfm`
- Last successful: `sfm` → Resume from: `mvs`
- Last successful: `mvs` → Resume from: `publishing`

**Communication with AI Gateway**:
```python
payload = {
    "job_id": str(new_job.id),
    "dataset_id": str(new_job.dataset_id),
    "organization_id": str(org_id),
}

# Add starting_stage if resuming
if resume_from_stage and not force_restart:
    payload["starting_stage"] = resume_from_stage

await client.post(f"{ai_gateway_url}/v1/api/jobs/start", json=payload)
```

### 3. Stage Tracking (Backend)

**File**: `backend/apps/jobs/api/views/ai_callback.py`

Enhanced `_handle_progress_update`:
- Maps AI Gateway stages to Django stages
- Saves `last_successful_stage` when `stage_progress=100`
- Enables precise resume points

**Stage Mapping**:
```python
ai_to_django_stages = {
    'radiometric_calibration': 'queued',
    'sfm': 'sfm',
    'mvs': 'mvs',
    'orthomosaic_generation': 'publishing',
    'uploading_results': 'publishing',
}
```

### 4. AI Gateway Resume Support

**File**: `image-analysis-core/api_gateway/app/entities/jobs.py`

Added `starting_stage` field to `JobRunRequest`:
```python
class JobRunRequest(BaseModel):
    dataset_id: str
    download_url: str | list[dict]
    parameters: dict | None = None
    starting_stage: str | None = None  # NEW: for resume
```

**File**: `image-analysis-core/api_gateway/app/v1/api/products/upload/endpoints/jobs.py`

Modified `run_pipeline_task` to:
1. Accept `starting_stage` parameter
2. Set initial progress based on starting stage
3. Skip completed stages

**Stage Skipping Logic**:
```python
# Skip calibration if starting_stage is later than 'radiometric_calibration'
if not starting_stage or starting_stage == 'radiometric_calibration':
    # Run calibration
    ...
else:
    logger.info(f"Skipping calibration (resuming from {starting_stage})")

# Skip SFM if starting_stage is later than 'sfm'
if not starting_stage or starting_stage in ['radiometric_calibration', 'sfm']:
    # Run SFM
    ...
else:
    logger.info(f"Skipping SFM (resuming from {starting_stage})")
    sfm_result = {"skipped": True}
```

### 5. SFM Database Persistence

**File**: `image-analysis-core/docker-compose.yml`

Added named volume for COLMAP SQLite database:
```yaml
volumes:
  shared_processing_data:
  sfm_database:  # NEW: COLMAP database persistence

services:
  sfm:
    volumes:
      - shared_processing_data:/app/data/temp
      - sfm_database:/app/data/colmap_db  # NEW: Persist database
```

**Purpose**:
- COLMAP creates SQLite database during SFM processing
- Database contains reconstruction progress and intermediate results
- Persisting database allows resuming SFM from checkpoint
- Without this, container restart loses all SFM progress

**Database Location**:
- Path in code: `workspace / run_path / "database.db"`
- Mounted at: `/app/data/colmap_db`

## Usage Examples

### Basic Retry (Resume from Checkpoint)

```bash
# Retry failed job, automatically resume from last successful stage
curl -X POST "http://localhost:8000/v1/api/jobs/{job_id}/retry/" \
  -H "Authorization: Bearer {token}"
```

### Force Restart from Beginning

```bash
# Retry job but restart from beginning
curl -X POST "http://localhost:8000/v1/api/jobs/{job_id}/retry/?force_restart=true" \
  -H "Authorization: Bearer {token}"
```

### Response

```json
{
  "new_job_id": "550e8400-e29b-41d4-a716-446655440001",
  "original_job_id": "550e8400-e29b-41d4-a716-446655440000",
  "retry_count": 1,
  "resume_from_stage": "mvs",
  "force_restart": false,
  "message": "Job retry initiated successfully. Resuming from stage: mvs",
  "dataset": {
    "id": "dataset-123",
    "name": "My Dataset"
  }
}
```

## Retry Limits

- **Maximum retries**: 3 per job chain
- Retry count tracks entire chain (original + all retries)
- After 3 failed retries, user must create new job

## Validation Rules

1. **Status**: Only failed jobs can be retried
2. **Retry flag**: Job must have `can_retry=True`
3. **Retry limit**: Chain cannot exceed 3 retries
4. **Organization**: User must belong to job's organization

## Stage Flow

### Normal Flow (No Resume)
```
queued → sfm → mvs → publishing
```

### Resume Flow Example
```
Job 1: queued → sfm → [FAILED at mvs]
Job 2 (retry): [skip queued] → [skip sfm] → mvs → publishing
```

### Force Restart Flow
```
Job 1: queued → sfm → [FAILED at mvs]
Job 2 (retry with force_restart=true): queued → sfm → mvs → publishing
```

## Error Handling

### AI Gateway Communication Failure

If retry endpoint cannot reach AI Gateway:
1. New job marked as `failed`
2. Returns HTTP 503 error
3. User can retry again when AI Gateway is available

### Stage Skip Validation

AI Gateway validates starting_stage:
- Valid stages: `sfm`, `mvs`, `orthomosaic_generation`
- Invalid stage: Falls back to starting from beginning
- Logs warning for unknown stages

## Benefits

1. **Time Savings**: Skip completed stages (e.g., 2-hour SFM doesn't need to rerun)
2. **Cost Efficiency**: Reduce computation and storage costs
3. **User Experience**: Faster recovery from transient failures
4. **Data Preservation**: SFM database persists reconstruction progress

## Related Documentation

- [JOB_RETRY_SYSTEM.md](./JOB_RETRY_SYSTEM.md) - Comprehensive retry system guide
- [DIRECTORY_STRUCTURE.md](./DIRECTORY_STRUCTURE.md) - Timeout and directory solutions

## Testing Checklist

- [ ] Create job that fails at SFM stage
- [ ] Retry with `force_restart=false` → Should resume from MVS
- [ ] Retry with `force_restart=true` → Should restart from beginning
- [ ] Verify SQLite persists across container restarts
- [ ] Test retry limit enforcement (max 3 retries)
- [ ] Test organization permission validation
- [ ] Test AI Gateway communication error handling
- [ ] Verify stage skipping logs appear in AI Gateway

## Future Enhancements

1. **Granular Resume**: Resume within a stage (e.g., 50% through SFM)
2. **Manual Stage Selection**: Allow user to specify exact starting stage
3. **Automatic Retry**: Auto-retry on specific error types
4. **Retry Analytics**: Track retry success rates and common failure points
