# Changelog — backend (Django)

All notable changes to the `backend` project related to the image-analysis-core integration.

---

## [Unreleased] — master branch (unstaged changes)

### Added

#### New Product Types (`products/models.py`)
- **5 new product type choices** for radiometric calibration outputs:
  - `ndvi` — NDVI Map
  - `ndre` — NDRE Map
  - `gndvi` — GNDVI Map
  - `calibrated_reflectance` — Calibrated Reflectance
  - `band_manifest` — Band Classification Manifest
- New **Calibration** product category in `get_category()` for all 5 new types
- These are first-class `Product` rows (superseding the legacy `ndvi_url` field on `Processing` model)

#### Environment Configuration (`.env.example`)
- Added `AI_GATEWAY_URL` — URL for the image-analysis-core API gateway
- Added `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` settings
- Added `WEBHOOK_SIGNING_SECRET` for secure service-to-service callbacks
- Added `CORS_ALLOWED_ORIGINS` configuration

### Changed

- **Renamed** `AWS_S3_AI_DEV_BUCKET` → `AWS_S3_AI_BUCKET` across:
  - `.env.example`
  - `config/settings.py`
- **Renamed** `AI_SERVICE_SECRET_KEY` → `AI_GATEWAY_SECRET_KEY` in `apps/uploads/permissions.py`
- **S3 presigned URL generation** (`apps/jobs/infra/services/tasks/tasks.py`):
  - Added bucket fallback logic
  - Switched to `s3v4` signature version
  - Skip empty keys instead of generating invalid URLs
  - Improved error logging for failed presigned URL generation
- **S3Service** (`apps/uploads/domain/services.py`): removed `kms_key_id` from constructor

### Product Upload Flow (Presigned URLs)

The existing `ProductListView` and `ProductDetailView` already generate presigned URLs for **all** product types via the `Product.file` field and S3 storage backend. The 5 new product types automatically get presigned URL support without any additional code:

1. API Gateway uploads `band_manifest.json` as a `Product(type='band_manifest')` during calibration callback
2. Future vegetation index products will be uploaded as `Product(type='ndvi')`, etc. after orthomosaic generation
3. Frontend fetches product list → each product's `file` URL is already a presigned S3 URL

### Files Changed

| File | Changes |
|------|---------|
| `.env.example` | Renamed bucket, added gateway URL, Celery, CORS |
| `config/settings.py` | Renamed `AWS_S3_AI_DEV_BUCKET` → `AWS_S3_AI_BUCKET` |
| `products/models.py` | 5 new product types + Calibration category |
| `apps/uploads/permissions.py` | Renamed auth token setting |
| `apps/uploads/domain/services.py` | Removed `kms_key_id` |
| `apps/jobs/infra/services/tasks/tasks.py` | Hardened presigned URL generation |
