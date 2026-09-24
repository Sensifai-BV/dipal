"""Classify individual images into spectral band types.

Uses a priority chain:
  1. XMP BandName  (DJI / MicaSense)
  2. Filename patterns  (DJI suffix conventions)
  3. EXIF sensor / channel heuristics
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from infrastructure.logging import get_logger

from .metadata_reader import extract_all_metadata
from .models import (
    DJI_BAND_NAME_MAP,
    DJI_FILENAME_BAND_PATTERNS,
    GENERIC_FILENAME_BAND_PATTERNS,
    MICASENSE_BAND_NAME_MAP,
    BandType,
    DroneManufacturer,
    ImageBandInfo,
)

logger = get_logger(__name__)


def _detect_manufacturer(metadata: dict[str, object]) -> DroneManufacturer:
    """
    Detect the drone / camera manufacturer from metadata.

    Args:
        metadata: Merged EXIF + XMP metadata dictionary

    Returns:
        Detected manufacturer enum value
    """
    make = str(metadata.get("Make", "")).lower()
    model = str(metadata.get("DroneModel", "")).lower()
    software = str(metadata.get("Software", "")).lower()

    if "dji" in make or "dji" in model or "dji" in software:
        return DroneManufacturer.DJI

    if "micasense" in make or "micasense" in model or "micasense" in software:
        return DroneManufacturer.MICASENSE

    camera_model = str(metadata.get("Model", "")).lower()
    if "rededge" in camera_model or "altum" in camera_model:
        return DroneManufacturer.MICASENSE

    if "parrot" in make:
        return DroneManufacturer.PARROT

    return DroneManufacturer.UNKNOWN


def _classify_from_xmp_band_name(
    metadata: dict[str, object],
    manufacturer: DroneManufacturer,
) -> tuple[BandType, str] | None:
    """
    Attempt classification from XMP BandName tag.

    Args:
        metadata: Merged metadata dictionary
        manufacturer: Detected manufacturer

    Returns:
        Tuple of (BandType, raw_band_name) or None if not found
    """
    raw_name = str(metadata.get("BandName", "")).strip()
    if not raw_name:
        return None

    lookup_map = (
        MICASENSE_BAND_NAME_MAP
        if manufacturer == DroneManufacturer.MICASENSE
        else DJI_BAND_NAME_MAP
    )

    for key, band_type in lookup_map.items():
        if raw_name.lower() == key.lower():
            return band_type, raw_name

    for key, band_type in DJI_BAND_NAME_MAP.items():
        if raw_name.lower() == key.lower():
            return band_type, raw_name
    for key, band_type in MICASENSE_BAND_NAME_MAP.items():
        if raw_name.lower() == key.lower():
            return band_type, raw_name

    logger.debug(f"Unknown BandName value: '{raw_name}'")
    return None


def _classify_from_filename(file_name: str) -> tuple[BandType, str] | None:
    """
    Attempt classification from filename suffix conventions.

    Checks DJI-specific patterns first (longer, more specific), then
    generic patterns (Parrot Sequoia, Sentera, etc.).

    Args:
        file_name: Image file name (stem, no extension)

    Returns:
        Tuple of (BandType, matched_pattern) or None
    """
    upper = file_name.upper()
    for suffix, band_type in sorted(
        DJI_FILENAME_BAND_PATTERNS.items(), key=lambda x: -len(x[0])
    ):
        if upper.endswith(suffix.upper()):
            return band_type, suffix

    for suffix, band_type in sorted(
        GENERIC_FILENAME_BAND_PATTERNS.items(), key=lambda x: -len(x[0])
    ):
        if upper.endswith(suffix.upper()):
            return band_type, f"generic{suffix}"

    return None


def _classify_from_channels(image_path: Path) -> tuple[BandType, str]:
    """
    Fallback classification based on image channel count.

    Args:
        image_path: Path to image file

    Returns:
        Tuple of (BandType, detection_reason)
    """
    try:
        with Image.open(image_path) as img:
            mode = img.mode
            if mode in ("RGB", "RGBA", "YCbCr"):
                return BandType.RGB, f"channel_mode={mode}"
            if mode in ("L", "I", "I;16", "I;16B", "F"):
                return BandType.UNKNOWN, f"single_channel_mode={mode}"
    except Exception as exc:
        logger.warning(f"Cannot open {image_path.name} to check channels: {exc}")
    return BandType.UNKNOWN, "fallback"


def classify_image(image_path: Path) -> ImageBandInfo:
    """
    Classify a single image into its spectral band type.

    Priority:
      1. XMP BandName metadata
      2. DJI filename suffix conventions
      3. Image channel count heuristic

    Args:
        image_path: Absolute path to the image file

    Returns:
        ImageBandInfo with classification result
    """
    metadata = extract_all_metadata(image_path)
    manufacturer = _detect_manufacturer(metadata)
    drone_model = (
        str(metadata.get("DroneModel"))
        if metadata.get("DroneModel")
        else str(metadata.get("Model")) if metadata.get("Model") else None
    )

    sensor_index_raw = metadata.get("SensorIndex")
    sensor_index = (
        int(sensor_index_raw)
        if sensor_index_raw is not None and str(sensor_index_raw).strip()
        else None
    )

    wavelength_raw = metadata.get("CentralWavelength")
    center_wavelength = (
        float(wavelength_raw)
        if wavelength_raw is not None and str(wavelength_raw).strip()
        else None
    )

    xmp_result = _classify_from_xmp_band_name(metadata, manufacturer)
    if xmp_result:
        band_type, raw_name = xmp_result
        return ImageBandInfo(
            file_path=str(image_path),
            file_name=image_path.name,
            band_type=band_type,
            band_name_raw=raw_name,
            manufacturer=manufacturer,
            drone_model=drone_model,
            sensor_index=sensor_index,
            center_wavelength_nm=center_wavelength,
            detection_method="xmp_band_name",
            confidence=0.95,
        )

    filename_result = _classify_from_filename(image_path.stem)
    if filename_result:
        band_type, pattern = filename_result
        return ImageBandInfo(
            file_path=str(image_path),
            file_name=image_path.name,
            band_type=band_type,
            band_name_raw=None,
            manufacturer=manufacturer,
            drone_model=drone_model,
            sensor_index=sensor_index,
            center_wavelength_nm=center_wavelength,
            detection_method=f"filename_pattern={pattern}",
            confidence=0.80,
        )

    band_type, reason = _classify_from_channels(image_path)
    return ImageBandInfo(
        file_path=str(image_path),
        file_name=image_path.name,
        band_type=band_type,
        band_name_raw=None,
        manufacturer=manufacturer,
        drone_model=drone_model,
        sensor_index=sensor_index,
        center_wavelength_nm=center_wavelength,
        detection_method=f"channel_heuristic={reason}",
        confidence=0.50 if band_type == BandType.RGB else 0.30,
    )
