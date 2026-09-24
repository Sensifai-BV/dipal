"""High-level API: scan a directory and classify all images by band type."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from infrastructure.logging import get_logger

from .band_classifier import classify_image
from .models import (
    IMAGE_EXTENSIONS,
    BandGroup,
    BandType,
    DatasetBandManifest,
    DroneManufacturer,
)

logger = get_logger(__name__)


def scan_dataset(
    images_dir: Path,
    dataset_id: str,
    recursive: bool = True,
) -> DatasetBandManifest:
    """
    Scan a directory of images and classify every file by spectral band.

    Args:
        images_dir: Directory containing images
        dataset_id: Dataset identifier for the manifest
        recursive: Whether to search subdirectories

    Returns:
        DatasetBandManifest with all images grouped by band type
    """
    images_dir = Path(images_dir)
    if not images_dir.is_dir():
        raise FileNotFoundError(f"Images directory does not exist: {images_dir}")

    glob_fn = images_dir.rglob if recursive else images_dir.glob
    image_files = sorted(
        f
        for f in glob_fn("*")
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not image_files:
        logger.warning(f"No images found in {images_dir}")
        return DatasetBandManifest(dataset_id=dataset_id, total_images=0)

    logger.info(f"Scanning {len(image_files)} images in {images_dir}")

    bands: dict[str, BandGroup] = {}
    errors: list[str] = []
    manufacturers: list[DroneManufacturer] = []
    drone_models: list[str] = []

    for img_path in image_files:
        try:
            info = classify_image(img_path)

            key = info.band_type.value
            if key not in bands:
                bands[key] = BandGroup(band_type=info.band_type)
            bands[key].images.append(info)

            manufacturers.append(info.manufacturer)
            if info.drone_model:
                drone_models.append(info.drone_model)

        except Exception as exc:
            msg = f"Error classifying {img_path.name}: {exc}"
            logger.error(msg)
            errors.append(msg)

    manufacturer_counts = Counter(manufacturers)
    primary_manufacturer = (
        manufacturer_counts.most_common(1)[0][0]
        if manufacturer_counts
        else DroneManufacturer.UNKNOWN
    )

    model_counts = Counter(drone_models)
    primary_model = model_counts.most_common(1)[0][0] if model_counts else None

    is_multispectral = any(
        bt not in (BandType.RGB.value, BandType.UNKNOWN.value) for bt in bands
    )

    manifest = DatasetBandManifest(
        dataset_id=dataset_id,
        total_images=len(image_files),
        bands=bands,
        manufacturer=primary_manufacturer,
        drone_model=primary_model,
        is_multispectral=is_multispectral,
        errors=errors,
    )

    band_summary = {bt: bands[bt].count for bt in bands}
    logger.info(
        f"Dataset {dataset_id}: {manifest.total_images} images, "
        f"multispectral={manifest.is_multispectral}, "
        f"manufacturer={primary_manufacturer.value}, "
        f"bands={band_summary}"
    )

    return manifest
