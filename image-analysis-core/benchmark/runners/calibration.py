import json
from pathlib import Path

import requests

from benchmark.runners.base import BaseRunner, RunResult


class CalibrationRunner(BaseRunner):
    """Runner for the radiometric calibration stage."""

    @property
    def stage_name(self) -> str:
        return "calibration"

    def _execute(self, run_index: int) -> RunResult:
        """
        Trigger radiometric calibration via the service API.

        Args:
            run_index: Index of current run (0-based)

        Returns:
            RunResult with calibration output info
        """
        job_id = f"bench_cal_{run_index}"
        dataset_id = f"bench_dataset_{run_index}"
        images_path = self.settings.dataset_path / "images"

        image_files = self._collect_image_files(images_path)

        payload = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "download_url": image_files,
            "parameters": self._build_parameters(),
        }

        response = requests.post(
            f"{self.settings.gateway_url}/api/v1/calibration/run",
            json=payload,
            timeout=self.settings.timeout_seconds,
        )
        response.raise_for_status()
        result_data = response.json()

        output_dir = self.settings.output_path / "calibration" / f"run_{run_index}"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "result.json").write_text(json.dumps(result_data, indent=2))

        return RunResult(
            stage=self.stage_name,
            run_index=run_index,
            success=True,
            elapsed_seconds=0.0,
            output_path=output_dir,
            metrics={
                "is_multispectral": result_data.get("is_multispectral", False),
                "has_reflectance": result_data.get("has_reflectance", False),
                "image_count": len(image_files),
            },
        )

    def _collect_image_files(self, images_path: Path) -> list[dict]:
        """
        Collect image file paths formatted for the calibration API.

        Args:
            images_path: Path to directory containing images

        Returns:
            List of dicts with filename and url keys
        """
        extensions = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".dng"}
        files = []
        for f in sorted(images_path.iterdir()):
            if f.suffix.lower() in extensions:
                files.append({"filename": f.name, "url": str(f)})
        return files

    def _build_parameters(self) -> dict:
        """
        Build parameters dict from benchmark settings.

        Returns:
            Parameters dict for the calibration API
        """
        params: dict = {}
        if self.settings.target_gsd is not None:
            params["target_gsd"] = self.settings.target_gsd
        return params
