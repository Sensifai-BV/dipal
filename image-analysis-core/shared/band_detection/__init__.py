"""Spectral band detection, classification, and folder organisation.

Usage::

    from shared.band_detection import scan_dataset, organize_by_band, BandType

    manifest = scan_dataset(Path("/data/datasets/abc123/images"), "abc123")
    folders  = organize_by_band(manifest, Path("/data/datasets/abc123"))
    rgb_path = folders.get("rgb")
"""
from .band_classifier import classify_image
from .detector import scan_dataset
from .models import (
    BAND_WAVELENGTH_MAP,
    IMAGE_EXTENSIONS,
    BandGroup,
    BandType,
    DatasetBandManifest,
    DroneManufacturer,
    ImageBandInfo,
)
from .organizer import (
    get_band_folder,
    get_rgb_folder,
    load_manifest,
    organize_by_band,
)

__all__ = [
    "BAND_WAVELENGTH_MAP",
    "BandGroup",
    "BandType",
    "DatasetBandManifest",
    "DroneManufacturer",
    "IMAGE_EXTENSIONS",
    "ImageBandInfo",
    "classify_image",
    "get_band_folder",
    "get_rgb_folder",
    "load_manifest",
    "organize_by_band",
    "scan_dataset",
]
