"""
Vegetation index computation from orthorectified multispectral bands.

Computes NDVI, NDRE, and GNDVI from single-band reflectance GeoTIFFs
and writes each index as a Cloud Optimized GeoTIFF (COG).

Band mapping (expected input):
  - green_ortho.tif  → Green reflectance
  - red_ortho.tif    → Red reflectance
  - red_edge_ortho.tif → Red Edge reflectance
  - nir_ortho.tif    → NIR reflectance
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from services.orthomosaic_generation.logger import logger

try:
    from osgeo import gdal

    gdal.UseExceptions()
except ImportError:
    gdal = None


def compute_vegetation_indices(
    band_ortho_paths: dict[str, str],
    output_dir: str,
) -> dict[str, str]:
    """
    Compute all available vegetation indices from orthorectified bands.

    Args:
        band_ortho_paths: Mapping of band_name → GeoTIFF path
                          (keys: green, red, red_edge, nir)
        output_dir: Directory for output index GeoTIFFs

    Returns:
        Mapping of index_name → output GeoTIFF path
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    indices: dict[str, str] = {}

    nir_path = band_ortho_paths.get("nir")
    red_path = band_ortho_paths.get("red")
    re_path = band_ortho_paths.get("red_edge")
    green_path = band_ortho_paths.get("green")

    if nir_path and red_path:
        ndvi_out = out / "ndvi.tif"
        _normalised_difference(nir_path, red_path, str(ndvi_out), "NDVI")
        indices["ndvi"] = str(ndvi_out)

    if nir_path and re_path:
        ndre_out = out / "ndre.tif"
        _normalised_difference(nir_path, re_path, str(ndre_out), "NDRE")
        indices["ndre"] = str(ndre_out)

    if nir_path and green_path:
        gndvi_out = out / "gndvi.tif"
        _normalised_difference(nir_path, green_path, str(gndvi_out), "GNDVI")
        indices["gndvi"] = str(gndvi_out)

    logger.info(f"Computed {len(indices)} vegetation indices: {list(indices.keys())}")
    return indices


def _normalised_difference(
    band_a_path: str,
    band_b_path: str,
    output_path: str,
    label: str,
) -> None:
    """
    Compute normalised difference index: (A - B) / (A + B).

    Result is clipped to [-1, 1] and stored as Float32 GeoTIFF.

    Args:
        band_a_path: Path to numerator-positive band (e.g. NIR)
        band_b_path: Path to numerator-negative band (e.g. Red)
        output_path: Destination GeoTIFF
        label: Human-readable name for logging
    """
    if gdal is None:
        raise RuntimeError("GDAL Python bindings are required")

    logger.info(f"Computing {label}: {band_a_path}, {band_b_path}")

    ds_a = gdal.Open(band_a_path, gdal.GA_ReadOnly)
    ds_b = gdal.Open(band_b_path, gdal.GA_ReadOnly)

    if ds_a is None or ds_b is None:
        raise FileNotFoundError(f"Cannot open input bands for {label}")

    band_a = ds_a.GetRasterBand(1)
    band_b = ds_b.GetRasterBand(1)

    a = band_a.ReadAsArray().astype(np.float32)
    b = band_b.ReadAsArray().astype(np.float32)

    nd_a = band_a.GetNoDataValue()
    nd_b = band_b.GetNoDataValue()

    # Mask nodata pixels: a pixel is invalid if either input band is nodata.
    _NODATA_OUT = -9999.0
    nodata_mask = np.zeros(a.shape, dtype=bool)
    if nd_a is not None:
        nodata_mask |= (a == np.float32(nd_a))
    if nd_b is not None:
        nodata_mask |= (b == np.float32(nd_b))
    # Also treat non-finite values as nodata.
    nodata_mask |= ~np.isfinite(a) | ~np.isfinite(b)

    denominator = a + b
    denominator[denominator == 0] = 1e-10

    index = np.clip((a - b) / denominator, -1.0, 1.0).astype(np.float32)
    index[nodata_mask] = _NODATA_OUT

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(
        output_path,
        ds_a.RasterXSize,
        ds_a.RasterYSize,
        1,
        gdal.GDT_Float32,
        options=["COMPRESS=DEFLATE", "TILED=YES"],
    )
    out_ds.SetGeoTransform(ds_a.GetGeoTransform())
    out_ds.SetProjection(ds_a.GetProjection())
    out_ds.GetRasterBand(1).WriteArray(index)
    out_ds.GetRasterBand(1).SetNoDataValue(_NODATA_OUT)
    out_ds.FlushCache()
    out_ds = None
    ds_a = None
    ds_b = None

    logger.info(f"{label} written to {output_path}")


def convert_index_to_cog(input_path: str, output_path: str | None = None) -> str:
    """
    Convert a vegetation index GeoTIFF to Cloud Optimized GeoTIFF.

    Args:
        input_path: Source index GeoTIFF
        output_path: Destination COG path (default: replaces _suffix with _cog)

    Returns:
        Path to the COG file
    """
    if output_path is None:
        p = Path(input_path)
        output_path = str(p.with_name(p.stem + "_cog.tif"))

    cmd = [
        "gdal_translate",
        "-of", "COG",
        "-co", "COMPRESS=DEFLATE",
        "-co", "BLOCKSIZE=512",
        "-co", "OVERVIEW_RESAMPLING=AVERAGE",
        input_path,
        output_path,
    ]

    logger.info(f"Converting {input_path} to COG")
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    if result.stdout:
        logger.debug(result.stdout[:300])

    return output_path
