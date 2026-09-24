"""
Local pipeline runner — no API, no S3 upload, no Redis.

Runs the three processing stages (calibration → SFM → orthomosaic) directly
by calling the same coroutines the production services use, with callbacks
and S3 uploads suppressed so everything stays on local disk.

Usage
-----
    cd image-analysis-core
    python run_local_pipeline.py \
        --dataset-dir  /path/to/raw/images \
        --work-dir     /tmp/photogear_local \
        --dataset-id   my_dataset \
        --stages       calibration,sfm,orthomosaic \
        --mode         full \
        --gsd          5.0

Stages can be run individually to resume after a crash:
    python run_local_pipeline.py ... --stages sfm,orthomosaic

Arguments
---------
--dataset-dir   Directory that contains the raw drone images (JPG/TIF).
                The same layout the real pipeline expects after download.
--work-dir      Root directory for all intermediate and final outputs.
                Created if it does not exist.  Mirrors the structure that
                TEMP_BASE_PATH=/app/data/temp produces in production.
--dataset-id    Arbitrary identifier string (used as a folder name inside
                work-dir).  Safe to reuse across runs — cached results are
                detected and skipped automatically.
--stages        Comma-separated list of stages to run.
                Valid values: calibration, sfm, orthomosaic
                Default: calibration,sfm,orthomosaic
--mode          Analysis mode: fast | full
                Use "full" to run multispectral analysis + vegetation indices.
                Default: full
--gsd           Target ground sampling distance in cm/pixel.
                Default: 5.0
--job-id        Optional base job ID.  Suffixes (_calibration, _sfm,
                _orthomosaic) are appended automatically.
                Default: local_<dataset-id>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# The services use relative imports, so we need their roots on sys.path.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
for _svc in [
    _HERE / "services" / "radiometric_calibration",
    _HERE / "services" / "sfm",
    _HERE / "services" / "orthomosaic_generation",
    _HERE,
]:
    if str(_svc) not in sys.path:
        sys.path.insert(0, str(_svc))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset-dir", required=True, type=Path, help="Raw images directory")
    p.add_argument("--work-dir", required=True, type=Path, help="Root output directory")
    p.add_argument("--dataset-id", default=None, help="Dataset identifier (default: random UUID)")
    p.add_argument("--stages", default="calibration,sfm,orthomosaic", help="Comma-separated stages to run")
    p.add_argument("--mode", default="full", choices=["fast", "full"], help="Analysis mode")
    p.add_argument("--gsd", default=5.0, type=float, help="GSD in cm/pixel")
    p.add_argument("--job-id", default=None, help="Base job ID (suffixes added automatically)")
    return p.parse_args()


def _configure_env(work_dir: Path) -> None:
    """
    Set environment variables so every settings class points at local paths.
    Must be called BEFORE importing any service module.
    """
    temp_base = str(work_dir)
    os.environ.setdefault("TEMP_BASE_PATH", temp_base)
    os.environ["TEMP_BASE_PATH"] = temp_base

    # Disable Redis — use in-process job state only.
    os.environ["BACKGROUND_TASK_USE_REDIS"] = "false"

    # Point callbacks at localhost:1 so they fail silently (we suppress them).
    os.environ["API_GATEWAY_URL"] = "http://127.0.0.1:1"

    # Disable SQS.
    os.environ["SQS_ENABLED"] = "false"
    os.environ["SQS_CALIBRATION_QUEUE_URL"] = ""
    os.environ["SQS_SFM_QUEUE_URL"] = ""
    os.environ["SQS_ORTHOMOSAIC_QUEUE_URL"] = ""


def _configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("local_pipeline")


# ---------------------------------------------------------------------------
# Callback suppressors
# ---------------------------------------------------------------------------

async def _noop_callback(*args, **kwargs) -> None:  # noqa: ANN001
    """Replace all HTTP callbacks with a no-op."""
    pass


def _patch_callbacks() -> None:
    """
    Monkey-patch the callback functions in each service module so they log
    instead of attempting HTTP connections to the API Gateway.
    """
    try:
        import services.radiometric_calibration.app.api.v1.endpoints.calibration_endpoint as _cal
        _cal.send_callback = _noop_callback  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        import services.sfm.app.api.v1.endpoints.sfm_endpoint as _sfm
        _sfm._send_sfm_callback = _noop_callback  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        import services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint as _ortho
        _ortho._send_orthomosaic_callback = _noop_callback  # type: ignore[attr-defined]
        _ortho._send_orthomosaic_failure_callback = _noop_callback  # type: ignore[attr-defined]
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Stage: Calibration
# ---------------------------------------------------------------------------

async def run_calibration(
    dataset_dir: Path,
    work_dir: Path,
    dataset_id: str,
    job_id: str,
    parameters: dict,
    log: logging.Logger,
) -> dict:
    """
    Run radiometric calibration on local images.

    Instead of a download URL, the images are already on disk at `dataset_dir`.
    We copy/symlink them into the expected dataset directory so the calibration
    code finds them without any network access.
    """
    from services.radiometric_calibration.app.api.v1.endpoints.calibration_endpoint import (
        run_calibration_task,
    )

    # _download_images() checks for images at:
    #   {TEMP_BASE_PATH}/datasets/{dataset_id}/images
    # If that path exists and is non-empty the download step is skipped entirely.
    # We create that path as a symlink to the caller-supplied dataset directory.
    images_target = work_dir / "datasets" / dataset_id / "images"

    if not images_target.exists():
        log.info(f"Symlinking {dataset_dir} → {images_target}")
        images_target.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(str(dataset_dir.resolve()), str(images_target))

    # download_url is only reached if the symlink above is missing/empty.
    # Use a dummy value; the cache-hit path will return before any HTTP call.
    download_url = "https://localhost:1/unused"

    log.info(f"[CALIBRATION] Starting — job_id={job_id}, dataset_id={dataset_id}")
    result = await run_calibration_task(
        job_id=job_id,
        dataset_id=dataset_id,
        download_url=download_url,
        parameters=parameters,
    )
    log.info(f"[CALIBRATION] Done — calibration_path={result.get('calibration_path')}")
    return result


# ---------------------------------------------------------------------------
# Stage: SFM
# ---------------------------------------------------------------------------

async def run_sfm(
    work_dir: Path,
    dataset_id: str,
    job_id: str,
    parameters: dict,
    log: logging.Logger,
) -> dict:
    from services.sfm.app.api.v1.endpoints.sfm_endpoint import run_sfm_task
    from services.sfm.app.core.algorithms.algorithm_factory import AlgorithmFactory
    from services.sfm.app.core.services.service_factory import ServiceFactory

    service_factory = ServiceFactory()
    algorithm_factory = AlgorithmFactory()

    # SFM reads images from: {TEMP_BASE_PATH}/datasets/{dataset_id}/rgb/
    # (same directory the calibration step populated)
    dataset_images_path = work_dir / "datasets" / dataset_id / "rgb"
    if not dataset_images_path.exists():
        # Fall back to top-level dataset dir if no rgb/ subfolder
        dataset_images_path = work_dir / "datasets" / dataset_id

    download_url = f"file://{dataset_images_path}"

    log.info(f"[SFM] Starting — job_id={job_id}")
    result = await run_sfm_task(
        job_id=job_id,
        dataset_id=dataset_id,
        download_url=download_url,
        parameters=parameters,
        service_factory=service_factory,
        algorithm_factory=algorithm_factory,
    )
    log.info(f"[SFM] Done — run_path={result.get('run_path')}")
    return result


# ---------------------------------------------------------------------------
# Stage: Orthomosaic
# ---------------------------------------------------------------------------

async def run_orthomosaic(
    work_dir: Path,
    dataset_id: str,
    job_id: str,
    sfm_run_path: str,
    calibration_path: str | None,
    band_manifest: dict | None,
    is_multispectral: bool,
    parameters: dict,
    log: logging.Logger,
) -> dict:
    from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
        run_orthomosaic_task,
    )

    log.info(f"[ORTHOMOSAIC] Starting — job_id={job_id}")
    result = await run_orthomosaic_task(
        job_id=job_id,
        dataset_id=dataset_id,
        dataset_path=sfm_run_path,
        parameters={
            **parameters,
            "calibration_path": calibration_path,
            "sfm_run_path": sfm_run_path,
            "band_manifest": band_manifest,
            "is_multispectral": is_multispectral,
        },
    )
    log.info(f"[ORTHOMOSAIC] Done — outputs={list(result.get('outputs', {}).keys())}")
    return result


# ---------------------------------------------------------------------------
# State persistence — lets you resume interrupted runs
# ---------------------------------------------------------------------------

def _state_path(work_dir: Path, dataset_id: str) -> Path:
    return work_dir / "datasets" / dataset_id / ".local_pipeline_state.json"


def _load_state(work_dir: Path, dataset_id: str) -> dict:
    p = _state_path(work_dir, dataset_id)
    if p.exists():
        return json.loads(p.read_text())
    return {}


def _save_state(work_dir: Path, dataset_id: str, state: dict) -> None:
    p = _state_path(work_dir, dataset_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, default=str))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    args = _parse_args()

    dataset_dir: Path = args.dataset_dir.resolve()
    work_dir: Path = args.work_dir.resolve()
    dataset_id: str = args.dataset_id or str(uuid.uuid4())
    stages = [s.strip() for s in args.stages.split(",")]
    mode: str = args.mode
    gsd: float = args.gsd
    base_job_id: str = args.job_id or f"local_{dataset_id[:8]}"

    work_dir.mkdir(parents=True, exist_ok=True)

    # Must happen before any import that reads settings.
    _configure_env(work_dir)

    log = _configure_logging()
    _patch_callbacks()

    log.info("=" * 60)
    log.info("PhotoGear local pipeline runner")
    log.info(f"  dataset-dir : {dataset_dir}")
    log.info(f"  work-dir    : {work_dir}")
    log.info(f"  dataset-id  : {dataset_id}")
    log.info(f"  stages      : {stages}")
    log.info(f"  mode        : {mode}")
    log.info(f"  gsd         : {gsd} cm/px")
    log.info("=" * 60)

    state = _load_state(work_dir, dataset_id)

    base_params = {
        "resolution_gsd": gsd,
        "analysis_mode": mode,
        "generate_cog": False,  # skip COG conversion locally
    }

    # ------------------------------------------------------------------
    # Stage 1: Calibration
    # ------------------------------------------------------------------
    if "calibration" in stages:
        cal_job_id = f"{base_job_id}_calibration"
        cal_result = await run_calibration(
            dataset_dir=dataset_dir,
            work_dir=work_dir,
            dataset_id=dataset_id,
            job_id=cal_job_id,
            parameters=base_params,
            log=log,
        )
        state["calibration"] = cal_result
        _save_state(work_dir, dataset_id, state)
    elif "calibration" not in stages and "calibration" not in state:
        log.warning(
            "Calibration stage skipped but no cached calibration result found. "
            "SFM and orthomosaic may fail if calibrated images do not already exist."
        )

    cal_result = state.get("calibration", {})
    calibration_path: str | None = cal_result.get("calibration_path")
    band_manifest: dict | None = cal_result.get("band_manifest")
    is_multispectral: bool = cal_result.get("is_multispectral", False)

    log.info(f"Calibration result: path={calibration_path}, multispectral={is_multispectral}")

    # ------------------------------------------------------------------
    # Stage 2: SFM
    # ------------------------------------------------------------------
    if "sfm" in stages:
        sfm_job_id = f"{base_job_id}_sfm"
        sfm_result = await run_sfm(
            work_dir=work_dir,
            dataset_id=dataset_id,
            job_id=sfm_job_id,
            parameters=base_params,
            log=log,
        )
        state["sfm"] = sfm_result
        _save_state(work_dir, dataset_id, state)

    sfm_result = state.get("sfm", {})
    sfm_run_path: str | None = sfm_result.get("run_path")
    if sfm_run_path is None:
        # Construct expected path so orthomosaic can still run if SFM was skipped
        # but results exist on disk from a previous full run.
        sfm_run_path = str(work_dir / "jobs" / "sfm" / f"{base_job_id}_sfm" / "run_1")
        log.info(f"SFM run_path not in state, using computed path: {sfm_run_path}")

    # ------------------------------------------------------------------
    # Stage 3: Orthomosaic
    # ------------------------------------------------------------------
    if "orthomosaic" in stages:
        ortho_job_id = f"{base_job_id}_orthomosaic"
        ortho_result = await run_orthomosaic(
            work_dir=work_dir,
            dataset_id=dataset_id,
            job_id=ortho_job_id,
            sfm_run_path=sfm_run_path,
            calibration_path=calibration_path,
            band_manifest=band_manifest,
            is_multispectral=is_multispectral,
            parameters=base_params,
            log=log,
        )
        state["orthomosaic"] = ortho_result
        _save_state(work_dir, dataset_id, state)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    ortho_result = state.get("orthomosaic", {})
    outputs = ortho_result.get("outputs", {})

    log.info("")
    log.info("=" * 60)
    log.info("Pipeline complete. Output files:")
    if outputs:
        for name, path in outputs.items():
            log.info(f"  {name:30s}: {path}")
    else:
        ortho_ws = work_dir / "jobs" / "orthomosaic" / f"{base_job_id}_orthomosaic"
        log.info(f"  (check {ortho_ws} for output files)")
    log.info("=" * 60)

    state_file = _state_path(work_dir, dataset_id)
    log.info(f"State saved to: {state_file}")


if __name__ == "__main__":
    asyncio.run(main())
