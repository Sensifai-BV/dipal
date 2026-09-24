"""Data models for spectral band detection and image classification."""
from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class BandType(str, Enum):
    """Spectral band types supported by the pipeline."""

    RGB = "rgb"
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    NIR = "nir"
    RED_EDGE = "red_edge"
    THERMAL = "thermal"
    PANCHROMATIC = "panchromatic"
    UNKNOWN = "unknown"


class DroneManufacturer(str, Enum):
    """Known drone / camera manufacturers."""

    DJI = "dji"
    MICASENSE = "micasense"
    PARROT = "parrot"
    UNKNOWN = "unknown"


class ImageBandInfo(BaseModel):
    """Classification result for a single image file."""

    file_path: str = Field(..., description="Absolute path to the image file")
    file_name: str = Field(..., description="Image filename")
    band_type: BandType = Field(..., description="Detected band type")
    band_name_raw: str | None = Field(
        None, description="Raw band name from metadata"
    )
    manufacturer: DroneManufacturer = Field(
        default=DroneManufacturer.UNKNOWN,
        description="Detected drone manufacturer",
    )
    drone_model: str | None = Field(None, description="Drone model from metadata")
    sensor_index: int | None = Field(
        None, description="Sensor index for multi-camera rigs"
    )
    center_wavelength_nm: float | None = Field(
        None, description="Center wavelength in nanometres (if available)"
    )
    detection_method: str = Field(
        "unknown", description="How band type was determined"
    )
    confidence: float = Field(
        1.0, description="Detection confidence 0-1"
    )

    @property
    def path(self) -> Path:
        """Return the file path as a Path object."""
        return Path(self.file_path)


class BandGroup(BaseModel):
    """A group of images sharing the same band type."""

    band_type: BandType
    images: list[ImageBandInfo] = Field(default_factory=list)

    @property
    def count(self) -> int:
        """Number of images in this group."""
        return len(self.images)


class DatasetBandManifest(BaseModel):
    """Complete band classification result for a dataset."""

    dataset_id: str = Field(..., description="Dataset identifier")
    total_images: int = Field(0, description="Total images scanned")
    bands: dict[str, BandGroup] = Field(
        default_factory=dict,
        description="Images grouped by band type",
    )
    manufacturer: DroneManufacturer = Field(
        default=DroneManufacturer.UNKNOWN,
        description="Primary manufacturer detected",
    )
    drone_model: str | None = Field(None, description="Primary drone model")
    is_multispectral: bool = Field(
        False, description="True if non-RGB bands were detected"
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Errors encountered during scanning",
    )

    def get_band_paths(self, band_type: BandType) -> list[Path]:
        """
        Get all image paths for a specific band type.

        Args:
            band_type: The band type to retrieve

        Returns:
            List of Path objects for images of that band type
        """
        group = self.bands.get(band_type.value)
        if not group:
            return []
        return [info.path for info in group.images]

    @property
    def has_rgb(self) -> bool:
        """Whether dataset contains RGB images."""
        return BandType.RGB.value in self.bands and self.bands[BandType.RGB.value].count > 0

    @property
    def has_nir(self) -> bool:
        """Whether dataset contains NIR images."""
        return BandType.NIR.value in self.bands and self.bands[BandType.NIR.value].count > 0

    @property
    def available_bands(self) -> list[BandType]:
        """List of band types present in the dataset."""
        return [
            BandType(k) for k, v in self.bands.items() if v.count > 0
        ]


# Mapping from raw XMP/EXIF band names to BandType
DJI_BAND_NAME_MAP: dict[str, BandType] = {
    "RGB": BandType.RGB,
    "Wide": BandType.RGB,
    "Visible": BandType.RGB,
    "Red": BandType.RED,
    "Green": BandType.GREEN,
    "Blue": BandType.BLUE,
    "NIR": BandType.NIR,
    "Near-Infrared": BandType.NIR,
    "RedEdge": BandType.RED_EDGE,
    "Red Edge": BandType.RED_EDGE,
    "Thermal": BandType.THERMAL,
}

MICASENSE_BAND_NAME_MAP: dict[str, BandType] = {
    "Blue": BandType.BLUE,
    "Green": BandType.GREEN,
    "Red": BandType.RED,
    "Red edge": BandType.RED_EDGE,
    "RedEdge": BandType.RED_EDGE,
    "NIR": BandType.NIR,
    "Near-IR": BandType.NIR,
    "Near IR": BandType.NIR,
    "LWIR": BandType.THERMAL,
    "Panchro": BandType.PANCHROMATIC,
}

# DJI filename suffix patterns  (e.g., DJI_xxxx_W.JPG = wide/RGB)
DJI_FILENAME_BAND_PATTERNS: dict[str, BandType] = {
    "_D": BandType.RGB,
    "_W": BandType.RGB,
    "_T": BandType.THERMAL,
    "_MS_G": BandType.GREEN,
    "_MS_R": BandType.RED,
    "_MS_RE": BandType.RED_EDGE,
    "_MS_NIR": BandType.NIR,
}

# Generic filename suffix patterns (Parrot Sequoia, Sentera, etc.)
GENERIC_FILENAME_BAND_PATTERNS: dict[str, BandType] = {
    "_GRE": BandType.GREEN,
    "_GRN": BandType.GREEN,
    "_RED": BandType.RED,
    "_REG": BandType.RED_EDGE,
    "_NIR": BandType.NIR,
    "_BLU": BandType.BLUE,
    "_TIR": BandType.THERMAL,
    "_PAN": BandType.PANCHROMATIC,
    "_RGB": BandType.RGB,
}

# Known center wavelengths (nm) per band for common sensors
BAND_WAVELENGTH_MAP: dict[BandType, float] = {
    BandType.BLUE: 475.0,
    BandType.GREEN: 560.0,
    BandType.RED: 668.0,
    BandType.RED_EDGE: 717.0,
    BandType.NIR: 842.0,
}

IMAGE_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".dng",
}
