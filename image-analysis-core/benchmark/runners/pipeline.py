import json
import time
import uuid
from pathlib import Path

import requests

from benchmark.runners.base import RunResult
from benchmark.settings import BenchmarkSettings

# Maps gateway current_stage values to benchmark stage names
_GATEWAY_STAGE_MAP = {
    "radiometric_calibration": "calibration",
    "sfm": "sfm",
    "orthomosaic": "orthomosaic",
    "uploading": None,
    "completed": None,
    "failed": None,
}

# Maps benchmark stage names to gateway stage_results keys
_RESULT_KEY_MAP = {
    "calibration": "radiometric_calibration",
    "sfm": "sfm",
    "orthomosaic": "orthomosaic",
}

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".dng"}


class PipelineRunner:
    """Orchestrator that submits full pipeline jobs to the API gateway and polls for completion."""

    def __init__(self, settings: BenchmarkSettings):
        self.settings = settings

    def run_all(self) -> dict[str, list[RunResult]]:
        """
        Run the full pipeline via the gateway for each configured run.

        Returns:
            Dict mapping stage name to list of RunResult
        """
        stages = self.settings.get_stages()
        all_results: dict[str, list[RunResult]] = {stage: [] for stage in stages}

        for run_index in range(self.settings.num_runs):
            print(f"\n{'='*60}")
            print(f"  PIPELINE RUN {run_index + 1}/{self.settings.num_runs}")
            print(f"{'='*60}")

            run_results = self._execute_pipeline(run_index)
            for stage, result in run_results.items():
                if stage in all_results:
                    all_results[stage].append(result)
                    status = "PASS" if result.success else "FAIL"
                    print(f"  {stage}: {status} ({result.elapsed_seconds:.2f}s)")

        return all_results

    def _execute_pipeline(self, run_index: int) -> dict[str, RunResult]:
        """Submit a job to the gateway and poll until completion."""
        job_id = f"bench-{run_index}-{uuid.uuid4().hex[:8]}"
        dataset_id = f"bench-dataset-{run_index}"

        download_url = self._collect_image_urls()
        parameters = self._build_parameters()

        payload = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "download_url": download_url,
            "parameters": parameters,
        }

        submit_time = time.perf_counter()
        stage_times: dict[str, dict[str, float | None]] = {}

        print(f"  Submitting job {job_id} ({len(download_url)} images)...")
        response = requests.post(
            f"{self.settings.gateway_url}/jobs/run",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        resp_data = response.json()
        actual_job_id = resp_data.get("job_id", job_id)

        current_stage = None
        poll_interval = 5
        status_data: dict = {}

        while True:
            elapsed = time.perf_counter() - submit_time
            if elapsed > self.settings.timeout_seconds:
                print(f"    Timeout after {elapsed:.0f}s")
                return self._build_failure_results(
                    run_index, stage_times, submit_time, "Timeout exceeded"
                )

            time.sleep(poll_interval)

            status_resp = requests.get(
                f"{self.settings.gateway_url}/jobs/{actual_job_id}/status",
                timeout=30,
            )
            status_data = status_resp.json()

            new_stage = status_data.get("current_stage")
            job_status = status_data.get("status")
            progress = status_data.get("progress", 0)

            if new_stage != current_stage:
                now = time.perf_counter()
                if current_stage:
                    mapped_old = _GATEWAY_STAGE_MAP.get(current_stage)
                    if mapped_old and mapped_old in stage_times:
                        stage_times[mapped_old]["end"] = now

                mapped_new = _GATEWAY_STAGE_MAP.get(new_stage)
                if mapped_new and mapped_new not in stage_times:
                    stage_times[mapped_new] = {"start": now, "end": None}
                    print(f"    Stage: {new_stage} (progress: {progress:.1f}%)")

                current_stage = new_stage

            if job_status == "completed":
                now = time.perf_counter()
                for s in stage_times.values():
                    if s["end"] is None:
                        s["end"] = now
                break
            elif job_status == "failed":
                error = status_data.get("error", "Unknown error")
                print(f"    FAILED: {error}")
                return self._build_failure_results(
                    run_index, stage_times, submit_time, error
                )

            if elapsed > 300:
                poll_interval = 15
            elif elapsed > 60:
                poll_interval = 10

        total_time = time.perf_counter() - submit_time
        stage_results = status_data.get("result") or {}
        return self._build_success_results(
            run_index, stage_times, stage_results, total_time
        )

    def _collect_image_urls(self) -> list[dict]:
        """Collect image files as HTTP URLs for Docker container access.

        Scans dataset_path recursively for image files.
        """
        files = []
        for f in sorted(self.settings.dataset_path.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in _IMAGE_EXTENSIONS:
                continue

            if self.settings.file_server_url:
                relative = f.relative_to(self.settings.dataset_path)
                url = f"{self.settings.file_server_url.rstrip('/')}/{relative}"
            else:
                url = str(f)

            files.append({"filename": f.name, "url": url})
        return files

    def _build_parameters(self) -> dict:
        """Build processing parameters from settings."""
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

    def _build_success_results(
        self,
        run_index: int,
        stage_times: dict[str, dict[str, float | None]],
        stage_results: dict,
        total_time: float,
    ) -> dict[str, RunResult]:
        """Build RunResult objects for each completed stage."""
        results: dict[str, RunResult] = {}

        for stage in self.settings.get_stages():
            gateway_key = _RESULT_KEY_MAP.get(stage, stage)
            stage_data = stage_results.get(gateway_key, {})
            times = stage_times.get(stage, {})
            elapsed = 0.0
            if times.get("start") is not None and times.get("end") is not None:
                elapsed = times["end"] - times["start"]

            output_dir = self.settings.output_path / stage / f"run_{run_index}"
            output_dir.mkdir(parents=True, exist_ok=True)
            if stage_data:
                (output_dir / "result.json").write_text(
                    json.dumps(stage_data, indent=2)
                )

            metrics = self._extract_metrics(stage, stage_data)
            metrics["total_pipeline_time"] = total_time
            metrics["gpu_count"] = self.settings.gpu_count

            results[stage] = RunResult(
                stage=stage,
                run_index=run_index,
                success=True,
                elapsed_seconds=elapsed,
                output_path=output_dir,
                metrics=metrics,
            )

        return results

    def _build_failure_results(
        self,
        run_index: int,
        stage_times: dict[str, dict[str, float | None]],
        submit_time: float,
        error: str,
    ) -> dict[str, RunResult]:
        """Build RunResult objects marking failure."""
        results: dict[str, RunResult] = {}
        now = time.perf_counter()

        for stage in self.settings.get_stages():
            times = stage_times.get(stage, {})
            started = times.get("start") is not None
            elapsed = 0.0
            if started:
                elapsed = (times.get("end") or now) - times["start"]

            results[stage] = RunResult(
                stage=stage,
                run_index=run_index,
                success=False,
                elapsed_seconds=elapsed,
                error=error if started or not results else None,
                metrics={"gpu_count": self.settings.gpu_count},
            )

        return results

    @staticmethod
    def _extract_metrics(stage: str, stage_data: dict) -> dict:
        """Extract relevant metrics from gateway stage results."""
        metrics: dict = {}

        if stage == "calibration":
            metrics["is_multispectral"] = stage_data.get("is_multispectral", False)
            metrics["has_reflectance"] = stage_data.get("has_reflectance", False)
        elif stage == "sfm":
            metrics["run_path"] = stage_data.get("run_path", "")
        elif stage == "orthomosaic":
            outputs = stage_data.get("outputs", {})
            metrics["has_dsm"] = bool(outputs.get("dsm"))
            metrics["has_orthomosaic"] = bool(outputs.get("orthomosaic_rgb"))
            metrics["has_hillshade"] = bool(outputs.get("hillshade"))

        return metrics
