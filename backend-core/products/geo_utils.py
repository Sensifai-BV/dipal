"""
Geospatial utilities for extracting footprint and metadata from GeoTIFF files.

Uses GDAL (osgeo) which is already configured in the Django project.
"""
from typing import Optional
from django.contrib.gis.geos import Polygon
from config.logging_config import get_logger

logger = get_logger(__name__)


def extract_footprint_from_s3(
    s3_key: str,
    bucket: str,
) -> Optional[Polygon]:
    """
    Extract geospatial footprint from a GeoTIFF file stored in S3.
    
    Uses GDAL's virtual filesystem (vsicurl/vsis3) to read directly from S3.
    
    Args:
        s3_key: S3 object key
        bucket: S3 bucket name
        
    Returns:
        Polygon in EPSG:4326, or None if extraction fails
    """
    try:
        from osgeo import gdal, osr
        
        # Use GDAL virtual filesystem to read from S3
        # Format: /vsis3/bucket/key
        vsi_path = f"/vsis3/{bucket}/{s3_key}"
        
        # Open the dataset
        ds = gdal.Open(vsi_path, gdal.GA_ReadOnly)
        if ds is None:
            logger.warning(f"Could not open {vsi_path} with GDAL")
            return None
        
        # Get geotransform
        gt = ds.GetGeoTransform()
        if gt is None:
            logger.warning(f"No geotransform found in {s3_key}")
            ds = None
            return None
        
        # Calculate bounds from geotransform
        # gt = (origin_x, pixel_width, rotation_x, origin_y, rotation_y, pixel_height)
        width = ds.RasterXSize
        height = ds.RasterYSize
        
        # Corner coordinates in source CRS
        min_x = gt[0]
        max_x = gt[0] + width * gt[1]
        max_y = gt[3]
        min_y = gt[3] + height * gt[5]  # gt[5] is typically negative
        
        # Get source CRS
        src_srs = osr.SpatialReference()
        src_srs.ImportFromWkt(ds.GetProjection())
        
        if src_srs.IsEmpty():
            logger.warning(f"No CRS found in {s3_key}, cannot extract footprint")
            ds = None
            return None
        
        # Transform to WGS84 (EPSG:4326) if needed
        tgt_srs = osr.SpatialReference()
        tgt_srs.ImportFromEPSG(4326)
        tgt_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)  # lon, lat order
        
        if not src_srs.IsSame(tgt_srs):
            transform = osr.CoordinateTransformation(src_srs, tgt_srs)
            
            # Transform corners
            ll = transform.TransformPoint(min_x, min_y)
            lr = transform.TransformPoint(max_x, min_y)
            ur = transform.TransformPoint(max_x, max_y)
            ul = transform.TransformPoint(min_x, max_y)
            
            west = min(ll[0], ul[0])
            east = max(lr[0], ur[0])
            south = min(ll[1], lr[1])
            north = max(ul[1], ur[1])
        else:
            west, south, east, north = min_x, min_y, max_x, max_y
        
        ds = None  # Close dataset
        
        # Create polygon from bounds (ring must be closed)
        coords = [
            (west, south),
            (east, south),
            (east, north),
            (west, north),
            (west, south),  # Close the ring
        ]
        
        footprint = Polygon(coords, srid=4326)
        
        logger.info(f"Extracted footprint from {s3_key}: {footprint.extent}")
        return footprint
        
    except ImportError as e:
        logger.warning(f"GDAL (osgeo) not installed, cannot extract footprint: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to extract footprint from {s3_key}: {e}", exc_info=True)
        return None


def extract_footprint_from_file(
    file_path: str,
) -> Optional[Polygon]:
    """
    Extract geospatial footprint from a local GeoTIFF file.
    
    Args:
        file_path: Path to the GeoTIFF file
        
    Returns:
        Polygon in EPSG:4326, or None if extraction fails
    """
    try:
        from osgeo import gdal, osr
        
        ds = gdal.Open(file_path, gdal.GA_ReadOnly)
        if ds is None:
            logger.warning(f"Could not open {file_path} with GDAL")
            return None
        
        # Get geotransform
        gt = ds.GetGeoTransform()
        if gt is None:
            logger.warning(f"No geotransform found in {file_path}")
            ds = None
            return None
        
        # Calculate bounds
        width = ds.RasterXSize
        height = ds.RasterYSize
        
        min_x = gt[0]
        max_x = gt[0] + width * gt[1]
        max_y = gt[3]
        min_y = gt[3] + height * gt[5]
        
        # Get source CRS
        src_srs = osr.SpatialReference()
        src_srs.ImportFromWkt(ds.GetProjection())
        
        if src_srs.IsEmpty():
            logger.warning(f"No CRS found in {file_path}, cannot extract footprint")
            ds = None
            return None
        
        # Transform to WGS84 if needed
        tgt_srs = osr.SpatialReference()
        tgt_srs.ImportFromEPSG(4326)
        tgt_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        
        if not src_srs.IsSame(tgt_srs):
            transform = osr.CoordinateTransformation(src_srs, tgt_srs)
            
            ll = transform.TransformPoint(min_x, min_y)
            lr = transform.TransformPoint(max_x, min_y)
            ur = transform.TransformPoint(max_x, max_y)
            ul = transform.TransformPoint(min_x, max_y)
            
            west = min(ll[0], ul[0])
            east = max(lr[0], ur[0])
            south = min(ll[1], lr[1])
            north = max(ul[1], ur[1])
        else:
            west, south, east, north = min_x, min_y, max_x, max_y
        
        ds = None  # Close dataset
        
        # Create polygon from bounds
        coords = [
            (west, south),
            (east, south),
            (east, north),
            (west, north),
            (west, south),
        ]
        
        footprint = Polygon(coords, srid=4326)
        
        logger.info(f"Extracted footprint from {file_path}: {footprint.extent}")
        return footprint
        
    except ImportError as e:
        logger.warning(f"GDAL (osgeo) not installed, cannot extract footprint: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to extract footprint from {file_path}: {e}", exc_info=True)
        return None


def extract_raster_metadata(
    s3_key: str,
    bucket: str,
) -> Optional[dict]:
    """
    Extract metadata from a raster file stored in S3.
    
    Args:
        s3_key: S3 object key
        bucket: S3 bucket name
        
    Returns:
        Dict with width, height, bands, resolution, crs, etc.
    """
    try:
        from osgeo import gdal
        
        vsi_path = f"/vsis3/{bucket}/{s3_key}"
        
        ds = gdal.Open(vsi_path, gdal.GA_ReadOnly)
        if ds is None:
            logger.warning(f"Could not open {vsi_path} with GDAL")
            return None
        
        gt = ds.GetGeoTransform()
        
        # Calculate resolution from geotransform
        res_x = abs(gt[1]) if gt else None
        res_y = abs(gt[5]) if gt else None
        
        # Get bounds
        if gt:
            width = ds.RasterXSize
            height = ds.RasterYSize
            bounds = {
                'left': gt[0],
                'top': gt[3],
                'right': gt[0] + width * gt[1],
                'bottom': gt[3] + height * gt[5],
            }
        else:
            bounds = None
        
        metadata = {
            'width': ds.RasterXSize,
            'height': ds.RasterYSize,
            'bands': ds.RasterCount,
            'dtype': gdal.GetDataTypeName(ds.GetRasterBand(1).DataType) if ds.RasterCount > 0 else None,
            'crs': ds.GetProjection() if ds.GetProjection() else None,
            'resolution_x': res_x,
            'resolution_y': res_y,
            'bounds': bounds,
            'nodata': ds.GetRasterBand(1).GetNoDataValue() if ds.RasterCount > 0 else None,
        }
        
        ds = None  # Close dataset
        
        return metadata
        
    except ImportError as e:
        logger.warning(f"GDAL (osgeo) not installed, cannot extract metadata: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to extract metadata from {s3_key}: {e}", exc_info=True)
        return None


# Product types that support footprint extraction
GEOSPATIAL_PRODUCT_TYPES = [
    'orthomosaic',
    'dsm',
    'dem',
    'hillshade',
]
