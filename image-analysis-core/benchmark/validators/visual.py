from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class VisualQAResult:
    """Result of visual quality assessment."""

    score: float
    passed: bool
    artifacts_detected: list[str]
    coverage_percent: float
    details: dict


VISUAL_QA_PASS_THRESHOLD = 0.7


class VisualQAValidator:
    """
    Assess visual quality of orthomosaic outputs.

    Detects common artifacts: black regions (no-data), blurriness,
    seam lines, and color inconsistency.
    """

    def validate(self, output_path: Path) -> VisualQAResult:
        """
        Run visual QA checks on orthomosaic imagery.

        Args:
            output_path: Path to orthomosaic output directory

        Returns:
            VisualQAResult with quality score and detected artifacts
        """
        try:
            import cv2
        except ImportError:
            return VisualQAResult(
                score=0.0,
                passed=False,
                artifacts_detected=["cv2_not_installed"],
                coverage_percent=0.0,
                details={"error": "opencv-python not installed"},
            )
        ortho_files = list(output_path.glob("*orthomosaic*.tif"))
        if not ortho_files:
            ortho_files = list(output_path.glob("*.tif"))

        if not ortho_files:
            return VisualQAResult(
                score=0.0,
                passed=False,
                artifacts_detected=["no_output_file"],
                coverage_percent=0.0,
                details={"error": "No orthomosaic TIF found"},
            )

        image = cv2.imread(str(ortho_files[0]), cv2.IMREAD_UNCHANGED)
        if image is None:
            return VisualQAResult(
                score=0.0,
                passed=False,
                artifacts_detected=["unreadable_file"],
                coverage_percent=0.0,
                details={"error": f"Could not read {ortho_files[0]}"},
            )

        artifacts = []
        scores = []

        coverage = self._check_coverage(image)
        if coverage < 0.5:
            artifacts.append("low_coverage")
        scores.append(coverage)

        blur_score = self._check_blur(image)
        if blur_score < 0.3:
            artifacts.append("excessive_blur")
        scores.append(blur_score)

        color_score = self._check_color_consistency(image)
        if color_score < 0.5:
            artifacts.append("color_inconsistency")
        scores.append(color_score)

        seam_score = self._check_seam_artifacts(image)
        if seam_score < 0.5:
            artifacts.append("visible_seams")
        scores.append(seam_score)

        overall = float(np.mean(scores))

        return VisualQAResult(
            score=overall,
            passed=overall >= VISUAL_QA_PASS_THRESHOLD,
            artifacts_detected=artifacts,
            coverage_percent=coverage * 100.0,
            details={
                "coverage_score": coverage,
                "blur_score": blur_score,
                "color_consistency_score": color_score,
                "seam_score": seam_score,
                "file": str(ortho_files[0]),
            },
        )

    @staticmethod
    def _check_coverage(image: np.ndarray) -> float:
        """
        Measure fraction of non-black (non-nodata) pixels.

        Args:
            image: Input image array

        Returns:
            Coverage fraction 0.0 to 1.0
        """
        import cv2

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        non_zero = np.count_nonzero(gray)
        total = gray.size
        return non_zero / total if total > 0 else 0.0

    @staticmethod
    def _check_blur(image: np.ndarray) -> float:
        """
        Assess image sharpness using Laplacian variance.

        Args:
            image: Input image array

        Returns:
            Normalized sharpness score 0.0 to 1.0
        """
        import cv2

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        if gray.dtype != np.uint8:
            gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return min(laplacian_var / 500.0, 1.0)

    @staticmethod
    def _check_color_consistency(image: np.ndarray) -> float:
        """
        Check for color banding or abrupt shifts across the image.

        Args:
            image: Input image array (BGR)

        Returns:
            Color consistency score 0.0 to 1.0
        """
        if len(image.shape) != 3 or image.shape[2] < 3:
            return 1.0

        h, w = image.shape[:2]
        quarter_h = max(h // 4, 1)
        quarter_w = max(w // 4, 1)

        quadrants = [
            image[:quarter_h, :quarter_w],
            image[:quarter_h, -quarter_w:],
            image[-quarter_h:, :quarter_w],
            image[-quarter_h:, -quarter_w:],
        ]

        means = []
        for q in quadrants:
            mask = np.any(q > 0, axis=2) if len(q.shape) == 3 else q > 0
            if np.any(mask):
                means.append(q[mask].mean())

        if len(means) < 2:
            return 1.0

        mean_range = max(means) - min(means)
        return max(0.0, 1.0 - mean_range / 128.0)

    @staticmethod
    def _check_seam_artifacts(image: np.ndarray) -> float:
        """
        Detect visible seam lines using edge detection.

        Args:
            image: Input image array

        Returns:
            Seam quality score 0.0 to 1.0 (higher = fewer seams)
        """
        import cv2

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        if gray.dtype != np.uint8:
            gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.count_nonzero(edges) / edges.size
        return max(0.0, 1.0 - edge_density * 10.0)
