# Changelog — image-analysis-core

All notable changes to the `image-analysis-core` project are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions.

---

## [v0.10.11] — 2026-05-07

### Fixed

- **`stereo_fusion` near-empty point cloud** — `StereoFusion.max_depth_error` raised
  from `0.01` (1 %) to `0.05` (5 %) so depth maps survive the geo-registration
  residual (~10 % at 10 m AGL).
- **`model_aligner` in-place overwrite** — output now written to staging dir
  `sparse/0_aligned`; only renamed to `sparse/0` on success.  On failure `sparse/0`
  is left completely untouched.
- **No recovery path after bad alignment** — `sparse/0_original` backup created
  before every `model_aligner` run.
- **Silent bad alignment** — `model_aligner` RMSE and scale factor are now extracted
  from stdout and logged with warnings if out of expected range.
- **GLOMAP camera outlier drift** — cameras whose post-alignment position deviates
  from GPS by more than `geo_registration_outlier_filter_m` (default 10 m) are
  deregistered from the sparse model before dense reconstruction.

---

## [Unreleased] — feat/sqs-efs-ndvi branch

### Added

#### Spectral Band Detection Module (`shared/band_detection/`)
- **Auto-detect spectral bands** from any drone image set using a 3-tier priority chain:
  1. XMP BandName metadata (DJI / MicaSense — confidence 0.95)
  2. Filename suffix patterns: DJI (`_D`, `_W`, `_MS_G`, `_MS_R`, `_MS_RE`, `_MS_NIR`) and generic (`_GRE`, `_NIR`, `_RED`, `_REG`) — confidence 0.80
  3. Image channel count heuristic (RGB vs single-channel) — confidence 0.50
- `scan_dataset()` — scan a flat directory and produce a `DatasetBandManifest`
- `organize_by_band()` — physically reorganise images into `rgb/`, `nir/`, `red/`, `red_edge/`, `green/`, etc. subfolders and write `metadata/band_manifest.json`
- Lightweight XMP reader (`metadata_reader.py`) — raw byte scanning + `xml.etree` + regex fallback, no `libxmp` dependency
- Tested on 3 real datasets:
  - DJI M3M (595 images, 5 bands) — 1.82s, 3.1ms/image
  - Parrot Sequoia (1217 images, 5 bands) — 3.43s, 2.8ms/image
  - DJI Phantom 4 Pro RGB (425 images, 1 band) — 1.35s, 3.2ms/image
- Drone manufacturer detection: DJI, MicaSense, Parrot (from EXIF Make/Model + camera heuristics)

#### Shared Storage Abstraction (`infrastructure/storage/shared_storage/`)
- `SharedStorageBase` abstract base class with `store()`, `retrieve()`, `exists()`, `list_files()`, `delete()`, `get_path()`
- `LocalSharedStorage` — local Docker volume mode (`/shared-data/datasets/`)
- `EFSSharedStorage` — AWS EFS mode (same interface, configurable mount point)
- `SharedStorageFactory` — selects driver via `SHARED_STORAGE_MODE` env var (`local` | `efs`)
- `TempStorageSettings` — Pydantic settings for shared/temp storage paths

#### Calibration Service Rewrite (`services/radiometric_calibration/`)
- **Base calibrator** (`base_calibrator.py`) — shared logic for calibration parameter extraction, vignette correction, lens distortion correction
- **MicaSense calibrator** (`micasense_calibration.py`) — dedicated calibrator for MicaSense RedEdge / Altum sensors
- **Calibrator factory** rewritten with auto-detection from `DatasetBandManifest`
- **Calibration endpoint** fully rewritten:
  - Integrates band detection at the start of every calibration job
  - Organises images into band folders before processing
  - Uploads `band_manifest.json` as a job product
  - Multi-band calibration applies radiometric correction per spectral band
  - RGB-only datasets get a passthrough copy (no calibration needed)
  - **Vegetation index generation removed** (correctly deferred to post-orthomosaic stage)

#### Environment & Settings
- Added port variables (`API_GATEWAY_PORT`, `CALIBRATION_SERVICE_PORT`, `SFM_SERVICE_PORT`, `ORTHOMOSAIC_SERVICE_PORT`) to `.env.example`
- Added shared storage settings (`SHARED_STORAGE_MODE`, `SHARED_STORAGE_BASE_PATH`, `EFS_MOUNT_POINT`, etc.) to `.env.example`
- Added `TempStorageSettings` import in calibration service settings

#### Real-World Test Suite
- `tests/test_band_detection_real.py` — end-to-end test against 3 live drone datasets with assertions and performance benchmarks

### Changed

- **Renamed** `ai_dev_bucket` → `ai_bucket` across all settings files (`s3_settings.py`, calibration `settings.py`) and `.env` / `.env.example` (`AWS_S3_AI_BUCKET`)
- **API Gateway `jobs.py`** — calibration callback handler now uploads only `band_manifest.json` (no vegetation indices)
- **SFM service** — `colmap_service.py` `_get_image_path()` now prefers `rgb/` subfolder for band-organised datasets; `sfm_endpoint.py` checks for `rgb/` in cached results
- **Calibration interfaces** (`interfaces.py`) rewritten with updated method signatures for band-aware calibration
- **Mavic M3M calibrator** rewritten to extend new `BaseDroneCalibrator`
- **Calibrator factory** rewritten to use manifest-based auto-detection instead of hardcoded manufacturer checks
- **All service settings** updated to use full URL patterns (`http://host:port`) instead of separate host/port fields
- **Redis settings** consolidated with `BACKGROUND_TASK_USE_REDIS` flag for in-memory vs Redis job state
- **S3 uploader** updated for new bucket naming

### Fixed

- Band classifier crash on empty-string `CentralWavelength` or `SensorIndex` metadata values (Parrot Sequoia)
- DJI M3M visible images (`_D.JPG`) now correctly classified as RGB via filename pattern (previously fell through to low-confidence channel heuristic)

### Architecture Decisions

- **Vegetation indices (NDVI, NDRE, GNDVI) are NOT generated during calibration** — they require the orthomosaic as input and will be computed in a dedicated post-orthomosaic stage
- **Band detection runs at the start of every calibration job** regardless of manufacturer — ensures consistent folder structure for downstream SFM and orthomosaic services
- **EFS requires no Docker-compose changes** — mounted via ECS task definition, same filesystem path for all containers
- **No new packages required** for EFS or shared storage — uses `pathlib` (stdlib) and existing `boto3`

---

### Files Changed

#### New Files
| File | Purpose |
|------|---------|
| `shared/band_detection/__init__.py` | Public API for band detection module |
| `shared/band_detection/models.py` | Pydantic models (BandType, ImageBandInfo, DatasetBandManifest) |
| `shared/band_detection/metadata_reader.py` | XMP/EXIF metadata extraction (no libxmp) |
| `shared/band_detection/band_classifier.py` | Image classification engine (XMP → filename → channel) |
| `shared/band_detection/detector.py` | Dataset-level scanning (scan_dataset) |
| `shared/band_detection/organizer.py` | Folder reorganisation (organize_by_band) |
| `infrastructure/storage/shared_storage/__init__.py` | Shared storage exports |
| `infrastructure/storage/shared_storage/settings.py` | TempStorageSettings pydantic model |
| `infrastructure/storage/shared_storage/base.py` | SharedStorageBase ABC |
| `infrastructure/storage/shared_storage/local_storage.py` | Local Docker volume driver |
| `infrastructure/storage/shared_storage/efs_storage.py` | AWS EFS driver |
| `infrastructure/storage/shared_storage/factory.py` | SharedStorageFactory |
| `services/radiometric_calibration/app/core/services/base_calibrator.py` | BaseDroneCalibrator with shared calibration logic |
| `services/radiometric_calibration/app/core/services/micasense_calibration.py` | MicaSense-specific calibrator |
| `tests/test_band_detection_real.py` | Real-world band detection tests |

#### Modified Files
| File | Changes |
|------|---------|
| `.env.example` | Added port vars, shared storage config, renamed bucket |
| `api_gateway/app/api/settings.py` | Full URL patterns for service addresses |
| `api_gateway/app/api/v1/endpoints/jobs.py` | Calibration handler: band_manifest only |
| `infrastructure/redis/settings.py` | Added BACKGROUND_TASK_USE_REDIS flag |
| `infrastructure/storage/s3_settings.py` | Renamed ai_dev_bucket → ai_bucket |
| `infrastructure/storage/s3_uploader.py` | Updated for new bucket naming |
| `services/radiometric_calibration/app/api/settings.py` | Full URL patterns |
| `services/radiometric_calibration/app/api/v1/endpoints/calibration_endpoint.py` | Full rewrite with band detection |
| `services/radiometric_calibration/app/core/__init__.py` | Updated exports |
| `services/radiometric_calibration/app/core/services/factory.py` | Manifest-based factory |
| `services/radiometric_calibration/app/core/services/interfaces.py` | Updated method signatures |
| `services/radiometric_calibration/app/core/services/mavic_m3m_calibration.py` | Extends BaseDroneCalibrator |
| `services/radiometric_calibration/app/core/settings.py` | Added TempStorageSettings, S3Settings |
| `services/sfm/app/api/settings.py` | Full URL patterns |
| `services/sfm/app/api/v1/endpoints/sfm_endpoint.py` | rgb/ folder check |
| `services/sfm/app/core/services/colmap_service.py` | Prefers rgb/ subfolder |
| `services/sfm/app/core/settings.py` | Full URL patterns |
| `services/orthomosaic_generation/app/api/settings.py` | Full URL patterns |
| `services/orthomosaic_generation/app/core/settings.py` | Full URL patterns |
