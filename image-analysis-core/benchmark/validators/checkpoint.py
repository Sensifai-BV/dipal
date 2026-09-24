import csv
import math
from dataclasses import dataclass
from pathlib import Path

from benchmark.settings import BenchmarkSettings


@dataclass
class CheckpointResult:
    """Result of checkpoint RMSE validation."""

    horizontal_rmse: float
    vertical_rmse: float | None
    num_checkpoints: int
    passed_horizontal: bool
    passed_vertical: bool
    details: list[dict]


class CheckpointValidator:
    """
    Validate 3D reconstruction accuracy against ground control points.

    Computes horizontal and vertical RMSE between estimated camera/point
    positions and known GCP coordinates.
    """

    def __init__(self, settings: BenchmarkSettings):
        self.settings = settings

    def validate(self, output_path: Path) -> CheckpointResult:
        """
        Compare reconstructed coordinates against GCPs.

        Args:
            output_path: Path to the benchmark run output directory

        Returns:
            CheckpointResult with RMSE values and pass/fail

        Raises:
            FileNotFoundError: If GCP or reconstruction files not found
        """
        gcp_path = self._find_gcp_file()
        gcps = self._load_gcps(gcp_path)

        estimated_path = self._find_estimated_coordinates(output_path)
        estimated = self._load_estimated(estimated_path)

        matched = self._match_points(gcps, estimated)

        h_errors = []
        v_errors = []
        details = []

        for point_id, (gcp, est) in matched.items():
            dx = gcp["x"] - est["x"]
            dy = gcp["y"] - est["y"]
            h_err = math.sqrt(dx**2 + dy**2)
            h_errors.append(h_err)

            v_err = None
            if "z" in gcp and "z" in est:
                v_err = abs(gcp["z"] - est["z"])
                v_errors.append(v_err)

            details.append({
                "point_id": point_id,
                "horizontal_error": h_err,
                "vertical_error": v_err,
                "gcp": gcp,
                "estimated": est,
            })

        h_rmse = self._compute_rmse(h_errors) if h_errors else float("inf")
        v_rmse = self._compute_rmse(v_errors) if v_errors else None

        passed_v = True
        if v_rmse is not None:
            passed_v = v_rmse <= self.settings.checkpoint_rmse_v_threshold

        return CheckpointResult(
            horizontal_rmse=h_rmse,
            vertical_rmse=v_rmse,
            num_checkpoints=len(matched),
            passed_horizontal=h_rmse <= self.settings.checkpoint_rmse_h_threshold,
            passed_vertical=passed_v,
            details=details,
        )

    def _find_gcp_file(self) -> Path:
        """
        Locate the GCP file in the ground truth directory.

        Returns:
            Path to the GCP CSV file

        Raises:
            FileNotFoundError: If no GCP file found
        """
        if self.settings.ground_truth_path is None:
            raise FileNotFoundError("No ground_truth_path configured")
        gt = self.settings.ground_truth_path
        for name in ["gcps.csv", "gcp.csv", "ground_control_points.csv", "checkpoints.csv"]:
            candidate = gt / name
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"No GCP file found in {gt}")

    def _find_estimated_coordinates(self, output_path: Path) -> Path:
        """
        Locate estimated coordinate file from reconstruction output.

        Args:
            output_path: Path to benchmark run output

        Returns:
            Path to estimated coordinates file

        Raises:
            FileNotFoundError: If no coordinate file found
        """
        for name in ["estimated_coords.csv", "cameras.csv", "geo_reference.csv"]:
            candidate = output_path / name
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"No estimated coordinates in {output_path}")

    def _load_gcps(self, path: Path) -> dict[str, dict]:
        """
        Load GCPs from CSV (columns: id, x, y, z).

        Args:
            path: Path to CSV file

        Returns:
            Dict mapping point_id to coordinate dict
        """
        points: dict[str, dict] = {}
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row.get("id", row.get("point_id", row.get("name", "")))
                point: dict = {"x": float(row["x"]), "y": float(row["y"])}
                if "z" in row and row["z"]:
                    point["z"] = float(row["z"])
                points[pid] = point
        return points

    def _load_estimated(self, path: Path) -> dict[str, dict]:
        """
        Load estimated coordinates from CSV.

        Args:
            path: Path to CSV file

        Returns:
            Dict mapping point_id to coordinate dict
        """
        return self._load_gcps(path)

    def _match_points(
        self, gcps: dict[str, dict], estimated: dict[str, dict]
    ) -> dict[str, tuple[dict, dict]]:
        """
        Match GCPs with estimated coordinates by point ID.

        Args:
            gcps: Ground control point coordinates
            estimated: Estimated coordinates

        Returns:
            Dict mapping point_id to (gcp, estimated) tuple
        """
        matched = {}
        for pid in gcps:
            if pid in estimated:
                matched[pid] = (gcps[pid], estimated[pid])
        return matched

    @staticmethod
    def _compute_rmse(errors: list[float]) -> float:
        """
        Compute root mean square error.

        Args:
            errors: List of individual errors

        Returns:
            RMSE value
        """
        if not errors:
            return 0.0
        mean_sq = sum(e**2 for e in errors) / len(errors)
        return math.sqrt(mean_sq)
