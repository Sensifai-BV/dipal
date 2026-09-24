"""Shared utilities for image-analysis-core"""
# Import gsd_conversion utilities (no heavy dependencies)
from .gsd_conversion import (
    gsd_to_max_image_size,
    get_colmap_settings_for_gsd,
)

# Lazy import image_preprocessing to avoid cv2 dependency for services that don't need it
# Import directly from shared.utils.image_preprocessing if needed:
#   from shared.utils.image_preprocessing import downsample_image, etc.

__all__ = [
    "gsd_to_max_image_size",
    "get_colmap_settings_for_gsd",
]


def __getattr__(name):
    """Lazy import for image_preprocessing functions to avoid cv2 dependency."""
    image_preprocessing_functions = [
        "calculate_downsample_factor",
        "downsample_image",
        "downsample_dataset",
        "estimate_gsd_from_exif",
    ]
    if name in image_preprocessing_functions:
        from . import image_preprocessing
        return getattr(image_preprocessing, name)
    raise AttributeError(f"module 'shared.utils' has no attribute '{name}'")
