from __future__ import annotations

import json
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from services.orthomosaic_generation.logger import logger


def _load_geo_reference(workspace: Path) -> dict | None:
    """
    Search for ``geo_reference.json`` written by the SFM geo_register step.

    The file is expected at ``{workspace}/{run_name}/geo_reference.json``
    for any run directory. The first match is returned.

    Args:
        workspace: Root dataset path (same directory passed to OrthomosaicService.start)

    Returns:
        Parsed geo-reference dict or None if not found
    """
    for candidate in workspace.rglob("geo_reference.json"):
        try:
            return json.loads(candidate.read_text())
        except Exception as exc:
            logger.warning(f"Could not read {candidate}: {exc}")
    return None


class OrthomosaicSettings(BaseSettings):
    """Settings for orthomosaic generation service."""

    # DSM generation settings
    dsm_resolution: float = 0.05  # Resolution in meters per pixel
    dsm_output_type: str = "max"  # max, min, mean, idw, count
    dsm_radius: float = 0.5  # Search radius for interpolation
    pdal_threads: int = 0  # 0 = use all available cores

    # Hole filling settings
    fill_max_distance: int = 100  # Maximum distance to search for valid pixels
    fill_smoothing_iterations: int = 0  # Number of smoothing iterations after filling

    # COG settings
    cog_compression: str = "LZW"  # LZW, DEFLATE, ZSTD, etc.
    cog_predictor: int = 2  # 1=None, 2=Horizontal differencing, 3=Floating point
    cog_blocksize: int = 512  # Tile size for COG
    cog_overview_resampling: str = "AVERAGE"  # NEAREST, AVERAGE, CUBIC, etc.

    # Orthophoto settings (for textured orthomosaic)
    ortho_resolution: float = 0.05  # Resolution in meters per pixel
    ortho_interpolation: str = "bilinear"  # nearest, bilinear, cubic

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_prefix="ORTHOMOSAIC_",
    )


class OrthomosaicService:
    """
    Service for generating orthomosaics from SFM results.

    This service takes dense point clouds from COLMAP/SFM and generates:
    1. Digital Surface Model (DSM) - elevation raster
    2. Filled DSM - holes filled using interpolation
    3. Cloud Optimized GeoTIFF (COG) - optimized for web serving
    4. Optional orthophoto - textured orthomosaic from original images
    """

    __service_name = "OrthomosaicService"

    def __init__(self, additional_settings: dict | None = None):
        self.settings = OrthomosaicSettings(**(additional_settings or {}))
        self._projects: dict[str, Path] = {}

    def _get_workspace(self, project_id: str) -> Path:
        """Get workspace path for a project."""
        if project_id not in self._projects:
            raise ValueError(f"Project '{project_id}' not found. Call start() first.")
        return self._projects[project_id]

    def _run_command(
        self,
        cmd: list[str],
        description: str,
    ) -> subprocess.CompletedProcess:
        """Run a shell command and log output."""
        cmd_str = " ".join(cmd[:4])
        logger.info(f"[CMD] Running: {description} ({cmd_str})")
        logger.debug(f"[CMD] Full command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            if result.stdout:
                logger.debug(f"[CMD] Output: {result.stdout}")
            return result
        except subprocess.CalledProcessError as e:
            stderr_tail = (e.stderr or "")[-2000:]
            stdout_tail = (e.stdout or "")[-2000:]
            logger.error(
                f"[CMD] '{cmd_str}' failed (return code {e.returncode}) "
                f"during: {description}\n"
                f"  Stderr: {stderr_tail}\n"
                f"  Stdout: {stdout_tail}"
            )
            raise RuntimeError(
                f"'{cmd_str}' failed (rc={e.returncode}) during {description}. "
                f"Stderr: {stderr_tail[:500]}"
            ) from e
        except FileNotFoundError:
            raise RuntimeError(
                f"Command not found: {cmd[0]}. "
                f"Ensure PDAL/GDAL is installed and in PATH."
            )

    def generate_dsm_from_pointcloud(
        self,
        project_id: str,
        input_pointcloud: Path | None = None,
        output_dsm: Path | None = None,
    ) -> Path:
        """
        Generate Digital Surface Model (DSM) from point cloud using PDAL.

        Args:
            project_id: Project identifier
            input_pointcloud: Path to input point cloud (PLY format). If None, uses default location.
            output_dsm: Path to output DSM (GeoTIFF). If None, uses default location.

        Returns:
            Path to generated DSM
        """
        workspace = self._get_workspace(project_id)

        # Default paths
        if input_pointcloud is None:
            # Prefer fused_georef.ply (ECEF-transformed, correct for PDAL
            # reprojection to UTM).  Fall back to fused.ply (local SFM,
            # no CRS) and then to the Poisson mesh as a last resort.
            georef_candidate = workspace / "dense" / "fused_georef.ply"
            if georef_candidate.exists():
                input_pointcloud = georef_candidate
            else:
                input_pointcloud = workspace / "dense" / "fused.ply"
                if not input_pointcloud.exists():
                    input_pointcloud = workspace / "dense" / "meshed-poisson.ply"

        if output_dsm is None:
            output_dsm = workspace / "dsm.tif"

        if not input_pointcloud.exists():
            raise FileNotFoundError(f"Point cloud not found: {input_pointcloud}")

        logger.info(f"Generating DSM from {input_pointcloud}")

        geo_ref = _load_geo_reference(workspace)

        if geo_ref:
            logger.info(
                f"Geo-reference found: ECEF input → UTM EPSG:{geo_ref['utm_epsg']}"
            )
            writers_gdal_stage: dict = {
                "type": "writers.gdal",
                "filename": str(output_dsm),
                "resolution": self.settings.dsm_resolution,
                "output_type": self.settings.dsm_output_type,
                "radius": self.settings.dsm_radius,
                "override_srs": f"EPSG:{geo_ref['utm_epsg']}",
            }
            pipeline = {
                "pipeline": [
                    str(input_pointcloud),
                    {
                        "type": "filters.reprojection",
                        "in_srs": geo_ref["input_srs"],
                        "out_srs": f"EPSG:{geo_ref['utm_epsg']}",
                    },
                    writers_gdal_stage,
                ],
            }
        else:
            logger.warning(
                "No geo_reference.json found — DSM will be generated without CRS. "
                "Output will NOT be geotagged."
            )
            pipeline = {
                "pipeline": [
                    str(input_pointcloud),
                    {
                        "type": "writers.gdal",
                        "filename": str(output_dsm),
                        "resolution": self.settings.dsm_resolution,
                        "output_type": self.settings.dsm_output_type,
                        "radius": self.settings.dsm_radius,
                    },
                ],
            }

        # Write pipeline to temp file
        pipeline_file = workspace / "pdal_dsm_pipeline.json"
        with open(pipeline_file, "w") as f:
            json.dump(pipeline, f, indent=2)

        # Run PDAL
        cmd = ["pdal", "pipeline", str(pipeline_file)]
        if self.settings.pdal_threads > 0:
            cmd.extend(["--threads", str(self.settings.pdal_threads)])
        self._run_command(cmd, "PDAL DSM generation")

        logger.info(f"DSM generated: {output_dsm}")
        return output_dsm

    def generate_rgb_orthomosaic(
        self,
        project_id: str,
        input_pointcloud: Path | None = None,
        output_orthomosaic: Path | None = None,
    ) -> Path:
        """
        Generate RGB orthomosaic from point cloud with color information.

        This creates a textured orthomosaic showing actual terrain features
        (fields, roads, water, etc.) in their true colors.

        Args:
            project_id: Project identifier
            input_pointcloud: Path to input point cloud with RGB data
            output_orthomosaic: Path to output RGB orthomosaic

        Returns:
            Path to generated RGB orthomosaic
        """
        workspace = self._get_workspace(project_id)

        # Default paths
        if input_pointcloud is None:
            # Prefer fused_georef.ply (ECEF) so reprojection to UTM is correct.
            georef_candidate = workspace / "dense" / "fused_georef.ply"
            if georef_candidate.exists():
                input_pointcloud = georef_candidate
            else:
                input_pointcloud = workspace / "dense" / "fused.ply"
                if not input_pointcloud.exists():
                    input_pointcloud = workspace / "dense" / "meshed-poisson.ply"

        if output_orthomosaic is None:
            output_orthomosaic = workspace / "orthomosaic_rgb.tif"

        if not input_pointcloud.exists():
            raise FileNotFoundError(f"Point cloud not found: {input_pointcloud}")

        logger.info(f"Generating RGB orthomosaic from {input_pointcloud}")

        geo_ref = _load_geo_reference(workspace)
        if geo_ref:
            logger.info(
                f"Geo-reference found: reprojecting point cloud ECEF → "
                f"UTM EPSG:{geo_ref['utm_epsg']} for RGB orthomosaic"
            )
        else:
            logger.warning(
                "No geo_reference.json found — RGB orthomosaic will be generated "
                "without CRS. Output will NOT be geotagged."
            )

        red_file = workspace / "temp_red.tif"
        green_file = workspace / "temp_green.tif"
        blue_file = workspace / "temp_blue.tif"

        bands = [
            ("Red", red_file, workspace / "pdal_red.json"),
            ("Green", green_file, workspace / "pdal_green.json"),
            ("Blue", blue_file, workspace / "pdal_blue.json"),
        ]

        for dimension, output_file, pipeline_file in bands:
            writer_stage: dict = {
                "type": "writers.gdal",
                "filename": str(output_file),
                "resolution": self.settings.ortho_resolution,
                "output_type": "mean",
                "dimension": dimension,
                "data_type": "uint8",
                "window_size": 3,
            }

            if geo_ref:
                writer_stage["override_srs"] = f"EPSG:{geo_ref['utm_epsg']}"
                pipeline = {
                    "pipeline": [
                        str(input_pointcloud),
                        {
                            "type": "filters.reprojection",
                            "in_srs": geo_ref["input_srs"],
                            "out_srs": f"EPSG:{geo_ref['utm_epsg']}",
                        },
                        writer_stage,
                    ],
                }
            else:
                pipeline = {
                    "pipeline": [str(input_pointcloud), writer_stage],
                }

            with open(pipeline_file, "w") as f:
                json.dump(pipeline, f, indent=2)

        def _run_pdal_band(dimension: str, pipeline_file: Path) -> None:
            cmd = ["pdal", "pipeline", str(pipeline_file)]
            self._run_command(cmd, f"PDAL {dimension} band generation")

        logger.info("Running R/G/B PDAL pipelines in parallel...")
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(_run_pdal_band, dim, pf)
                for dim, _output_file, pf in bands
            ]
            for fut in futures:
                fut.result()

        # Merge RGB bands into single RGB GeoTIFF
        logger.info("Merging RGB bands into single orthomosaic...")
        cmd = [
            "gdal_merge.py",
            "-separate",
            "-o",
            str(output_orthomosaic),
            "-co",
            "PHOTOMETRIC=RGB",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "TILED=YES",
            str(red_file),
            str(green_file),
            str(blue_file),
        ]
        self._run_command(cmd, "GDAL RGB merge")

        # Clean up temporary files
        for temp_file in [
            red_file,
            green_file,
            blue_file,
        ] + [pf for _, _, pf in bands]:
            if temp_file.exists():
                temp_file.unlink()

        logger.info(f"RGB orthomosaic generated: {output_orthomosaic}")
        return output_orthomosaic

    def generate_hillshade(
        self,
        project_id: str,
        input_dsm: Path | None = None,
        output_hillshade: Path | None = None,
        azimuth: float = 315.0,
        altitude: float = 45.0,
    ) -> Path:
        """
        Generate hillshade from DSM for better visualization.

        Args:
            project_id: Project identifier
            input_dsm: Path to input DSM
            output_hillshade: Path to output hillshade
            azimuth: Light azimuth angle (0-360 degrees)
            altitude: Light altitude angle (0-90 degrees)

        Returns:
            Path to hillshade file
        """
        workspace = self._get_workspace(project_id)

        # Default paths
        if input_dsm is None:
            input_dsm = workspace / "dsm_filled.tif"
        if output_hillshade is None:
            output_hillshade = workspace / "hillshade.tif"

        if not input_dsm.exists():
            raise FileNotFoundError(f"Input DSM not found: {input_dsm}")

        logger.info(f"Generating hillshade from {input_dsm}")

        # Use GDAL DEM to create hillshade
        cmd = [
            "gdaldem",
            "hillshade",
            str(input_dsm),
            str(output_hillshade),
            "-az",
            str(azimuth),
            "-alt",
            str(altitude),
            "-compute_edges",
        ]
        self._run_command(cmd, "GDAL hillshade generation")

        logger.info(f"Hillshade generated: {output_hillshade}")
        return output_hillshade

    def fill_dsm_holes(
        self,
        project_id: str,
        input_dsm: Path | None = None,
        output_filled_dsm: Path | None = None,
    ) -> Path:
        """
        Fill holes in DSM using GDAL fillnodata algorithm.

        Args:
            project_id: Project identifier
            input_dsm: Path to input DSM with holes
            output_filled_dsm: Path to output filled DSM

        Returns:
            Path to filled DSM
        """
        workspace = self._get_workspace(project_id)

        # Default paths
        if input_dsm is None:
            input_dsm = workspace / "dsm.tif"
        if output_filled_dsm is None:
            output_filled_dsm = workspace / "dsm_filled.tif"

        if not input_dsm.exists():
            raise FileNotFoundError(f"Input DSM not found: {input_dsm}")

        logger.info(f"Filling holes in DSM: {input_dsm}")

        # Use GDAL fillnodata
        cmd = [
            "gdal_fillnodata.py",
            "-md",
            str(self.settings.fill_max_distance),
            "-si",
            str(self.settings.fill_smoothing_iterations),
            str(input_dsm),
            str(output_filled_dsm),
        ]
        self._run_command(cmd, "GDAL hole filling")

        logger.info(f"Filled DSM generated: {output_filled_dsm}")
        return output_filled_dsm

    def convert_to_cog(
        self,
        project_id: str,
        input_dsm: Path | None = None,
        output_cog: Path | None = None,
    ) -> Path:
        """
        Convert DSM to Cloud Optimized GeoTIFF (COG) format.

        Args:
            project_id: Project identifier
            input_dsm: Path to input DSM
            output_cog: Path to output COG

        Returns:
            Path to COG file
        """
        workspace = self._get_workspace(project_id)

        # Default paths
        if input_dsm is None:
            input_dsm = workspace / "dsm_filled.tif"
        if output_cog is None:
            output_cog = workspace / "dsm_filled_cog.tif"

        if not input_dsm.exists():
            raise FileNotFoundError(f"Input DSM not found: {input_dsm}")

        logger.info(f"Converting to COG: {input_dsm}")

        # Use GDAL translate to create COG
        cmd = [
            "gdal_translate",
            "-of",
            "COG",
            "-co",
            f"COMPRESS={self.settings.cog_compression}",
            "-co",
            f"PREDICTOR={self.settings.cog_predictor}",
            "-co",
            f"BLOCKSIZE={self.settings.cog_blocksize}",
            "-co",
            f"OVERVIEW_RESAMPLING={self.settings.cog_overview_resampling}",
            str(input_dsm),
            str(output_cog),
        ]
        self._run_command(cmd, "GDAL COG conversion")

        logger.info(f"COG generated: {output_cog}")
        return output_cog

    def add_overviews(
        self,
        input_path: Path,
        levels: list[int] | None = None,
    ) -> Path:
        """
        Add overview pyramids to a GeoTIFF using gdaladdo.

        Args:
            input_path: GeoTIFF to add overviews to
            levels: Overview levels (default: [2, 4, 8, 16])

        Returns:
            Path to the file (modified in-place)
        """
        if levels is None:
            levels = [2, 4, 8, 16]

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        logger.info(f"Adding overviews to {input_path}: levels={levels}")

        cmd = [
            "gdaladdo",
            "-r", "cubic",
            "--config", "COMPRESS_OVERVIEW", "DEFLATE",
            str(input_path),
        ] + [str(lv) for lv in levels]

        self._run_command(cmd, f"gdaladdo overviews for {input_path.name}")
        return input_path

    def generate_multi_resolution_outputs(
        self,
        project_id: str,
        input_raster: Path | None = None,
        scale_factors: list[int] | None = None,
    ) -> dict[str, str]:
        """
        Generate downsampled orthomosaic outputs at multiple resolutions.

        Creates resampled GeoTIFFs at 2×, 4×, and 8× the native GSD using
        cubic interpolation, plus adds overview pyramids to the native file.

        Args:
            project_id: Project identifier
            input_raster: Source GeoTIFF (default: orthomosaic_rgb.tif)
            scale_factors: Downsample factors (default: [2, 4, 8])

        Returns:
            Mapping of product key → output file path
        """
        workspace = self._get_workspace(project_id)

        if input_raster is None:
            input_raster = workspace / "orthomosaic_rgb.tif"

        if not input_raster.exists():
            raise FileNotFoundError(f"Input raster not found: {input_raster}")

        if scale_factors is None:
            scale_factors = [2, 4, 8]

        self.add_overviews(input_raster)

        native_gsd = self._read_pixel_size(input_raster)
        logger.info(
            f"Native GSD: {native_gsd:.4f} m/px — "
            f"generating {len(scale_factors)} downsampled variants"
        )

        products: dict[str, str] = {}

        for factor in scale_factors:
            target_res = native_gsd * factor
            out_name = f"orthomosaic_rgb_{factor}x.tif"
            out_path = workspace / out_name

            pct = 100.0 / factor

            cmd = [
                "gdal_translate",
                "-of", "COG",
                "-outsize", f"{pct}%", f"{pct}%",
                "-r", "cubic",
                "-co", f"COMPRESS={self.settings.cog_compression}",
                "-co", f"BLOCKSIZE={self.settings.cog_blocksize}",
                "-co", f"OVERVIEW_RESAMPLING={self.settings.cog_overview_resampling}",
                str(input_raster),
                str(out_path),
            ]

            self._run_command(
                cmd,
                f"Downsample {factor}× ({target_res:.4f} m/px) → {out_name}",
            )
            products[f"orthomosaic_rgb_{factor}x"] = str(out_path)

            logger.info(
                f"Generated {out_name}: {factor}× downsample "
                f"({target_res:.4f} m/px)"
            )

        return products

    def _read_pixel_size(self, raster_path: Path) -> float:
        """
        Read the pixel size (GSD) from a GeoTIFF.

        Args:
            raster_path: Path to the GeoTIFF

        Returns:
            Pixel size in map units (typically meters)
        """
        result = subprocess.run(
            ["gdalinfo", "-json", str(raster_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        info = json.loads(result.stdout)
        gt = info.get("geoTransform", [0, 1, 0, 0, 0, -1])
        return abs(gt[1])

    def generate_statistics(self, project_id: str) -> dict:
        """
        Generate statistics about the orthomosaic outputs.

        Args:
            project_id: Project identifier

        Returns:
            Dictionary with statistics
        """
        workspace = self._get_workspace(project_id)

        logger.info(f"Generating statistics for project {project_id}")

        stats = {
            "project_id": project_id,
            "workspace": str(workspace),
            "outputs": {},
        }

        # Check for output files and get their info
        for output_file in [
            "dsm.tif",
            "dsm_filled.tif",
            "dsm_filled_cog.tif",
            "orthomosaic_rgb.tif",
            "hillshade.tif",
        ]:
            file_path = workspace / output_file
            if file_path.exists():
                # Get file size
                stats["outputs"][output_file] = {  # type: ignore
                    "path": str(file_path),
                    "size_mb": file_path.stat().st_size / (1024 * 1024),
                    "exists": True,
                }

                # Get raster info using gdalinfo
                try:
                    result = subprocess.run(
                        ["gdalinfo", "-json", str(file_path)],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    info = json.loads(result.stdout)
                    stats["outputs"][output_file]["width"] = info["size"][0]  # type: ignore
                    stats["outputs"][output_file]["height"] = info["size"][1]  # type: ignore
                    stats["outputs"][output_file]["bands"] = len(info["bands"])  # type: ignore
                    if "geoTransform" in info:
                        stats["outputs"][output_file]["geotransform"] = info[  # type: ignore
                            "geoTransform"
                        ]
                    if "coordinateSystem" in info:
                        stats["outputs"][output_file]["crs"] = info["coordinateSystem"][  # type: ignore
                            "wkt"
                        ]
                except Exception as e:
                    logger.warning(
                        f"Could not get detailed info for {output_file}: {e}",
                    )
            else:
                stats["outputs"][output_file] = {"exists": False}  # type: ignore

        # Save statistics
        stats_file = workspace / "orthomosaic_statistics.json"
        with open(stats_file, "w") as f:
            json.dump(stats, f, indent=2)

        logger.info(f"Statistics saved to {stats_file}")
        return stats

    def start(self, dataset_path: Path) -> str:
        """
        Initialize orthomosaic workspace.

        Args:
            dataset_path: Path to dataset containing SFM results

        Returns:
            project_id: Identifier for this orthomosaic project
        """
        if not dataset_path.is_absolute():
            raise ValueError("The dataset_path must be an absolute path.")

        if not dataset_path.exists():
            raise ValueError(f"The dataset_path '{dataset_path}' does not exist.")

        # Generate unique project ID
        project_id = f"{self.__service_name}_{dataset_path.name}_{uuid.uuid4().hex[:8]}"

        # Use dataset path as workspace
        workspace = dataset_path

        # Store project workspace
        self._projects[project_id] = workspace

        logger.info(f"Orthomosaic workspace initialized: {workspace}")
        logger.info(f"Project ID: {project_id}")

        return project_id

    def stop(self, project_id: str):
        """
        Stop project (no-op, kept for interface compatibility).

        Args:
            project_id: Project identifier
        """
        logger.info(f"Stop called for project {project_id} (no-op)")

    def clean(self, project_id: str):
        """
        Clean up project workspace (removes from tracking only).

        Args:
            project_id: Project identifier
        """
        if project_id not in self._projects:
            logger.warning(f"Project '{project_id}' not found for cleanup")
            return

        workspace = self._projects[project_id]

        logger.info(
            f"Cleaning project {project_id} (workspace preserved at: {workspace})",
        )

        # Remove from tracking only - workspace remains intact
        del self._projects[project_id]
