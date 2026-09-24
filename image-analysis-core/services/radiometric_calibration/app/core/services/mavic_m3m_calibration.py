"""DJI Mavic 3M multispectral image processor.

Parses DJI-specific XMP metadata and delegates correction algorithms
to BaseDroneCalibrator.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from infrastructure.logging import get_logger
from shared.band_detection.metadata_reader import extract_all_metadata

from .base_calibrator import BaseDroneCalibrator
from .interfaces import CalibrationMetadata

logger = get_logger(__name__)

DJI_MULTISPECTRAL_BANDS = ["Green", "Red", "RedEdge", "NIR"]


class Mavic3MImageProcessor(BaseDroneCalibrator):
    """
    DJI Mavic 3M multispectral image processor.

    Supports Green, Red, RedEdge, and NIR bands from the
    multispectral camera, plus RGB from the wide camera.
    """

    def get_supported_bands(self) -> list[str]:
        """
        Return the bands this processor can handle.

        Returns:
            List of band name strings
        """
        return list(DJI_MULTISPECTRAL_BANDS)

    def extract_calibration_metadata(
        self, image_path: str | Path
    ) -> CalibrationMetadata:
        """
        Extract DJI-specific calibration metadata from XMP + EXIF.

        Args:
            image_path: Path to the image file

        Returns:
            CalibrationMetadata populated from DJI drone-dji namespace
        """
        image_path = Path(image_path)
        raw = extract_all_metadata(image_path)

        band_name = str(raw.get("BandName", "Unknown"))

        vignetting_str = str(raw.get("VignettingData", ""))
        vig_coeffs = (
            [float(x) for x in vignetting_str.split(",")]
            if vignetting_str
            else []
        )

        dewarp_str = str(raw.get("DewarpData", ""))
        dewarp_params: list[float] = []
        if dewarp_str:
            parts = dewarp_str.split(";")
            if len(parts) >= 2:
                dewarp_params = [float(x) for x in parts[1].split(",")]

        hmatrix_str = str(raw.get("CalibratedHMatrix", ""))
        hmatrix = (
            [float(x) for x in hmatrix_str.split(",")]
            if hmatrix_str
            else []
        )

        with Image.open(image_path) as img:
            w, h = img.size

        return CalibrationMetadata(
            band_name=band_name,
            sensor_gain=float(raw.get("SensorGain", 1.0)),
            exposure_time_us=float(raw.get("ExposureTime", 1000.0)),
            black_level=float(raw.get("BlackLevel") or raw.get("BlackCurrent", 3200.0)),
            sensor_gain_adjustment=float(raw.get("SensorGainAdjustment", 1.0)),
            irradiance=_extract_irradiance(raw, image_path),
            irradiance_exposure_time=_positive_float(
                raw.get("IrradianceExposureTime"), 1.0,
            ),
            irradiance_gain=_positive_float(raw.get("IrradianceGain"), 1.0),
            bit_depth=int(raw.get("BitsPerSample", 16)),
            vignetting_center_x=_safe_float(raw.get("CalibratedOpticalCenterX")),
            vignetting_center_y=_safe_float(raw.get("CalibratedOpticalCenterY")),
            vignetting_coefficients=vig_coeffs,
            dewarp_params=dewarp_params,
            homography_matrix=hmatrix,
            focal_length=_safe_float(raw.get("CalibratedFocalLength")),
            image_width=w,
            image_height=h,
            raw_metadata=raw,
        )


def _positive_float(value: object, default: float) -> float:
    """
    Coerce a metadata value to a strictly-positive float.

    Used for irradiance normalisation factors (``IrradianceExposureTime`` /
    ``IrradianceGain``) where a missing, non-numeric, or non-positive value must
    fall back to ``default`` rather than zero — a zero would make the normalised
    irradiance diverge and collapse reflectance to ~0.

    Args:
        value: Raw metadata value
        default: Fallback used when the value is absent or not strictly positive

    Returns:
        The positive float value, or ``default``
    """
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


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


def _extract_irradiance(raw: dict, image_path: Path) -> float:
    """
    Extract the DLS irradiance value from XMP metadata with a logged fallback.

    The DJI M3M records ``drone-dji:Irradiance`` per image when the Downwelling
    Light Sensor (DLS) is active.  If the field is absent (e.g. DLS disabled or
    firmware that omits it in single-band TIFFs), reflectance conversion will be
    incorrect because every image receives the same nominal irradiance of 1.0,
    making strip-to-strip sun-angle changes appear as systematic reflectance offsets.

    KNOWN LIMITATION — DLS-only, no Calibrated Reflectance Panel (CRP).
        Calibration uses only the DLS irradiance, which corrects for *changing*
        illumination during a flight but not for absolute calibration.  The
        scientific standard (Empirical Line Method) additionally images a
        Calibrated Reflectance Panel of known reflectance before/after the flight
        to anchor absolute surface reflectance.  Without it, absolute values may
        carry a systematic offset even though relative/index values (NDVI etc.)
        are reliable.  A CRP/ELM path is not implemented.

    Args:
        raw: Merged EXIF/XMP metadata dict from ``extract_all_metadata``
        image_path: Source image path (used in log messages only)

    Returns:
        Irradiance value parsed from XMP, or 1.0 with a warning when absent
    """
    raw_value = raw.get("Irradiance")
    if raw_value is not None:
        try:
            value = float(raw_value)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    logger.warning(
        f"{image_path.name}: drone-dji:Irradiance not found in XMP — "
        "defaulting to 1.0.  Reflectance values will be uncorrected for "
        "illumination.  Check that the DLS sunshine sensor is active and "
        "that the DJI XMP namespace is being read correctly."
    )
    return 1.0


# Example usage
if __name__ == "__main__":
    processor = Mavic3MImageProcessor()
    print("Mavic 3M Image Processor initialized successfully")
    print("Load images using: processor.load_image(path, band_name)")
    print("Calculate NDVI using: processor.calculate_ndvi()")
