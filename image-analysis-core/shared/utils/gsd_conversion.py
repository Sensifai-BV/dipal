"""
GSD to COLMAP parameter conversion utilities.

Converts Ground Sampling Distance (GSD) to appropriate COLMAP max_image_size parameters.
"""
from __future__ import annotations

from infrastructure.logging import get_logger

logger = get_logger(__name__)


def gsd_to_max_image_size(gsd: float, base_gsd: float = 2.5, base_size: int = 5280) -> int:
    """
    Convert GSD to COLMAP max_image_size parameter.
    
    The relationship between GSD and image size is inverse:
    - Higher GSD (e.g., 10 cm/px) = Lower resolution = Smaller max_image_size
    - Lower GSD (e.g., 2.5 cm/px) = Higher resolution = Larger max_image_size
    
    Formula:
        max_image_size = base_size * (base_gsd / target_gsd)
    
    Args:
        gsd: Target GSD in cm/pixel
        base_gsd: Reference GSD (default: 2.5 cm/px for high quality)
        base_size: Max image size at base GSD (default: 5280 pixels)
        
    Returns:
        Calculated max_image_size for COLMAP
        
    Examples:
        >>> gsd_to_max_image_size(2.5)  # Same as base
        5280
        >>> gsd_to_max_image_size(5.0)  # Half resolution
        2640
        >>> gsd_to_max_image_size(10.0)  # Quarter resolution
        1320
    """
    if gsd <= 0:
        logger.warning(f"Invalid GSD value: {gsd}, using base size: {base_size}")
        return base_size
    
    # Calculate max_image_size based on GSD ratio
    max_size = int(base_size * (base_gsd / gsd))
    
    # Ensure reasonable bounds
    max_size = max(640, min(8192, max_size))  # Between 640 and 8192 pixels
    
    logger.info(
        f"GSD {gsd} cm/px → max_image_size: {max_size} "
        f"(base: {base_gsd} cm/px @ {base_size}px)"
    )
    
    return max_size


def get_colmap_settings_for_gsd(gsd: float | None) -> dict:
    """
    Get all COLMAP max_image_size settings for a given GSD.
    
    All max_image_size parameters are set to the same value for consistency:
    - feature_extraction_max_image_size
    - undistort_max_image_size
    - patch_match_max_image_size
    - fusion_max_image_size
    
    Args:
        gsd: Target GSD in cm/pixel (None = use defaults)
        
    Returns:
        Dictionary of COLMAP settings
        
    Example:
        >>> get_colmap_settings_for_gsd(5.0)
        {
            'feature_extraction_max_image_size': 2640,
            'undistort_max_image_size': 2640,
            'patch_match_max_image_size': 2640,
            'fusion_max_image_size': 2640
        }
    """
    if gsd is None or gsd <= 0:
        logger.info("No GSD specified, using default max_image_size: 5280")
        return {
            'feature_extraction_max_image_size': 5280,
            'undistort_max_image_size': 5280,
            'patch_match_max_image_size': 5280,
            'fusion_max_image_size': 5280,
        }
    
    max_size = gsd_to_max_image_size(gsd)
    
    settings = {
        'feature_extraction_max_image_size': max_size,
        'undistort_max_image_size': max_size,
        'patch_match_max_image_size': max_size,
        'fusion_max_image_size': max_size,
    }
    
    logger.info(f"COLMAP settings for GSD {gsd} cm/px: max_image_size={max_size}")
    
    return settings
