from __future__ import annotations

import asyncio
import json
import math
import shutil
from pathlib import Path

import httpx
import cv2
import numpy as np

try:
    from osgeo import gdal as _gdal, osr as _osr
    _gdal.UseExceptions()
except ImportError:
    _gdal = None
    _osr = None

try:
    from PIL import Image as _PILImage
    from PIL.ExifTags import GPSTAGS as _GPSTAGS
except ImportError:
    _PILImage = None
    _GPSTAGS = {}

# Default camera HFOV for GSD estimation when focal data is unavailable.
_DEFAULT_HFOV_DEG: float = 65.0
from fastapi import APIRouter
from lagom.integrations.fast_api import FastApiIntegration

from infrastructure.logging import get_logger
from infrastructure.message_queue import BackgroundTaskHandler
from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.factory import StorageDriverFactory
from shared.band_detection import (
    BandType,
    DatasetBandManifest,
    DroneManufacturer,
    organize_by_band,
    scan_dataset,
)
from shared.band_detection.organizer import BAND_FOLDER_NAMES, load_manifest

from ....core.services.factory import DroneImageProcessorFactory
from ....core.services.interfaces import IDroneImageProcessor
from ....core.settings import CallbackSettings, S3Settings, TempStorageSettings
from ....entities import (
    CalibrationJobRequest,
    CalibrationJobResponse,
    CalibrationJobStatusResponse,
    NDVICalculationInput,
)
from ...base_endpoint import BaseEndpoint

logger = get_logger(__name__)

callback_settings = CallbackSettings()
s3_settings = S3Settings()
temp_settings = TempStorageSettings()

BAND_TO_PROCESSOR_BAND: dict[BandType, str] = {
    BandType.GREEN: "Green",
    BandType.RED: "Red",
    BandType.RED_EDGE: "RedEdge",
    BandType.NIR: "NIR",
    BandType.BLUE: "Blue",
}


class CalibrationEndpoint(BaseEndpoint):
    """Radiometric calibration API endpoint."""

    def __init__(self, deps: FastApiIntegration) -> None:
        self.deps = deps
        self._router = APIRouter(prefix="/calibration", tags=["calibration"])

    @property
    def router(self) -> APIRouter:
        return self._router

    def register_api(self) -> None:
        @self._router.post("/run", response_model=CalibrationJobResponse)
        async def run_calibration(
            request: CalibrationJobRequest,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
        ):
            """Start radiometric calibration job."""
            job_id = request.job_id
            logger.info(f"[CALIBRATION] Received request for job {job_id}")

            background_task_handler.create_job(
                job_id,
                metadata={
                    "dataset_id": request.dataset_id,
                    "download_url": request.download_url,
                    "parameters": request.parameters,
                },
            )

            background_task_handler.start_background_task(
                job_id,
                run_calibration_task,
                job_id,
                request.dataset_id,
                request.download_url,
                request.parameters or {},
            )

            return CalibrationJobResponse(
                job_id=job_id, status="running", message="Calibration job started"
            )

        @self._router.get(
            "/jobs/{job_id}/status",
            response_model=CalibrationJobStatusResponse,
        )
        async def get_job_status(
            job_id: str,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
        ):
            """Get calibration job status."""
            task_status = background_task_handler.get_task_status(job_id)
            return CalibrationJobStatusResponse(
                job_id=job_id,
                status=task_status.get("status", "not_found"),
                progress=task_status.get("progress"),
                result=task_status.get("result"),
                error=task_status.get("error"),
            )

        @self._router.post(
            "/jobs/{job_id}/cancel",
            response_model=CalibrationJobResponse,
        )
        async def cancel_job(
            job_id: str,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
        ):
            """Cancel calibration job."""
            cancelled = background_task_handler.cancel_job(job_id)
            return CalibrationJobResponse(
                job_id=job_id,
                status="cancelled" if cancelled else "not_found",
                message="Job cancelled" if cancelled else "Job not found",
            )

        @self._router.get("/jobs/{job_id}/result")
        async def get_job_result(
            job_id: str,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
        ):
            """Get calibration job result."""
            task_status = background_task_handler.get_task_status(job_id)
            if task_status.get("status") == "completed":
                return task_status.get("result", {})
            return {"error": "Job not completed or not found"}

        @self._router.post("/ndvi-calculation")
        async def ndvi_calculation(ndvi_input: NDVICalculationInput):
            """Legacy NDVI endpoint (deprecated)."""


# ---------------------------------------------------------------------------
# Callback helper
# ---------------------------------------------------------------------------

async def send_callback(
    job_id: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    """
    Send completion / failure callback to API Gateway.

    Args:
        job_id: Sub-job ID (may contain _calibration suffix)
        status: 'completed' or 'failed'
        result: Result payload for completed jobs
        error: Error message for failed jobs
    """
    callback_url = callback_settings.callback_url
    main_job_id = job_id.replace("_calibration", "")

    payload = {
        "job_id": main_job_id,
        "service": "calibration",
        "status": status,
        "result": result,
        "error": error,
    }

    logger.info(f"Sending callback to {callback_url} for job {main_job_id}: status={status}")

    try:
        async with httpx.AsyncClient(timeout=callback_settings.timeout_seconds) as client:
            response = await client.post(callback_url, json=payload)
            if response.status_code == 200:
                logger.info(f"Callback sent successfully for job {main_job_id}")
            else:
                logger.error(
                    f"Callback failed for job {main_job_id}: "
                    f"{response.status_code} - {response.text}"
                )
    except Exception as exc:
        logger.error(f"Failed to send callback for job {main_job_id}: {exc}")


# ---------------------------------------------------------------------------
# Image download helper (reusable)
# ---------------------------------------------------------------------------

async def _download_images(
    dataset_id: str,
    download_url: str | list,
    base_path: Path,
) -> Path:
    """
    Download images to shared volume if not already present.

    Args:
        dataset_id: Dataset identifier
        download_url: S3 URI, presigned URL, or list of presigned URLs
        base_path: Temp storage base path

    Returns:
        Path to the images directory
    """
    images_path = base_path / "datasets" / dataset_id / "images"

    if images_path.exists() and any(images_path.iterdir()):
        logger.info(f"Images already present at {images_path}")
        return images_path

    logger.info(f"Images not found at {images_path}, downloading...")

    if isinstance(download_url, list):
        driver = StorageDriverFactory.create(
            "presigned_url",
            {"project_urls": {dataset_id: {"images": download_url}}},
        )
    elif isinstance(download_url, str) and download_url.startswith("s3://"):
        s3_parts = download_url.replace("s3://", "").split("/", 1)
        bucket_name = s3_parts[0]
        full_path = s3_parts[1].rstrip("/") if len(s3_parts) > 1 else ""
        prefix = "/".join(full_path.split("/")[:-1]) if "/" in full_path else ""
        driver = StorageDriverFactory.create(
            "s3", {"bucket_name": bucket_name, "prefix": prefix}
        )
    else:
        driver = StorageDriverFactory.create(
            "presigned_url",
            {"project_urls": {dataset_id: {"download_url": download_url}}},
        )

    driver.connect()
    dataset = Dataset(
        project_id=dataset_id, storage_driver=driver, temp_base_path=base_path
    )
    await asyncio.to_thread(dataset.initialize_dataset)
    await asyncio.to_thread(dataset.fetch_images)
    driver.disconnect()

    logger.info(f"Downloaded images to {images_path}")
    return images_path


def _has_organized_bands(dataset_dir: Path) -> bool:
    """
    Check if band folders already contain organized images from a prior run.

    Args:
        dataset_dir: Root dataset directory

    Returns:
        True if any band folder has image files
    """
    for folder_name in BAND_FOLDER_NAMES.values():
        band_dir = dataset_dir / folder_name
        if band_dir.is_dir() and any(band_dir.iterdir()):
            return True
    return False


def _rebuild_manifest_from_bands(
    dataset_dir: Path,
    dataset_id: str,
) -> DatasetBandManifest:
    """
    Rebuild complete manifest by scanning existing band folders.

    Used on re-runs when images are already organized into band
    folders from a previous calibration.

    Args:
        dataset_dir: Root dataset directory with band subfolders
        dataset_id: Dataset identifier

    Returns:
        DatasetBandManifest built from all organized band folders
    """
    merged = DatasetBandManifest(dataset_id=dataset_id, total_images=0)

    for folder_name in BAND_FOLDER_NAMES.values():
        band_dir = dataset_dir / folder_name
        if not band_dir.is_dir():
            continue

        partial = scan_dataset(band_dir, dataset_id, recursive=False)
        for band_key, group in partial.bands.items():
            if band_key in merged.bands:
                merged.bands[band_key].images.extend(group.images)
            else:
                merged.bands[band_key] = group
        merged.total_images += partial.total_images

        if partial.manufacturer != DroneManufacturer.UNKNOWN:
            merged.manufacturer = partial.manufacturer
        if partial.drone_model:
            merged.drone_model = partial.drone_model

    merged.is_multispectral = sum(
        1 for k in merged.bands if k != BandType.RGB.value
    ) > 0

    logger.info(
        f"[CALIBRATION] Rebuilt manifest from band folders: "
        f"{merged.total_images} images across {len(merged.bands)} bands"
    )
    return merged


async def _load_or_scan_images(
    dataset_id: str,
    download_url: str | list,
    base_path: Path,
    dataset_dir: Path,
) -> DatasetBandManifest:
    """
    Load existing band manifest or download, scan, and organize images.

    On first run: downloads images, scans them, and organizes into
    band folders. On re-runs: detects existing band folders and
    rebuilds the manifest from them instead of re-scanning the
    (potentially incomplete) images/ directory.

    Args:
        dataset_id: Dataset identifier
        download_url: S3 URI, presigned URL, or list of presigned URLs
        base_path: Temp storage base path
        dataset_dir: Root dataset directory

    Returns:
        Complete DatasetBandManifest
    """
    if _has_organized_bands(dataset_dir):
        logger.info(
            f"[CALIBRATION] Band folders exist for {dataset_id}, "
            f"rebuilding manifest from organized data"
        )
        return _rebuild_manifest_from_bands(dataset_dir, dataset_id)

    images_path = await _download_images(dataset_id, download_url, base_path)

    manifest = scan_dataset(images_path, dataset_id, True)
    logger.info(
        f"[CALIBRATION] Band detection: {manifest.total_images} images, "
        f"multispectral={manifest.is_multispectral}, "
        f"manufacturer={manifest.manufacturer.value}"
    )

    organize_by_band(manifest, dataset_dir, True)
    return manifest


# ---------------------------------------------------------------------------
# Core calibration logic (runs in thread pool)
# ---------------------------------------------------------------------------

def _calibrate_multispectral_images(
    manifest: DatasetBandManifest,
    dataset_dir: Path,
    output_dir: Path,
    processor: IDroneImageProcessor,
) -> dict:
    """
    Calibrate multispectral band images with reflectance conversion.

    For each spectral band image:
      1. Geometric corrections (vignetting, distortion, homography)
      2. DN-to-reflectance conversion using irradiance metadata
      3. Save as float32 GeoTIFF (0-1 reflectance range)

    Vegetation indices (NDVI, NDRE, GNDVI) are NOT generated here.
    They are computed from orthomosaic-stitched band rasters in a later stage.

    Args:
        manifest: Band classification manifest
        dataset_dir: Root dataset directory (with band subfolders)
        output_dir: Job output directory
        processor: Drone-specific image processor

    Returns:
        Result dictionary with paths and statistics
    """
    calibrated_dir = output_dir / "calibrated_images"
    calibrated_dir.mkdir(parents=True, exist_ok=True)

    calibrated_counts: dict[str, int] = {}
    reflectance_counts: dict[str, int] = {}
    failed_images: list[str] = []
    total_processed = 0

    spectral_bands = [
        BandType.GREEN,
        BandType.RED,
        BandType.RED_EDGE,
        BandType.NIR,
        BandType.BLUE,
    ]

    for band_type in spectral_bands:
        band_key = band_type.value
        group = manifest.bands.get(band_key)
        if not group or group.count == 0:
            continue

        proc_band = BAND_TO_PROCESSOR_BAND.get(band_type)
        if not proc_band:
            continue

        band_out = calibrated_dir / band_key
        band_out.mkdir(parents=True, exist_ok=True)
        band_count = 0
        refl_count = 0

        for info in group.images:
            src = Path(info.file_path)
            if not src.exists():
                failed_images.append(f"{src.name}: file not found")
                continue

            try:
                processor.load_image(src, proc_band)
                processor.process_all_steps(proc_band)

                reflectance = processor.calculate_reflectance(proc_band)

                out_path = band_out / (src.stem + "_reflectance.tif")
                _save_reflectance_image(reflectance, out_path, source_image_path=src)
                refl_count += 1

                band_count += 1
                total_processed += 1
            except Exception as exc:
                failed_images.append(f"{src.name}: {exc}")
                logger.warning(f"Calibration failed for {src.name}: {exc}")

        calibrated_counts[band_key] = band_count
        reflectance_counts[band_key] = refl_count
        logger.info(
            f"Calibrated {band_count} {band_key} images "
            f"({refl_count} with reflectance)"
        )

    rgb_group = manifest.bands.get(BandType.RGB.value)
    if rgb_group and rgb_group.count > 0:
        rgb_out = calibrated_dir / "rgb"
        rgb_out.mkdir(parents=True, exist_ok=True)
        rgb_count = 0
        for info in rgb_group.images:
            src = Path(info.file_path)
            if src.exists():
                shutil.copy2(str(src), str(rgb_out / src.name))
                rgb_count += 1
                total_processed += 1
        calibrated_counts["rgb"] = rgb_count
        logger.info(f"Copied {rgb_count} RGB images (no spectral calibration needed)")

    return {
        "calibrated_dir": str(calibrated_dir),
        "calibrated_counts": calibrated_counts,
        "reflectance_counts": reflectance_counts,
        "has_reflectance": True,
        "total_processed": total_processed,
        "total_failed": len(failed_images),
        "failed_images": failed_images[:20],
    }


def _calibrate_rgb_only(
    manifest: DatasetBandManifest,
    dataset_dir: Path,
    output_dir: Path,
) -> dict:
    """
    Handle RGB-only datasets (no spectral calibration, passthrough copy).

    Args:
        manifest: Band manifest
        dataset_dir: Root dataset directory
        output_dir: Job output directory

    Returns:
        Result dictionary
    """
    calibrated_dir = output_dir / "calibrated_images" / "rgb"
    calibrated_dir.mkdir(parents=True, exist_ok=True)

    rgb_group = manifest.bands.get(BandType.RGB.value)
    if not rgb_group:
        raise ValueError("No RGB images found in dataset")

    copied = 0
    for info in rgb_group.images:
        src = Path(info.file_path)
        if src.exists():
            shutil.copy2(str(src), str(calibrated_dir / src.name))
            copied += 1

    logger.info(f"RGB-only dataset: copied {copied} images (no spectral calibration)")

    return {
        "calibrated_dir": str(output_dir / "calibrated_images"),
        "calibrated_counts": {"rgb": copied},
        "total_processed": copied,
        "total_failed": 0,
        "failed_images": [],
    }


def _extract_gps_for_reflectance(
    source_image_path: Path,
) -> tuple[float, float, float] | None:
    """
    Extract (latitude, longitude, altitude_m) from source image GPS EXIF.

    Returns None when GPS data is absent or Pillow is unavailable.
    """
    if _PILImage is None:
        return None
    try:
        with _PILImage.open(str(source_image_path)) as img:
            exif = img.getexif()
            if not exif:
                return None
            gps_ifd = exif.get_ifd(0x8825)
            if not gps_ifd:
                return None
            gps = {_GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}

            lat_dms = gps.get("GPSLatitude")
            lon_dms = gps.get("GPSLongitude")
            if lat_dms is None or lon_dms is None:
                return None

            def _dms(dms, ref):
                d, m, s = dms
                v = float(d) + float(m) / 60.0 + float(s) / 3600.0
                return -v if ref in ("S", "W") else v

            lat = _dms(lat_dms, gps.get("GPSLatitudeRef", "N"))
            lon = _dms(lon_dms, gps.get("GPSLongitudeRef", "E"))
            alt_tag = gps.get("GPSAltitude")
            alt_m = float(alt_tag) if alt_tag is not None else 100.0
            if gps.get("GPSAltitudeRef", 0) == 1:
                alt_m = -alt_m
            return lat, lon, alt_m
    except Exception as exc:
        logger.debug(f"GPS extraction failed for {source_image_path.name}: {exc}")
        return None


def _save_reflectance_image(
    reflectance: np.ndarray,
    output_path: Path,
    source_image_path: Path | None = None,
) -> None:
    """
    Save a reflectance image (0-1 float) as a georeferenced float32 GeoTIFF.

    When ``source_image_path`` is supplied and contains GPS EXIF, the output
    is written via GDAL with a WGS84 geotransform derived from the image
    centre GPS position and an altitude-based GSD estimate.  This makes each
    calibrated reflectance TIFF spatially referenced so it can be inspected
    in GIS tools and consumed by downstream analytics services.

    Falls back to a plain ``cv2.imwrite`` when GPS is unavailable or GDAL is
    not installed.

    Args:
        reflectance: Reflectance array in 0-1 range
        output_path: Destination path (.tif)
        source_image_path: Original drone image to read GPS EXIF from
    """
    img = reflectance.astype(np.float32)

    gps = None
    if source_image_path is not None and _gdal is not None and _osr is not None:
        gps = _extract_gps_for_reflectance(source_image_path)

    if gps is None or _gdal is None or _osr is None:
        # Fallback: plain TIFF with no spatial reference
        cv2.imwrite(str(output_path), img)
        return

    lat, lon, alt_m = gps
    h, w = img.shape[:2]

    # Estimate GSD from altitude and default HFOV
    hfov_rad = math.radians(_DEFAULT_HFOV_DEG)
    ground_width_m = 2.0 * max(alt_m, 1.0) * math.tan(hfov_rad / 2.0)
    gsd_m = ground_width_m / w
    lat_rad = math.radians(lat)
    px_deg_x = gsd_m / (111320.0 * math.cos(lat_rad))
    px_deg_y = gsd_m / 111320.0

    # Read yaw from XMP so the geotransform matches actual image orientation.
    # Without this, axis-aligned footprints misregister at image corners when
    # the drone is not flying due north.
    yaw_deg = 0.0
    try:
        with open(source_image_path, "rb") as _fh:
            _raw = _fh.read()
        _xs = _raw.find(b"<x:xmpmeta")
        _xe = _raw.find(b"</x:xmpmeta>")
        if _xs != -1 and _xe != -1:
            import re as _re
            _xmp = _raw[_xs : _xe + 12].decode("utf-8", errors="ignore")
            _m = _re.search(r'drone-dji:FlightYawDegree="([+-]?\d+\.?\d*)"', _xmp)
            if _m:
                yaw_deg = float(_m.group(1))
            else:
                _m = _re.search(r'drone-dji:GimbalYawDegree="([+-]?\d+\.?\d*)"', _xmp)
                if _m:
                    yaw_deg = float(_m.group(1))
    except Exception:
        pass

    # Build rotated geotransform: centre pixel == GPS point.
    # GDAL: X(col,row) = gt[0] + col*gt[1] + row*gt[2]
    #       Y(col,row) = gt[3] + col*gt[4] + row*gt[5]
    _yr = math.radians(yaw_deg)
    _cy, _sy = math.cos(_yr), math.sin(_yr)
    gt1 =  px_deg_x * _cy
    gt2 = -px_deg_y * _sy
    gt4 =  px_deg_x * _sy
    gt5 = -px_deg_y * _cy
    ul_lon = lon - (w / 2.0) * gt1 - (h / 2.0) * gt2
    ul_lat = lat - (w / 2.0) * gt4 - (h / 2.0) * gt5
    geotransform = (ul_lon, gt1, gt2, ul_lat, gt4, gt5)

    srs = _osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    # Nodata is -9999.0, consistent with the orthorectification pipeline.
    # 0.0 was used previously — wrong because valid low-reflectance pixels
    # (deep water, dark soil) are a legitimate value near zero.
    _REFL_NODATA = -9999.0

    driver = _gdal.GetDriverByName("GTiff")
    ds = driver.Create(
        str(output_path), w, h, 1, _gdal.GDT_Float32,
        ["COMPRESS=DEFLATE", "TILED=YES"],
    )
    ds.SetGeoTransform(geotransform)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.WriteArray(img)
    band.SetNoDataValue(_REFL_NODATA)
    ds.FlushCache()
    ds = None

    logger.debug(
        f"Geotagged reflectance saved: {output_path.name} "
        f"(lat={lat:.5f}, lon={lon:.5f}, alt={alt_m:.1f}m, gsd≈{gsd_m*100:.2f}cm)"
    )


def _save_image(image: np.ndarray, output_path: Path) -> None:
    """
    Save a corrected image array to disk (legacy uint16 format).

    Args:
        image: Image array (float64 or uint16)
        output_path: Destination path
    """
    if image.dtype == np.float64 or image.dtype == np.float32:
        max_val = np.max(image)
        if max_val > 0:
            scaled = np.clip(image / max_val * 65535, 0, 65535).astype(np.uint16)
        else:
            scaled = np.zeros_like(image, dtype=np.uint16)
    else:
        scaled = image

    cv2.imwrite(str(output_path), scaled)


# ---------------------------------------------------------------------------
# Main background task
# ---------------------------------------------------------------------------

async def run_calibration_task(
    job_id: str,
    dataset_id: str,
    download_url: str | list,
    parameters: dict,
) -> dict:
    """
    Full radiometric calibration pipeline.

    Steps:
      1. Download images (if not cached)
      2. Scan images → detect bands → organise into subfolders
      3. Choose appropriate drone processor
      4. Calibrate spectral bands (or passthrough for RGB-only)
      5. Send callback to API Gateway

    Vegetation indices (NDVI, NDRE, GNDVI) are NOT generated here.
    They are computed from orthomosaic-stitched band rasters in a later stage.

    Args:
        job_id: Calibration job ID (has _calibration suffix)
        dataset_id: Dataset identifier
        download_url: Source URL(s)
        parameters: Calibration parameters

    Returns:
        Result dictionary

    Directory layout after completion::

        temp/datasets/{dataset_id}/
        ├── rgb/
        ├── nir/
        ├── red/
        ├── red_edge/
        ├── green/
        ├── blue/
        └── metadata/band_manifest.json

        temp/jobs/radiometric/{job_id}/
        └── calibrated_images/
            ├── rgb/
            ├── nir/
            ├── red/
            └── ...
    """
    try:
        base_path = Path(temp_settings.base_path)
        dataset_dir = base_path / "datasets" / dataset_id
        job_workspace = base_path / "jobs" / "radiometric" / job_id
        calibrated_dir = job_workspace / "calibrated_images"

        if _has_existing_results(calibrated_dir):
            return await _send_cached_result(
                job_id, dataset_id, dataset_dir, job_workspace
            )

        logger.info(
            f"[CALIBRATION] Starting full processing for job {job_id}, "
            f"dataset {dataset_id}"
        )

        logger.info(f"[CALIBRATION] Step 1: Loading/scanning images for dataset {dataset_id}")
        manifest = await _load_or_scan_images(
            dataset_id, download_url, base_path, dataset_dir
        )
        logger.info(
            f"[CALIBRATION] Step 1 complete: multispectral={manifest.is_multispectral}, "
            f"bands={list(manifest.bands.keys()) if manifest.bands else 'none'}"
        )

        if manifest.is_multispectral:
            logger.info(f"[CALIBRATION] Step 2: Creating processor for multispectral calibration")
            processor = _create_processor(manifest, parameters)
            logger.info(f"[CALIBRATION] Step 3: Running multispectral calibration")
            cal_result = await asyncio.to_thread(
                _calibrate_multispectral_images,
                manifest,
                dataset_dir,
                job_workspace,
                processor,
            )
        else:
            logger.info(f"[CALIBRATION] Step 2: Running RGB-only calibration (passthrough)")
            cal_result = await asyncio.to_thread(
                _calibrate_rgb_only, manifest, dataset_dir, job_workspace
            )
        logger.info(
            f"[CALIBRATION] Calibration complete: processed={cal_result['total_processed']}, "
            f"failed={cal_result['total_failed']}"
        )

        result = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "dataset_dir": str(dataset_dir),
            "calibration_path": cal_result["calibrated_dir"],
            "images_path": str(dataset_dir / "rgb"),
            "band_manifest": manifest.model_dump(),
            "is_multispectral": manifest.is_multispectral,
            "has_reflectance": cal_result.get("has_reflectance", False),
            "calibrated_counts": cal_result["calibrated_counts"],
            "reflectance_counts": cal_result.get("reflectance_counts", {}),
            "total_processed": cal_result["total_processed"],
            "total_failed": cal_result["total_failed"],
            "status": "completed",
        }

        if cal_result["total_failed"] > 0:
            result["warnings"] = (
                f"{cal_result['total_failed']} images failed calibration"
            )
            result["failed_images"] = cal_result["failed_images"]

        await send_callback(job_id, "completed", result=result)
        return result

    except Exception as exc:
        logger.error(
            f"[CALIBRATION] Task failed for job {job_id}, dataset {dataset_id}: "
            f"{type(exc).__name__}: {exc}",
            exc_info=True,
        )
        await send_callback(job_id, "failed", error=f"{type(exc).__name__}: {exc}")
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_existing_results(calibrated_dir: Path) -> bool:
    """
    Check whether calibration results already exist on disk.

    Args:
        calibrated_dir: Path to calibrated_images directory

    Returns:
        True if usable results are present
    """
    if not calibrated_dir.exists():
        return False
    files = list(calibrated_dir.rglob("*"))
    return any(f.is_file() for f in files)


async def _send_cached_result(
    job_id: str,
    dataset_id: str,
    dataset_dir: Path,
    job_workspace: Path,
) -> dict:
    """
    Build and send result from previously cached calibration.

    Args:
        job_id: Job identifier
        dataset_id: Dataset identifier
        dataset_dir: Root dataset directory
        job_workspace: Job workspace directory

    Returns:
        Cached result dictionary
    """
    logger.info(f"[CALIBRATION] Using cached results for job {job_id}")

    # Restore band manifest so downstream stages (orthomosaic multispectral
    # pipeline) have is_multispectral and band_manifest available even when
    # calibration itself was skipped.
    manifest = load_manifest(dataset_dir)
    if manifest:
        logger.info(
            f"[CALIBRATION] Loaded cached band manifest: "
            f"is_multispectral={manifest.is_multispectral}, "
            f"bands={list(manifest.bands.keys()) if manifest.bands else 'none'}"
        )
    else:
        logger.warning(
            f"[CALIBRATION] No band manifest found at {dataset_dir}/metadata/band_manifest.json — "
            f"is_multispectral will default to False"
        )

    # Detect has_reflectance from the calibrated_images directory structure:
    # reflectance TIFFs are stored under calibrated_images/reflectance/ if present.
    calibrated_dir = job_workspace / "calibrated_images"
    reflectance_dir = calibrated_dir / "reflectance"
    has_reflectance = reflectance_dir.exists() and any(reflectance_dir.rglob("*.tif"))

    result = {
        "job_id": job_id,
        "dataset_id": dataset_id,
        "dataset_dir": str(dataset_dir),
        "calibration_path": str(calibrated_dir),
        "images_path": str(dataset_dir / "rgb"),
        "band_manifest": manifest.model_dump() if manifest else None,
        "is_multispectral": manifest.is_multispectral if manifest else False,
        "has_reflectance": has_reflectance,
        "status": "completed",
        "skipped_processing": True,
    }

    await send_callback(job_id, "completed", result=result)
    return result


def _create_processor(
    manifest: DatasetBandManifest,
    parameters: dict,
) -> IDroneImageProcessor:
    """
    Create the right image processor based on detected metadata.

    Args:
        manifest: Band manifest with manufacturer / drone model
        parameters: Calibration parameters (may override drone_type)

    Returns:
        Configured IDroneImageProcessor
    """
    explicit_type = parameters.get("drone_type")
    if explicit_type:
        from ....core.services.factory import DroneType
        return DroneImageProcessorFactory.create(DroneType(explicit_type))

    if manifest.drone_model:
        try:
            return DroneImageProcessorFactory.create_from_model_name(
                manifest.drone_model
            )
        except ValueError:
            logger.warning(
                f"Unknown drone model '{manifest.drone_model}', "
                f"falling back to manufacturer"
            )

    return DroneImageProcessorFactory.create_from_manufacturer(
        manifest.manufacturer.value,
        is_multispectral=manifest.is_multispectral,
    )
