# API Endpoint Clarification

## Job Endpoints - Why Two Different Endpoints?

There are currently TWO job listing endpoints with different purposes:

### 1. `/v1/api/jobs/list/` (Legacy - Processing Jobs tag)

**Purpose**: Used by the AI Gateway for internal communication
- **File**: `apps/jobs/api/views/views.py` (JobListView)
- **Authentication**: None (uses secret key at gateway level)
- **Authorization**: Accepts optional `org_id` query parameter
- **Tag**: "Processing Jobs"
- **Features**:
  - Minimal security (no authentication required)
  - Simple filtering (org_id, status, stage via query params)
  - Used by microservices to query job status
  - Returns basic job information
  
**Security Note**: This endpoint was recently patched to accept `org_id` parameter filtering, but does NOT require authentication. If `org_id` is not provided, it returns ALL jobs across all organizations.

**Recommendation**: 
- Consider requiring API key authentication
- Make `org_id` parameter mandatory
- Add rate limiting
- Eventually deprecate in favor of dedicated microservice-to-microservice communication

---

### 2. `/v1/api/jobs/` (New - Job Management tag)

**Purpose**: Full-featured job management for frontend applications
- **File**: `apps/jobs/api/views/job_management_views.py` (JobListView)
- **Authentication**: Required (IsAuthenticated)
- **Authorization**: Automatic (filters by request.user.org_id)
- **Tag**: "Job Management"
- **Features**:
  - Full authentication and authorization
  - Advanced filtering (status, stage, dataset_id, progress range, dates, search)
  - Array-based filters (accepts comma-separated values for status/stage)
  - Comprehensive pagination
  - Detailed job information with computed fields
  - Swagger UI documentation

**Filter Examples**:
```
# Single status
GET /v1/api/jobs/?status=completed

# Multiple statuses (comma-separated)
GET /v1/api/jobs/?status=completed,failed

# Multiple stages
GET /v1/api/jobs/?stage=sfm,mvs

# Combined filters
GET /v1/api/jobs/?status=completed,failed&dataset_id=123e4567-e89b-12d3-a456-426614174000&page=1&page_size=20
```

---

## Recommendation

**For Frontend Developers**: 
- Use `/v1/api/jobs/` (Job Management endpoints)
- These endpoints are secure, well-documented, and feature-rich

**For AI Gateway**: 
- Currently uses `/v1/api/jobs/list/`
- Should migrate to authenticated endpoint or dedicated microservice API
- Always include `org_id` parameter for security

**For Backend Team**:
- Consider deprecating `/v1/api/jobs/list/` once AI Gateway is updated
- OR add authentication requirements to the legacy endpoint
- OR keep it but make `org_id` mandatory and add rate limiting

---

## Filter Design - Array Support

All new endpoints support **array-based filtering** using comma-separated values:

### Jobs
- `status`: `pending`, `queued`, `processing`, `completed`, `failed`
- `stage`: `queued`, `sfm`, `mvs`, `publishing`

### Datasets
- `platform`: `UAV`, `Satellite`, `Aerial`, `Ground` (any custom value)
- `status`: `PENDING`, `PROCESSING`, `COMPLETED`, `HAS_ERROR`

### Products
- `type`: Single value for product type

**Syntax**: 
```
?status=completed,failed
?platform=UAV,Satellite
```

---

## Organization-Based Security

All authenticated endpoints automatically filter by organization:

| Endpoint | Security | Org Filtering |
|----------|----------|---------------|
| `/v1/api/uploads/datasets/` | ✅ IsAuthenticated | ✅ Automatic via request.user.organization_id |
| `/v1/api/uploads/datasets/{id}/` | ✅ IsAuthenticated | ✅ Automatic via request.user.organization_id |
| `/v1/api/uploads/datasets/{id}/delete/` | ✅ IsAuthenticated | ✅ Automatic via request.user.organization_id |
| `/v1/api/jobs/` | ✅ IsAuthenticated | ✅ Automatic via request.user.org_id |
| `/v1/api/jobs/{id}/` | ✅ IsAuthenticated | ✅ Automatic via request.user.org_id |
| `/v1/api/jobs/{id}/delete/` | ✅ IsAuthenticated | ✅ Automatic via request.user.org_id |
| `/v1/api/products/` | ✅ IsAuthenticated | ✅ Automatic via request.user.org_id |
| `/v1/api/products/{id}/` | ✅ IsAuthenticated | ✅ Automatic via request.user.org_id |
| `/v1/api/jobs/{id}/products/` | ✅ IsAuthenticated | ✅ Automatic via request.user.org_id |
| `/v1/api/uploads/datasets/{id}/products/` | ✅ IsAuthenticated | ✅ Automatic via request.user.organization_id |
| **`/v1/api/jobs/list/` (Legacy)** | ❌ No Auth | ⚠️ Optional via ?org_id= |

**CRITICAL**: The legacy endpoint `/v1/api/jobs/list/` is the only endpoint without automatic org filtering. Always pass `org_id` when using it.

---

## Platform Values

Common platform values (not enforced, can be any string):
- `UAV` - Unmanned Aerial Vehicle (drone)
- `Satellite` - Satellite imagery
- `Aerial` - Manned aircraft
- `Ground` - Ground-level photography
- `Terrestrial` - Similar to ground
- Custom values are allowed

---

## Status Values

### Dataset Status (computed from images)
- `PENDING` - No images uploaded yet or all pending
- `PROCESSING` - Some images are being processed
- `COMPLETED` - All images successfully processed
- `HAS_ERROR` - At least one image failed

### Job Status
- `pending` - Job created but not started
- `queued` - Job queued for processing
- `processing` - Currently being processed
- `completed` - Successfully completed
- `failed` - Failed with errors

### Job Stage
- `queued` - Waiting in queue
- `sfm` - Structure from Motion processing
- `mvs` - Multi-View Stereo processing
- `publishing` - Publishing results to S3

---

## API Design Consistency

All paginated list endpoints return:
```json
{
  "count": 100,
  "page": 1,
  "page_size": 20,
  "next": "?page=2&page_size=20",
  "previous": null,
  "results": [...],
  "summary": {
    "total_items": 100,
    "page_info": "Showing 1-20 of 100"
  }
}
```

All detail endpoints return single objects with full information.

All delete endpoints return:
```json
{
  "message": "Resource deleted successfully",
  "deleted_<resource>_id": "uuid"
}
```
