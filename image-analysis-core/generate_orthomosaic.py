#!/usr/bin/env python3
"""
Script to generate orthomosaic from SFM results.

Usage:
    python generate_orthomosaic.py <dataset_path>

Example:
    python generate_orthomosaic.py data/selected_images_2
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent))

from services.orthomosaic_generation.app.core.algorithms.orthomosaic_pipeline import (
    OrthomosaicPipeline,
)
from services.orthomosaic_generation.app.core.services.orthomosaic_service import (
    OrthomosaicService,
)


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_orthomosaic.py <dataset_path>")
        print("Example: python generate_orthomosaic.py data/selected_images_2")
        sys.exit(1)

    dataset_path = Path(sys.argv[1])

    if not dataset_path.exists():
        print(f"Error: Dataset path '{dataset_path}' does not exist")
        sys.exit(1)

    # Check if dataset has required SFM outputs
    dense_path = dataset_path / "dense"
    if not dense_path.exists():
        print(f"Error: No 'dense' folder found in {dataset_path}")
        print("Please run SFM pipeline first to generate dense reconstruction")
        sys.exit(1)

    # Check for point cloud
    fused_ply = dense_path / "fused.ply"
    meshed_ply = dense_path / "meshed-poisson.ply"

    if not fused_ply.exists() and not meshed_ply.exists():
        print(f"Error: No point cloud found in {dense_path}")
        print("Expected: fused.ply or meshed-poisson.ply")
        print("Please run SFM pipeline with dense reconstruction first")
        sys.exit(1)

    # Create service and pipeline
    service = OrthomosaicService()
    pipeline = OrthomosaicPipeline(service)

    # Run pipeline
    print(f"\nGenerating orthomosaic for: {dataset_path.absolute()}")
    print("=" * 60)

    pipeline.run_pipeline(dataset_path.absolute(), generate_cog=True)

    print("\n" + "=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print(f"\nGenerated files in: {dataset_path.absolute()}")
    print("  - dsm.tif              : Digital Surface Model (raw)")
    print("  - dsm_filled.tif       : DSM with holes filled")
    print("  - dsm_filled_cog.tif   : Cloud Optimized GeoTIFF (recommended)")
    print("  - orthomosaic_statistics.json : Statistics and metadata")
    print("\nYou can now:")
    print("  1. View the results in QGIS or any GIS software")
    print("  2. Publish dsm_filled_cog.tif to web services")
    print("  3. Use it for further analysis")


if __name__ == "__main__":
    main()
