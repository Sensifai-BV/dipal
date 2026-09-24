import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from benchmark.settings import BenchmarkSettings


@dataclass
class VegetationResult:
    """Result of vegetation index accuracy validation."""

    ndvi_r_squared: float | None
    ndre_r_squared: float | None
    overall_r_squared: float
    passed: bool
    num_samples: int
    index_results: dict[str, float]
    details: dict


class VegetationIndexValidator:
    """
    Validate vegetation index accuracy against reference maps.

    Computes NDVI and NDRE from ortho band data and compares
    against reference vegetation index rasters or CSV values.
    """

    BAND_NAMES_NIR = ("nir", "nir_band", "band_nir", "band5")
    BAND_NAMES_RED = ("red", "red_band", "band_red", "band3")
    BAND_NAMES_REDEDGE = ("rededge", "red_edge", "rededge_band", "band_rededge", "band4")

    def __init__(self, settings: BenchmarkSettings):
        self.settings = settings

    def validate(self, output_path: Path) -> VegetationResult:
        """
        Compare computed vegetation indices against reference data.

        Args:
            output_path: Path to orthomosaic output directory

        Returns:
            VegetationResult with per-index R² values

        Raises:
            FileNotFoundError: If reference or computed indices not found
        """
        reference = self._load_reference_indices()
        computed = self._load_computed_indices(output_path)

        index_results: dict[str, float] = {}
        all_ref: list[float] = []
        all_comp: list[float] = []

        for idx_name in reference:
            if idx_name not in computed:
                continue

            ref_vals = reference[idx_name]
            comp_vals = computed[idx_name]

            min_len = min(len(ref_vals), len(comp_vals))
            ref_arr = np.array(ref_vals[:min_len])
            comp_arr = np.array(comp_vals[:min_len])

            valid = np.isfinite(ref_arr) & np.isfinite(comp_arr)
            ref_arr = ref_arr[valid]
            comp_arr = comp_arr[valid]

            if len(ref_arr) < 2:
                continue

            r2 = self._compute_r_squared(ref_arr, comp_arr)
            index_results[idx_name] = r2
            all_ref.extend(ref_arr.tolist())
            all_comp.extend(comp_arr.tolist())

        overall_r2 = 0.0
        if len(all_ref) >= 2:
            overall_r2 = self._compute_r_squared(
                np.array(all_ref), np.array(all_comp)
            )

        ndvi_r2 = index_results.get("ndvi")
        ndre_r2 = index_results.get("ndre")

        return VegetationResult(
            ndvi_r_squared=ndvi_r2,
            ndre_r_squared=ndre_r2,
            overall_r_squared=overall_r2,
            passed=overall_r2 >= self.settings.vegetation_r2_threshold,
            num_samples=len(all_ref),
            index_results=index_results,
            details={
                "threshold": self.settings.vegetation_r2_threshold,
                "indices_tested": list(index_results.keys()),
            },
        )

    @staticmethod
    def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
        """
        Compute Normalised Difference Vegetation Index.

        Args:
            nir: Near-infrared band array
            red: Red band array

        Returns:
            NDVI array with values in [-1, 1]
        """
        denom = nir.astype(np.float64) + red.astype(np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            ndvi = np.where(denom != 0, (nir - red) / denom, np.nan)
        return ndvi

    @staticmethod
    def compute_ndre(nir: np.ndarray, rededge: np.ndarray) -> np.ndarray:
        """
        Compute Normalised Difference Red-Edge Index.

        Args:
            nir: Near-infrared band array
            rededge: Red-edge band array

        Returns:
            NDRE array with values in [-1, 1]
        """
        denom = nir.astype(np.float64) + rededge.astype(np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            ndre = np.where(denom != 0, (nir - rededge) / denom, np.nan)
        return ndre

    @staticmethod
    def _compute_r_squared(observed: np.ndarray, predicted: np.ndarray) -> float:
        """
        Compute coefficient of determination (R²).

        Args:
            observed: Ground truth values
            predicted: Predicted / computed values

        Returns:
            R² value (can be negative for poor fits)
        """
        if len(observed) < 2:
            return 0.0
        ss_res = np.sum((observed - predicted) ** 2)
        ss_tot = np.sum((observed - np.mean(observed)) ** 2)
        if ss_tot == 0:
            return 1.0 if ss_res == 0 else 0.0
        return float(1.0 - ss_res / ss_tot)

    def _load_reference_indices(self) -> dict[str, list[float]]:
        """
        Load reference vegetation index values from ground truth.

        Returns:
            Dict mapping index name (ndvi, ndre) to list of values

        Raises:
            FileNotFoundError: If no reference vegetation data found
        """
        if self.settings.ground_truth_path is None:
            raise FileNotFoundError("No ground_truth_path configured")

        gt = self.settings.ground_truth_path

        for name in ["reference_ndvi.csv", "vegetation_indices.csv", "ndvi_reference.csv"]:
            candidate = gt / name
            if candidate.exists():
                return self._parse_index_csv(candidate)

        ndvi_raster = self._find_raster(gt, "ndvi")
        ndre_raster = self._find_raster(gt, "ndre")
        if ndvi_raster or ndre_raster:
            return self._load_raster_indices(ndvi_raster, ndre_raster)

        raise FileNotFoundError(f"No reference vegetation index data in {gt}")

    def _load_computed_indices(self, output_path: Path) -> dict[str, list[float]]:
        """
        Load computed vegetation index values from benchmark output.

        Args:
            output_path: Path to orthomosaic output directory

        Returns:
            Dict mapping index name to list of values

        Raises:
            FileNotFoundError: If no computed index data found
        """
        for name in ["vegetation_indices.csv", "ndvi_values.csv", "computed_indices.csv"]:
            candidate = output_path / name
            if candidate.exists():
                return self._parse_index_csv(candidate)

        ndvi_raster = self._find_raster(output_path, "ndvi")
        ndre_raster = self._find_raster(output_path, "ndre")
        if ndvi_raster or ndre_raster:
            return self._load_raster_indices(ndvi_raster, ndre_raster)

        return self._compute_from_bands(output_path)

    @staticmethod
    def _parse_index_csv(path: Path) -> dict[str, list[float]]:
        """
        Parse a CSV file containing vegetation index columns.

        Args:
            path: Path to vegetation index CSV

        Returns:
            Dict mapping index name to list of float values
        """
        result: dict[str, list[float]] = {}
        with path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                for col, val in row.items():
                    col_lower = col.strip().lower()
                    if col_lower in ("id", "plot_id", "point_id", "sample_id"):
                        continue
                    try:
                        result.setdefault(col_lower, []).append(float(val))
                    except (ValueError, TypeError):
                        continue
        return result

    @staticmethod
    def _find_raster(directory: Path, pattern: str) -> Path | None:
        """
        Find a raster file matching a pattern in a directory.

        Args:
            directory: Directory to search
            pattern: Substring to match in filenames

        Returns:
            Path to matching raster file or None
        """
        for ext in (".tif", ".tiff"):
            matches = list(directory.glob(f"*{pattern}*{ext}"))
            if matches:
                return matches[0]
        return None

    @staticmethod
    def _load_raster_indices(
        ndvi_path: Path | None,
        ndre_path: Path | None,
    ) -> dict[str, list[float]]:
        """
        Load vegetation index values from GeoTIFF rasters.

        Args:
            ndvi_path: Path to NDVI raster or None
            ndre_path: Path to NDRE raster or None

        Returns:
            Dict mapping index name to sampled pixel values
        """
        try:
            import rasterio
        except ImportError:
            return {}

        result: dict[str, list[float]] = {}

        for name, path in [("ndvi", ndvi_path), ("ndre", ndre_path)]:
            if path is None or not path.exists():
                continue
            with rasterio.open(path) as ds:
                band = ds.read(1).astype(np.float64).ravel()
                valid = np.isfinite(band) & (band >= -1.0) & (band <= 1.0)
                values = band[valid]
                if len(values) > 10000:
                    rng = np.random.default_rng(seed=42)
                    values = rng.choice(values, size=10000, replace=False)
                result[name] = values.tolist()

        return result

    def _compute_from_bands(self, output_path: Path) -> dict[str, list[float]]:
        """
        Compute NDVI/NDRE from multi-band orthomosaic.

        Args:
            output_path: Path to orthomosaic output directory

        Returns:
            Dict mapping index name to computed values
        """
        try:
            import rasterio
        except ImportError:
            return {}

        ortho_candidates = list(output_path.glob("*orthomosaic*.tif"))
        if not ortho_candidates:
            return {}

        with rasterio.open(ortho_candidates[0]) as ds:
            if ds.count < 4:
                return {}

            red = ds.read(3).astype(np.float64).ravel()
            nir = ds.read(4).astype(np.float64).ravel()

            ndvi = self.compute_ndvi(nir, red).ravel()
            valid = np.isfinite(ndvi)
            ndvi_vals = ndvi[valid]

            result: dict[str, list[float]] = {}

            if len(ndvi_vals) > 10000:
                rng = np.random.default_rng(seed=42)
                indices = rng.choice(len(ndvi_vals), size=10000, replace=False)
                result["ndvi"] = ndvi_vals[indices].tolist()
            else:
                result["ndvi"] = ndvi_vals.tolist()

            if ds.count >= 5:
                rededge = ds.read(5).astype(np.float64).ravel()
                ndre = self.compute_ndre(nir, rededge).ravel()
                valid_re = np.isfinite(ndre)
                ndre_vals = ndre[valid_re]
                if len(ndre_vals) > 10000:
                    rng = np.random.default_rng(seed=42)
                    indices = rng.choice(len(ndre_vals), size=10000, replace=False)
                    result["ndre"] = ndre_vals[indices].tolist()
                else:
                    result["ndre"] = ndre_vals.tolist()

            return result
