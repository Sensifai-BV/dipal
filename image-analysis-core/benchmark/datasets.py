from dataclasses import dataclass, field
from pathlib import Path

KNOWN_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".dng"}


@dataclass
class DatasetPreset:
    """
    Predefined dataset profile with expected layout and ground truth info.

    Attributes:
        name: Short identifier for the dataset
        description: Human-readable description
        source_url: Download URL or DOI
        sensor_type: rgb | multispectral | thermal
        expected_gsd_cm: Expected GSD in cm/px
        images_subdir: Relative path to raw images within dataset root
        ground_truth_subdir: Relative path to ground truth data
        reference_products: Relative paths to pre-processed reference outputs
        stages: Stages applicable for benchmarking
    """

    name: str
    description: str
    source_url: str
    sensor_type: str
    expected_gsd_cm: float | None = None
    images_subdir: str = "images"
    ground_truth_subdir: str | None = None
    reference_products: dict[str, str] = field(default_factory=dict)
    stages: list[str] = field(default_factory=lambda: ["calibration", "sfm", "orthomosaic"])


DATASET_PRESETS: dict[str, DatasetPreset] = {
    "zenodo-eastkazakhstan": DatasetPreset(
        name="zenodo-eastkazakhstan",
        description=(
            "East Kazakhstan Multispectral Crop Dataset — wheat, soybean, barley. "
            "DJI Phantom 4 Multispectral at 3 cm/px. Includes raw images, "
            "orthomosaics, DEMs, and NDVI layers across multiple flight dates."
        ),
        source_url="https://zenodo.org/records/7749239",
        sensor_type="multispectral",
        expected_gsd_cm=3.0,
        images_subdir=".",
        ground_truth_subdir=None,
        reference_products={
            "orthomosaic": "orthomosaic",
            "dem": "dem",
            "ndvi": "ndvi",
        },
        stages=["calibration", "sfm", "orthomosaic"],
    ),
    "wur-dataverse": DatasetPreset(
        name="wur-dataverse",
        description=(
            "Wageningen University Multispectral & Thermal Dataset — wheat, barley, "
            "potato fields. Multi-sensor (senseFly MSP4C, Parrot Sequoia, SlantRange P3). "
            "Includes radiometric calibration plates + handheld spectrometer measurements."
        ),
        source_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/RYA2ZQ",
        sensor_type="multispectral",
        expected_gsd_cm=None,
        images_subdir=".",
        ground_truth_subdir=None,
        reference_products={},
        stages=["calibration"],
    ),
    "odm-aukerman": DatasetPreset(
        name="odm-aukerman",
        description=(
            "OpenDroneMap Aukerman Dataset — park/campus area. RGB only. "
            "77 images captured by a consumer drone at ~2.5 cm/px. "
            "Standard ODM benchmark for SFM and orthomosaic generation."
        ),
        source_url="https://github.com/OpenDroneMap/odm_data_aukerman",
        sensor_type="rgb",
        expected_gsd_cm=2.5,
        images_subdir="images",
        ground_truth_subdir=None,
        reference_products={},
        stages=["sfm", "orthomosaic"],
    ),
    "dronemapper-sample": DatasetPreset(
        name="dronemapper-sample",
        description=(
            "DroneMapper Sample Data — mixed terrain/agricultural area. RGB. "
            "Includes pre-processed ortho, DSM, and DTM reference products "
            "for accuracy comparison."
        ),
        source_url="https://dronemapper.com/sample_data/",
        sensor_type="rgb",
        expected_gsd_cm=None,
        images_subdir="images",
        ground_truth_subdir=None,
        reference_products={
            "orthomosaic": "products/orthomosaic",
            "dsm": "products/dsm",
            "dtm": "products/dtm",
        },
        stages=["sfm", "orthomosaic"],
    ),
}


def get_preset(name: str) -> DatasetPreset | None:
    """
    Look up a dataset preset by name.

    Args:
        name: Preset identifier (case-insensitive)

    Returns:
        DatasetPreset if found, None otherwise
    """
    return DATASET_PRESETS.get(name.lower())


def list_presets() -> list[DatasetPreset]:
    """
    Return all available dataset presets.

    Returns:
        List of all DatasetPreset instances
    """
    return list(DATASET_PRESETS.values())


def detect_dataset_layout(dataset_path: Path) -> dict:
    """
    Auto-detect the structure of a dataset directory.

    Scans for image files, ground truth CSVs, and reference products
    to help users understand what they have.

    Args:
        dataset_path: Root path of the dataset

    Returns:
        Dict describing the detected layout
    """
    layout: dict = {
        "root": str(dataset_path),
        "image_dirs": [],
        "image_count": 0,
        "ground_truth_files": [],
        "reference_products": [],
        "sensors_detected": [],
    }

    gt_patterns = [
        "gcps.csv", "gcp.csv", "ground_control_points.csv", "checkpoints.csv",
        "reference_reflectance.csv", "panel_values.csv", "spectral_reference.csv",
    ]

    reference_patterns = [
        "*orthomosaic*", "*ortho*", "*dsm*", "*dem*", "*ndvi*",
        "*hillshade*", "*reflectance*",
    ]

    for path in dataset_path.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() in KNOWN_IMAGE_EXTENSIONS:
            parent = str(path.parent.relative_to(dataset_path))
            if parent not in layout["image_dirs"]:
                layout["image_dirs"].append(parent)
            layout["image_count"] += 1

        if path.name.lower() in gt_patterns:
            layout["ground_truth_files"].append(
                str(path.relative_to(dataset_path))
            )

        for pattern in reference_patterns:
            if path.match(pattern):
                layout["reference_products"].append(
                    str(path.relative_to(dataset_path))
                )
                break

    sensor_hints = {
        "sequoia": "Parrot Sequoia",
        "msp4c": "senseFly MSP4C",
        "slantrange": "SlantRange P3",
        "phantom4": "DJI Phantom 4 Multispectral",
        "p4m": "DJI Phantom 4 Multispectral",
        "altum": "MicaSense Altum",
        "rededge": "MicaSense RedEdge",
    }

    dir_names = " ".join(layout["image_dirs"]).lower()
    for hint, sensor in sensor_hints.items():
        if hint in dir_names:
            layout["sensors_detected"].append(sensor)

    return layout
