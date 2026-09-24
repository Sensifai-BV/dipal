"""
Image preprocessing utilities for photogrammetry pipeline.

Includes image downsampling based on GSD (Ground Sampling Distance) requirements.
"""
from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple
from PIL import Image

from infrastructure.logging import get_logger

logger = get_logger(__name__)


def calculate_downsample_factor(
    image_width: int,
    image_height: int,
    current_gsd: float,
    target_gsd: float
) -> float:
    """
    Calculate the downsample factor based on GSD requirements.
    
    GSD (Ground Sampling Distance) is the physical size that one pixel represents
    on the ground. Higher GSD = lower resolution = smaller image.
    
    Args:
        image_width: Original image width in pixels
        image_height: Original image height in pixels
        current_gsd: Current GSD in cm/pixel
        target_gsd: Target GSD in cm/pixel
        
    Returns:
        Downsample factor (1.0 = no downsampling, 0.5 = half resolution, etc.)
        
    Example:
        If current_gsd=2.5 cm/px and target_gsd=5.0 cm/px:
        - We want each pixel to represent MORE ground area
        - So we need FEWER pixels (lower resolution)
        - Downsample factor = 2.5 / 5.0 = 0.5 (half the resolution)
    """
    if target_gsd <= current_gsd:
        # Target GSD is lower or equal, no downsampling needed
        logger.info(
            f"Target GSD ({target_gsd}) <= current GSD ({current_gsd}), "
            "no downsampling required"
        )
        return 1.0
    
    # Calculate downsample factor
    downsample_factor = current_gsd / target_gsd
    
    # Ensure factor is valid
    downsample_factor = max(0.1, min(1.0, downsample_factor))
    
    new_width = int(image_width * downsample_factor)
    new_height = int(image_height * downsample_factor)
    
    logger.info(
        f"Downsampling: {image_width}x{image_height} -> {new_width}x{new_height} "
        f"(factor: {downsample_factor:.3f}, GSD: {current_gsd} -> {target_gsd} cm/px)"
    )
    
    return downsample_factor


def downsample_image(
    image_path: Path,
    output_path: Path,
    downsample_factor: float,
    quality: int = 95
) -> Tuple[int, int]:
    """
    Downsample an image by the given factor.
    
    Args:
        image_path: Path to input image
        output_path: Path to save downsampled image
        downsample_factor: Scaling factor (0.0 to 1.0)
        quality: JPEG quality for output (1-100)
        
    Returns:
        Tuple of (new_width, new_height)
    """
    if downsample_factor >= 1.0:
        # No downsampling needed, just copy
        import shutil
        shutil.copy2(image_path, output_path)
        img = Image.open(image_path)
        return img.size
    
    # Read image
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Failed to read image: {image_path}")
    
    original_height, original_width = img.shape[:2]
    new_width = int(original_width * downsample_factor)
    new_height = int(original_height * downsample_factor)
    
    # Downsample using high-quality interpolation
    downsampled = cv2.resize(
        img,
        (new_width, new_height),
        interpolation=cv2.INTER_AREA  # Best for downsampling
    )
    
    # Save with high quality
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if output_path.suffix.lower() in ['.jpg', '.jpeg']:
        cv2.imwrite(
            str(output_path),
            downsampled,
            [cv2.IMWRITE_JPEG_QUALITY, quality]
        )
    elif output_path.suffix.lower() == '.png':
        cv2.imwrite(
            str(output_path),
            downsampled,
            [cv2.IMWRITE_PNG_COMPRESSION, 3]
        )
    else:
        cv2.imwrite(str(output_path), downsampled)
    
    logger.debug(
        f"Downsampled {image_path.name}: "
        f"{original_width}x{original_height} -> {new_width}x{new_height}"
    )
    
    return new_width, new_height


def downsample_dataset(
    input_dir: Path,
    output_dir: Path,
    target_gsd: float,
    current_gsd: float | None = None,
    quality: int = 95
) -> dict:
    """
    Downsample all images in a dataset based on GSD requirements.
    
    Args:
        input_dir: Directory containing original images
        output_dir: Directory to save downsampled images
        target_gsd: Target GSD in cm/pixel
        current_gsd: Current GSD in cm/pixel (if None, will be estimated)
        quality: JPEG quality for output (1-100)
        
    Returns:
        Dict with processing statistics
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.JPG', '.JPEG', '.PNG'}
    image_files = [
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix in image_extensions
    ]
    
    if not image_files:
        raise ValueError(f"No images found in {input_dir}")
    
    logger.info(f"Found {len(image_files)} images to process")
    
    # If current GSD not provided, estimate from metadata or use target
    if current_gsd is None:
        # TODO: Extract from EXIF if available
        # For now, assume target GSD means no downsampling
        current_gsd = target_gsd
        logger.warning(
            "Current GSD not provided, assuming it matches target GSD. "
            "No downsampling will be applied."
        )
    
    # Get dimensions of first image to calculate downsample factor
    first_img = Image.open(image_files[0])
    img_width, img_height = first_img.size
    
    downsample_factor = calculate_downsample_factor(
        img_width, img_height, current_gsd, target_gsd
    )
    
    # Process all images
    processed_count = 0
    failed_count = 0
    total_original_size = 0
    total_downsampled_size = 0
    
    for image_file in image_files:
        try:
            output_file = output_dir / image_file.name
            
            original_size = image_file.stat().st_size
            total_original_size += original_size
            
            new_width, new_height = downsample_image(
                image_file,
                output_file,
                downsample_factor,
                quality
            )
            
            downsampled_size = output_file.stat().st_size
            total_downsampled_size += downsampled_size
            
            processed_count += 1
            
        except Exception as e:
            logger.error(f"Failed to process {image_file.name}: {e}")
            failed_count += 1
    
    # Calculate statistics
    size_reduction_pct = (
        100 * (1 - total_downsampled_size / total_original_size)
        if total_original_size > 0 else 0
    )
    
    stats = {
        "total_images": len(image_files),
        "processed": processed_count,
        "failed": failed_count,
        "downsample_factor": downsample_factor,
        "current_gsd": current_gsd,
        "target_gsd": target_gsd,
        "original_size_mb": total_original_size / (1024 * 1024),
        "downsampled_size_mb": total_downsampled_size / (1024 * 1024),
        "size_reduction_percent": size_reduction_pct,
    }
    
    logger.info(
        f"Processed {processed_count}/{len(image_files)} images. "
        f"Size reduction: {size_reduction_pct:.1f}% "
        f"({stats['original_size_mb']:.1f} MB -> {stats['downsampled_size_mb']:.1f} MB)"
    )
    
    if failed_count > 0:
        logger.warning(f"{failed_count} images failed to process")
    
    return stats


def estimate_gsd_from_exif(image_path: Path) -> float | None:
    """
    Estimate GSD from image EXIF metadata.
    
    This is a placeholder for future EXIF-based GSD extraction.
    Requires drone metadata including altitude, sensor size, and focal length.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Estimated GSD in cm/pixel, or None if cannot be determined
    """
    # TODO: Implement EXIF parsing
    # GSD = (sensor_width * flight_altitude * 100) / (focal_length * image_width)
    logger.warning("GSD extraction from EXIF not yet implemented")
    return None
