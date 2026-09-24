"""Factory for creating drone-specific image processors."""
from __future__ import annotations

from enum import Enum

from infrastructure.logging import get_logger

from .interfaces import IDroneImageProcessor
from .mavic_m3m_calibration import Mavic3MImageProcessor
from .micasense_calibration import MicaSenseImageProcessor

logger = get_logger(__name__)


class DroneType(Enum):
    """Supported drone types for radiometric calibration."""

    DJI_MAVIC_3M = "dji_mavic_3_m"
    DJI_P4_MULTISPECTRAL = "dji_p4_multispectral"
    DJI_PHANTOM_4_RTK = "dji_phantom_4_rtk"
    MICASENSE_REDEDGE = "micasense_rededge"
    MICASENSE_ALTUM = "micasense_altum"


_REGISTRY: dict[DroneType, type[IDroneImageProcessor]] = {
    DroneType.DJI_MAVIC_3M: Mavic3MImageProcessor,
    DroneType.DJI_P4_MULTISPECTRAL: Mavic3MImageProcessor,
    DroneType.DJI_PHANTOM_4_RTK: Mavic3MImageProcessor,
    DroneType.MICASENSE_REDEDGE: MicaSenseImageProcessor,
    DroneType.MICASENSE_ALTUM: MicaSenseImageProcessor,
}

_MODEL_NAME_MAP: dict[str, DroneType] = {
    "mavic 3m": DroneType.DJI_MAVIC_3M,
    "m3m": DroneType.DJI_MAVIC_3M,
    "mavic3m": DroneType.DJI_MAVIC_3M,
    "p4 multispectral": DroneType.DJI_P4_MULTISPECTRAL,
    "p4m": DroneType.DJI_P4_MULTISPECTRAL,
    "phantom 4 multispectral": DroneType.DJI_P4_MULTISPECTRAL,
    "phantom 4 rtk": DroneType.DJI_PHANTOM_4_RTK,
    "p4 rtk": DroneType.DJI_PHANTOM_4_RTK,
    "rededge": DroneType.MICASENSE_REDEDGE,
    "rededge-m": DroneType.MICASENSE_REDEDGE,
    "rededge-mx": DroneType.MICASENSE_REDEDGE,
    "altum": DroneType.MICASENSE_ALTUM,
    "altum-pt": DroneType.MICASENSE_ALTUM,
}


class DroneImageProcessorFactory:
    """Create the right processor for a given drone type or model name."""

    @classmethod
    def create(cls, drone_type: DroneType) -> IDroneImageProcessor:
        """
        Create a processor from an explicit DroneType enum.

        Args:
            drone_type: Drone type enum value

        Returns:
            Configured IDroneImageProcessor

        Raises:
            ValueError: If drone type is not supported
        """
        processor_class = _REGISTRY.get(drone_type)
        if processor_class is None:
            raise ValueError(f"Unsupported drone type: {drone_type}")
        logger.info(f"Creating processor for {drone_type.value}")
        return processor_class()

    @classmethod
    def create_from_model_name(cls, model_name: str) -> IDroneImageProcessor:
        """
        Create a processor by matching a model name string.

        Args:
            model_name: Drone model name (case insensitive)

        Returns:
            Configured IDroneImageProcessor

        Raises:
            ValueError: If model name cannot be matched
        """
        key = model_name.strip().lower()
        for pattern, drone_type in _MODEL_NAME_MAP.items():
            if pattern in key:
                return cls.create(drone_type)
        raise ValueError(
            f"Cannot determine drone type from model name: '{model_name}'"
        )

    @classmethod
    def create_from_manufacturer(
        cls, manufacturer: str, is_multispectral: bool = False
    ) -> IDroneImageProcessor:
        """
        Create a default processor based on manufacturer.

        Args:
            manufacturer: Manufacturer name ('dji', 'micasense', etc.)
            is_multispectral: Whether the dataset has spectral bands

        Returns:
            Configured IDroneImageProcessor

        Raises:
            ValueError: If manufacturer is unknown
        """
        mfr = manufacturer.strip().lower()
        if mfr == "dji":
            return cls.create(DroneType.DJI_MAVIC_3M)
        if mfr == "micasense":
            return cls.create(DroneType.MICASENSE_REDEDGE)
        if mfr == "parrot":
            logger.info(
                "Parrot manufacturer detected — using DJI processor as fallback"
            )
            return cls.create(DroneType.DJI_MAVIC_3M)
        raise ValueError(f"Unknown manufacturer: '{manufacturer}'")
