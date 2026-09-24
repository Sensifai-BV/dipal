import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from benchmark.settings import BenchmarkSettings


@dataclass
class RadiometricResult:
    """Result of radiometric calibration validation."""

    r_squared: float
    passed: bool
    num_samples: int
    band_results: dict[str, float]
    details: dict


class RadiometricValidator:
    """
    Validate radiometric calibration accuracy.

    Compares calibrated reflectance values against known reference
    panel values or ground truth spectral data.
    """

    def __init__(self, settings: BenchmarkSettings):
        self.settings = settings

    def validate(self, output_path: Path) -> RadiometricResult:
        """
        Validate radiometric calibration output against reference data.

        Args:
            output_path: Path to calibration benchmark output

        Returns:
            RadiometricResult with R² values per band

        Raises:
            FileNotFoundError: If reference or calibrated data not found
        """
        reference = self._load_reference_values()
        calibrated = self._load_calibrated_values(output_path)

        band_results: dict[str, float] = {}
        all_ref = []
        all_cal = []

        for band in reference:
            if band not in calibrated:
                continue
            ref_vals = np.array(reference[band])
            cal_vals = np.array(calibrated[band])

            min_len = min(len(ref_vals), len(cal_vals))
            ref_vals = ref_vals[:min_len]
            cal_vals = cal_vals[:min_len]

            r2 = self._compute_r_squared(ref_vals, cal_vals)
            band_results[band] = r2

            all_ref.extend(ref_vals.tolist())
            all_cal.extend(cal_vals.tolist())

        overall_r2 = 0.0
        if all_ref:
            overall_r2 = self._compute_r_squared(
                np.array(all_ref), np.array(all_cal)
            )

        return RadiometricResult(
            r_squared=overall_r2,
            passed=overall_r2 >= self.settings.radiometric_r2_threshold,
            num_samples=len(all_ref),
            band_results=band_results,
            details={
                "threshold": self.settings.radiometric_r2_threshold,
                "bands_tested": list(band_results.keys()),
            },
        )

    def _load_reference_values(self) -> dict[str, list[float]]:
        """
        Load reference reflectance values from ground truth directory.

        Returns:
            Dict mapping band name to list of reflectance values

        Raises:
            FileNotFoundError: If no reference file found
        """
        if self.settings.ground_truth_path is None:
            raise FileNotFoundError("No ground_truth_path configured")

        gt = self.settings.ground_truth_path
        for name in ["reference_reflectance.csv", "panel_values.csv", "spectral_reference.csv"]:
            candidate = gt / name
            if candidate.exists():
                return self._parse_reflectance_csv(candidate)
        raise FileNotFoundError(f"No reference reflectance file in {gt}")

    def _load_calibrated_values(self, output_path: Path) -> dict[str, list[float]]:
        """
        Load calibrated reflectance values from benchmark output.

        Args:
            output_path: Path to calibration output directory

        Returns:
            Dict mapping band name to list of calibrated reflectance values

        Raises:
            FileNotFoundError: If no calibrated reflectance file found
        """
        for name in ["calibrated_reflectance.csv", "reflectance_values.csv"]:
            candidate = output_path / name
            if candidate.exists():
                return self._parse_reflectance_csv(candidate)
        raise FileNotFoundError(f"No calibrated reflectance file in {output_path}")

    @staticmethod
    def _parse_reflectance_csv(path: Path) -> dict[str, list[float]]:
        """
        Parse a CSV with band columns and reflectance value rows.

        Args:
            path: Path to CSV file

        Returns:
            Dict mapping band name to list of values
        """
        bands: dict[str, list[float]] = {}
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                for key, val in row.items():
                    if key.lower() in ("id", "sample", "index", "name"):
                        continue
                    if key not in bands:
                        bands[key] = []
                    try:
                        bands[key].append(float(val))
                    except (ValueError, TypeError):
                        continue
        return bands

    @staticmethod
    def _compute_r_squared(observed: np.ndarray, predicted: np.ndarray) -> float:
        """
        Compute coefficient of determination (R²).

        Args:
            observed: Reference/observed values
            predicted: Predicted/calibrated values

        Returns:
            R² value between 0 and 1
        """
        if len(observed) < 2:
            return 0.0
        ss_res = np.sum((observed - predicted) ** 2)
        ss_tot = np.sum((observed - np.mean(observed)) ** 2)
        if ss_tot == 0:
            return 1.0 if ss_res == 0 else 0.0
        return float(1.0 - ss_res / ss_tot)
