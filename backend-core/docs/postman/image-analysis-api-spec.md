# PhotoGear Image Analysis API Specification

## Overview
This document defines the internal API for the PhotoGear image analysis service (be-analytics). This service handles the computationally intensive photogrammetry processing, including Structure from Motion (SfM), Multi-View Stereo (MVS), orthomosaic generation, and 3D reconstruction.

## Base URL
```
Internal service communication (gRPC/HTTP)
http://analytics-service:8080/v1
```

## Authentication
Internal service authentication via service tokens or mTLS.

---

## Processing Pipeline APIs

### POST /v1/jobs/{job_id}/preprocess
**Description**: Execute preprocessing pipeline (calibration, validation, QC)
**Request Body**:
```json
{
  "job_id": "job_preproc_001",
  "dataset_id": "ds_101",
  "images": [
    {
      "id": "img_123",
      "uri": "s3://raw/ds_101/IMG_001.JPG",
      "band": "RGB",
      "exif": {...},
      "imu": {...}
    }
  ],
  "calibration": {
    "id": "cal_123",
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
    }
  },
  "parameters": {
    "validate_overlap": true,
    "generate_qc_report": true,
    "output_format": "TIFF"
  }
}
```
**Response**:
```json
{
  "job_id": "job_preproc_001",
  "status": "started",
  "stages": [
    "validate_images",
    "apply_calibration",
    "generate_qc_report"
  ],
  "estimated_duration_minutes": 15
}
```

### POST /v1/jobs/{job_id}/orthomosaic
**Description**: Execute orthomosaic generation pipeline
**Request Body**:
```json
{
  "job_id": "job_ortho_001",
  "dataset_id": "ds_101",
  "images": [
    {
      "id": "img_123",
      "uri": "s3://staging/ds_101/calibrated/IMG_001.tif",
      "camera_params": {...},
      "gps_coords": [35.123, 31.456, 120.5]
    }
  ],
  "parameters": {
    "resolution_cm": 5,
    "bands": ["RGB", "NIR"],
    "crs": "EPSG:32639",
    "surface_type": "DSM",
    "quality": "standard",
    "engine": "opensfm",
    "sfm_params": {
      "feature_type": "SIFT",
      "matching_max_distance": 0.7,
      "bundle_adjustment_iterations": 100
    },
    "mvs_params": {
      "depth_map_resolution": 640,
      "num_views": 10,
      "geometric_consistency": true
    },
    "ortho_params": {
      "seam_mode": "poisson",
      "blend_width": 20,
      "color_correction": true
    }
  },
  "output": {
    "cog_compression": "JPEG",
    "overview_levels": [2, 4, 8, 16],
    "tile_size": 512
  }
}
```
**Response**:
```json
{
  "job_id": "job_ortho_001",
  "status": "started",
  "stages": [
    "feature_extraction",
    "feature_matching",
    "bundle_adjustment",
    "dense_reconstruction",
    "mesh_generation",
    "orthomosaic_generation",
    "cog_conversion"
  ],
  "estimated_duration_minutes": 180
}
```

### POST /v1/jobs/{job_id}/recon3d
**Description**: Execute 3D reconstruction pipeline
**Request Body**:
```json
{
  "job_id": "job_recon3d_001",
  "dataset_id": "ds_101",
  "sparse_pointcloud_uri": "s3://staging/job_ortho_001/sparse.ply",
  "camera_poses_uri": "s3://staging/job_ortho_001/cameras.json",
  "images": [
    {
      "id": "img_123",
      "uri": "s3://staging/ds_101/calibrated/IMG_001.tif"
    }
  ],
  "parameters": {
    "quality": "high",
    "densify": true,
    "generate_texture": true,
    "mesh_resolution": "medium",
    "point_cloud_filter": true,
    "engine": "colmap",
    "mvs_params": {
      "patch_match_iterations": 3,
      "geom_consistency_max_cost": 3.0,
      "filter_min_triangulation_angle": 1.0
    },
    "mesh_params": {
      "poisson_depth": 10,
      "outlier_removal_factor": 0.1,
      "surface_trimming": 7.0
    },
    "texture_params": {
      "texture_size": 8192,
      "geometric_visibility_test": true,
      "color_processing": "gamma_correction"
    }
  }
}
```
**Response**:
```json
{
  "job_id": "job_recon3d_001",
  "status": "started",
  "stages": [
    "dense_stereo_matching",
    "point_cloud_fusion",
    "point_cloud_filtering",
    "mesh_reconstruction",
    "texture_mapping"
  ],
  "estimated_duration_minutes": 240
}
```

---

## Job Status & Progress APIs

### GET /v1/jobs/{job_id}/status
**Description**: Get detailed job status and progress
**Response**:
```json
{
  "job_id": "job_ortho_001",
  "status": "running",
  "current_stage": "bundle_adjustment",
  "progress": {
    "overall_percent": 45,
    "current_stage_percent": 75,
    "stages_completed": 2,
    "total_stages": 7
  },
  "metrics": {
    "images_processed": 180,
    "total_images": 245,
    "features_extracted": 2450000,
    "matches_found": 850000,
    "reprojection_error": 1.2,
    "processing_rate_imgs_per_min": 12.5
  },
  "resource_usage": {
    "cpu_percent": 85,
    "memory_mb": 16384,
    "gpu_percent": 92,
    "disk_usage_gb": 45.2
  },
  "timestamps": {
    "started_at": "2025-09-02T14:35:00Z",
    "current_stage_started": "2025-09-02T15:10:00Z",
    "estimated_completion": "2025-09-02T17:35:00Z"
  }
}
```

### GET /v1/jobs/{job_id}/logs
**Description**: Get job execution logs
**Query Parameters**:
- `stage` (optional): Filter by processing stage
- `level` (optional): Log level (DEBUG, INFO, WARN, ERROR)
- `since` (optional): ISO timestamp for recent logs
**Response**:
```json
{
  "job_id": "job_ortho_001",
  "logs": [
    {
      "timestamp": "2025-09-02T15:10:15Z",
      "level": "INFO",
      "stage": "bundle_adjustment",
      "message": "Iteration 45/100: RMSE=1.23px, converging",
      "context": {
        "iteration": 45,
        "rmse": 1.23,
        "num_observations": 125000
      }
    },
    {
      "timestamp": "2025-09-02T15:10:20Z",
      "level": "WARN",
      "stage": "bundle_adjustment",
      "message": "Image IMG_089.JPG has low feature count: 850",
      "context": {
        "image_id": "img_089",
        "feature_count": 850,
        "threshold": 1000
      }
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
  "status": "canceling",
  "message": "Job cancellation initiated"
}
```

---

## Artifact & Output APIs

### GET /v1/jobs/{job_id}/artifacts
**Description**: List artifacts produced by job
**Response**:
```json
{
  "job_id": "job_ortho_001",
  "artifacts": [
    {
      "id": "artifact_001",
      "type": "sparse_pointcloud",
      "stage": "bundle_adjustment",
      "uri": "s3://staging/job_ortho_001/sparse.ply",
      "size_mb": 15.2,
      "format": "PLY",
      "created_at": "2025-09-02T15:20:00Z"
    },
    {
      "id": "artifact_002",
      "type": "camera_poses",
      "stage": "bundle_adjustment",
      "uri": "s3://staging/job_ortho_001/cameras.json",
      "size_mb": 0.8,
      "format": "JSON",
      "created_at": "2025-09-02T15:20:00Z"
    },
    {
      "id": "artifact_003",
      "type": "dense_pointcloud",
      "stage": "dense_reconstruction",
      "uri": "s3://staging/job_ortho_001/dense.ply",
      "size_mb": 145.6,
      "format": "PLY",
      "created_at": "2025-09-02T15:45:00Z"
    },
    {
      "id": "artifact_004",
      "type": "orthomosaic_cog",
      "stage": "cog_conversion",
      "uri": "s3://products/ds_101/orthomosaic_5cm.tif",
      "size_mb": 245.8,
      "format": "COG",
      "created_at": "2025-09-02T16:00:00Z"
    }
  ]
}
```

### POST /v1/jobs/{job_id}/publish
**Description**: Publish final products to output storage
**Request Body**:
```json
{
  "job_id": "job_ortho_001",
  "artifacts": [
    {
      "artifact_id": "artifact_004",
      "product_type": "orthomosaic",
      "metadata": {
        "bands": ["R", "G", "B", "NIR"],
        "resolution_cm": 5,
        "crs": "EPSG:32639",
        "compression": "JPEG"
      }
    }
  ],
  "generate_previews": true,
  "notification_webhook": "https://api.photogear.com/v1/jobs/job_ortho_001/completion"
}
```
**Response**:
```json
{
  "job_id": "job_ortho_001",
  "published_products": [
    {
      "product_id": "prod_567",
      "type": "orthomosaic",
      "uri": "s3://products/ds_101/orthomosaic_5cm.tif",
      "preview_uri": "s3://products/ds_101/preview_5cm.png"
    }
  ],
  "status": "published"
}
```

---

## Quality Control APIs

### POST /v1/qc/calibration
**Description**: Run calibration quality control analysis
**Request Body**:
```json
{
  "dataset_id": "ds_101",
  "calibration_id": "cal_123",
  "panel_images": [
    {
      "image_id": "img_panel_001",
      "uri": "s3://raw/ds_101/panel_IMG_001.JPG",
      "expected_reflectance": {
        "R": 0.18,
        "G": 0.18,
        "B": 0.18,
        "NIR": 0.18
      }
    }
  ],
  "test_images": [
    {
      "image_id": "img_123",
      "uri": "s3://staging/ds_101/calibrated/IMG_001.tif"
    }
  ]
}
```
**Response**:
```json
{
  "calibration_id": "cal_123",
  "qc_results": {
    "panel_error_pct": 2.1,
    "validation_status": "passed",
    "band_analysis": {
      "R": {
        "mean_error_pct": 1.8,
        "std_error_pct": 0.4,
        "status": "passed"
      },
      "G": {
        "mean_error_pct": 2.1,
        "std_error_pct": 0.5,
        "status": "passed"
      },
      "B": {
        "mean_error_pct": 2.4,
        "std_error_pct": 0.6,
        "status": "passed"
      },
      "NIR": {
        "mean_error_pct": 1.9,
        "std_error_pct": 0.3,
        "status": "passed"
      }
    },
    "variance_reduction": {
      "before_calibration": 15.2,
      "after_calibration": 3.8,
      "improvement_pct": 75.0
    }
  },
  "report_uri": "s3://staging/ds_101/qc_report_cal_123.pdf"
}
```

### POST /v1/qc/orthomosaic
**Description**: Run orthomosaic quality control analysis
**Request Body**:
```json
{
  "job_id": "job_ortho_001",
  "orthomosaic_uri": "s3://products/ds_101/orthomosaic_5cm.tif",
  "reference_data": {
    "ground_control_points": [
      {
        "id": "gcp_001",
        "coordinates": [35.123456, 31.654321, 125.5],
        "pixel_coords": [2045, 1823]
      }
    ],
    "reference_boundary": {
      "type": "Polygon",
      "coordinates": [[[35.12, 31.65], [35.13, 31.65], [35.13, 31.66], [35.12, 31.66], [35.12, 31.65]]]
    }
  }
}
```
**Response**:
```json
{
  "job_id": "job_ortho_001",
  "qc_results": {
    "geometric_accuracy": {
      "rmse_px": 1.2,
      "rmse_meters": 0.06,
      "max_error_px": 2.8,
      "gcp_errors": [
        {
          "gcp_id": "gcp_001",
          "error_px": 1.1,
          "error_meters": 0.055
        }
      ]
    },
    "coverage_analysis": {
      "total_area_sqm": 125000,
      "covered_area_sqm": 123125,
      "coverage_pct": 98.5,
      "gaps": [
        {
          "area_sqm": 45,
          "center": [35.1245, 31.6578]
        }
      ]
    },
    "radiometric_quality": {
      "seamline_artifacts": "minimal",
      "color_balance_score": 8.5,
      "brightness_uniformity": 0.92
    },
    "validation_status": "passed"
  },
  "report_uri": "s3://staging/job_ortho_001/qc_report.pdf"
}
```

---

## Engine Configuration APIs

### GET /v1/engines
**Description**: List available processing engines
**Response**:
```json
{
  "engines": [
    {
      "name": "opensfm",
      "type": "sfm",
      "version": "0.5.2",
      "capabilities": ["feature_extraction", "matching", "bundle_adjustment"],
      "supported_formats": ["JPEG", "TIFF"],
      "license": "BSD-2-Clause"
    },
    {
      "name": "colmap",
      "type": "sfm_mvs",
      "version": "3.8",
      "capabilities": ["feature_extraction", "matching", "bundle_adjustment", "dense_reconstruction"],
      "supported_formats": ["JPEG", "TIFF", "PNG"],
      "license": "BSD-3-Clause"
    },
    {
      "name": "openmvs",
      "type": "mvs",
      "version": "2.0.1",
      "capabilities": ["dense_reconstruction", "mesh_generation", "texture_mapping"],
      "supported_formats": ["PLY", "OBJ"],
      "license": "AGPL-3.0"
    }
  ]
}
```

### GET /v1/engines/{engine_name}/parameters
**Description**: Get configurable parameters for specific engine
**Response**:
```json
{
  "engine_name": "opensfm",
  "parameters": {
    "feature_extraction": {
      "feature_type": {
        "type": "enum",
        "values": ["SIFT", "SURF", "ORB", "AKAZE"],
        "default": "SIFT"
      },
      "feature_min_frames": {
        "type": "integer",
        "min": 2,
        "max": 10,
        "default": 4
      },
      "feature_process_size": {
        "type": "integer",
        "min": 1024,
        "max": 4096,
        "default": 2048
      }
    },
    "matching": {
      "matching_max_distance": {
        "type": "float",
        "min": 0.1,
        "max": 1.0,
        "default": 0.7
      },
      "matching_max_neighbors": {
        "type": "integer",
        "min": 5,
        "max": 50,
        "default": 20
      }
    },
    "bundle_adjustment": {
      "optimize_camera_parameters": {
        "type": "boolean",
        "default": true
      },
      "bundle_adjustment_iterations": {
        "type": "integer",
        "min": 10,
        "max": 500,
        "default": 100
      }
    }
  }
}
```

---

## Health & Monitoring APIs

### GET /v1/health
**Description**: Service health check
**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "processing_queue": "healthy",
    "storage_access": "healthy",
    "gpu_resources": "healthy"
  },
  "system_info": {
    "cpu_cores": 16,
    "memory_gb": 64,
    "gpu_devices": [
      {
        "name": "NVIDIA RTX 4090",
        "memory_gb": 24,
        "utilization_pct": 15
      }
    ],
    "disk_space_gb": 2048
  }
}
```

### GET /v1/metrics
**Description**: Processing metrics and statistics
**Response**:
```json
{
  "current_load": {
    "active_jobs": 3,
    "queued_jobs": 7,
    "worker_utilization_pct": 75
  },
  "performance_stats": {
    "avg_processing_time_minutes": {
      "preprocess": 12,
      "orthomosaic": 145,
      "recon3d": 180
    },
    "throughput_jobs_per_hour": 4.2,
    "success_rate_pct": 96.8
  },
  "resource_usage": {
    "cpu_avg_pct": 68,
    "memory_avg_pct": 72,
    "gpu_avg_pct": 45,
    "storage_used_gb": 1245
  }
}
```

---

## Error Responses

All endpoints return standard HTTP status codes and error responses:

```json
{
  "error": {
    "code": "PROCESSING_ERROR",
    "message": "Feature extraction failed",
    "details": {
      "stage": "feature_extraction",
      "engine": "opensfm",
      "image_id": "img_123",
      "reason": "insufficient features detected"
    }
  },
  "job_id": "job_ortho_001",
  "timestamp": "2025-09-02T15:30:00Z"
}
```

**Common Error Codes**:
- `400` - Bad Request (invalid parameters)
- `404` - Job/Resource Not Found
- `409` - Job Already Running
- `422` - Processing Error (algorithm failure)
- `429` - Resource Limit Exceeded
- `500` - Internal Processing Error
- `503` - Service Unavailable (overloaded)
