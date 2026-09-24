import json

import requests

from benchmark.runners.base import BaseRunner, RunResult


class SFMRunner(BaseRunner):
    """Runner for the Structure from Motion (COLMAP) stage."""

    @property
    def stage_name(self) -> str:
        return "sfm"

    def _execute(self, run_index: int) -> RunResult:
        """
        Trigger SFM processing via the service API.

        Args:
            run_index: Index of current run (0-based)

        Returns:
            RunResult with SFM output info
        """
        job_id = f"bench_sfm_{run_index}"
        dataset_id = f"bench_dataset_{run_index}"
        images_path = self.settings.dataset_path / "images"

        image_files = []
        extensions = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}
        for f in sorted(images_path.iterdir()):
            if f.suffix.lower() in extensions:
                image_files.append({"filename": f.name, "url": str(f)})

        payload = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "download_url": image_files,
            "parameters": self._build_parameters(),
        }

        response = requests.post(
            f"{self.settings.gateway_url}/api/v1/sfm/run",
            json=payload,
            timeout=self.settings.timeout_seconds,
        )
        response.raise_for_status()
        result_data = response.json()

        output_dir = self.settings.output_path / "sfm" / f"run_{run_index}"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "result.json").write_text(json.dumps(result_data, indent=2))

        return RunResult(
            stage=self.stage_name,
            run_index=run_index,
            success=True,
            elapsed_seconds=0.0,
            output_path=output_dir,
            metrics={
                "image_count": len(image_files),
                "run_path": result_data.get("run_path", ""),
            },
        )

    def _build_parameters(self) -> dict:
        """
        Build parameters dict from benchmark settings.

        Returns:
            Parameters dict for the SFM API
        """
        params: dict = {}
        if self.settings.target_gsd is not None:
            params["target_gsd"] = self.settings.target_gsd
        if self.settings.max_image_size is not None:
            params["max_image_size"] = self.settings.max_image_size
        if self.settings.gpu_count > 0:
            params["use_gpu"] = True
            params["gpu_index"] = ",".join(str(i) for i in range(self.settings.gpu_count))
        else:
            params["use_gpu"] = False
        return params
