import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from benchmark.settings import BenchmarkSettings


@dataclass
class SpatialResult:
    """Result of spatial accuracy validation."""

    gsd_measured: float | None
    gsd_expected: float | None
    gsd_deviation: float | None
    gsd_passed: bool
    reproducibility_correlation: float | None
    reproducibility_passed: bool
    details: dict


class SpatialValidator:
    """
    Validate GSD accuracy and run-to-run reproducibility.

    Measures Ground Sampling Distance accuracy against expected values
    and compares orthomosaic outputs across multiple runs.
    """

    def __init__(self, settings: BenchmarkSettings):
        self.settings = settings

    def validate(self, run_results: list[dict]) -> SpatialResult:
        """
        Validate spatial accuracy across benchmark runs.

        Args:
            run_results: List of per-run result dicts with output_path keys

        Returns:
            SpatialResult with GSD accuracy and reproducibility metrics
        """
        gsd_measured = None
        gsd_expected = self.settings.target_gsd
        gsd_deviation = None
        gsd_passed = True

        if run_results:
            gsd_measured = self._measure_gsd(Path(run_results[0].get("output_path", "")))

        if gsd_measured is not None and gsd_expected is not None:
            gsd_deviation = abs(gsd_measured - gsd_expected) / gsd_expected
            gsd_passed = gsd_deviation <= self.settings.gsd_accuracy_threshold

        repro_corr = None
        repro_passed = True

        if len(run_results) >= 2:
            repro_corr = self._compute_reproducibility(run_results)
            if repro_corr is not None:
                repro_passed = repro_corr >= self.settings.reproducibility_threshold

        return SpatialResult(
            gsd_measured=gsd_measured,
            gsd_expected=gsd_expected,
            gsd_deviation=gsd_deviation,
            gsd_passed=gsd_passed,
            reproducibility_correlation=repro_corr,
            reproducibility_passed=repro_passed,
            details={
                "gsd_threshold": self.settings.gsd_accuracy_threshold,
                "reproducibility_threshold": self.settings.reproducibility_threshold,
                "num_runs_compared": len(run_results),
            },
        )

    def _measure_gsd(self, output_path: Path) -> float | None:
        """
        Measure GSD from orthomosaic statistics or GeoTIFF metadata.

        Args:
            output_path: Path to orthomosaic output directory

        Returns:
            Measured GSD in cm/px or None if unavailable
        """
        stats_file = output_path / "orthomosaic_statistics.json"
        if stats_file.exists():
            stats = json.loads(stats_file.read_text())
            if "gsd" in stats:
                return float(stats["gsd"])
            if "resolution" in stats:
                return float(stats["resolution"]) * 100.0

        try:
            import rasterio

            ortho_candidates = list(output_path.glob("*orthomosaic*.tif"))
            if ortho_candidates:
                with rasterio.open(ortho_candidates[0]) as ds:
                    return abs(ds.transform.a) * 100.0
        except ImportError:
            pass

        return None

    def _compute_reproducibility(self, run_results: list[dict]) -> float | None:
        """
        Compute pixel-wise correlation between outputs of multiple runs.

        Args:
            run_results: List of per-run result dicts

        Returns:
            Mean pairwise correlation coefficient or None
        """
        try:
            import rasterio
        except ImportError:
            return None

        arrays = []
        for r in run_results:
            path = Path(r.get("output_path", ""))
            ortho_files = list(path.glob("*orthomosaic*.tif"))
            if not ortho_files:
                continue
            with rasterio.open(ortho_files[0]) as ds:
                data = ds.read(1).flatten().astype(np.float64)
                arrays.append(data)

        if len(arrays) < 2:
            return None

        correlations = []
        for i in range(len(arrays)):
            for j in range(i + 1, len(arrays)):
                min_len = min(len(arrays[i]), len(arrays[j]))
                a = arrays[i][:min_len]
                b = arrays[j][:min_len]
                if np.std(a) == 0 or np.std(b) == 0:
                    correlations.append(1.0 if np.array_equal(a, b) else 0.0)
                else:
                    corr = np.corrcoef(a, b)[0, 1]
                    correlations.append(float(corr))

        return float(np.mean(correlations)) if correlations else None
