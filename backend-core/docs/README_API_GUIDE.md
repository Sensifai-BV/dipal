# PhotoGear Backend API Guide

> A practical guide for developers integrating with the PhotoGear photogrammetry backend.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
   - [Register](#1-register-a-new-user)
   - [Login](#2-login--get-tokens)
3. [File Upload](#file-upload)
   - [Method A: Multipart Upload (ZIP)](#method-a-multipart-upload-recommended-for-large-files)
   - [Method B: Import from S3 URL](#method-b-import-from-s3-presigned-url)
4. [Start Processing Job](#start-processing-job)
5. [Monitor Job Progress](#monitor-job-progress)
6. [Get Results (Products)](#get-results-products)
7. [Complete Workflow Diagram](#complete-workflow-diagram)
8. [API Reference Summary](#api-reference-summary)
9. [Changelog](#changelog)

---

## Quick Start

**Base URL:**
```
https://api-photogear.sensifai.com/v1/
```

**Headers for authenticated requests:**
```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

---

## Authentication

### 1. Register a New User

**Endpoint:** `POST /v1/accounts/register/`

**Request:**
```bash
curl -X POST https://api-photogear.sensifai.com/v1/accounts/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Doe",
    "email": "john@example.com",
    "organization": "My Company",
    "role": 1,
    "password": "securepass123",
    "confirm_password": "securepass123"
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `full_name` | string | Yes | User's full name |
| `email` | string | Yes | User's email (must be unique) |
| `organization` | string | Yes | Organization name (created if doesn't exist) |
| `role` | integer | Yes | Role ID (1 = admin, 2 = user) |
| `password` | string | Yes | Password (min 8 characters) |
| `confirm_password` | string | Yes | Must match password |

**Success Response (201):**
```json
{
  "status": "success",
  "data": {
    "id": 5,
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "organization_id": 3
  }
}
```

---

### 2. Login / Get Tokens

**Endpoint:** `POST /v1/accounts/login/`

**Request:**
```bash
curl -X POST https://api-photogear.sensifai.com/v1/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "securepass123"
  }'
```

**Success Response (200):**
```json
{
  "status": "success",
  "data": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "access_expires_in": 432000,
    "refresh_expires_in": 86400
  }
}
```

**Token Usage:**
- **Access Token:** Valid for 5 days. Use in `Authorization` header.
- **Refresh Token:** Valid for 1 day. Use to get new access token when expired.

**Using the Token:**
```bash
# All subsequent requests require the Authorization header
curl -X GET https://api-photogear.sensifai.com/v1/api/uploads/datasets/stats/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## File Upload

PhotoGear supports two methods for uploading datasets:

| Method | Best For | How It Works |
|--------|----------|--------------|
| **Multipart Upload** | Large ZIP files (>100MB) | Upload directly from client in chunks |
| **Import from S3 URL** | Files already in S3/cloud | Server downloads from your presigned URL |

---

### Method A: Multipart Upload (Recommended for Large Files)

This is a 3-step process for reliable large file uploads.

#### Step 1: Initialize Upload Session

**Endpoint:** `POST /v1/api/uploads/multipart/init/`

```bash
curl -X POST https://api-photogear.sensifai.com/v1/api/uploads/multipart/init/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "Farm Survey 2024",
    "batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "file_name": "drone_images.zip",
    "file_type": "ARCHIVE",
    "content_type": "application/zip",
    "file_size": 5368709120
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dataset_name` | string | Yes* | Name for the dataset |
| `dataset_id` | UUID | No | Use existing dataset (alternative to name) |
| `batch_id` | UUID | Yes | Unique batch identifier (generate one) |
| `file_name` | string | Yes | Original filename |
| `file_type` | string | Yes | `"ARCHIVE"` for ZIP files |
| `content_type` | string | Yes | MIME type (`"application/zip"`) |
| `file_size` | integer | Yes | File size in bytes |

*Either `dataset_name` or `dataset_id` is required.

**Success Response (200):**
```json
{
  "upload_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "s3_upload_id": "VXBsb2FkSWQtMTIzNDU2Nzg5",
  "s3_key": "orgs/1/users/5/datasets/abc123/batch_xyz/drone_images.zip",
  "dataset_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

> ⚠️ **Save `upload_id`** - You need it for the next steps!

---

#### Step 2: Upload Each Chunk

Split your file into chunks (recommended: 10MB each) and get a presigned URL for each chunk.

**Endpoint:** `POST /v1/api/uploads/multipart/sign-part/`

```bash
# For each part (chunk), request a presigned URL
curl -X POST https://api-photogear.sensifai.com/v1/api/uploads/multipart/sign-part/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "upload_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "part_number": 1
  }'
```

**Response:**
```json
{
  "url": "https://s3.amazonaws.com/bucket/key?X-Amz-Signature=..."
}
```

**Then upload the chunk directly to S3:**
```bash
# Upload binary data to the presigned URL
curl -X PUT "https://s3.amazonaws.com/bucket/key?X-Amz-Signature=..." \
  --data-binary @chunk_1.bin
```

**Save the ETag from the response headers!**

```bash
# The response header will include:
# ETag: "a1b2c3d4e5f6..."
```

Repeat for all chunks (Part 1, Part 2, Part 3, etc.)

---

#### Step 3: Complete the Upload

**Endpoint:** `POST /v1/api/uploads/multipart/complete/`

```bash
curl -X POST https://api-photogear.sensifai.com/v1/api/uploads/multipart/complete/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "upload_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "parts": [
      {"PartNumber": 1, "ETag": "\"a1b2c3d4e5f6...\""},
      {"PartNumber": 2, "ETag": "\"d4e5f6g7h8i9...\""},
      {"PartNumber": 3, "ETag": "\"j1k2l3m4n5o6...\""}
    ]
  }'
```

**Success Response (200):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "dataset_id": "123e4567-e89b-12d3-a456-426614174000",
  "file_name": "drone_images.zip",
  "status": "EXTRACTING",
  "s3_key": "orgs/1/users/5/datasets/abc123/batch_xyz/drone_images.zip"
}
```

The server will now:
1. ✅ Merge all chunks in S3
2. ✅ Extract the ZIP file
3. ✅ Create individual image records
4. ✅ Mark dataset as ready for processing

---

### Method B: Import from S3 Presigned URL

If your images are already in another S3 bucket, use this method.

**Endpoint:** `POST /v1/api/uploads/upload/url/`

```bash
curl -X POST https://api-photogear.sensifai.com/v1/api/uploads/upload/url/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "Field Survey 2024",
    "file_url": "https://your-bucket.s3.amazonaws.com/images.zip?X-Amz-Signature=...",
    "file_name": "field_images.zip"
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dataset_name` | string | Yes* | Name for the dataset |
| `dataset_id` | UUID | No | Use existing dataset |
| `file_url` | string | Yes | Presigned S3 URL to your file |
| `file_name` | string | No | Override filename (auto-detected if omitted) |
| `batch_id` | UUID | No | Batch identifier (auto-generated if omitted) |

**Success Response (202 Accepted):**
```json
{
  "upload_id": "7fa85f64-5717-4562-b3fc-2c963f66afa6",
  "dataset_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "DOWNLOADING",
  "message": "Start downloading 'field_images.zip' in background."
}
```

The server handles the download in the background. You can poll the upload status:

```bash
curl -X GET "https://api-photogear.sensifai.com/v1/api/uploads/list/?dataset_id=123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer <token>"
```

---

## Start Processing Job

Once your images are uploaded and extracted, start the photogrammetry processing.

**Endpoint:** `POST /v1/api/jobs/start-job/`

```bash
curl -X POST https://api-photogear.sensifai.com/v1/api/jobs/start-job/ \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "123e4567-e89b-12d3-a456-426614174000",
    "resolution_gsd": 2.5,
    "radiometric_calibration": true,
    "analysis_mode": "full"
  }'
```

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `dataset_id` | UUID | Yes | — | ID of the uploaded dataset |
| `resolution_gsd` | float | Yes | — | Desired output resolution in cm/pixel (e.g., 2.5 = 2.5cm per pixel) |
| `radiometric_calibration` | boolean | Yes | — | Enable radiometric calibration for consistent color |
| `analysis_mode` | string | **No** | `"fast"` | Processing depth: `"fast"` = RGB-only (faster), `"full"` = RGB + multispectral vegetation indices (NDVI, NDRE, GNDVI) |

> **Note:** When `analysis_mode` is omitted, it defaults to `"fast"`. In fast mode, SFM
> resolution is doubled for speed. In full mode, calibrated spectral bands are
> orthorectified and vegetation indices are computed as additional products.

**Success Response (201 Created):**
```json
{
  "id": "fe566e35-189c-49fa-acec-a3568a21176a",
  "job_uid": "job_fe566e35",
  "status": "pending",
  "resolution_gsd": 2.5,
  "message": "Processing started successfully"
}
```

> 💡 **Save the `id`** - This is your job ID for monitoring and retrieving results!

---

## Monitor Job Progress

### Get Job Details

**Endpoint:** `GET /v1/api/jobs/{job_id}/`

```bash
curl -X GET https://api-photogear.sensifai.com/v1/api/jobs/fe566e35-189c-49fa-acec-a3568a21176a/ \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "id": "fe566e35-189c-49fa-acec-a3568a21176a",
  "dataset_id": "123e4567-e89b-12d3-a456-426614174000",
  "dataset_name": "Farm Survey 2024",
  "status": "running",
  "stage": "sfm",
  "progress": 45,
  "start_time": "2024-01-15 10:30",
  "duration": "0h 15m",
  "resolution_gsd": 2.5,
  "analysis_mode": "full"
}
```

### Job Status Values

| Status | Description |
|--------|-------------|
| `pending` | Job created, waiting to start |
| `queued` | Job is queued for processing |
| `running` | Job is actively processing |
| `completed` | Job finished successfully ✅ |
| `failed` | Job encountered an error ❌ |
| `cancelled` | Job was cancelled by user |

### Job Stages (Processing Pipeline)

| Stage | Description |
|-------|-------------|
| `pending` | Initial state |
| `queued` | Waiting in queue |
| `radiometric_calibration` | Color/light calibration |
| `sfm` | Structure from Motion (3D reconstruction) |
| `orthomosaic` | Generating orthomosaic map |
| `uploading` | Uploading results to storage |
| `publishing` | Finalizing and making available |
| `completed` | All done! |
| `failed` | Processing failed |

### List All Jobs

**Endpoint:** `GET /v1/api/jobs/`

```bash
curl -X GET "https://api-photogear.sensifai.com/v1/api/jobs/?status=running" \
  -H "Authorization: Bearer <token>"
```

**Query Parameters:**
- `status`: Filter by status (`pending`, `running`, `completed`, `failed`)
- `stage`: Filter by current stage
- `ordering`: Sort by field (`-created_at` for newest first)

---

## Get Results (Products)

After a job completes, retrieve the generated products (orthomosaic, DSM, 3D models, etc.)

### List Products by Job

**Endpoint:** `GET /v1/api/products/?job_id={job_id}`

```bash
curl -X GET "https://api-photogear.sensifai.com/v1/api/products/?job_id=fe566e35-189c-49fa-acec-a3568a21176a" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "count": 3,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "id": "abc12345-6789-0def-ghij-klmnopqrstuv",
      "dataset_id": "123e4567-e89b-12d3-a456-426614174000",
      "dataset_name": "Farm Survey 2024",
      "job_id": "fe566e35-189c-49fa-acec-a3568a21176a",
      "type": "orthomosaic",
      "type_display": "Orthomosaic",
      "category": "Raster",
      "uri": "products/abc123/orthomosaic.tif",
      "download_url": "https://s3.amazonaws.com/bucket/products/abc123/orthomosaic.tif?X-Amz-Signature=...",
      "download_expires_in_seconds": 3600,
      "resolution_cm": 2.5,
      "bands": ["red", "green", "blue", "nir"],
      "created_at": "2024-01-15T11:45:00Z"
    },
    {
      "id": "def67890-1234-5abc-defg-hijklmnopqrs",
      "type": "dsm",
      "type_display": "Digital Surface Model",
      "category": "Raster",
      "download_url": "https://s3.amazonaws.com/bucket/products/abc123/dsm.tif?...",
      "resolution_cm": 5.0,
      "created_at": "2024-01-15T11:46:00Z"
    },
    {
      "id": "ghi13579-2468-0xyz-abcd-efghijklmnop",
      "type": "pointcloud",
      "type_display": "Point Cloud",
      "category": "3D",
      "download_url": "https://s3.amazonaws.com/bucket/products/abc123/pointcloud.las?...",
      "created_at": "2024-01-15T11:47:00Z"
    }
  ],
  "summary": {
    "total_products": 3,
    "by_type": {
      "orthomosaic": 1,
      "dsm": 1,
      "pointcloud": 1
    },
    "by_category": {
      "Raster": 2,
      "3D": 1
    }
  }
}
```

### Product Types

| Type | Category | Description | Mode |
|------|----------|-------------|------|
| `orthomosaic` | Raster | Georeferenced 2D RGB map (GeoTIFF) | All |
| `dsm` | Raster | Digital Surface Model (elevation) | All |
| `dem` | Raster | Digital Elevation Model | All |
| `dtm` | Raster | Digital Terrain Model | All |
| `hillshade` | Raster | Shaded relief visualization | All |
| `pointcloud` | 3D | 3D point cloud (LAS/LAZ format) | All |
| `mesh` | 3D | Textured 3D mesh model | All |
| `ndvi` | Raster | Normalized Difference Vegetation Index | Full only |
| `ndre` | Raster | Normalized Difference Red Edge Index | Full only |
| `gndvi` | Raster | Green Normalized Difference Vegetation Index | Full only |
| `calibrated_reflectance` | Raster | Multi-band reflectance (G/R/RE/NIR) GeoTIFF | Full only |
| `orthomosaic_2x` | Raster | 2× downsampled orthomosaic (COG) | All |
| `orthomosaic_4x` | Raster | 4× downsampled orthomosaic (COG) | All |
| `orthomosaic_8x` | Raster | 8× downsampled orthomosaic (COG) | All |

> **Full mode products** (`ndvi`, `ndre`, `gndvi`, `calibrated_reflectance`) are only
> generated when `analysis_mode = "full"` and the dataset contains multispectral imagery.
> Multi-resolution products (`orthomosaic_2x`, `orthomosaic_4x`, `orthomosaic_8x`) are
> generated for all jobs regardless of mode.

### Download a Product

The `download_url` in the response is a presigned S3 URL valid for 1 hour:

```bash
# Download the orthomosaic
curl -o orthomosaic.tif "https://s3.amazonaws.com/bucket/products/abc123/orthomosaic.tif?X-Amz-Signature=..."
```

### Get Single Product Details

**Endpoint:** `GET /v1/api/products/{product_id}/`

```bash
curl -X GET "https://api-photogear.sensifai.com/v1/api/products/abc12345-6789-0def-ghij-klmnopqrstuv/" \
  -H "Authorization: Bearer <token>"
```

**Response includes additional metadata:**
```json
{
  "id": "abc12345-6789-0def-ghij-klmnopqrstuv",
  "type": "orthomosaic",
  "dataset": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Farm Survey 2024"
  },
  "job": {
    "id": "fe566e35-189c-49fa-acec-a3568a21176a",
    "status": "completed",
    "progress": 100
  },
  "resolution_cm": 2.5,
  "bands": ["red", "green", "blue", "nir"],
  "stats": {
    "min": 0,
    "max": 255,
    "mean": 127.5
  },
  "footprint": {
    "type": "Polygon",
    "coordinates": [[[...], [...], ...]]
  },
  "download_url": "https://s3.amazonaws.com/...",
  "download_expires_in_seconds": 3600,
  "created_at": "2024-01-15T11:45:00Z"
}
```

---

## Complete Workflow Diagram

### End-to-End API Workflow

```mermaid
flowchart TD
    subgraph Phase1["Phase 1: Authentication"]
        A[Client] -->|POST /accounts/register/| B[Create User & Organization]
        A -->|POST /accounts/login/| C[Get JWT Tokens]
        C --> D[Use Bearer Token for all requests]
    end

    Phase1 --> Phase2

    subgraph Phase2["Phase 2: File Upload"]
        direction TB
        E{Choose Upload Method}

        subgraph MethodA["Method A: Multipart Upload"]
            F[Step 1: Init Upload] -->|upload_id, s3_key, dataset_id| G[Step 2: Sign & Upload Each Chunk]
            G -->|presigned URLs + ETags| H[Step 3: Complete Upload]
            H --> I[ZIP auto-extracted]
        end

        subgraph MethodB["Method B: S3 URL Import"]
            J[POST file_url + dataset_name] --> K[Server downloads file in background]
            K --> L[Poll upload status until COMPLETED]
        end

        E -->|Large files| MethodA
        E -->|Files already in cloud| MethodB
    end

    Phase2 --> Phase3

    subgraph Phase3["Phase 3: Start Processing Job"]
        M["POST /api/jobs/start-job/\ndataset_id, resolution,\ncalibration, analysis_mode"] --> N[Job Created — status: pending]
        N --> O[AI Gateway Pipeline]
    end

    subgraph Pipeline["AI Processing Pipeline"]
        direction TB
        P1[radiometric_calibration] --> P2[sfm — 3D reconstruction]
        P2 --> P3[orthomosaic]
        P3 --> P4[uploading]
        P4 --> P5[publishing]
        P5 --> P6[completed ✓]
    end

    O --> Pipeline
    Pipeline --> Phase4

    subgraph Phase4["Phase 4: Monitor Progress"]
        Q[Poll job status every few seconds] -->|GET /api/jobs/job_id/| R["status: running\nstage: sfm\nprogress: 45%"]
        R -->|repeat until completed| Q
        Q --> S["Job Complete!\nstatus: done — progress: 100%"]
    end

    Phase4 --> Phase5

    subgraph Phase5["Phase 5: Get Results"]
        T[GET /api/products/?job_id=xxx] --> U["Products list:\northomosaic.tif, dsm.tif,\npointcloud.las + download URLs"]
        U --> V[Use download_url to download files — 1 hour validity]
    end
```

### Multipart Upload Flow (Detailed)

```mermaid
sequenceDiagram
    participant C as Client
    participant API as PhotoGear API
    participant S3 as AWS S3

    C->>API: POST /uploads/multipart/init/<br/>file_name, file_size, dataset_name
    API-->>C: upload_id, s3_key, dataset_id

    loop For each chunk
        C->>API: POST /uploads/multipart/sign-part/<br/>upload_id, s3_key, part_number
        API-->>C: presigned_url
        C->>S3: PUT chunk to presigned_url
        S3-->>C: ETag
    end

    C->>API: POST /uploads/multipart/complete/<br/>upload_id, s3_key, parts[]
    API-->>C: success — ZIP auto-extracted
```

### S3 URL Import Flow (Detailed)

```mermaid
sequenceDiagram
    participant C as Client
    participant API as PhotoGear API
    participant S3 as AWS S3

    C->>API: POST /uploads/upload/url/<br/>file_url, dataset_name
    API-->>C: upload record created — status: DOWNLOADING
    API->>S3: Download file in background (async)
    S3-->>API: File downloaded
    API->>API: Extract archive, process images

    loop Poll status
        C->>API: GET /uploads/datasets/stats/
        API-->>C: status: DOWNLOADING / COMPLETED / FAILED
    end
```

---

## API Reference Summary

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/accounts/register/` | Create new user account |
| POST | `/v1/accounts/login/` | Login and get JWT tokens |
| GET | `/v1/accounts/profile/` | Get current user profile |

### Upload Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/api/uploads/multipart/init/` | Step 1: Initialize multipart upload |
| POST | `/v1/api/uploads/multipart/sign-part/` | Step 2: Get presigned URL for chunk |
| POST | `/v1/api/uploads/multipart/complete/` | Step 3: Complete multipart upload |
| POST | `/v1/api/uploads/upload/url/` | Import from S3 presigned URL |
| GET | `/v1/api/uploads/list/` | List user's uploads |
| GET | `/v1/api/uploads/datasets/stats/` | Get dataset statistics |
| GET | `/v1/api/uploads/datasets/` | List all datasets |
| GET | `/v1/api/uploads/datasets/{id}/` | Get dataset details |

### Job Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/api/jobs/start-job/` | Start processing job |
| GET | `/v1/api/jobs/` | List all jobs |
| GET | `/v1/api/jobs/{job_id}/` | Get job details |
| DELETE | `/v1/api/jobs/{job_id}/delete/` | Delete a job |
| POST | `/v1/api/jobs/{job_id}/cancel/` | Cancel a running job |
| POST | `/v1/api/jobs/{job_id}/retry/` | Retry a failed job |

### Product Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/api/products/` | List all products (with filters) |
| GET | `/v1/api/products/?job_id={id}` | Get products for a job |
| GET | `/v1/api/products/?dataset_id={id}` | Get products for a dataset |
| GET | `/v1/api/products/{product_id}/` | Get product details + download URL |

### Export Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/api/uploads/export/dataset/{id}/` | Export dataset as ZIP |
| GET | `/v1/api/uploads/export/status/{job_id}/` | Check export job status |

---

## Error Handling

All endpoints return consistent error responses:

**400 Bad Request:**
```json
{
  "error": "Either 'dataset_name' or 'dataset_id' must be provided."
}
```

**401 Unauthorized:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**404 Not Found:**
```json
{
  "error": "Dataset Not Found"
}
```

**500 Internal Server Error:**
```json
{
  "error": "Internal Server Error"
}
```

---

## Interactive API Documentation

For live API testing, visit the Swagger UI:

```
https://api-photogear.sensifai.com/v1/api/docs/
```

Or the ReDoc documentation:

```
https://api-photogear.sensifai.com/v1/api/redoc/
```

---

## Changelog

### v0.6.0 — March 2026

- **S3 download reliability:** Rewrote presigned URL download to use `iter_content()` with temp file — fixes corrupt archive downloads.
- **Archive detection:** Magic-byte fallback (ZIP, GZIP, RAR) for files without extensions.
- **Dataset stats pagination:** `GET /v1/api/uploads/datasets/stats/` now supports `page` and `page_size` — response wrapped in `{ count, results, next, previous }`.
- **Field rename:** Dataset stats `dataset_status` → `status`.
- **Image count fix:** `total_files` now counts only IMAGE file types, not archive records.
- **New permission:** `IsAIServiceOrAuthenticated` on `POST /v1/api/jobs/start-job/` — AI service token or user auth accepted.
- **New status:** `DOWNLOADING` upload status seeded via migration `0008_add_downloading_status`.
- **URL validation:** `validate_file_url` uses `GET stream=True` instead of `HEAD` for S3 presigned URL compatibility.
- **Database engine:** Switched to `django.contrib.gis.db.backends.postgis`.

### v0.5.0 — March 2026

- Job API now exposes `started_at`/`completed_at` timestamps with accurate duration calculation.
- New `upload_status` callback from AI Gateway marks jobs as FAILED when product uploads fail.
- 6 new tests for timing and upload status handling.

### v0.4.0 — March 2026

- RBAC role-based access control, security hardening, integration and load tests (389 total).

### v0.3.0 — March 2026

- Health check endpoint, URL upload fix, job duration display, FMIS webhooks, `.env.example`.

### v0.2.0 — March 2026

- **New parameter:** `analysis_mode` on `POST /v1/api/jobs/start-job/` — optional, defaults to `"fast"`.
  - `"fast"` — RGB-only processing with doubled GSD for faster SFM reconstruction.
  - `"full"` — RGB + multispectral pipeline: reflectance conversion, band orthorectification, and vegetation indices.
- **New product types** (generated only in `full` mode with multispectral imagery):
  - `ndvi` — Normalized Difference Vegetation Index
  - `ndre` — Normalized Difference Red Edge Index
  - `gndvi` — Green Normalized Difference Vegetation Index
  - `calibrated_reflectance` — 4-band (G/R/RE/NIR) reflectance GeoTIFF
- **New product types** (generated for all jobs — multi-resolution output):
  - `orthomosaic_2x` — 2× downsampled orthomosaic (COG)
  - `orthomosaic_4x` — 4× downsampled orthomosaic (COG)
  - `orthomosaic_8x` — 8× downsampled orthomosaic (COG)
- **Job response** now includes `analysis_mode` field.
- **Migration required:** Run `0005_add_analysis_mode` on the database.

### v0.1.0 — March 2026

- Initial release: multipart upload, S3 URL import, job start/monitor/cancel/retry, product listing with presigned download URLs.
- Dynamic metadata extraction, configurable file extensions, dataset statistics.

---

## Support

- **API Schema:** `https://api-photogear.sensifai.com/v1/api/schema/` (OpenAPI 3.0 JSON)
- **Swagger UI:** `https://api-photogear.sensifai.com/v1/api/docs/`
- **ReDoc:** `https://api-photogear.sensifai.com/v1/api/redoc/`

---

*Last Updated: March 2026*
