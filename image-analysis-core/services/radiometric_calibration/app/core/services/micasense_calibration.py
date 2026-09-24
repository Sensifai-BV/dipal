"""MicaSense RedEdge / Altum multispectral image processor.

Parses MicaSense-specific XMP and EXIF metadata and delegates correction
algorithms to BaseDroneCalibrator.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from infrastructure.logging import get_logger
from shared.band_detection.metadata_reader import extract_all_metadata

from .base_calibrator import BaseDroneCalibrator
from .interfaces import CalibrationMetadata

logger = get_logger(__name__)

MICASENSE_BANDS = ["Blue", "Green", "Red", "RedEdge", "NIR"]


class MicaSenseImageProcessor(BaseDroneCalibrator):
    """
    MicaSense RedEdge / Altum multispectral image processor.

    Supports Blue, Green, Red, Red Edge, and NIR bands.
    MicaSense cameras store calibration data differently from DJI:
      - Vignetting polynomial in Camera:VignettingPolynomial
      - Dark level in EXIF BlackLevel / BlackLevelRepeatDim
      - Radiometric calibration coefficients in Camera namespace
    """

    def get_supported_bands(self) -> list[str]:
        """
        Return the bands this processor can handle.

        Returns:
            List of band name strings
        """
        return list(MICASENSE_BANDS)

    def extract_calibration_metadata(
        self, image_path: str | Path
    ) -> CalibrationMetadata:
        """
        Extract MicaSense-specific calibration metadata.

        Args:
            image_path: Path to the image file

        Returns:
            CalibrationMetadata populated from MicaSense XMP/EXIF
        """
        image_path = Path(image_path)
        raw = extract_all_metadata(image_path)

        band_name = _normalise_micasense_band(str(raw.get("BandName", "Unknown")))

        vig_str = str(raw.get("VignettingPolynomial", ""))
        vig_coeffs = _parse_float_list(vig_str)

        vig_center_str = str(raw.get("VignettingCenter", ""))
        vig_center = _parse_float_list(vig_center_str)
        vig_cx = vig_center[0] if len(vig_center) >= 1 else None
        vig_cy = vig_center[1] if len(vig_center) >= 2 else None

        dark_level = float(raw.get("BlackLevel", raw.get("DarkRowValue", 0)))

        gain = float(raw.get("ISOSpeed", raw.get("SensorGain", 1.0)))
        exposure = float(raw.get("ExposureTime", 0.001)) * 1e6

        irradiance = float(raw.get("Irradiance", 1.0))
        sensitivity = float(raw.get("BandSensitivity", 1.0))

        wavelength = _safe_float(raw.get("CentralWavelength"))

        with Image.open(image_path) as img:
            w, h = img.size

        return CalibrationMetadata(
            band_name=band_name,
            sensor_gain=gain,
            exposure_time_us=exposure,
            black_level=dark_level,
            sensor_gain_adjustment=sensitivity,
            irradiance=irradiance,
            bit_depth=int(raw.get("BitsPerSample", 16)),
            vignetting_center_x=vig_cx,
            vignetting_center_y=vig_cy,
            vignetting_coefficients=vig_coeffs,
            dewarp_params=[],
            homography_matrix=[],
            focal_length=_safe_float(raw.get("FocalLength")),
            image_width=w,
            image_height=h,
            raw_metadata=raw,
        )


def _normalise_micasense_band(raw_name: str) -> str:
    """
    Normalise MicaSense band names to standard form.

    Args:
        raw_name: Raw band name from metadata

    Returns:
        Normalised band name
    """
    mapping = {
        "blue": "Blue",
        "green": "Green",
        "red": "Red",
        "red edge": "RedEdge",
        "rededge": "RedEdge",
        "nir": "NIR",
        "near-ir": "NIR",
        "near ir": "NIR",
        "lwir": "Thermal",
    }
    return mapping.get(raw_name.lower().strip(), raw_name)


def _parse_float_list(value: str) -> list[float]:
    """
    Parse a comma or space separated string of floats.

    Args:
        value: Raw string value

    Returns:
        List of floats
    """
    if not value or not value.strip():
        return []
    separators = "," if "," in value else " "
    try:
        return [float(x.strip()) for x in value.split(separators) if x.strip()]
    except ValueError:
        return []


def _safe_float(value: object) -> float | None:
    """
    Safely convert a value to float.

    Args:
        value: Raw metadata value

    Returns:
        Float value or None if conversion fails
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
