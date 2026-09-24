# Job Processing Flow - Complete Technical Documentation

## Overview

This document describes the complete flow of job processing between Backend (Django), AI Gateway (FastAPI), and AI Sub-services. It covers job creation, processing stages, callbacks, retry mechanisms, and data flow.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    FRONTEND                                          │
│                           (React / Web Application)                                  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ POST /v1/api/jobs/start-job/
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (Django)                                        │
│                                 Port: 8000                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  • REST API for job management                                                       │
│  • Celery for async task dispatch                                                   │
│  • PostgreSQL for job state persistence                                             │
│  • Receives AI callbacks for status updates                                         │
│  • Manages Products (upload metadata, S3 references)                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
                    │                                       ▲
                    │ POST /jobs/run                        │ POST /v1/api/jobs/ai-callback/
                    │ (via Celery task)                     │ (progress, complete, error)
                    ▼                                       │
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           AI GATEWAY (FastAPI)                                       │
│                               Port: 8080                                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  • Central orchestration service                                                     │
│  • Redis for job state management                                                   │
│  • Triggers sub-services sequentially via callbacks                                 │
│  • Receives callbacks from sub-services                                             │
│  • Sends progress updates to Backend                                                │
│  • Coordinates product uploads to S3                                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
                    │                                       ▲
                    │ POST /calibration/run                 │ POST /jobs/subservice-callback
                    │ POST /sfm/run                         │ (service, job_id, status, result)
                    │ POST /orthomosaic/run                 │
                    ▼                                       │
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              AI SUB-SERVICES                                         │
├──────────────────────┬──────────────────────┬───────────────────────────────────────┤
│    CALIBRATION       │        SFM           │        ORTHOMOSAIC                    │
│     Port: 8001       │     Port: 8002       │         Port: 8003                    │
│                      │                      │                                       │
│  Duration: ~2s       │  Duration: 2-4h      │  Duration: 1-2h                       │
│  (mock)              │  (COLMAP)            │  (ODM)                                │
│                      │                      │                                       │
│  Downloads images,   │  Generates sparse/   │  Generates orthomosaic,               │
│  applies radiometric │  dense point cloud,  │  DSM, and COG files                   │
│  calibration         │  mesh                │                                       │
└──────────────────────┴──────────────────────┴───────────────────────────────────────┘
                    │
                    │ Upload products
                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                AWS S3 BUCKETS                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  • AWS_S3_RAW_IMAGES_BUCKET: Source images (input)                                  │
│  • AWS_S3_AI_DEV_BUCKET: Intermediate processing files                              │
│  • AWS_S3_RESULTS_BUCKET: Final products (orthomosaic, DSM, point cloud)            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Job Lifecycle

### Job States

| State | Description |
|-------|-------------|
| `pending` | Job created, not yet queued |
| `queued` | Job queued for processing |
| `processing` | Job actively being processed by AI |
| `completed` | Job finished successfully |
| `failed` | Job failed with error |
| `cancelled` | Job cancelled by user |

### Processing Stages

Stages are defined separately in each service for consistency:
- **Backend:** `backend/apps/jobs/processing_stages.py` (Django TextChoices)
- **AI Gateway:** `infrastructure/state/models.py` (Python Enum)

| Stage | Service | Progress Range | Description |
|-------|---------|----------------|-------------|
| `pending` | Backend | 0% | Job created |
| `queued` | Backend | 0-5% | Job queued for processing |
| `radiometric_calibration` | Calibration | 5-15% | Radiometric calibration (if enabled) |
| `sfm` | SFM | 15-60% | Structure from Motion (COLMAP) |
| `orthomosaic` | Orthomosaic | 60-90% | Orthomosaic & DSM generation (ODM) |
| `uploading` | AI Gateway | 90-95% | Uploading products to S3 |
| `publishing` | Backend | 95-100% | Finalizing product records |
| `completed` | Backend | 100% | Job finished |

---

## Flow Details

### 1. Job Creation (Backend)

**Endpoint:** `POST /v1/api/jobs/start-job/`

**Request:**
```json
{
  "dataset_id": "4ee43b40-d3fb-4ae6-8c5e-0c5b4288a6f0",
  "resolution_gsd": 10,
  "radiometric_calibration": true
}
```

**Process:**
1. Backend validates request and dataset existence
2. Creates `ProcessingJob` record in PostgreSQL
3. Dispatches Celery task `process_drone_imagery(job_id)`
4. Returns job ID to frontend

**Response:**
```json
{
  "id": "abc123-uuid",
  "dataset_id": "4ee43b40-d3fb-4ae6-8c5e-0c5b4288a6f0",
  "status": "queued",
  "resolution_gsd": 10,
  "radiometric_calibration": true
}
```

### 2. Celery Task → AI Gateway

**File:** `backend/apps/jobs/infra/services/tasks/tasks.py`

The Celery task:
1. Fetches job details from database
2. Generates presigned URLs for all dataset images
3. Calls AI Gateway: `POST http://AI_GATEWAY_URL:8080/jobs/run`

**Request to AI Gateway:**
```json
{
  "job_id": "abc123-uuid",
  "dataset_id": "4ee43b40-d3fb-4ae6-8c5e-0c5b4288a6f0",
  "download_url": [
    {"url": "https://s3.../image1.jpg?presigned...", "filename": "image1.jpg"},
    {"url": "https://s3.../image2.jpg?presigned...", "filename": "image2.jpg"}
  ],
  "parameters": {
    "resolution_gsd": 10,
    "radiometric_calibration": true,
    "calibration": {"enabled": true},
    "sfm": {"resolution_gsd": 10},
    "orthomosaic": {"generate_cog": true, "resolution_gsd": 10}
  },
  "starting_stage": null
}
```

### 3. AI Gateway Orchestration

**File:** `api_gateway/app/v1/api/products/upload/endpoints/jobs.py`

The AI Gateway:
1. Creates job state in Redis
2. Starts background task for pipeline execution
3. Returns immediately with job status

**Redis Job State (key: `photogear:job:{job_id}`):**
```json
{
  "job_id": "abc123-uuid",
  "backend_job_id": "abc123-uuid",
  "dataset_id": "4ee43b40-d3fb-4ae6-8c5e-0c5b4288a6f0",
  "download_url": [...],
  "parameters": {...},
  "current_stage": "radiometric_calibration",
  "status": "running",
  "progress": 5.0,
  "stage_statuses": {
    "radiometric_calibration": "running",
    "sfm": "pending",
    "orthomosaic_generation": "pending",
    "uploading_results": "pending"
  },
  "stage_results": {},
  "created_at": "2026-02-03T10:00:00Z",
  "updated_at": "2026-02-03T10:00:00Z"
}
```

### 4. Callback-Driven Stage Execution

**Execution Model:** Callback-driven (NOT fire-and-forget)

```
API Gateway                     Sub-Service                    API Gateway Callback
     │                               │                               │
     │──POST /calibration/run───────►│                               │
     │                               │ (process 2s)                  │
     │                               │──POST /subservice-callback───►│
     │                               │                               │
     │◄─────────────────────────────────────trigger sfm──────────────│
     │                               │                               │
     │──POST /sfm/run───────────────►│                               │
     │                               │ (process 2-4h)                │
     │                               │──POST /subservice-cal$$lback───►│
     │                               │                               │
     │◄────────────────────────────────trigger orthomosaic───────────│
     │                               │                               │
     │──POST /orthomosaic/run───────►│                               │
     │                               │ (process 1-2h)                │
     │                               │──POST /subservice-callback───►│
     │                               │                               │
     │◄─────────────────────────────────────complete─────────────────│
```

### 5. Sub-Service Callback

**Endpoint:** `POST /jobs/subservice-callback` (AI Gateway)

Each sub-service sends a callback with service-specific results:

#### Calibration Service Callback
```json
{
  "job_id": "abc123-uuid",
  "service": "calibration",
  "status": "completed",
  "result": {
    "job_id": "abc123-uuid",
    "dataset_id": "dataset-uuid",
    "calibrated_images": [
      "s3://ai-dev-bucket/calibration/{dataset_id}/image1_calibrated.tif",
      "s3://ai-dev-bucket/calibration/{dataset_id}/image2_calibrated.tif"
    ],
    "calibration_path": "s3://ai-dev-bucket/calibration/{dataset_id}/",
    "status": "completed"
  },
  "error": null
}
```

#### SFM Service Callback
```json
{
  "job_id": "abc123-uuid",
  "service": "sfm",
  "status": "completed",
  "result": {
    "job_id": "abc123-uuid_sfm",
    "dataset_id": "dataset-uuid",
    "run_path": "/temp/jobs/sfm/{job_id}_sfm/run_1",
    "workspace_path": "/temp/jobs/sfm/{job_id}_sfm",
    "images_path": "/temp/datasets/{dataset_id}/images",
    "output_path": "/temp/jobs/sfm/{job_id}_sfm/run_1",
    "status": "completed"
  },
  "error": null
}
```
**Key outputs in `run_path`:** `sparse/` (point cloud), `dense/` (mesh), `report.json`

#### Orthomosaic Service Callback
```json
{
  "job_id": "abc123-uuid",
  "service": "orthomosaic",
  "status": "completed",
  "result": {
    "job_id": "abc123-uuid_orthomosaic",
    "dataset_id": "dataset-uuid",
    "dataset_path": "/temp/jobs/sfm/{job_id}_sfm/run_1",
    "workspace_path": "/temp/jobs/orthomosaic/{job_id}_orthomosaic",
    "outputs": {
      "dsm": "/temp/jobs/sfm/{job_id}_sfm/run_1/dsm.tif",
      "dsm_filled": "/temp/jobs/sfm/{job_id}_sfm/run_1/dsm_filled.tif",
      "dsm_filled_cog": "/temp/jobs/sfm/{job_id}_sfm/run_1/dsm_filled_cog.tif",
      "orthomosaic_rgb": "/temp/jobs/sfm/{job_id}_sfm/run_1/orthomosaic_rgb.tif",
      "hillshade": "/temp/jobs/sfm/{job_id}_sfm/run_1/hillshade.tif",
      "statistics": "/temp/jobs/sfm/{job_id}_sfm/run_1/orthomosaic_statistics.json"
    },
    "status": "completed"
  },
  "error": null
}
```

**Process:**
1. Updates Redis job state (stage complete)
2. Uploads stage products to S3 via `ProductUploadClient`
3. Sends progress update to Backend: `POST /v1/api/jobs/ai-callback/`
4. Triggers next stage (or completes pipeline)

### 6. Backend AI Callback

**Endpoint:** `POST /v1/api/jobs/ai-callback/`

**Request:**
```json
{
  "job_id": "abc123-uuid",
  "type": "progress",
  "progress": 45.0,
  "current_stage": "sfm",
  "message": "SFM processing in progress"
}
```

**Callback Types:**
- `progress`: Progress update during processing
- `complete`: Job completed successfully
- `error`: Job failed with error

---

## Product Upload Flow (AI → Backend)

When processing stages complete, the AI Gateway uploads products to S3 through the Backend's Product Upload API. This ensures products are properly tracked in the database.

### Upload Flow Diagram

```
AI Gateway                     Backend API                         S3
     │                              │                               │
     │  POST /v1/api/products/upload/init/                              │
     │  {job_id, dataset_id, product_type, file_name}               │
     │─────────────────────────────►│                               │
     │                              │  Create Product record        │
     │                              │  Initialize multipart upload  │
     │                              │──────────────────────────────►│
     │  {product_id, upload_id, s3_upload_id, s3_key}               │
     │◄─────────────────────────────│                               │
     │                              │                               │
     │  POST /v1/api/products/upload/chunk/  (per chunk)                │
     │  {upload_id, s3_upload_id, s3_key, part_number}              │
     │─────────────────────────────►│                               │
     │  {presigned_url, part_number}│                               │
     │◄─────────────────────────────│                               │
     │                              │                               │
     │  PUT presigned_url (upload chunk directly to S3)             │
     │──────────────────────────────────────────────────────────────►│
     │  {ETag}                      │                               │
     │◄──────────────────────────────────────────────────────────────│
     │                              │                               │
     │  POST /v1/api/products/upload/complete/                          │
     │  {upload_id, s3_upload_id, s3_key, parts: [{PartNumber, ETag}]}
     │─────────────────────────────►│                               │
     │                              │  Complete multipart upload    │
     │                              │──────────────────────────────►│
     │                              │  Update Product.uri           │
     │  {product_id, s3_uri, status: "completed"}                   │
     │◄─────────────────────────────│                               │
```

### Product Upload APIs (`/v1/api/products/upload/`)

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| POST | `/init/` | Initialize multipart upload | `{job_id, dataset_id, product_type, file_name, file_size, resolution_cm?, bands?, stats?}` |
| POST | `/chunk/` | Get presigned URL for chunk | `{upload_id, s3_upload_id, s3_key, part_number}` |
| POST | `/complete/` | Complete multipart upload | `{upload_id, s3_upload_id, s3_key, parts: [{PartNumber, ETag}]}` |

**Authentication:** All endpoints require `X-API-Secret-Key` header (same key as AI Gateway callback).

### Product Types

| Type | Description | Source Service |
|------|-------------|----------------|
| `orthomosaic` | 2D Orthomosaic (GeoTIFF) | Orthomosaic |
| `dsm` | Digital Surface Model | Orthomosaic |
| `dem` | Digital Elevation Model | Orthomosaic |
| `hillshade` | Hillshade/Terrain Visualization | Orthomosaic |
| `pointcloud` | 3D Point Cloud (PLY/LAS) | SFM |
| `mesh` | 3D Mesh Model | SFM |
| `sparse_reconstruction` | Sparse Point Cloud | SFM |
| `dense_reconstruction` | Dense Point Cloud | SFM |
| `preview` | Preview/Thumbnail | Any |
| `statistics` | Statistics/Metadata (JSON) | Any |
| `orthomosaic_2x` | 2× Downsampled Orthomosaic (COG) | Orthomosaic |
| `orthomosaic_4x` | 4× Downsampled Orthomosaic (COG) | Orthomosaic |
| `orthomosaic_8x` | 8× Downsampled Orthomosaic (COG) | Orthomosaic |

### S3 Key Structure for Products

```
products/{dataset_id}/{job_id}/{product_type}/{filename}

Examples:
- products/4ee43b40-d3fb-4ae6-8c5e-0c5b4288a6f0/abc123-uuid/orthomosaic/orthomosaic_rgb.tif
- products/4ee43b40-d3fb-4ae6-8c5e-0c5b4288a6f0/abc123-uuid/dsm/dsm_filled_cog.tif
- products/4ee43b40-d3fb-4ae6-8c5e-0c5b4288a6f0/abc123-uuid/pointcloud/sparse.ply
```

---

## Redis Usage

**Purpose:** Transient job state during AI processing

**Key Pattern:** `photogear:job:{job_id}`

**TTL:** 72 hours (jobs expire after this period)

**Operations:**
- `JobStateManager.create_job()`: Creates job state
- `JobStateManager.get_job()`: Retrieves job state
- `JobStateManager.start_stage()`: Marks stage as running
- `JobStateManager.complete_stage()`: Marks stage complete, returns next stage
- `JobStateManager.fail_stage()`: Marks stage and job as failed

**Why Redis (not just PostgreSQL):**
- Fast read/write for frequent progress updates
- TTL for automatic cleanup
- Atomic operations for state transitions
- Backend PostgreSQL is authoritative; Redis is for AI orchestration

---

## S3 Bucket Usage

| Bucket | Environment Variable | Purpose | Access |
|--------|---------------------|---------|--------|
| Raw Images | `AWS_S3_RAW_IMAGES_BUCKET` | Source drone images | Backend generates presigned URLs |
| AI Dev | `AWS_S3_AI_DEV_BUCKET` | Intermediate files (calibration, SFM outputs) | AI services read/write |
| Results | `AWS_S3_RESULTS_BUCKET` | Final products (orthomosaic, DSM, COG) | AI uploads, Backend serves |

**Path Conventions:**
- Calibration: `s3://{AI_DEV_BUCKET}/calibration/{dataset_id}/`
- SFM: `s3://{AI_DEV_BUCKET}/sfm/{dataset_id}/`
- Orthomosaic: `s3://{RESULTS_BUCKET}/products/{dataset_id}/orthomosaic.tif`
- DSM: `s3://{RESULTS_BUCKET}/products/{dataset_id}/dsm.tif`

---

## Retry & Rerun Mechanism

### Rerun (Re-trigger existing job)

**Endpoint:** `POST /v1/api/jobs/{job_id}/rerun/`

**Purpose:** Re-run an existing job without creating a new record

**Options:**
- `reset_status=true` (default): Reset job to 'queued' state
- `resume=true`: Resume from last stage (uses `last_successful_stage`)

**Use Cases:**
- Job got stuck and needs restart
- Testing/debugging a specific job
- Resuming after transient failure

### Cancel Job

**Endpoint:** `POST /v1/api/jobs/{job_id}/cancel/`

**Purpose:** Stop a running job

**Process:**
1. Backend updates job status to 'cancelled'
2. Backend calls AI Gateway: `POST /jobs/{job_id}/cancel`
3. AI Gateway stops background task
4. AI Gateway updates Redis state

### Delete Job

**Endpoint:** `DELETE /v1/api/jobs/{job_id}/delete/`

**Purpose:** Remove job record and associated products

**Process:**
1. Validates job can be deleted (not running)
2. Deletes associated products from S3
3. Removes Product records from database
4. Deletes ProcessingJob record

---

## Error Handling

### Stage Failure

When a sub-service fails:
1. Sub-service sends callback with `status: "failed"` and `error` message
2. AI Gateway updates Redis: stage → failed, job → failed
3. AI Gateway sends error callback to Backend
4. Backend updates PostgreSQL job status
5. Job can be rerun with `resume=true` to continue from failed stage

### Retry Logic

**Backend tracks:**
- `last_successful_stage`: Last completed stage (for resume)
- `error_message`: Error details
- `can_retry`: Boolean flag for retry eligibility

**Resume Flow:**
```
Original Job: queued → sfm → [FAILED at sfm]
                             ↓
Rerun with resume=true: sfm → orthomosaic_generation → complete
```

---

## API Summary

### Backend Job APIs (`/v1/api/jobs/`)

| Method | Endpoint | Description | Tag |
|--------|----------|-------------|-----|
| POST | `/start-job/` | Create and start new job | Processing Jobs |
| GET | `/` | List all jobs | Processing Jobs |
| GET | `/{job_id}/` | Get job details | Processing Jobs |
| DELETE | `/{job_id}/delete/` | Delete job | Processing Jobs |
| POST | `/{job_id}/cancel/` | Cancel running job | Processing Jobs |
| POST | `/{job_id}/rerun/` | Rerun existing job | Processing Jobs |
| POST | `/ai-callback/` | AI Gateway callback (internal) | AI Callbacks |
| GET | `/{job_id}/products/` | Get job products | Processing Jobs |

### AI Gateway APIs (`/jobs/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/run` | Start processing pipeline |
| GET | `/{job_id}/status` | Get job status from Redis |
| POST | `/{job_id}/cancel` | Cancel running job |
| POST | `/subservice-callback` | Receive sub-service callbacks |

### Sub-Service APIs

| Service | Port | Endpoint | Description |
|---------|------|----------|-------------|
| Calibration | 8001 | POST `/calibration/run` | Start calibration |
| SFM | 8002 | POST `/sfm/run` | Start SFM processing |
| Orthomosaic | 8003 | POST `/orthomosaic/run` | Start orthomosaic generation |

---

## Configuration

### Environment Variables

**Backend:**
```env
AI_GATEWAY_URL=http://192.168.254.16:8080
AI_GATEWAY_SECRET_KEY=your-secret-key
AWS_S3_RAW_IMAGES_BUCKET=photogear-raw-images
AWS_S3_RESULTS_BUCKET=photogear-results
```

**AI Gateway:**
```env
BACKEND_API_URL=http://192.168.254.16:8000
BACKEND_API_SECRET_KEY=your-secret-key
CALIBRATION_CLIENT_ADDRESS=http://192.168.254.30:8001
SFM_CLIENT_ADDRESS=http://192.168.254.30:8002
ORTHOMOSAIC_CLIENT_ADDRESS=http://192.168.254.30:8003
REDIS_HOST=localhost
REDIS_PORT=6379
AWS_S3_AI_DEV_BUCKET=photogear-ai-dev
AWS_S3_RESULTS_BUCKET=photogear-results
```

**Sub-Services:**
```env
API_GATEWAY_HOST=192.168.254.16
API_GATEWAY_PORT=8080
AWS_S3_AI_DEV_BUCKET=photogear-ai-dev
```

---

## Database Tables

### Core Tables for Job Processing

| Table | App | Purpose |
|-------|-----|---------|
| `jobs_processing_job` | jobs | Main job record - status, progress, retry tracking |
| `products_product` | products | Processing outputs - orthomosaic, DSM, mesh, etc. |
| `uploads_datasets` | uploads | Dataset metadata - name, organization, bounding box |
| `uploads_images` | uploads | Source image metadata - S3 key, EXIF, dimensions |
| `uploads_statuses` | uploads | Status lookup table - PENDING, PROCESSING, etc. |

### Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Organization                               │
│                           (accounts_organization)                       │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ 1:N
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                                Dataset                                   │
│                           (uploads_datasets)                             │
├─────────────────────────────────────────────────────────────────────────┤
│  id (UUID PK)                                                           │
│  org_id (FK → Organization)                                             │
│  name, platform, capture_start, capture_end, crs, bbox (Polygon)        │
│  notes, created_at, updated_at                                          │
└─────────────────────────────────────────────────────────────────────────┘
             │                                           │
             │ 1:N                                       │ 1:N
             ▼                                           ▼
┌─────────────────────────────────┐    ┌─────────────────────────────────┐
│           Image                  │    │        ProcessingJob            │
│      (uploads_images)            │    │    (jobs_processing_job)        │
├─────────────────────────────────┤    ├─────────────────────────────────┤
│  id (UUID PK)                   │    │  id (UUID PK)                   │
│  dataset_id (FK → Dataset)      │    │  dataset_id (FK → Dataset)      │
│  status_id (FK → UploadStatus)  │    │  resolution_gsd (Float)         │
│  user_id (UUID)                 │    │  radiometric_calibration (Bool) │
│  file_name, content_type        │    │  status (queued/processing/...) │
│  s3_key, s3_upload_id           │    │  stage (queued/sfm/mvs/...)     │
│  file_size, batch_id            │    │  progress (0-100)               │
│  parent_image (FK → self)       │    │  error_message (Text)           │
│  file_type (IMAGE/ARCHIVE)      │    │  retry_count (Int)              │
│  width, height, checksum        │    │  last_successful_stage          │
│  exif (JSON), imu (JSON)        │    │  original_job_id (UUID)         │
│  created_at, updated_at         │    │  can_retry (Bool)               │
└─────────────────────────────────┘    │  created_at, updated_at         │
                                       └─────────────────────────────────┘
                                                        │
                                                        │ 1:N
                                                        ▼
                                       ┌─────────────────────────────────┐
                                       │           Product               │
                                       │     (products_product)          │
                                       ├─────────────────────────────────┤
                                       │  id (UUID PK)                   │
                                       │  dataset_id (FK → Dataset)      │
                                       │  job_id (FK → ProcessingJob)    │
                                       │  type (orthomosaic/dsm/mesh/...)│
                                       │  uri (S3 key, VARCHAR 512)      │
                                       │  footprint (Polygon, SRID 4326) │
                                       │  resolution_cm (Float)          │
                                       │  bands (Array[VARCHAR])         │
                                       │  stats (JSON)                   │
                                       │  created_at                     │
                                       └─────────────────────────────────┘
```

### ProcessingJob Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `dataset_id` | FK | Reference to Dataset |
| `resolution_gsd` | Float | Ground Sample Distance in cm/px |
| `radiometric_calibration` | Bool | Whether to run calibration |
| `status` | Enum | `pending`, `queued`, `processing`, `completed`, `failed` |
| `stage` | Enum | `queued`, `sfm`, `mvs`, `publishing` |
| `progress` | Int | 0-100 progress percentage |
| `error_message` | Text | Error details if failed |
| `retry_count` | Int | Number of retries (max 3) |
| `last_successful_stage` | Enum | For resume on retry |
| `original_job_id` | UUID | Points to original if this is a retry |
| `can_retry` | Bool | Whether job is eligible for retry |

### Product Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `dataset_id` | FK | Reference to Dataset |
| `job_id` | FK | Reference to ProcessingJob (nullable) |
| `type` | Enum | Product type (see Product Types above) |
| `uri` | VARCHAR(512) | S3 key for the product file |
| `footprint` | Polygon | Geospatial footprint (EPSG:4326) |
| `resolution_cm` | Float | Resolution in cm/pixel |
| `bands` | Array | List of spectral bands |
| `stats` | JSON | Product statistics and metadata |

---

## Deprecated Endpoints

The following endpoints are deprecated and should not be used:

| Endpoint | Replacement | Reason |
|----------|-------------|--------|
| `POST /v1/api/jobs/{job_id}/retry/` | Use `/rerun/` | Duplicate functionality |
| `POST /v1/api/processings/start/{dataset_id}/` | Use `/v1/api/jobs/start-job/` | Legacy endpoint |
| `POST /v1/api/processings/callback/` | Use `/v1/api/jobs/ai-callback/` | Legacy endpoint |
---

## Known Issues & Implementation Gaps

### 1. ⚠️ Upload Session Storage In-Memory

**Location:** `backend/products/views.py`

```python
UPLOAD_SESSIONS = {}  # TODO: In production, use Redis or database
```

**Issue:** Upload sessions are stored in memory. If the backend restarts during an upload, the session is lost and the multipart upload cannot be completed.

**Recommendation:** Move to Redis or database-backed session storage.

### 2. ✅ FIXED - Calibration Service Now Uses Shared Volume

**Location:** `services/radiometric_calibration/app/v1/api/products/upload/endpoints/calibration_endpoint.py`

**Previous Issue:** The calibration service was returning mock S3 paths without performing actual calibration.

**Fix Applied:** Calibration service now:
- Downloads images from shared volume (`temp/datasets/{dataset_id}/images/`)
- Performs passthrough calibration (copies images as calibrated)
- Writes to shared volume (`temp/jobs/radiometric/{job_id}_radiometric/calibrated_images/`)
- Returns actual file paths for next stage

### 3. ✅ FIXED - Product Footprint Now Extracted

**Location:** `backend/products/geo_utils.py`, `backend/products/views.py`

**Previous Issue:** The `footprint` field on Product model was never populated.

**Fix Applied:** 
- New `geo_utils.py` module with `extract_footprint_from_s3()` function
- Uses rasterio to extract geographic bounds from GeoTIFF files
- `ProductUploadCompleteView` now extracts footprint for orthomosaic, dsm, dem, hillshade products
- Footprint stored as GeoDjango Polygon in WGS84

### 4. ✅ FIXED - Upload Abort Endpoint Added

**Location:** `backend/products/views.py`, `backend/products/urls.py`

**Previous Issue:** No cleanup mechanism for failed multipart uploads.

**Fix Applied:**
- New `ProductUploadAbortView` at `POST /v1/api/products/upload/api/products/upload/abort/`
- Aborts S3 multipart upload using `upload_id`
- Deletes partial Product record
- Cleans up session storage
- AI Gateway can call this if upload fails midway

**Recommendation (still applies):** Add S3 lifecycle rule to clean up incomplete uploads after 7 days.

### 5. ✅ FIXED - Stage Names Now Consistent

**Locations:**
- Backend: `backend/apps/jobs/processing_stages.py` (Django TextChoices)
- AI Gateway: `infrastructure/state/models.py` (Python Enum)
- API Gateway entities: `api_gateway/app/entities/jobs.py`

**Previous Issue:** Stage names differed between AI Gateway and Backend.

**Fix Applied:**
- Backend uses Django `TextChoices` for proper model integration
- AI Gateway uses Python `Enum` for consistency
- Stage values: `pending`, `queued`, `radiometric_calibration`, `sfm`, `orthomosaic`, `uploading`, `publishing`, `completed`, `failed`, `cancelled`
- Backend `ai_callback.py` uses `ProcessingStage.is_valid_stage()` for validation
- Backend no longer needs stage_mapping dictionary

### 6. ✅ FIXED - Shared Volume Path Configuration

**Location:** `infrastructure/storage/s3_settings.py`, all sub-services

**Previous Issue:** Paths were potentially hardcoded, causing issues if volumes weren't shared.

**Fix Applied:**
- `TempStorageSettings` class uses `TEMP_BASE_PATH` environment variable
- Default: `/app/data/temp` (configurable per deployment)
- All sub-services use consistent path structure:
  ```
  temp/
  ├── datasets/{dataset_id}/images/     # Source images
  └── jobs/
      ├── radiometric/{job_id}_radiometric/  # Calibration outputs
      ├── sfm/{job_id}_sfm/                  # SFM outputs
      └── orthomosaic/{job_id}_orthomosaic/  # Orthomosaic outputs
  ```
- Sub-services MUST share this volume for processing to work

---

## Future Enhancements

- [ ] **Progress granularity:** Report sub-stage progress (e.g., "SFM: Feature extraction 45%")
- [ ] **WebSocket support:** Real-time progress updates to frontend
- [ ] **Priority queue:** Urgent jobs can skip the queue
- [ ] **Resource management:** GPU allocation, memory limits per job
- [ ] **Cost estimation:** Estimate processing time/cost before starting
- [ ] **Batch processing:** Process multiple datasets in one job