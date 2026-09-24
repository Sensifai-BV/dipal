"""Lightweight image metadata reader using Pillow + stdlib XML parsing.

Does NOT depend on libxmp — extracts XMP from raw image bytes so it
works in every service without heavy C dependencies.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS

from infrastructure.logging import get_logger

logger = get_logger(__name__)

XMP_START_MARKER = b"<x:xmpmeta"
XMP_END_MARKER = b"</x:xmpmeta>"

DJI_NS = "http://www.dji.com/drone-dji/1.0/"
CAMERA_NS = "http://purl.org/dc/elements/1.1/"
XMP_NS = "http://ns.adobe.com/xap/1.0/"
TIFF_NS = "http://ns.adobe.com/tiff/1.0/"
EXIF_NS = "http://ns.adobe.com/exif/1.0/"
# DJI M3M declares xmlns:Camera="http://pix4d.com/camera/1.0" (Pix4D schema).
# MicaSense sensors use "http://www.micasense.com/1.0/" — kept as a fallback key.
PIX4D_CAMERA_NS = "http://pix4d.com/camera/1.0"
MICASENSE_NS = "http://www.micasense.com/1.0/"

_NS_PREFIXES: dict[str, str] = {
    "drone-dji": DJI_NS,
    "Camera": PIX4D_CAMERA_NS,
    "Camera_micasense": MICASENSE_NS,
    "dc": CAMERA_NS,
    "xmp": XMP_NS,
    "tiff": TIFF_NS,
    "exif": EXIF_NS,
}

DJI_XMP_PROPERTIES: list[str] = [
    "BandName",
    "BandFreq",
    "SensorIndex",
    "DroneModel",
    "DroneSerialNumber",
    "CameraSerialNumber",
    "ImageSource",
    "Irradiance",
    "SensorGain",
    "ExposureTime",
    "BlackLevel",
    "SensorGainAdjustment",
    "CalibratedOpticalCenterX",
    "CalibratedOpticalCenterY",
    "VignettingData",
    "DewarpData",
    "CalibratedHMatrix",
    "CalibratedFocalLength",
    "GpsLatitude",
    "GpsLongitude",
    "AbsoluteAltitude",
    "RelativeAltitude",
]

MICASENSE_XMP_PROPERTIES: list[str] = [
    "BandName",
    "CentralWavelength",
    "WavelengthFWHM",
    "BandSensitivity",
    "Irradiance",
    "IrradianceExposureTime",
    "IrradianceGain",
    "IrradianceYaw",
    "IrradiancePitch",
    "IrradianceRoll",
    "RigCameraIndex",
    "CaptureId",
    "FlightId",
    "PressureAlt",
    "BlackCurrent",
    "SunSensor",
    "SunSensorExposureTime",
]


def extract_exif(image_path: Path) -> dict[str, object]:
    """
    Extract EXIF tags from an image.

    Args:
        image_path: Path to the image file

    Returns:
        Dictionary of tag-name → value
    """
    metadata: dict[str, object] = {}
    try:
        with Image.open(image_path) as img:
            exif_data = img.getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    metadata[tag_name] = value
    except Exception as exc:
        logger.warning(f"Failed to read EXIF from {image_path.name}: {exc}")
    return metadata


def _read_xmp_bytes(image_path: Path) -> bytes | None:
    """
    Read raw XMP packet from an image file.

    Args:
        image_path: Path to the image file

    Returns:
        Raw XMP bytes or None
    """
    try:
        data = image_path.read_bytes()
        start = data.find(XMP_START_MARKER)
        if start == -1:
            return None
        end = data.find(XMP_END_MARKER, start)
        if end == -1:
            return None
        return data[start : end + len(XMP_END_MARKER)]
    except Exception as exc:
        logger.warning(f"Failed to read XMP bytes from {image_path.name}: {exc}")
        return None


def _parse_xmp_xml(xmp_bytes: bytes) -> dict[str, str]:
    """
    Parse XMP XML and extract known properties across all namespaces.

    Args:
        xmp_bytes: Raw XMP XML bytes

    Returns:
        Flat dictionary of property-name → string value
    """
    result: dict[str, str] = {}
    try:
        root = ET.fromstring(xmp_bytes)
    except ET.ParseError as exc:
        logger.warning(f"XMP XML parse error: {exc}")
        return result

    for elem in root.iter():
        tag = elem.tag
        text = (elem.text or "").strip()

        for ns_prefix, ns_uri in _NS_PREFIXES.items():
            if tag.startswith(f"{{{ns_uri}}}"):
                local_name = tag.replace(f"{{{ns_uri}}}", "")
                if text:
                    result[local_name] = text
                for attr_name, attr_val in elem.attrib.items():
                    clean_attr = attr_name.split("}")[-1] if "}" in attr_name else attr_name
                    result[f"{local_name}.{clean_attr}"] = attr_val

        for attr_name, attr_val in elem.attrib.items():
            for ns_prefix, ns_uri in _NS_PREFIXES.items():
                if attr_name.startswith(f"{{{ns_uri}}}"):
                    local_attr = attr_name.replace(f"{{{ns_uri}}}", "")
                    result[local_attr] = attr_val

    return result


def _parse_xmp_regex_fallback(xmp_bytes: bytes) -> dict[str, str]:
    """
    Regex fallback parser for XMP properties when XML parsing misses them.

    Args:
        xmp_bytes: Raw XMP XML bytes

    Returns:
        Dictionary of property-name → value
    """
    result: dict[str, str] = {}
    text = xmp_bytes.decode("utf-8", errors="replace")

    all_props = set(DJI_XMP_PROPERTIES + MICASENSE_XMP_PROPERTIES)
    for prop in all_props:
        patterns = [
            rf'drone-dji:{prop}="([^"]*)"',
            rf"drone-dji:{prop}>([^<]*)<",
            rf'Camera:{prop}="([^"]*)"',
            rf"Camera:{prop}>([^<]*)<",
            rf'{prop}="([^"]*)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                result[prop] = match.group(1).strip()
                break

    return result


def extract_xmp(image_path: Path) -> dict[str, str]:
    """
    Extract XMP metadata from an image file without libxmp.

    Uses raw byte scanning + stdlib XML parsing with regex fallback.

    Args:
        image_path: Path to the image file

    Returns:
        Dictionary of property-name → string value
    """
    xmp_bytes = _read_xmp_bytes(image_path)
    if not xmp_bytes:
        return {}

    result = _parse_xmp_xml(xmp_bytes)

    regex_result = _parse_xmp_regex_fallback(xmp_bytes)
    for k, v in regex_result.items():
        if k not in result:
            result[k] = v

    return result


def extract_all_metadata(image_path: Path) -> dict[str, object]:
    """
    Extract both EXIF and XMP metadata from an image.

    Args:
        image_path: Path to the image file

    Returns:
        Merged dictionary of all metadata
    """
    metadata: dict[str, object] = {}
    metadata.update(extract_exif(image_path))
    metadata.update(extract_xmp(image_path))
    return metadata
