# PhotoGear Backend API Specification

## Overview
This document defines the REST API for the PhotoGear backend core service (be-core). The backend handles authentication, data management, job orchestration, and serves as the main gateway for the platform.

## Base URL
```
https://api.photogear.com/v1
```

## Authentication
All endpoints require JWT authentication via the `Authorization: Bearer <token>` header, obtained through OIDC flow (Cognito/Keycloak).

---

## Authentication & User Management

### POST /v1/auth/login
**Description**: Local authentication (if not using OIDC)
**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```
**Response**:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### GET /v1/me
**Description**: Get current user profile
**Response**:
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "name": "John Doe",
  "org_id": "org_456",
  "roles": ["viewer", "operator"]
}
```

---

## Organization Management

### GET /v1/orgs
**Description**: List organizations for current user
**Response**:
```json
{
  "organizations": [
    {
      "id": "org_456",
      "name": "AgriTech Solutions",
      "created_at": "2025-01-15T10:00:00Z"
    }
  ]
}
```

### POST /v1/orgs
**Description**: Create new organization (admin only)
**Request Body**:
```json
{
  "name": "New AgriTech Corp",
  "description": "Agricultural technology company"
}
```
**Response**:
```json
{
  "id": "org_789",
  "name": "New AgriTech Corp",
  "description": "Agricultural technology company",
  "created_at": "2025-09-02T14:30:00Z"
}
```

---

## User & Role Management

### POST /v1/users
**Description**: Create new user (admin only)
**Request Body**:
```json
{
  "email": "newuser@example.com",
  "name": "Jane Smith",
  "org_id": "org_456"
}
```
**Response**:
```json
{
  "id": "user_789",
  "email": "newuser@example.com",
  "name": "Jane Smith",
  "org_id": "org_456",
  "created_at": "2025-09-02T14:30:00Z"
}
```

### POST /v1/roles
**Description**: Create role within organization
**Request Body**:
```json
{
  "name": "field_operator",
  "org_id": "org_456",
  "permissions": ["upload_data", "view_products"]
}
```

### POST /v1/users/{id}/roles
**Description**: Assign role to user
**Request Body**:
```json
{
  "role_id": "role_123"
}
```

---

## Dataset Management

### POST /v1/datasets
**Description**: Create new dataset
**Request Body**:
```json
{
  "name": "Field-A Summer 2025",
  "crs": "EPSG:32639",
  "capture_start": "2025-08-29T09:00:00Z",
  "capture_end": "2025-08-29T11:30:00Z",
  "platform": "DJI Mavic 3M",
  "notes": "Morning flight, clear conditions"
}
```
**Response**:
```json
{
  "id": "ds_101",
  "name": "Field-A Summer 2025",
  "crs": "EPSG:32639",
  "capture_start": "2025-08-29T09:00:00Z",
  "capture_end": "2025-08-29T11:30:00Z",
  "platform": "DJI Mavic 3M",
  "notes": "Morning flight, clear conditions",
  "org_id": "org_456",
  "created_at": "2025-09-02T14:30:00Z"
}
```

### GET /v1/datasets
**Description**: List datasets for organization
**Query Parameters**:
- `limit` (optional): Number of results (default: 50)
- `offset` (optional): Pagination offset (default: 0)
- `platform` (optional): Filter by platform
**Response**:
```json
{
  "datasets": [
    {
      "id": "ds_101",
      "name": "Field-A Summer 2025",
      "platform": "DJI Mavic 3M",
      "capture_start": "2025-08-29T09:00:00Z",
      "created_at": "2025-09-02T14:30:00Z"
    }
  ],
  "total": 1,
  "has_more": false
}
```

### GET /v1/datasets/{id}
**Description**: Get dataset details
**Response**:
```json
{
  "id": "ds_101",
  "name": "Field-A Summer 2025",
  "crs": "EPSG:32639",
  "capture_start": "2025-08-29T09:00:00Z",
  "capture_end": "2025-08-29T11:30:00Z",
  "platform": "DJI Mavic 3M",
  "bbox": {
    "type": "Polygon",
    "coordinates": [[[...], [...], [...], [...]]]
  },
  "image_count": 245,
  "total_size_mb": 2840,
  "notes": "Morning flight, clear conditions"
}
```

---

## Image Upload Management

### POST /v1/datasets/{id}/images/upload-url
**Description**: Get presigned URLs for multipart upload
**Request Body**:
```json
{
  "files": [
    {
      "filename": "IMG_001.JPG",
      "size": 12456789,
      "checksum": "sha256:abc123...",
      "parts": 2
    }
  ]
}
```
**Response**:
```json
{
  "upload_id": "upload_456",
  "files": [
    {
      "filename": "IMG_001.JPG",
      "file_id": "file_789",
      "upload_urls": [
        {
          "part_number": 1,
          "upload_url": "https://s3.amazonaws.com/...",
          "expires_at": "2025-09-02T15:30:00Z"
        },
        {
          "part_number": 2,
          "upload_url": "https://s3.amazonaws.com/...",
          "expires_at": "2025-09-02T15:30:00Z"
        }
      ]
    }
  ]
}
```

### POST /v1/datasets/{id}/images/complete
**Description**: Complete multipart upload and commit manifest
**Request Body**:
```json
{
  "upload_id": "upload_456",
  "files": [
    {
      "file_id": "file_789",
      "etags": [
        {"part_number": 1, "etag": "etag1"},
        {"part_number": 2, "etag": "etag2"}
      ],
      "exif": {...},
      "imu": {...}
    }
  ]
}
```
**Response**:
```json
{
  "upload_id": "upload_456",
  "status": "completed",
  "images": [
    {
      "id": "img_123",
      "filename": "IMG_001.JPG",
      "uri": "s3://bucket/raw/ds_101/IMG_001.JPG",
      "band": "RGB",
      "width": 4000,
      "height": 3000,
      "gsd": 2.5
    }
  ]
}
```

---

## Calibration Management

### POST /v1/datasets/{id}/calibration
**Description**: Upload calibration data for dataset
**Request Body**:
```json
{
  "panel_type": "MicaSense v2",
  "coefficients": {
    "R": 0.98,
    "G": 1.01,
    "B": 1.00,
    "NIR": 1.03
  },
  "illumination": {
    "lux": 55000,
    "sun_elev_deg": 48
  },
  "captured_at": "2025-08-29T10:10:00Z",
  "notes": "cloudless"
}
```
**Response**:
```json
{
  "calibration_id": "cal_123",
  "qc": {
    "panel_error_pct": 2.1,
    "validation_status": "passed"
  },
  "created_at": "2025-09-02T14:30:00Z"
}
```

### GET /v1/datasets/{id}/calibrations
**Description**: List calibrations for dataset
**Response**:
```json
{
  "calibrations": [
    {
      "id": "cal_123",
      "panel_type": "MicaSense v2",
      "performed_at": "2025-08-29T10:10:00Z",
      "operator": "field_tech_1",
      "qc": {
        "panel_error_pct": 2.1,
        "validation_status": "passed"
      }
    }
  ]
}
```

---

## Job Management

### POST /v1/datasets/{id}/jobs/preprocess
**Description**: Start preprocessing job (includes calibration)
**Request Body**:
```json
{
  "calibration_id": "cal_123",
  "validate_overlap": true,
  "generate_qc_report": true
}
```
**Response**:
```json
{
  "job_id": "job_preproc_001"
}
```

### POST /v1/datasets/{id}/jobs/orthomosaic
**Description**: Start orthomosaic generation job
**Request Body**:
```json
{
  "resolution_cm": 5,
  "bands": ["RGB", "NIR"],
  "calibration_id": "cal_123",
  "crs": "EPSG:32639",
  "surface_type": "DSM",
  "quality": "standard",
  "notes": "Field-A, afternoon flight"
}
```
**Response**:
```json
{
  "job_id": "job_ortho_001"
}
```

### POST /v1/datasets/{id}/jobs/recon3d
**Description**: Start 3D reconstruction job
**Request Body**:
```json
{
  "quality": "high",
  "densify": true,
  "generate_texture": true,
  "mesh_resolution": "medium"
}
```
**Response**:
```json
{
  "job_id": "job_recon3d_001"
}
```

### GET /v1/jobs/{job_id}
**Description**: Get job status and details
**Response**:
```json
{
  "id": "job_ortho_001",
  "type": "orthomosaic",
  "status": "running",
  "dataset_id": "ds_101",
  "started_at": "2025-09-02T14:35:00Z",
  "stages": [
    {
      "name": "prep",
      "state": "completed",
      "logs_uri": "s3://logs/job_ortho_001/prep.log"
    },
    {
      "name": "sfm",
      "state": "running",
      "progress_pct": 65
    }
  ],
  "metrics": {
    "rmse_px": 1.2,
    "coverage_pct": 98.5
  },
  "artifacts": [
    {
      "type": "sparse_pointcloud",
      "uri": "s3://staging/job_ortho_001/sparse.ply"
    }
  ]
}
```

### POST /v1/jobs/{job_id}/cancel
**Description**: Cancel running job
**Response**:
```json
{
  "job_id": "job_ortho_001",
  "status": "canceled",
  "canceled_at": "2025-09-02T15:00:00Z"
}
```

### GET /v1/jobs
**Description**: List jobs with filters
**Query Parameters**:
- `dataset_id` (optional): Filter by dataset
- `type` (optional): Filter by job type
- `status` (optional): Filter by status
- `limit` (optional): Number of results
**Response**:
```json
{
  "jobs": [
    {
      "id": "job_ortho_001",
      "type": "orthomosaic",
      "status": "running",
      "dataset_id": "ds_101",
      "started_at": "2025-09-02T14:35:00Z"
    }
  ],
  "total": 1
}
```

---

## Product Management

### GET /v1/datasets/{id}/products
**Description**: List products for dataset
**Query Parameters**:
- `type` (optional): Filter by product type (orthomosaic, dem, dsm, pointcloud, mesh, preview)
**Response**:
```json
{
  "products": [
    {
      "id": "prod_567",
      "type": "orthomosaic",
      "job_id": "job_ortho_001",
      "resolution_cm": 5,
      "bands": ["R", "G", "B", "NIR"],
      "footprint": {
        "type": "Polygon",
        "coordinates": [[[...], [...], [...], [...]]]
      },
      "created_at": "2025-09-02T16:00:00Z"
    }
  ]
}
```

### GET /v1/products/{product_id}
**Description**: Get product metadata and download URL
**Response**:
```json
{
  "id": "prod_567",
  "type": "orthomosaic",
  "dataset_id": "ds_101",
  "job_id": "job_ortho_001",
  "uri": "s3://products/ds_101/orthomosaic_5cm.tif",
  "footprint": {
    "type": "Polygon",
    "coordinates": [[[...], [...], [...], [...]]]
  },
  "resolution_cm": 5,
  "bands": ["R", "G", "B", "NIR"],
  "file_size_mb": 245,
  "stats": {
    "rmse_px": 1.2,
    "coverage_pct": 98.5
  },
  "download_url": "https://signed.example.com/download?token=...",
  "download_expires_at": "2025-09-02T18:00:00Z",
  "created_at": "2025-09-02T16:00:00Z"
}
```

---

## Tile Serving

### GET /tiles/{z}/{x}/{y}.png
**Description**: Get map tile (proxied from TiTiler)
**Query Parameters**:
- `product_id`: Product ID for COG
- `bands` (optional): Band selection (e.g., "1,2,3")
- `colormap` (optional): Color mapping
**Response**: PNG image tile

### GET /tiles/{product_id}/tilejson.json
**Description**: Get TileJSON metadata for product
**Response**:
```json
{
  "tilejson": "2.2.0",
  "name": "Orthomosaic Field-A",
  "tiles": [
    "https://api.photogear.com/tiles/{z}/{x}/{y}.png?product_id=prod_567"
  ],
  "minzoom": 0,
  "maxzoom": 18,
  "bounds": [35.0, 31.0, 36.0, 32.0]
}
```

---

## Webhook Management

### POST /v1/webhooks
**Description**: Register webhook endpoint
**Request Body**:
```json
{
  "url": "https://partner.example.com/webhook",
  "events": ["product.published", "job.completed"],
  "secret": "webhook_secret_key"
}
```
**Response**:
```json
{
  "id": "webhook_123",
  "url": "https://partner.example.com/webhook",
  "events": ["product.published", "job.completed"],
  "created_at": "2025-09-02T14:30:00Z"
}
```

### GET /v1/webhooks
**Description**: List registered webhooks
**Response**:
```json
{
  "webhooks": [
    {
      "id": "webhook_123",
      "url": "https://partner.example.com/webhook",
      "events": ["product.published", "job.completed"],
      "created_at": "2025-09-02T14:30:00Z"
    }
  ]
}
```

### DELETE /v1/webhooks/{id}
**Description**: Delete webhook
**Response**: 204 No Content

---

## FMIS Integration

### POST /v1/export/fmis
**Description**: Export products to FMIS
**Request Body**:
```json
{
  "fmis_provider": "john_deere",
  "dataset_id": "ds_101",
  "product_ids": ["prod_567"],
  "field_mapping": {
    "external_field_id": "field_12345"
  }
}
```
**Response**:
```json
{
  "export_id": "export_789",
  "status": "queued",
  "products_count": 1
}
```

---

## Audit & Monitoring

### GET /v1/audit
**Description**: Get audit logs (admin only)
**Query Parameters**:
- `org_id` (optional): Filter by organization
- `actor_id` (optional): Filter by user
- `action` (optional): Filter by action type
- `resource` (optional): Filter by resource type
- `start_date` (optional): Start date filter
- `end_date` (optional): End date filter
**Response**:
```json
{
  "audit_logs": [
    {
      "id": "audit_001",
      "org_id": "org_456",
      "actor_id": "user_123",
      "action": "dataset.create",
      "resource": "dataset",
      "resource_id": "ds_101",
      "timestamp": "2025-09-02T14:30:00Z",
      "payload": {...}
    }
  ],
  "total": 1
}
```

---

## Error Responses

All endpoints return standard HTTP status codes and error responses:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "resolution_cm",
      "reason": "must be between 1 and 100"
    }
  },
  "request_id": "req_123456"
}
```

**Common Error Codes**:
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (invalid/expired token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (resource already exists)
- `422` - Unprocessable Entity (business logic error)
- `429` - Too Many Requests (rate limiting)
- `500` - Internal Server Error
