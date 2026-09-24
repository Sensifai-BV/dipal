# Multispectral Analysis Pipeline

> **Version:** 0.6.0 | **Status:** Production  
> **Trigger:** `analysis_mode = "full"` on a multispectral dataset

---

## Overview

The multispectral analysis pipeline extends the base photogrammetry workflow
with spectral band processing. When enabled, it converts raw digital numbers
to physical reflectance values, orthorectifies each spectral band onto a
common geographic grid, and computes vegetation indices (NDVI, NDRE, GNDVI).

All outputs are georeferenced GeoTIFFs compatible with standard GIS tools.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                       analysis_mode = "full"                          │
│                       is_multispectral = true                         │
└────────────────────────────────────────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌──────────────────┐  ┌─────────────────┐  ┌──────────────────────────┐
│   CALIBRATION    │  │      SFM        │  │      ORTHOMOSAIC         │
│   (Port 8001)    │  │   (Port 8002)   │  │     (Port 8003)          │
│                  │  │                 │  │                          │
│ DN → Reflectance │  │ Fast-mode GSD   │  │ 1. Base RGB pipeline     │
│ Per-band float32 │  │ doubling (×2)   │  │ 2. Band orthorectify     │
│ TIF output       │  │ COLMAP sparse   │  │ 3. Band stacking         │
│                  │  │ model           │  │ 4. Vegetation indices    │
│ Output:          │  │                 │  │ 5. COG conversion        │
│  has_reflectance │  │ Output:         │  │                          │
│  band_manifest   │  │  cameras.bin    │  │ Output:                  │
│  calibration_path│  │  images.bin     │  │  ndvi.tif, ndre.tif      │
│                  │  │  run_path       │  │  gndvi.tif               │
└──────────────────┘  └─────────────────┘  │  multiband_reflectance   │
                                           │  per-band ortho TIFs     │
                                           └──────────────────────────┘
```

---

## Pipeline Stages

### Stage 1: Radiometric Calibration

**Service:** `radiometric_calibration` (port 8001)  
**Module:** `calibration_endpoint._calibrate_multispectral_images()`

**What it does:**
- Iterates over spectral bands: Green, Red, Red Edge, NIR, Blue
- For each image: loads via drone processor → geometric corrections → DN-to-reflectance conversion
- Saves as **float32 GeoTIFF** in `calibrated_images/<band>/` directory
- Files named `<stem>_reflectance.tif` (values in 0–1 range)

**Callback payload additions:**
| Field | Type | Description |
|-------|------|-------------|
| `has_reflectance` | `bool` | `true` if reflectance conversion succeeded |
| `reflectance_counts` | `dict` | Per-band count of converted images |
| `calibration_path` | `str` | Path to calibrated image root directory |
| `band_manifest` | `dict` | Band detection manifest from dataset |
| `is_multispectral` | `bool` | Whether dataset has multiple spectral bands |

### Stage 2: Structure from Motion (SFM)

**Service:** `sfm` (port 8002)  
**Module:** `sfm_endpoint.run_sfm_task()`

**Fast-mode GSD doubling:**
When `analysis_mode = "fast"`, the input `resolution_gsd` is multiplied by 2
before being passed to `get_colmap_settings_for_gsd()`. This effectively halves
the reconstruction resolution, reducing COLMAP processing time significantly.

```
fast mode:  effective_gsd = resolution_gsd × 2.0
full mode:  effective_gsd = resolution_gsd (unchanged)
```

**COLMAP binary reader** (`shared/colmap/model_reader.py`):
- Reads `cameras.bin` → `ColmapCamera` (intrinsics: focal length, principal point)
- Reads `images.bin` → `ColmapImage` (extrinsics: quaternion, translation)
- Used by orthorectification to project spectral images onto the DSM grid

### Stage 3: Orthomosaic Generation (Multispectral Extension)

**Service:** `orthomosaic_generation` (port 8003)  
**Gate condition:** `analysis_mode == "full" AND is_multispectral AND calibration_path`

After the base RGB orthomosaic pipeline completes, the multispectral
extension runs these sub-steps:

#### 3a. Band Orthorectification
**Module:** `ms_orthorectification.orthorectify_bands()`

- Reads calibrated reflectance TIFs per band from `calibration_path`
- Reads DSM metadata (extent, CRS, resolution) from the generated DSM
- Creates a **median composite** per band, resampled to DSM grid dimensions
- Output: one GeoTIFF per band (`green_ortho.tif`, `red_ortho.tif`, etc.)

**Supported spectral bands:**
| Band | Input Directory | Output File |
|------|----------------|-------------|
| Green | `calibrated_images/green/` | `green_ortho.tif` |
| Red | `calibrated_images/red/` | `red_ortho.tif` |
| Red Edge | `calibrated_images/red_edge/` | `red_edge_ortho.tif` |
| NIR | `calibrated_images/nir/` | `nir_ortho.tif` |

#### 3b. Multi-Band Stacking
**Module:** `ms_orthorectification.stack_bands()`

- Stacks single-band ortho GeoTIFFs into a 4-band GeoTIFF
- Band order: Green (1), Red (2), Red Edge (3), NIR (4)
- Output: `multiband_reflectance.tif` (Float32, DEFLATE compressed)

#### 3c. Vegetation Index Computation
**Module:** `vegetation_indices.compute_vegetation_indices()`

All indices use the normalised difference formula:
$$\text{Index} = \frac{A - B}{A + B}$$

| Index | Formula | Band A | Band B | Use Case |
|-------|---------|--------|--------|----------|
| **NDVI** | $(NIR - Red) / (NIR + Red)$ | NIR | Red | General vegetation health |
| **NDRE** | $(NIR - RedEdge) / (NIR + RedEdge)$ | NIR | Red Edge | Chlorophyll content, late-season crops |
| **GNDVI** | $(NIR - Green) / (NIR + Green)$ | NIR | Green | Chlorophyll in early-stage vegetation |

- Values clipped to [-1, 1]
- Output format: Float32 GeoTIFF with DEFLATE compression
- NoData value: -9999.0

#### 3d. COG Conversion
**Module:** `vegetation_indices.convert_index_to_cog()`

Converts each vegetation index GeoTIFF to Cloud Optimized GeoTIFF for
efficient web visualization (tiled, with overview pyramids).

### Stage 4: Product Upload (API Gateway)

**Module:** `api_gateway/.../jobs.py → upload_stage_products()`

The gateway uploads all products generated by the orthomosaic service:

| Product Key | Product Type | Condition |
|-------------|-------------|-----------|
| `orthomosaic_rgb` | `orthomosaic` | Always |
| `dsm_filled_cog` | `dsm` | Always |
| `hillshade` | `hillshade` | Always || `orthomosaic_rgb_2x` | `orthomosaic_2x` | Always |
| `orthomosaic_rgb_4x` | `orthomosaic_4x` | Always |
| `orthomosaic_rgb_8x` | `orthomosaic_8x` | Always || `ndvi` | `ndvi` | Full mode + MS |
| `ndre` | `ndre` | Full mode + MS |
| `gndvi` | `gndvi` | Full mode + MS |
| `multiband_reflectance` | `calibrated_reflectance` | Full mode + MS |

---

## Data Flow Between Services

```
Calibration Callback
  └─ has_reflectance, calibration_path, band_manifest, is_multispectral
       │
       ▼
API Gateway (stores in stage_results["calibration"])
       │
       │ trigger_next_stage("orthomosaic")
       │ Enriches ortho_params with calibration data + sfm_run_path
       ▼
Orthomosaic Service
  ├─ parameters.is_multispectral = true
  ├─ parameters.calibration_path = "/data/.../calibrated_images"
  ├─ parameters.band_manifest = {...}
  ├─ parameters.has_reflectance = true
  ├─ parameters.sfm_run_path = "/data/.../sfm_run"
  └─ parameters.analysis_mode = "full"
       │
       ▼
Orthomosaic Callback → outputs dict includes:
  ndvi, ndre, gndvi, multiband_reflectance, per-band orthos
       │
       ▼
API Gateway → upload_stage_products("orthomosaic", ...)
  └─ Uploads each product to backend via ProductUploadClient
```

---

## Configuration

### Backend API Request

```json
POST /v1/api/jobs/start-job/
{
  "dataset_id": 123,
  "resolution_gsd": 5.0,
  "radiometric_calibration": true,
  "analysis_mode": "full"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `analysis_mode` | `string` | `"fast"` | `"fast"` = RGB only, `"full"` = RGB + multispectral |

### analysis_mode Behaviour

| Mode | Calibration | SFM | Orthomosaic |
|------|-------------|-----|-------------|
| `fast` | Geometric only | GSD × 2 (faster) | RGB orthomosaic only |
| `full` | Geometric + reflectance | Native GSD | RGB + band orthos + vegetation indices |

---

## Output Products (Full Mode)

When `analysis_mode = "full"` with a multispectral dataset, the pipeline
produces these additional outputs alongside the standard RGB products:

| File | Format | Description |
|------|--------|-------------|
| `green_ortho.tif` | Float32 GeoTIFF | Green band orthorectified |
| `red_ortho.tif` | Float32 GeoTIFF | Red band orthorectified |
| `red_edge_ortho.tif` | Float32 GeoTIFF | Red Edge band orthorectified |
| `nir_ortho.tif` | Float32 GeoTIFF | NIR band orthorectified |
| `multiband_reflectance.tif` | Float32 4-band GeoTIFF | Stacked G/R/RE/NIR |
| `orthomosaic_rgb_2x.tif` | COG GeoTIFF | 2× downsampled orthomosaic |
| `orthomosaic_rgb_4x.tif` | COG GeoTIFF | 4× downsampled orthomosaic |
| `orthomosaic_rgb_8x.tif` | COG GeoTIFF | 8× downsampled orthomosaic |
| `ndvi.tif` | Float32 GeoTIFF | NDVI vegetation index |
| `ndre.tif` | Float32 GeoTIFF | NDRE vegetation index |
| `gndvi.tif` | Float32 GeoTIFF | GNDVI vegetation index |

---

## Module Reference

| Module | Location | Purpose |
|--------|----------|---------|
| `ms_orthorectification` | `services/orthomosaic_generation/app/core/algorithms/` | Band median composite + stacking |
| `vegetation_indices` | `services/orthomosaic_generation/app/core/algorithms/` | NDVI/NDRE/GNDVI computation + COG |
| `model_reader` | `shared/colmap/` | COLMAP binary model parser |
| `calibration_endpoint` | `services/radiometric_calibration/.../endpoints/` | Reflectance conversion |
| `orthomosaic_endpoint` | `services/orthomosaic_generation/.../endpoints/` | MS pipeline orchestration |
| `jobs.py` | `api_gateway/app/api/v1/endpoints/` | Enrichment + upload |

---

## Testing

### Unit Tests

| Test File | Tests | Covers |
|-----------|-------|--------|
| `tests/unit/test_colmap_reader.py` | 7 | Binary model parsing, quaternion→rotation, projection center |
| `tests/unit/test_vegetation_indices.py` | 5 | Normalised difference, edge cases, multi-index dispatch |
| `tests/unit/test_multi_resolution.py` | 7 | Multi-resolution generation, GDAL translate calls, pixel size reading |
| `backend/tests/test_analysis_mode.py` | 5 | JobEntity defaults, UseCase validation, mode propagation |

Run all:
```bash
# AI tests
cd image-analysis-core
python -m unittest tests/unit/test_colmap_reader.py tests/unit/test_vegetation_indices.py -v

# Backend tests
cd backend
python -m unittest tests/test_analysis_mode.py -v
```

---

## Dependencies

| Package | Used By | Purpose |
|---------|---------|---------|
| GDAL (Python bindings) | ms_orthorectification, vegetation_indices | GeoTIFF I/O, COG conversion |
| NumPy | All MS modules | Array operations |
| OpenCV (cv2) | calibration_endpoint | Reflectance image saving |
| gdal_merge.py | ms_orthorectification | Band stacking CLI |
| gdal_translate | vegetation_indices | COG conversion CLI |

---

## Graceful Degradation

The pipeline handles missing data gracefully at every gate:

- **No `analysis_mode` in request** → defaults to `"fast"`, MS pipeline skipped
- **`analysis_mode = "full"` but not multispectral** → warning logged, MS skipped
- **Missing `calibration_path`** → MS pipeline skipped with warning
- **Band directory missing** → that band skipped, others still processed
- **No TIF files in band dir** → warning, band skipped
- **GDAL not available** → `RuntimeError` raised (hard dependency)
