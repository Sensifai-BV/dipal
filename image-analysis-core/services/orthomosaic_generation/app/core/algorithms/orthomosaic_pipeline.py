from __future__ import annotations

from pathlib import Path

from services.orthomosaic_generation.app.core.algorithms.ms_orthorectification import (
    orthorectify_bands,
    stack_bands,
)
from services.orthomosaic_generation.app.core.algorithms.vegetation_indices import (
    compute_vegetation_indices,
    convert_index_to_cog,
)
from services.orthomosaic_generation.app.core.services.orthomosaic_service import (
    OrthomosaicService,
)
from services.orthomosaic_generation.logger import logger


class OrthomosaicPipeline:
    """
    Pipeline for generating orthomosaics from SFM results.

    This pipeline orchestrates the complete orthomosaic generation process:
    1. Generate DSM from point cloud
    2. Generate RGB orthomosaic (textured, showing terrain features)
    3. Fill holes in DSM
    4. Convert to Cloud Optimized GeoTIFF
    5. Generate hillshade for visualization
    6. Generate statistics
    7. (Full mode) Orthorectify multispectral bands
    8. (Full mode) Compute vegetation indices (NDVI, NDRE, GNDVI)
    """

    def __init__(self, service: OrthomosaicService):
        self.service = service

    def run_pipeline(self, dataset_path: Path, generate_cog: bool = True) -> dict[str, str]:
        """
        Run complete orthomosaic generation pipeline.

        Args:
            dataset_path: Path to dataset containing SFM results (with dense/fused.ply)
            generate_cog: Whether to generate Cloud Optimized GeoTIFF

        Returns:
            Mapping of multi-resolution product key → file path
        """
        logger.info(f"Starting orthomosaic pipeline for {dataset_path}")

        project_id = self.service.start(dataset_path)

        try:
            # Step 1: Generate DSM from point cloud
            logger.info("Step 1: Generating DSM from point cloud...")
            self.service.generate_dsm_from_pointcloud(project_id)

            # Step 2: Generate RGB orthomosaic (THIS IS THE KEY FOR VISUALIZATION!)
            logger.info("Step 2: Generating RGB orthomosaic with terrain features...")
            try:
                rgb_path = self.service.generate_rgb_orthomosaic(project_id)
                logger.info(f"✓ RGB orthomosaic created: {rgb_path}")
            except Exception as e:
                logger.warning(
                    f"Step 2 failed — could not generate RGB orthomosaic: "
                    f"{type(e).__name__}: {e}",
                    exc_info=True,
                )
                logger.warning("Point cloud may not contain color information")

            # Step 3: Fill holes in DSM
            logger.info("Step 3: Filling holes in DSM...")
            self.service.fill_dsm_holes(project_id)

            # Step 4: Generate hillshade for better visualization
            logger.info("Step 4: Generating hillshade...")
            try:
                hillshade_path = self.service.generate_hillshade(project_id)
                logger.info(f"✓ Hillshade created: {hillshade_path}")
            except Exception as e:
                logger.warning(
                    f"Step 4 failed — could not generate hillshade: "
                    f"{type(e).__name__}: {e}",
                    exc_info=True,
                )

            # Step 5: Convert to COG (optional but recommended)
            if generate_cog:
                logger.info("Step 5: Converting to Cloud Optimized GeoTIFF...")
                self.service.convert_to_cog(project_id)
            else:
                logger.info("Step 5: Skipping COG generation")

            # Step 6: Generate multi-resolution outputs
            logger.info("Step 6: Generating multi-resolution outputs...")
            try:
                mr_products = self.service.generate_multi_resolution_outputs(
                    project_id
                )
                logger.info(
                    f"✓ Multi-resolution outputs: {list(mr_products.keys())}"
                )
            except Exception as e:
                mr_products = {}
                logger.warning(
                    f"Step 6 failed — could not generate multi-resolution outputs: "
                    f"{type(e).__name__}: {e}",
                    exc_info=True,
                )

            # Step 7: Generate statistics
            logger.info("Step 7: Generating statistics...")
            stats = self.service.generate_statistics(project_id)

            logger.info("=" * 60)
            logger.info("Orthomosaic pipeline completed successfully!")
            logger.info("=" * 60)
            logger.info("Outputs:")
            for output_name, output_info in stats["outputs"].items():
                if output_info.get("exists"):
                    logger.info(f"  - {output_name}: {output_info['path']}")
                    logger.info(f"    Size: {output_info['size_mb']:.2f} MB")
                    if "width" in output_info:
                        logger.info(
                            f"    Dimensions: {output_info['width']} x {output_info['height']}",
                        )

            if mr_products:
                logger.info("Multi-resolution variants:")
                for key, path in mr_products.items():
                    logger.info(f"  - {key}: {path}")

            logger.info("")
            logger.info("=" * 60)
            logger.info("VISUALIZATION TIP:")
            logger.info(
                "  Load 'orthomosaic_rgb.tif' in QGIS to see fields, roads, water",
            )
            logger.info("  Load 'dsm_filled_cog.tif' for elevation data")
            logger.info("  Load 'hillshade.tif' for terrain relief visualization")
            logger.info("=" * 60)

            return mr_products

        except Exception as e:
            logger.error(
                f"Orthomosaic pipeline failed for project {project_id}: "
                f"{type(e).__name__}: {e}",
                exc_info=True,
            )
            raise
        finally:
            self.service.stop(project_id)
            self.service.clean(project_id)

        return {}

    def run_multispectral_analysis(
        self,
        dataset_path: Path,
        calibration_path: str,
        sfm_run_path: str,
        band_manifest: dict | None = None,
    ) -> dict[str, str]:
        """
        Run multispectral analysis after the base pipeline has completed.

        Produces per-band orthorectified reflectance, multi-band stack,
        and vegetation indices (NDVI, NDRE, GNDVI) as COGs.

        Args:
            dataset_path: SFM output directory (contains dsm_filled.tif)
            calibration_path: Root of calibrated reflectance images
            sfm_run_path: SFM run dir with sparse/0/ model files
            band_manifest: Band manifest dict (informational)

        Returns:
            Mapping of product_name → file path
        """
        logger.info("=" * 60)
        logger.info("Starting multispectral analysis pipeline")
        logger.info("=" * 60)

        dsm_path = str(dataset_path / "dsm_filled.tif")
        if not Path(dsm_path).exists():
            dsm_path = str(dataset_path / "dsm.tif")

        ms_output_dir = dataset_path / "multispectral"
        ms_output_dir.mkdir(parents=True, exist_ok=True)

        products: dict[str, str] = {}

        logger.info("Step MS-1: Orthorectifying spectral bands...")
        band_orthos = orthorectify_bands(
            calibration_path=calibration_path,
            sfm_run_path=sfm_run_path,
            dsm_path=dsm_path,
            output_dir=str(ms_output_dir / "bands"),
            band_manifest=band_manifest,
        )

        for band_name, band_path in band_orthos.items():
            products[f"{band_name}_ortho"] = band_path

        if len(band_orthos) >= 2:
            logger.info("Step MS-2: Stacking bands into multi-band GeoTIFF...")
            stacked_path = str(ms_output_dir / "multiband_reflectance.tif")
            stack_bands(band_orthos, stacked_path)
            products["multiband_reflectance"] = stacked_path

        logger.info("Step MS-3: Computing vegetation indices...")
        vi_outputs = compute_vegetation_indices(
            band_ortho_paths=band_orthos,
            output_dir=str(ms_output_dir / "indices"),
        )

        for vi_name, vi_path in vi_outputs.items():
            cog_path = convert_index_to_cog(vi_path)
            products[vi_name] = cog_path
            logger.info(f"  {vi_name} COG: {cog_path}")

        logger.info("=" * 60)
        logger.info(f"Multispectral analysis complete: {len(products)} products")
        logger.info("=" * 60)

        return products

    def run_dsm_only(self, dataset_path: Path):
        """
        Generate only the DSM without hole filling or COG conversion.

        Args:
            dataset_path: Path to dataset containing SFM results
        """
        logger.info(f"Generating DSM only for {dataset_path}")

        project_id = self.service.start(dataset_path)

        try:
            dsm_path = self.service.generate_dsm_from_pointcloud(project_id)
            logger.info(f"DSM generated at: {dsm_path}")
        finally:
            self.service.stop(project_id)
            self.service.clean(project_id)

    def run_from_existing_dsm(self, dataset_path: Path):
        """
        Process existing DSM (fill holes and convert to COG).

        Args:
            dataset_path: Path to dataset containing existing dsm.tif
        """
        logger.info(f"Processing existing DSM in {dataset_path}")

        project_id = self.service.start(dataset_path)

        try:
            # Step 1: Fill holes
            logger.info("Step 1: Filling holes in DSM...")
            self.service.fill_dsm_holes(project_id)

            # Step 2: Convert to COG
            logger.info("Step 2: Converting to Cloud Optimized GeoTIFF...")
            self.service.convert_to_cog(project_id)

            # Step 3: Generate statistics
            logger.info("Step 3: Generating statistics...")
            self.service.generate_statistics(project_id)

            logger.info("Processing completed successfully!")

        finally:
            self.service.stop(project_id)
            self.service.clean(project_id)
