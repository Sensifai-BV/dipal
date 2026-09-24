"""Organize images into band-based subfolder structure.

After band detection, this module physically moves / copies images into
a standardised directory layout:

    datasets/{dataset_id}/
    ├── rgb/
    ├── nir/
    ├── red/
    ├── red_edge/
    ├── green/
    ├── blue/
    ├── thermal/
    └── metadata/
         └── band_manifest.json
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from infrastructure.logging import get_logger

from .models import BandType, DatasetBandManifest, ImageBandInfo

logger = get_logger(__name__)

BAND_FOLDER_NAMES: dict[BandType, str] = {
    BandType.RGB: "rgb",
    BandType.RED: "red",
    BandType.GREEN: "green",
    BandType.BLUE: "blue",
    BandType.NIR: "nir",
    BandType.RED_EDGE: "red_edge",
    BandType.THERMAL: "thermal",
    BandType.PANCHROMATIC: "panchromatic",
    BandType.UNKNOWN: "unknown",
}


def organize_by_band(
    manifest: DatasetBandManifest,
    dataset_dir: Path,
    move: bool = True,
) -> dict[str, Path]:
    """
    Organize images from a flat directory into band-type subfolders.

    Args:
        manifest: Band classification manifest from scan_dataset
        dataset_dir: Root directory for the dataset (parent of 'images/')
        move: If True, move files; if False, copy them

    Returns:
        Dictionary mapping band-type value to its subfolder Path

    Raises:
        FileNotFoundError: If a source image is missing
    """
    created_dirs: dict[str, Path] = {}
    moved_count = 0

    for band_key, group in manifest.bands.items():
        band_type = BandType(band_key)
        folder_name = BAND_FOLDER_NAMES.get(band_type, band_key)
        band_dir = dataset_dir / folder_name
        band_dir.mkdir(parents=True, exist_ok=True)
        created_dirs[band_key] = band_dir

        for info in group.images:
            src = Path(info.file_path)
            dst = band_dir / src.name

            if not src.exists():
                logger.warning(f"Source image missing, skipping: {src}")
                continue

            if src == dst:
                continue

            if dst.exists():
                logger.debug(f"Destination exists, skipping move: {dst}")
                info.file_path = str(dst)
                continue

            if move:
                shutil.move(str(src), str(dst))
            else:
                shutil.copy2(str(src), str(dst))

            info.file_path = str(dst)
            moved_count += 1

    metadata_dir = dataset_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = metadata_dir / "band_manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2))
    created_dirs["metadata"] = metadata_dir

    _cleanup_empty_source_dirs(manifest, dataset_dir)

    action = "Moved" if move else "Copied"
    logger.info(
        f"{action} {moved_count} images into {len(created_dirs) - 1} band folders "
        f"for dataset {manifest.dataset_id}"
    )

    return created_dirs


def _cleanup_empty_source_dirs(
    manifest: DatasetBandManifest,
    dataset_dir: Path,
) -> None:
    """
    Remove the original 'images/' directory if it is now empty.

    Args:
        manifest: Band manifest (used only for logging)
        dataset_dir: Root dataset directory
    """
    images_dir = dataset_dir / "images"
    if not images_dir.exists():
        return

    remaining = list(images_dir.rglob("*"))
    remaining_files = [f for f in remaining if f.is_file()]

    if not remaining_files:
        shutil.rmtree(images_dir, ignore_errors=True)
        logger.info(
            f"Removed empty images/ directory for dataset {manifest.dataset_id}"
        )
    else:
        logger.debug(
            f"images/ still has {len(remaining_files)} files after reorganization"
        )


def get_rgb_folder(dataset_dir: Path) -> Path | None:
    """
    Get the RGB images subfolder if it exists.

    Args:
        dataset_dir: Root dataset directory

    Returns:
        Path to rgb/ subfolder, or None if it doesn't exist
    """
    rgb_dir = dataset_dir / BAND_FOLDER_NAMES[BandType.RGB]
    return rgb_dir if rgb_dir.is_dir() else None


def get_band_folder(dataset_dir: Path, band_type: BandType) -> Path | None:
    """
    Get the subfolder for a specific band type.

    Args:
        dataset_dir: Root dataset directory
        band_type: Target band type

    Returns:
        Path to band subfolder, or None if it doesn't exist
    """
    folder_name = BAND_FOLDER_NAMES.get(band_type, band_type.value)
    band_dir = dataset_dir / folder_name
    return band_dir if band_dir.is_dir() else None


def load_manifest(dataset_dir: Path) -> DatasetBandManifest | None:
    """
    Load a previously saved band manifest from disk.

    Args:
        dataset_dir: Root dataset directory

    Returns:
        DatasetBandManifest or None if not found
    """
    manifest_path = dataset_dir / "metadata" / "band_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text())
        return DatasetBandManifest.model_validate(data)
    except Exception as exc:
        logger.error(f"Failed to load band manifest: {exc}")
        return None
