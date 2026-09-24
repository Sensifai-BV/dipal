# PhotoGear API Gateway and Services

This document describes the API Gateway and microservices architecture for the PhotoGear processing pipeline.

## Architecture Overview

The PhotoGear system consists of 4 microservices:

1. **API Gateway** - Orchestrates the entire processing pipeline
2. **Radiometric Calibration Service** - Performs radiometric calibration (mock implementation)
3. **SFM Service** - Structure from Motion processing
4. **Orthomosaic Generation Service** - Generates orthomosaics from SFM results

### Processing Pipeline

```
Backend Request → API Gateway → Radiometric Calibration → SFM → Orthomosaic Generation → Upload Results → Backend Notification
```

## API Gateway Endpoints

Base URL: `http://api-gateway:8000`

### 1. Run Job

Start a complete processing pipeline.

**Endpoint:** `POST /jobs/run`

**Request Body:**
```json
{
  "dataset_id": "dataset123",
  "download_url": "https://storage.example.com/presigned-url",
  "parameters": {
    "analysis_mode": "full",
    "resolution_gsd": 5.0,
    "calibration": {},
    "sfm": {},
    "orthomosaic": {
      "generate_cog": true
    }
  }
}
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `analysis_mode` | `string` | `"fast"` | `"fast"` = RGB pipeline only; `"full"` = RGB + multispectral vegetation indices |
| `resolution_gsd` | `float` | `null` | Ground sampling distance (cm/px). In fast mode, SFM doubles this for speed. |
```

**Response:**
```json
{
  "job_id": "uuid-here",
  "status": "running",
  "progress": 0.0,
  "current_stage": "radiometric_calibration",
  "result": null,
  "error": null,
  "created_at": null,
  "updated_at": null
}
```

### 2. Get Job Status

Query the status of a running or completed job.

**Endpoint:** `GET /jobs/{job_id}/status`

**Response:**
```json
{
  "job_id": "uuid-here",
  "status": "running",
  "progress": 45.5,
  "current_stage": "sfm",
  "result": null,
  "error": null,
  "created_at": "2025-12-08T10:00:00Z",
  "updated_at": "2025-12-08T10:05:00Z"
}
```

**Status Values:**
- `pending` - Job created but not started
- `running` - Job is currently executing
- `completed` - Job finished successfully
- `failed` - Job encountered an error
- `cancelled` - Job was cancelled
- `not_found` - Job ID not found

**Processing Stages:**
- `radiometric_calibration`
- `sfm`
- `orthomosaic_generation`
- `uploading_results`
- `finalizing`

### 3. Cancel Job

Cancel a running job.

**Endpoint:** `POST /jobs/{job_id}/cancel`

**Response:**
```json
{
  "job_id": "uuid-here",
  "cancelled": true,
  "message": "Job cancelled successfully"
}
```

## Service Endpoints

Each processing service exposes the following endpoints:

### Radiometric Calibration Service

Base URL: `http://radiometric-calibration:8001`

#### Run Calibration
**Endpoint:** `POST /calibration/run`

**Request:**
```json
{
  "job_id": "calib-job-123",
  "dataset_id": "dataset123",
  "download_url": "https://...",
  "parameters": {}
}
```

#### Get Status
**Endpoint:** `GET /calibration/jobs/{job_id}/status`

#### Cancel Job
**Endpoint:** `POST /calibration/jobs/{job_id}/cancel`

#### Get Result
**Endpoint:** `GET /calibration/jobs/{job_id}/result`

### SFM Service

Base URL: `http://sfm:8002`

#### Run SFM
**Endpoint:** `POST /sfm/run`

**Request:**
```json
{
  "job_id": "sfm-job-123",
  "dataset_id": "dataset123",
  "dataset_path": "/path/to/images",
  "parameters": {}
}
```

#### Get Status
**Endpoint:** `GET /sfm/jobs/{job_id}/status`

#### Cancel Job
**Endpoint:** `POST /sfm/jobs/{job_id}/cancel`

#### Get Result
**Endpoint:** `GET /sfm/jobs/{job_id}/result`

### Orthomosaic Generation Service

Base URL: `http://orthomosaic-generation:8003`

#### Run Orthomosaic Generation
**Endpoint:** `POST /orthomosaic/run`

**Request:**
```json
{
  "job_id": "ortho-job-123",
  "dataset_id": "dataset123",
  "dataset_path": "/path/to/sfm/results",
  "parameters": {
    "generate_cog": true
  }
}
```

#### Get Status
**Endpoint:** `GET /orthomosaic/jobs/{job_id}/status`

#### Cancel Job
**Endpoint:** `POST /orthomosaic/jobs/{job_id}/cancel`

#### Get Result
**Endpoint:** `GET /orthomosaic/jobs/{job_id}/result`

## Environment Variables

### API Gateway

```env
CALIBRATION_CLIENT_ADDRESS=http://radiometric-calibration:8001
SFM_CLIENT_ADDRESS=http://sfm:8002
ORTHOMOSAIC_CLIENT_ADDRESS=http://orthomosaic-generation:8003
```

## Background Task Processing

The system uses an enhanced `BackgroundTaskHandler` that provides:

- **Async Task Execution** - Tasks run in the background without blocking API responses
- **Job Status Tracking** - Track progress, status, and results
- **Job Cancellation** - Cancel running jobs
- **Error Handling** - Capture and report errors

### Job Status Tracking

Jobs go through the following lifecycle:

1. **Created** - Job record created with `pending` status
2. **Running** - Background task started
3. **Progress Updates** - Progress percentage updated throughout pipeline
4. **Completed/Failed/Cancelled** - Final status with results or error

## Storage System

The system uses the presigned URL driver to:

1. Download datasets from backend-provided URLs
2. Process data locally
3. Upload results back to backend (TODO)

## Dependency Injection

All services use **Lagom** for dependency injection:

```python
container = Container()
container[BackgroundTaskHandler] = Singleton(BackgroundTaskHandler)
container[SomeService] = Singleton(SomeService)

deps = FastApiIntegration(container=container)
```

## Docker Compose

All services are configured in `docker-compose.yml` and can be started with:

```bash
docker-compose up
```

## Development Notes

### Radiometric Calibration

Currently uses a **mock implementation** that simulates calibration processing. The actual calibration algorithms are in `services/radiometric_calibration/app/core/algorithms/` but are not yet integrated into the endpoint.

### SFM

Uses COLMAP for structure from motion processing. The implementation is in `services/sfm/app/core/`.

### Orthomosaic Generation

Generates DSM, RGB orthomosaic, hillshade, and COG outputs. Implementation in `services/orthomosaic_generation/app/core/`.

## TODO

- [ ] Implement actual upload to backend storage
- [ ] Add backend notification on completion
- [x] Integrate actual radiometric calibration algorithms (v0.6.0: reflectance conversion)
- [ ] Add authentication/authorization
- [ ] Add rate limiting
- [ ] Implement job result cleanup
- [ ] Add comprehensive logging
- [ ] Add metrics and monitoring

## Multispectral Analysis (v0.6.0)

When `analysis_mode = "full"` and the dataset is multispectral, the orthomosaic
stage produces additional products:

| Product | Type | Description |
|---------|------|-------------|
| NDVI | `ndvi` | Normalized Difference Vegetation Index |
| NDRE | `ndre` | Normalized Difference Red Edge Index |
| GNDVI | `gndvi` | Green Normalized Difference Vegetation Index |
| Multiband reflectance | `calibrated_reflectance` | 4-band (G/R/RE/NIR) stacked GeoTIFF |

### Multi-Resolution Outputs (v0.6.0)

All orthomosaic jobs (both fast and full mode) produce downsampled variants:

| Product | Type | Description |
|---------|------|-------------|
| Orthomosaic 2× | `orthomosaic_2x` | 2× downsampled COG |
| Orthomosaic 4× | `orthomosaic_4x` | 4× downsampled COG |
| Orthomosaic 8× | `orthomosaic_8x` | 8× downsampled COG |

See [MULTISPECTRAL_ANALYSIS.md](MULTISPECTRAL_ANALYSIS.md) for full details.
