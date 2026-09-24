import json

import requests

from benchmark.runners.base import BaseRunner, RunResult


class OrthoRunner(BaseRunner):
    """Runner for the orthomosaic generation stage."""

    @property
    def stage_name(self) -> str:
        return "orthomosaic"

    def _execute(self, run_index: int) -> RunResult:
        """
        Trigger orthomosaic generation via the service API.

        Args:
            run_index: Index of current run (0-based)

        Returns:
            RunResult with orthomosaic output info
        """
        job_id = f"bench_ortho_{run_index}"
        dataset_id = f"bench_dataset_{run_index}"

        sfm_result_path = self.settings.output_path / "sfm" / f"run_{run_index}" / "result.json"
        if sfm_result_path.exists():
            sfm_data = json.loads(sfm_result_path.read_text())
            dataset_path = sfm_data.get("run_path", "")
        else:
            dataset_path = str(self.settings.dataset_path / "sfm_output" / "run_1")

        payload = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "dataset_path": dataset_path,
            "parameters": self._build_parameters(),
        }

        response = requests.post(
            f"{self.settings.gateway_url}/api/v1/orthomosaic/run",
            json=payload,
            timeout=self.settings.timeout_seconds,
        )
        response.raise_for_status()
        result_data = response.json()

        output_dir = self.settings.output_path / "orthomosaic" / f"run_{run_index}"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "result.json").write_text(json.dumps(result_data, indent=2))

        outputs = result_data.get("outputs", {})
        return RunResult(
            stage=self.stage_name,
            run_index=run_index,
            success=True,
            elapsed_seconds=0.0,
            output_path=output_dir,
            metrics={
                "has_dsm": bool(outputs.get("dsm")),
                "has_orthomosaic": bool(outputs.get("orthomosaic_rgb")),
                "has_hillshade": bool(outputs.get("hillshade")),
            },
        )

    def _build_parameters(self) -> dict:
        """
        Build parameters dict from benchmark settings.

        Returns:
            Parameters dict for the orthomosaic API
        """
        params: dict = {}
        if self.settings.target_gsd is not None:
            params["dsm_resolution"] = self.settings.target_gsd / 100.0
        return params
