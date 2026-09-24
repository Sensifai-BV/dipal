# API Updates Summary - Array Filters & Security Audit

## Overview
Updated all frontend APIs to support array-based filtering and verified organization-based security across all endpoints.

---

## Changes Made

### 1. Job Management API - Array Filters

**File**: `apps/jobs/api/views/job_management_views.py`

**Changes**:
- Updated `status` parameter to accept comma-separated values (e.g., `status=completed,failed`)
- Updated `stage` parameter to accept comma-separated values (e.g., `stage=sfm,mvs`)
- Modified filter logic to use `status__in` and `stage__in` for array filtering
- Enhanced parameter descriptions with examples

**Code Changes**:
```python
# Before
status_filter = request.GET.get('status')
if status_filter:
    queryset = queryset.filter(status=status_filter)

# After
status_filter = request.GET.get('status')
if status_filter:
    status_list = [s.strip() for s in status_filter.split(',')]
    queryset = queryset.filter(status__in=status_list)
```

**Usage Examples**:
```bash
# Single value (backward compatible)
GET /v1/api/jobs/?status=completed

# Multiple values (new)
GET /v1/api/jobs/?status=completed,failed
GET /v1/api/jobs/?stage=sfm,mvs
GET /v1/api/jobs/?status=completed,failed&stage=sfm
```

---

### 2. Dataset Management API - Array Filters + Status Filter

**File**: `apps/uploads/presentation/dataset_management_views.py`

**Changes**:
1. **Platform Filter**: Now accepts comma-separated values
2. **Status Filter**: NEW - filter datasets by processing status (PENDING, PROCESSING, COMPLETED, HAS_ERROR)
3. **Platform Description**: Added explanation of valid platform values
4. **Status Calculation**: Annotate queryset with status counts from images
5. **Status in Response**: Added `status` field to dataset responses
6. **Status Breakdown**: Added `status_breakdown` debug info in responses

**Code Changes**:
```python
# Platform filter - accepts arrays
platform = request.query_params.get('platform')
if platform:
    platform_list = [p.strip() for p in platform.split(',')]
    platform_query = Q()
    for p in platform_list:
        platform_query |= Q(platform__icontains=p)
    query = query.filter(platform_query)

# New status filter
status_filter = request.query_params.get('status')
if status_filter:
    status_list = [s.strip().upper() for s in status_filter.split(',')]
    # Filter in Python after annotation

# Annotate with status counts
query = query.annotate(
    image_count=Count('images'),
    total_size=Sum('images__file_size'),
    pending_count=Count('images', filter=Q(images__status__name='PENDING')),
    processing_count=Count('images', filter=Q(images__status__name='PROCESSING')),
    completed_count=Count('images', filter=Q(images__status__name='COMPLETED')),
    failed_count=Count('images', filter=Q(images__status__name='FAILED'))
)

# Calculate status
if dataset.failed_count > 0:
    dataset_status = 'HAS_ERROR'
elif dataset.processing_count > 0:
    dataset_status = 'PROCESSING'
elif dataset.image_count == dataset.completed_count and dataset.completed_count > 0:
    dataset_status = 'COMPLETED'
else:
    dataset_status = 'PENDING'
```

**New Response Format**:
```json
{
  "count": 50,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "id": "uuid",
      "name": "Dataset Name",
      "platform": "UAV",
      "status": "COMPLETED",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T11:45:00Z",
      "capture_start": "2024-01-15T09:00:00Z",
      "capture_end": "2024-01-15T10:00:00Z",
      "image_count": 425,
      "total_size_mb": 1250.5,
      "status_breakdown": {
        "pending": 0,
        "processing": 0,
        "completed": 425,
        "failed": 0
      }
    }
  ]
}
```

**Usage Examples**:
```bash
# Filter by platform (array)
GET /v1/api/uploads/datasets/?platform=UAV,Satellite

# Filter by status (array)
GET /v1/api/uploads/datasets/?status=COMPLETED,PROCESSING

# Combined filters
GET /v1/api/uploads/datasets/?platform=UAV&status=COMPLETED&page=1
```

---

### 3. Documentation Updates

**File**: `backend/docs/ENDPOINT_CLARIFICATION.md` (NEW)

**Content**:
- Explanation of duplicate job endpoints (Legacy vs New)
- Security comparison table
- Array filter syntax documentation
- Platform values documentation
- Status values documentation
- Recommendations for frontend and backend teams

**Key Points**:
- `/v1/api/jobs/list/` - Legacy endpoint for AI Gateway (NO AUTH, optional org_id)
- `/v1/api/jobs/` - New full-featured endpoint for frontend (AUTH REQUIRED)
- All new endpoints support array filters via comma-separated values
- All authenticated endpoints auto-filter by organization

---

## Security Audit Results

✅ **All authenticated endpoints properly filter by organization:**

| Endpoint | Authentication | Org Filtering |
|----------|----------------|---------------|
| `GET /v1/api/uploads/datasets/` | ✅ IsAuthenticated | ✅ `request.user.organization_id` |
| `GET /v1/api/uploads/datasets/{id}/` | ✅ IsAuthenticated | ✅ `request.user.organization_id` |
| `DELETE /v1/api/uploads/datasets/{id}/delete/` | ✅ IsAuthenticated | ✅ `request.user.organization_id` |
| `GET /v1/api/jobs/` | ✅ IsAuthenticated | ✅ `request.user.org_id` |
| `GET /v1/api/jobs/{id}/` | ✅ IsAuthenticated | ✅ `request.user.org_id` |
| `DELETE /v1/api/jobs/{id}/delete/` | ✅ IsAuthenticated | ✅ `request.user.org_id` |
| `GET /v1/api/products/` | ✅ IsAuthenticated | ✅ `request.user.org_id` (via dataset) |
| `GET /v1/api/products/{id}/` | ✅ IsAuthenticated | ✅ `request.user.org_id` (via dataset) |
| `GET /v1/api/jobs/{id}/products/` | ✅ IsAuthenticated | ✅ `request.user.org_id` (via dataset) |
| `GET /v1/api/uploads/datasets/{id}/products/` | ✅ IsAuthenticated | ✅ `request.user.organization_id` |

⚠️ **Security Concern:**
- `GET /v1/api/jobs/list/` - NO authentication, accepts optional `org_id` parameter
  - Used by AI Gateway
  - Returns ALL jobs if `org_id` not provided
  - Recent patch added org_id filtering but doesn't enforce it
  - **Recommendation**: Require API key or migrate to authenticated endpoint

---

## Filter Parameters Summary

### Jobs (`/v1/api/jobs/`)
- `status` (array): `pending`, `queued`, `processing`, `completed`, `failed`
- `stage` (array): `queued`, `sfm`, `mvs`, `publishing`
- `dataset_id` (UUID): Single dataset filter
- `progress_min` (int): 0-100
- `progress_max` (int): 0-100
- `created_after` (datetime): ISO 8601
- `created_before` (datetime): ISO 8601
- `search` (string): Dataset name or job ID
- `ordering` (string): `created_at`, `-created_at`, etc.

### Datasets (`/v1/api/uploads/datasets/`)
- `platform` (array): `UAV`, `Satellite`, `Aerial`, `Ground`, etc.
- `status` (array): `PENDING`, `PROCESSING`, `COMPLETED`, `HAS_ERROR`
- `search` (string): Dataset name
- `created_after` (datetime): ISO 8601
- `created_before` (datetime): ISO 8601
- `capture_start_after` (datetime): ISO 8601
- `capture_start_before` (datetime): ISO 8601
- `order_by` (string): `created_at`, `-created_at`, `name`, `-name`

### Products (`/v1/api/products/`)
- `type` (string): Product type (single value)
- `dataset_id` (UUID): Single dataset filter
- `created_after` (datetime): ISO 8601
- `created_before` (datetime): ISO 8601
- `order_by` (string): `created_at`, `-created_at`, etc.

---

## Array Filter Syntax

All array-based filters use **comma-separated values**:

```bash
# Single value (backward compatible)
?status=completed

# Multiple values
?status=completed,failed

# Multiple different filters
?status=completed,failed&stage=sfm,mvs

# URL-encoded version (recommended for production)
?status=completed%2Cfailed&stage=sfm%2Cmvs
```

**Implementation**:
```python
# Parse comma-separated values
filter_param = request.GET.get('param_name')
if filter_param:
    value_list = [v.strip() for v in filter_param.split(',')]
    queryset = queryset.filter(field__in=value_list)
```

---

## Response Format Changes

### Dataset List Response - Added Fields:
```json
{
  "status": "COMPLETED",  // NEW
  "status_breakdown": {   // NEW
    "pending": 0,
    "processing": 0,
    "completed": 425,
    "failed": 0
  }
}
```

### All List Responses - Consistent Structure:
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

---

## Breaking Changes

❌ **None** - All changes are backward compatible:
- Single-value filters still work (e.g., `?status=completed`)
- Array syntax is additive (e.g., `?status=completed,failed`)
- Existing clients continue to work without modifications

✅ **New Features**:
- Multi-select filtering for status, stage, and platform
- Dataset status filtering (previously unavailable)
- Status breakdown in dataset responses
- Better documentation

---

## Testing Recommendations

### 1. Test Array Filters
```bash
# Test job status filter with multiple values
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.example.com/v1/api/jobs/?status=completed,failed"

# Test dataset platform filter
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.example.com/v1/api/uploads/datasets/?platform=UAV,Satellite"

# Test dataset status filter
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.example.com/v1/api/uploads/datasets/?status=COMPLETED,PROCESSING"
```

### 2. Test Organization Security
```bash
# Verify datasets are filtered by org
curl -H "Authorization: Bearer $ORG1_TOKEN" \
  "https://api.example.com/v1/api/uploads/datasets/"

curl -H "Authorization: Bearer $ORG2_TOKEN" \
  "https://api.example.com/v1/api/uploads/datasets/"

# Results should be different for different organizations
```

### 3. Test Status Calculation
```bash
# Upload images to dataset, check status progression:
# 1. PENDING (before processing)
# 2. PROCESSING (during processing)
# 3. COMPLETED (after successful processing)
# 4. HAS_ERROR (if any image fails)
```

### 4. Verify Legacy Endpoint
```bash
# Without org_id (SECURITY ISSUE - returns all)
curl "https://api.example.com/v1/api/jobs/list/"

# With org_id (secure)
curl "https://api.example.com/v1/api/jobs/list/?org_id=123"
```

---

## Migration Guide for Frontend

### Before (Single Values):
```javascript
// Jobs - single status
const response = await fetch('/v1/api/jobs/?status=completed');

// Datasets - single platform
const response = await fetch('/v1/api/uploads/datasets/?platform=UAV');
```

### After (Array Support):
```javascript
// Jobs - multiple statuses
const statuses = ['completed', 'failed'];
const statusParam = statuses.join(',');
const response = await fetch(`/v1/api/jobs/?status=${statusParam}`);

// Datasets - multiple platforms
const platforms = ['UAV', 'Satellite'];
const platformParam = platforms.join(',');
const response = await fetch(`/v1/api/uploads/datasets/?platform=${platformParam}`);

// New: Filter by dataset status
const statuses = ['COMPLETED', 'PROCESSING'];
const statusParam = statuses.join(',');
const response = await fetch(`/v1/api/uploads/datasets/?status=${statusParam}`);
```

---

## Future Improvements

### Short Term:
1. Add rate limiting to legacy `/v1/api/jobs/list/` endpoint
2. Make `org_id` mandatory on legacy endpoint
3. Add API key authentication for microservices

### Medium Term:
1. Migrate AI Gateway to use authenticated `/v1/api/jobs/` endpoint
2. Deprecate `/v1/api/jobs/list/` endpoint
3. Add caching for expensive status calculations

### Long Term:
1. Consider materializing dataset status in database for performance
2. Implement GraphQL for more flexible filtering
3. Add full-text search with Elasticsearch
4. Add audit logging for all API access

---

## Files Modified

1. `apps/jobs/api/views/job_management_views.py` - Array filters for status/stage
2. `apps/uploads/presentation/dataset_management_views.py` - Array filters, status filter, status calculation
3. `backend/docs/ENDPOINT_CLARIFICATION.md` - NEW documentation file

**Lines Changed**: ~100 lines modified, 1 new file created

**No Breaking Changes**: All changes are backward compatible.
