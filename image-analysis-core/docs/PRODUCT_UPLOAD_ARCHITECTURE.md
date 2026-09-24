# Product Upload Architecture

## Overview

This document explains how AI processing results are uploaded to the backend after each processing stage completes.

## Current Architecture

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CALLBACK-DRIVEN UPLOAD FLOW                        │
└─────────────────────────────────────────────────────────────────────────────────┘

1. Sub-service (SFM/Orthomosaic) completes processing
   │
   ▼
2. Sub-service sends callback to API Gateway
   POST /v1/api/products/upload/jobs/subservice-callback
   {
     "service": "sfm",
     "job_id": "abc123_sfm",
     "status": "completed",
     "result": { "run_path": "/app/data/temp/jobs/sfm/abc123_sfm/run_1", ... }
   }
   │
   ▼
3. API Gateway receives callback in `subservice_callback` endpoint
   │
   ├──► Updates JobState in Redis
   │
   ├──► Calls `upload_stage_products()` ◄─────────────────────────────────────────┐
   │    │                                                                          │
   │    │  For each product file (pointcloud, mesh, orthomosaic, dsm, etc.):       │
   │    │                                                                          │
   │    │  ┌─────────────────────────────────────────────────────────────────┐     │
   │    │  │  MULTIPART UPLOAD PROCESS (via ProductUploadClient)             │     │
   │    │  │                                                                 │     │
   │    │  │  Step 1: POST /v1/api/products/upload/init/                         │     │
   │    │  │          → Initializes upload, creates Product record           │     │
   │    │  │          → Returns product_id, upload_id, s3_upload_id         │     │
   │    │  │                                                                 │     │
   │    │  │  Step 2: POST /v1/api/products/upload/chunk/                        │     │
   │    │  │          → Gets presigned URL for each 500MB chunk              │     │
   │    │  │          → AI uploads chunk directly to S3                      │     │
   │    │  │          → Repeat for all chunks                                │     │
   │    │  │                                                                 │     │
   │    │  │  Step 3: POST /v1/api/products/upload/complete/                     │     │
   │    │  │          → Backend completes multipart upload in S3             │     │
   │    │  │          → Updates Product record with final S3 URI             │     │
   │    │  └─────────────────────────────────────────────────────────────────┘     │
   │    │                                                                          │
   │    └──────────────────────────────────────────────────────────────────────────┘
   │
   ├──► Sends progress update to backend
   │
   └──► Triggers next stage (or completes pipeline)
```

## Backend Endpoints Used

### 1. Initialize Upload
```
POST /v1/api/products/upload/init/
Authorization: X-API-Secret-Key: <secret>

Request:
{
  "job_id": "uuid",
  "dataset_id": "uuid",
  "product_type": "orthomosaic|dsm|pointcloud|mesh|hillshade",
  "file_name": "orthomosaic_rgb.tif",
  "file_size": 1073741824,
  "resolution_cm": 5.0,  // optional
  "bands": ["R", "G", "B"],  // optional
  "stats": {}  // optional
}

Response:
{
  "product_id": "uuid",
  "upload_id": "uuid",
  "s3_upload_id": "aws-multipart-id",
  "s3_key": "products/job-id/orthomosaic.tif"
}
```

### 2. Get Chunk Presigned URL
```
POST /v1/api/products/upload/chunk/
Authorization: X-API-Secret-Key: <secret>

Request:
{
  "upload_id": "uuid",
  "s3_upload_id": "aws-multipart-id",
  "s3_key": "products/job-id/orthomosaic.tif",
  "part_number": 1
}

Response:
{
  "url": "https://s3.amazonaws.com/bucket/key?presigned-params",
  "part_number": 1
}
```

### 3. Complete Upload
```
POST /v1/api/products/upload/complete/
Authorization: X-API-Secret-Key: <secret>

Request:
{
  "upload_id": "uuid",
  "s3_upload_id": "aws-multipart-id",
  "s3_key": "products/job-id/orthomosaic.tif",
  "parts": [
    {"PartNumber": 1, "ETag": "\"abc123\""},
    {"PartNumber": 2, "ETag": "\"def456\""}
  ]
}

Response:
{
  "product_id": "uuid",
  "s3_uri": "s3://bucket/products/job-id/orthomosaic.tif",
  "status": "completed"
}
```

## Products Uploaded Per Stage

### SFM Stage
| Product Type | File Path | Description |
|-------------|-----------|-------------|
| pointcloud | `{run_path}/dense/fused.ply` | Dense point cloud from stereo matching |
| mesh | `{run_path}/dense/meshed-poisson.ply` | 3D mesh from Poisson reconstruction |

### Orthomosaic Stage
| Product Type | File Path | Description |
|-------------|-----------|-------------|
| orthomosaic | `{dataset_path}/orthomosaic_rgb.tif` | RGB orthomosaic (GeoTIFF) |
| dsm | `{dataset_path}/dsm_filled_cog.tif` | Digital Surface Model (COG format) |
| hillshade | `{dataset_path}/hillshade.tif` | Hillshade visualization |
| orthomosaic_2x | `{dataset_path}/orthomosaic_rgb_2x.tif` | 2× downsampled orthomosaic (COG) |
| orthomosaic_4x | `{dataset_path}/orthomosaic_rgb_4x.tif` | 4× downsampled orthomosaic (COG) |
| orthomosaic_8x | `{dataset_path}/orthomosaic_rgb_8x.tif` | 8× downsampled orthomosaic (COG) |

## Current Issues & Recommendations

### Issue 1: File Path Resolution ✅ RESOLVED
**Problem**: The `upload_stage_products()` function checks if files exist on the API Gateway's filesystem, but sub-services run in separate containers with different volume mounts.

**Solution Implemented**: 
- Added detailed logging before upload attempts to trace file path resolution
- Logs include: file path, existence check, file size
- Error messages explicitly mention volume mount issues when files aren't found

### Issue 2: Upload Failures Don't Block Pipeline ✅ RESOLVED
**Problem**: If product upload fails, the pipeline continues to the next stage. This could result in processing completing but products not being saved.

**Solution Implemented**:
- Created `UploadResult` class to track successful and failed uploads
- Upload failures are recorded in job state via `job_state_manager.update_job()`
- Critical failures (orthomosaic) are logged with warnings
- Summary logging shows success/failure counts per stage

### Issue 3: No Cleanup After Upload
**Note**: This is handled by `TempStorageManager` which was implemented earlier with configurable cleanup policies.

### Issue 4: S3 Upload from Sub-services (NOT IMPLEMENTED)
**Decision**: Keep current approach using presigned URLs via backend because:
- Backend controls all S3 access (security)
- Backend creates Product records with proper metadata
- Sub-services remain stateless

### Issue 5: Redis Persistence
**Current Config**: Redis uses `appendonly yes` which provides sufficient durability for job state.

## Code Location Reference

| Component | File |
|-----------|------|
| ProductUploadClient | `api_gateway/app/clients/product_upload_client.py` |
| upload_stage_products() | `api_gateway/app/v1/api/products/upload/endpoints/jobs.py` |
| Backend Init Endpoint | `backend/apps/products/views.py` |
| Backend Chunk Endpoint | `backend/apps/products/views.py` |
| Backend Complete Endpoint | `backend/apps/products/views.py` |

## Testing Upload Flow

```bash
# Check if products were created for a job
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/api/jobs/{job_id}/products/

# Response includes all uploaded products with S3 URIs
```
