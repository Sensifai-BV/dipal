# Pipeline Architecture & Orchestration

## Overview

This document describes the current image processing pipeline architecture, identifies key issues, and proposes solutions for reliable orchestration of long-running processing jobs.

---

## Current Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (Django)                                │
│                              Port: 8000                                      │
│  - User-facing REST API                                                     │
│  - Job management (create, status, results)                                 │
│  - Celery for async task dispatch                                           │
│  - Receives progress callbacks from AI services                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ POST /jobs/run
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API GATEWAY (FastAPI)                              │
│                              Port: 8080                                      │
│  - Central orchestration service                                            │
│  - Triggers processing sub-services                                         │
│  - Receives callbacks from sub-services                                     │
│  - Sends progress updates to Backend                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│    CALIBRATION    │    │       SFM         │    │    ORTHOMOSAIC    │
│     Service       │    │     Service       │    │      Service      │
│    Port: 8004     │    │    Port: 8002     │    │     Port: 8003    │
│                   │    │                   │    │                   │
│  Duration: ~2s    │    │  Duration: 2-4h   │    │  Duration: 1-2h   │
│  (mock)           │    │  (COLMAP)         │    │  (ODM)            │
└───────────────────┘    └───────────────────┘    └───────────────────┘
```

### Processing Pipeline Stages

| Stage | Service | Duration | Description |
|-------|---------|----------|-------------|
| 1. Radiometric Calibration | Calibration | ~2 seconds | Calibrate multispectral imagery; DN-to-reflectance conversion (v0.6.0) |
| 2. Structure from Motion | SFM | 2-4 hours | Generate point cloud and mesh using COLMAP |
| 3. Orthomosaic Generation | Orthomosaic | 1-2 hours | Generate orthomosaic and DSM using ODM |
| 3a. Multi-Resolution Output | Orthomosaic | ~2 min | Generate 2×, 4×, 8× downsampled orthomosaics as COGs (v0.6.0) |
| 3b. Band Orthorectification | Orthomosaic | ~5 min | Orthorectify spectral bands onto DSM grid (full mode only, v0.6.0) |
| 3c. Vegetation Indices | Orthomosaic | ~1 min | Compute NDVI, NDRE, GNDVI from ortho bands (full mode only, v0.6.0) |

### Current Flow

```
1. User creates job via Backend API
2. Backend queues Celery task
3. Celery task calls API Gateway: POST /jobs/run
4. API Gateway creates background task (run_pipeline_task)
5. API Gateway returns 200 OK immediately
6. Background task triggers ALL stages sequentially:
   a. trigger_calibration_service() → returns immediately
   b. trigger_sfm_service() → returns immediately  
   c. trigger_orthomosaic_service() → returns immediately ← PROBLEM!
7. Each sub-service runs independently
8. Sub-services callback to API Gateway when complete
```

---

## Identified Issues

### Issue 1: Wrong Callback URL (FIXED ✓)

**Problem**: Sub-services were configured to callback to `api_gateway:8000` but API Gateway runs on port `8080`.

**Files affected**:
- `services/sfm/app/v1/api/products/upload/endpoints/sfm_endpoint.py`
- `services/orthomosaic_generation/app/v1/api/products/upload/endpoints/orthomosaic_endpoint.py`

**Status**: Fixed - changed default port to 8080.

---

### Issue 2: Fire-and-Forget Orchestration (CRITICAL)

**Problem**: API Gateway triggers all stages immediately without waiting for dependencies.

```python
# Current code in jobs.py
await trigger_calibration_service(...)   # Returns in ~100ms
await trigger_sfm_service(...)           # Returns in ~100ms (SFM runs 2+ hours)
await trigger_orthomosaic_service(...)   # Triggered IMMEDIATELY - SFM not done!
```

**Impact**:
- Orthomosaic service starts before SFM output exists
- Orthomosaic fails because it can't find input files
- Pipeline reports "completed" when only triggers were sent

---

### Issue 3: No Stage Dependency Tracking

**Problem**: No mechanism to ensure Stage N completes before Stage N+1 starts.

**Current behavior**:
```
Timeline:
0:00  - Calibration triggered
0:01  - SFM triggered
0:02  - Orthomosaic triggered ← Starts looking for SFM output
0:03  - Orthomosaic FAILS (no SFM output)
2:30  - SFM completes (too late)
```

**Expected behavior**:
```
Timeline:
0:00  - Calibration triggered
0:02  - Calibration completes
0:02  - SFM triggered
2:30  - SFM completes
2:30  - Orthomosaic triggered
3:45  - Orthomosaic completes
3:45  - Pipeline complete
```

---

## Proposed Solutions

### Option A: Callback-Driven Chaining (Recommended)

**Concept**: API Gateway orchestrates stages reactively based on callbacks.

```
┌─────────────┐     trigger      ┌─────────────┐
│ API Gateway │ ───────────────▶ │    SFM      │
│             │                  │   Service   │
│  [waiting]  │ ◀─────────────── │             │
│             │  callback:done   │  [2+ hours] │
└─────────────┘                  └─────────────┘
       │
       │ trigger next stage
       ▼
┌─────────────┐
│ Orthomosaic │
└─────────────┘
```

**Implementation**:

```python
# In API Gateway - subservice_callback endpoint
async def subservice_callback(callback_data: dict):
    service_name = callback_data.get("service")
    job_id = callback_data.get("job_id")
    status = callback_data.get("status")
    
    if status == "completed":
        if service_name == "calibration":
            # Trigger SFM
            await trigger_sfm_service(job_id, ...)
        elif service_name == "sfm":
            # Trigger Orthomosaic
            await trigger_orthomosaic_service(job_id, ...)
        elif service_name == "orthomosaic":
            # Pipeline complete
            await notify_backend_complete(job_id)
    elif status == "failed":
        await notify_backend_failed(job_id, callback_data.get("error"))
```

**Pros**:
- ✅ Simple to implement
- ✅ No external dependencies (no Redis/RabbitMQ needed)
- ✅ Natural event-driven flow
- ✅ Easy to track which stage we're at

**Cons**:
- ❌ State is implicit (based on callbacks)
- ❌ Need to handle callback failures
- ❌ Gateway must stay running throughout pipeline

---

### Option B: Persistent Job State Machine

**Concept**: Store job state in database, resume from any point.

```
┌─────────────────────────────────────────────────────────────┐
│                        JOB STATE                            │
├─────────────────────────────────────────────────────────────┤
│ job_id: "abc123"                                            │
│ current_stage: "sfm"                                        │
│ stage_status: {                                             │
│   "calibration": "completed",                               │
│   "sfm": "running",                                         │
│   "orthomosaic": "pending"                                  │
│ }                                                           │
│ sfm_output_path: null                                       │
│ last_updated: "2026-01-30T10:00:00Z"                       │
└─────────────────────────────────────────────────────────────┘
```

**Implementation**:
1. Create `JobState` model in API Gateway (SQLite or Redis)
2. Update state on each callback
3. Use state to determine next action
4. Support resume from any stage

**Pros**:
- ✅ Full state persistence
- ✅ Can resume after gateway restart
- ✅ Clear audit trail
- ✅ Easy to implement retry/resume

**Cons**:
- ❌ Requires database setup
- ❌ More complex implementation
- ❌ Need migration for existing jobs

---

### Option C: Message Queue (RabbitMQ/Redis Streams)

**Concept**: Use message broker for decoupled communication.

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│     SFM     │───▶│   Queue:    │───▶│ Orthomosaic │
│   Service   │    │ sfm_done    │    │   Service   │
└─────────────┘    └─────────────┘    └─────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ API Gateway │
                  │  (monitor)  │
                  └─────────────┘
```

**Pros**:
- ✅ Fully decoupled services
- ✅ Built-in retry/dead-letter queues
- ✅ Horizontal scalability
- ✅ Industry standard pattern

**Cons**:
- ❌ Requires RabbitMQ/Redis infrastructure
- ❌ More operational complexity
- ❌ Overkill for current scale

---

### Option D: Polling-Based Orchestration

**Concept**: API Gateway polls sub-service status until completion.

```python
async def orchestrate_pipeline(job_id, ...):
    # Trigger SFM
    await sfm_client.run_sfm(job_id, ...)
    
    # Poll until complete
    while True:
        status = await sfm_client.get_job_status(job_id)
        if status["status"] == "completed":
            break
        elif status["status"] == "failed":
            raise Exception(status["error"])
        await asyncio.sleep(30)  # Poll every 30s
    
    # Now trigger orthomosaic
    await orthomosaic_client.run_orthomosaic(job_id, ...)
    # ... poll again
```

**Pros**:
- ✅ Simple synchronous logic
- ✅ No callback infrastructure needed
- ✅ Easy to understand

**Cons**:
- ❌ Wastes resources (constant polling)
- ❌ Background task runs for hours
- ❌ Long-running HTTP connection issues
- ❌ Gateway must stay alive entire pipeline

---

## Recommendation

### For Immediate Fix: **Option A (Callback-Driven Chaining)**

**Rationale**:
1. Minimal code changes required
2. Callback infrastructure already exists
3. No new dependencies
4. Can be implemented in < 1 day

### For Long-Term: **Option B (Persistent State Machine)**

**Rationale**:
1. Better reliability
2. Support for resume/retry
3. Clear job audit trail
4. Foundation for future scaling

---

## Implementation Plan for Option A

### Step 1: Modify `run_pipeline_task` to only trigger first stage

```python
async def run_pipeline_task(job_id, dataset_id, download_url, parameters, ...):
    # Store job metadata for later stages
    background_task_handler.create_job(job_id, metadata={
        "dataset_id": dataset_id,
        "download_url": download_url,
        "parameters": parameters,
        "backend_job_id": job_id,
        "next_stage": "calibration",
    })
    
    # Only trigger first stage
    await trigger_calibration_service(...)
    # Do NOT trigger subsequent stages here
```

### Step 2: Modify `subservice_callback` to trigger next stage

```python
async def subservice_callback(callback_data: dict, ...):
    service_name = callback_data.get("service")
    job_id = callback_data.get("job_id")  # e.g., "abc123_sfm"
    main_job_id = job_id.rsplit("_", 1)[0]  # Extract "abc123"
    
    if callback_data.get("status") == "completed":
        job_metadata = get_job_metadata(main_job_id)
        
        if service_name == "calibration":
            await trigger_sfm_service(main_job_id, job_metadata, ...)
            
        elif service_name == "sfm":
            # Store SFM output path for orthomosaic
            job_metadata["sfm_output_path"] = callback_data["result"]["run_path"]
            await trigger_orthomosaic_service(main_job_id, job_metadata, ...)
            
        elif service_name == "orthomosaic":
            # Pipeline complete!
            await backend_client.send_completion(main_job_id, ...)
```

### Step 3: Update sub-services to include main job ID

Ensure callbacks include the main job ID for proper routing:

```python
# In SFM endpoint
await client.post(
    f"{gateway_url}/v1/api/products/upload/jobs/subservice-callback",
    json={
        "service": "sfm",
        "job_id": job_id,  # "abc123_sfm"
        "main_job_id": job_id.rsplit("_", 1)[0],  # "abc123"
        "status": "completed",
        "result": result,
    }
)
```

---

## Testing Checklist

- [ ] Calibration completes → SFM triggered
- [ ] SFM completes → Orthomosaic triggered
- [ ] Orthomosaic completes → Backend notified
- [ ] Stage failure → Backend notified with error
- [ ] Resume from SFM stage works
- [ ] Resume from Orthomosaic stage works
- [ ] Callback URL is correct (port 8080)
- [ ] Backend receives all progress updates

---

## Files to Modify

| File | Changes |
|------|---------|
| `api_gateway/app/v1/api/products/upload/endpoints/jobs.py` | Modify `run_pipeline_task` and `subservice_callback` |
| `api_gateway/app/entities/jobs.py` | Add `SubserviceCallback` model |
| `services/sfm/app/v1/api/products/upload/endpoints/sfm_endpoint.py` | Include `main_job_id` in callback |
| `services/orthomosaic_generation/app/v1/api/products/upload/endpoints/orthomosaic_endpoint.py` | Include `main_job_id` in callback |

---

## Questions for Review

1. Should we implement Option A (callback-driven) or Option B (state machine)?
2. Do we need to support parallel stages in the future?
3. Should failed stages auto-retry or require manual intervention?
4. Where should job metadata be stored (memory, Redis, SQLite)?
