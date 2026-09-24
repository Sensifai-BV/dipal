# Orthomosaic Generation Guide

## Overview

I've implemented a complete orthomosaic generation service that creates colorful, textured maps from your SFM (Structure from Motion) results. This will show actual terrain features like fields, roads, and water in QGIS.

## What Gets Generated

The pipeline creates multiple output files:

1. **`orthomosaic_rgb.tif`** ⭐ **THIS IS WHAT YOU WANT FOR VISUALIZATION!**
   - Full-color orthomosaic showing actual terrain features
   - Displays fields, roads, water, vegetation in their true colors
   - Load this in QGIS to see a colorful map

2. **`dsm.tif`** - Digital Surface Model (elevation data)
   - Shows height information as grayscale
   - Used for terrain analysis

3. **`dsm_filled.tif`** - DSM with holes filled
   - Improved version with gaps interpolated

4. **`dsm_filled_cog.tif`** - Cloud Optimized GeoTIFF
   - Optimized for web serving and fast loading
   - Best format for publishing online

5. **`hillshade.tif`** - Terrain relief visualization
   - Shows 3D terrain relief using simulated lighting
   - Great for visualizing topography

## How to Use

### Generate Orthomosaic for Your Dataset

```bash
python generate_orthomosaic.py data/selected_images_2
```

This will:
- Generate DSM from your dense point cloud
- Extract RGB color information and create orthomosaic_rgb.tif ⭐
- Fill holes in the DSM
- Generate hillshade for terrain visualization
- Create Cloud Optimized GeoTIFF
- Generate statistics

### Visualize in QGIS

1. Open QGIS
2. **Layer** → **Add Layer** → **Add Raster Layer**
3. Browse to `data/selected_images_2/orthomosaic_rgb.tif`
4. Click **Add**

You should now see a **colorful map** showing:
- Green vegetation/fields
- Brown/gray roads and paths
- Blue/dark water bodies
- Natural terrain colors

### For Better Visualization

#### Option 1: Load RGB Orthomosaic (Recommended)
- File: `orthomosaic_rgb.tif`
- Shows actual colors and features
- Best for identifying objects

#### Option 2: Load Hillshade + DSM
- Load `hillshade.tif` as base layer
- Add `dsm_filled_cog.tif` on top
- Adjust transparency to see both elevation and relief

#### Option 3: Combine RGB + Hillshade
- Load `orthomosaic_rgb.tif`
- Add `hillshade.tif` as overlay
- Set hillshade transparency to 50%
- This gives colorful map with 3D terrain effect

## Technical Details

### Processing Time
- DSM generation: ~5 minutes
- RGB orthomosaic: ~15 minutes (5 min per color band)
- Hole filling: ~1 second
- Hillshade: ~1 second
- Total: ~20-25 minutes

### Resolution
- Default: 0.01 meters per pixel (1 cm)
- Adjust in settings if needed

### How It Works

1. **PDAL** reads the dense point cloud (`fused.ply`)
2. Extracts Red, Green, and Blue color values from each point
3. Rasterizes each color band separately
4. **GDAL** merges the three bands into one RGB GeoTIFF
5. Additional processing creates DSM, hillshade, and COG formats

## Customization

### Adjust Resolution

Edit `services/orthomosaic_generation/app/core/services/orthomosaic_service.py`:

```python
# Orthophoto settings (for textured orthomosaic)
ortho_resolution: float = 0.02  # Change from 0.01 to 0.02 for faster processing
```

### Change Hillshade Lighting

```python
# Generate hillshade with different lighting angle
service.generate_hillshade(
    project_id,
    azimuth=135.0,  # Light from southeast
    altitude=30.0,  # Lower sun angle
)
```

## Troubleshooting

### Gray Rectangle in QGIS
- **Cause**: Viewing DSM instead of RGB orthomosaic
- **Solution**: Load `orthomosaic_rgb.tif`, not `dsm.tif`

### RGB Orthomosaic Not Generated
- **Cause**: Point cloud missing color information
- **Solution**: Ensure SFM pipeline processes original images with color

### Poor Color Quality
- **Cause**: Low resolution or sparse point cloud
- **Solution**: Increase SFM quality settings or use more images

## File Sizes (Typical)

- `orthomosaic_rgb.tif`: 15-30 MB (3 bands)
- `dsm_filled_cog.tif`: 3-7 MB (optimized)
- `hillshade.tif`: 0.5-2 MB (grayscale)

## Integration with API Gateway

To integrate with your API Gateway service:

```python
from services.orthomosaic_generation.app.core.algorithms.orthomosaic_pipeline import OrthomosaicPipeline
from services.orthomosaic_generation.app.core.services.orthomosaic_service import OrthomosaicService

# In your pipeline orchestrator
service = OrthomosaicService()
pipeline = OrthomosaicPipeline(service)

# Run after SFM completes
pipeline.run_pipeline(dataset_path, generate_cog=True)
```

## Next Steps

1. ✅ Generate RGB orthomosaic from your point cloud
2. ✅ Visualize in QGIS with true colors
3. 🔲 Publish COG to web services (AWS S3 + TiTiler)
4. 🔲 Add georeferencing if needed
5. 🔲 Generate vegetation indices (NDVI) from multispectral data

## References

- PDAL: https://pdal.io/
- GDAL: https://gdal.org/
- Cloud Optimized GeoTIFF: https://www.cogeo.org/
