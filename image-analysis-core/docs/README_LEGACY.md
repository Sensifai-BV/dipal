# PhotoGear - Structure from Motion Pipeline

## Overview

PhotoGear is a complete Structure from Motion (SfM) pipeline built using pycolmap. It reconstructs 3D scenes from a collection of 2D images by estimating camera poses and generating sparse and dense 3D point clouds.

## What is Structure from Motion?

Structure from Motion is a computer vision technique that reconstructs 3D structures from sequences of 2D images. The process involves:

1. **Feature Detection**: Finding distinctive points in each image
2. **Feature Matching**: Matching these points across multiple images
3. **Camera Pose Estimation**: Determining camera positions and orientations
4. **3D Point Triangulation**: Computing 3D positions of matched features
5. **Bundle Adjustment**: Refining camera poses and 3D points simultaneously

## Pipeline Components

### SfMPipeline Class

The main `SfMPipeline` class orchestrates the entire reconstruction process:

#### Initialization
```python
sfm = SfMPipeline(dataset_path)
```

Creates the necessary directory structure:
- `images/` - Input images
- `database.db` - SQLite database storing features and matches
- `sparse/` - Sparse reconstruction results
- `dense/` - Dense reconstruction results

#### Core Methods

1. **`check_images()`**
   - Validates image directory exists
   - Counts compatible image formats (.jpg, .jpeg, .png, .bmp, .tiff)
   - Logs basic statistics

2. **`feature_extraction()`**
   - Extracts SIFT features from all images
   - Uses GPU acceleration when available
   - Configurable parameters:
     - `max_image_size`: 3200 pixels
     - `max_num_features`: 8192 per image

3. **`feature_matching()`**
   - Matches SIFT features between image pairs
   - Uses exhaustive matching for small datasets
   - GPU accelerated when available

4. **`sparse_reconstruction()`**
   - Performs incremental Structure from Motion
   - Estimates camera poses and 3D point positions
   - Uses bundle adjustment for optimization
   - Outputs the largest connected component

5. **`dense_reconstruction()` (Optional)**
   - Generates dense point clouds using stereo matching
   - Creates detailed 3D models with higher point density
   - May fail on some datasets due to computational requirements

6. **`export_results()`**
   - Exports sparse point cloud to PLY format
   - Saves camera poses in text format
   - Creates human-readable output files

## Configuration Parameters

### Feature Extraction
- **GPU Usage**: Automatically detected
- **Max Image Size**: 3200 pixels (larger images are downscaled)
- **Max Features**: 8192 SIFT features per image

### Sparse Reconstruction
- **Min Model Size**: 10 images minimum for reconstruction
- **Init Trials**: 200 attempts to initialize reconstruction
- **Thread Usage**: All available CPU cores
- **Color Extraction**: Enabled for textured point clouds

### Dense Reconstruction
- **Max Image Size**: 2000 pixels for stereo processing
- **Window Radius**: 5 pixels for patch matching
- **Fusion Parameters**: Optimized for quality vs. speed

## Input Requirements

### Image Dataset
- **Format**: JPEG, PNG, BMP, or TIFF
- **Quantity**: Minimum 3 images, recommended 10+ for robust reconstruction
- **Overlap**: Images should have significant overlap (60-80%)
- **Quality**: Good lighting, minimal motion blur
- **Coverage**: Multiple viewpoints of the same scene

### Directory Structure
```
dataset_name/
├── images/
│   ├── image1.jpg
│   ├── image2.jpg
│   └── ...
```

## Output Files

### Sparse Reconstruction
- **`sparse/0/`**: COLMAP format reconstruction
  - `cameras.bin`: Camera intrinsic parameters
  - `images.bin`: Camera poses and image information
  - `points3D.bin`: 3D point coordinates and colors
- **`sparse_points.ply`**: Sparse point cloud (viewable in MeshLab, CloudCompare)
- **`camera_poses.txt`**: Human-readable camera poses

### Dense Reconstruction (if enabled)
- **`dense/fused.ply`**: Dense point cloud with millions of points
- **`dense/stereo/`**: Intermediate stereo processing files

### Database
- **`database.db`**: SQLite database containing:
  - Extracted SIFT features
  - Feature matches between images
  - Camera intrinsic estimates

## Performance Considerations

### Hardware Requirements
- **GPU**: NVIDIA GPU recommended for feature extraction/matching
- **RAM**: 8GB+ for medium datasets (100-500 images)
- **Storage**: Significant space for dense reconstruction

### Processing Time
- **Feature Extraction**: ~1-5 seconds per image
- **Feature Matching**: Quadratic in number of images
- **Sparse Reconstruction**: Minutes to hours depending on dataset size
- **Dense Reconstruction**: Very computationally intensive

### Optimization Tips
1. Use GPU acceleration when available
2. Resize large images before processing
3. Skip dense reconstruction for faster results
4. Use vocabulary tree matching for large datasets (>100 images)

## Error Handling

The pipeline includes comprehensive error handling:
- **Missing Images**: Validates image directory exists
- **No Features**: Checks if feature extraction succeeded
- **Failed Reconstruction**: Handles cases where SfM fails
- **Database Issues**: Manages corrupted or missing database files

## Usage Example

```python
from structure_from_motion import SfMPipeline

# Initialize pipeline
sfm = SfMPipeline("my_dataset")

# Run complete pipeline
sfm.run_full_pipeline(skip_dense=False)

# Or run individual steps
sfm.check_images()
sfm.feature_extraction()
sfm.feature_matching()
sfm.sparse_reconstruction()
sfm.export_results()
```

## Troubleshooting

### Common Issues

1. **No Reconstruction Generated**
   - Check image overlap and quality
   - Verify sufficient features are extracted
   - Ensure images are in focus

2. **GPU Not Detected**
   - Verify CUDA installation
   - Check pycolmap GPU support
   - Falls back to CPU processing

3. **Memory Issues**
   - Reduce `max_image_size` parameter
   - Process smaller batches of images
   - Skip dense reconstruction

4. **Poor Reconstruction Quality**
   - Improve image overlap
   - Add more viewpoints
   - Check lighting conditions
   - Verify camera is stable (no motion blur)

## Dependencies

- **pycolmap**: Core SfM algorithms
- **sqlite3**: Database management
- **pathlib**: File path handling
- **logging**: Progress tracking and debugging

See `requirements.txt` for complete dependency list.