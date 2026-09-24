from __future__ import annotations

import httpx
from pathlib import Path

from fastapi import APIRouter
from lagom.integrations.fast_api import FastApiIntegration

from infrastructure.message_queue import BackgroundTaskHandler
from infrastructure.storage.s3_settings import TempStorageSettings
from infrastructure.logging import get_logger

from ....core.algorithms.orthomosaic_pipeline import OrthomosaicPipeline
from ....core.services.orthomosaic_service import OrthomosaicService
from ....core.settings import CallbackSettings
from ....entities import (
    OrthomosaicJobRequest,
    OrthomosaicJobResponse,
    OrthomosaicJobStatusResponse,
)
from ...base_endpoint import BaseEndpoint

logger = get_logger(__name__)


class OrthomosaicEndpoint(BaseEndpoint):
    def __init__(self, deps: FastApiIntegration):
        self.deps = deps
        self._router = APIRouter(
            prefix="/orthomosaic",
            tags=["orthomosaic"],
        )

    @property
    def router(self) -> APIRouter:
        return self._router

    def register_api(self):
        @self._router.post(
            "/run",
            response_model=OrthomosaicJobResponse,
        )
        async def run_orthomosaic(
            request: OrthomosaicJobRequest,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
        ):
            """Start orthomosaic generation job"""
            job_id = request.job_id
            
            logger.info(f"[ORTHOMOSAIC] Received request for job {job_id}")
            logger.info(f"[ORTHOMOSAIC] Dataset: {request.dataset_id}, Path: {request.dataset_path}")

            # Create job in handler
            background_task_handler.create_job(
                job_id,
                metadata={
                    "dataset_id": request.dataset_id,
                    "dataset_path": request.dataset_path,
                    "parameters": request.parameters,
                },
            )
            logger.info(f"[ORTHOMOSAIC] Job {job_id} created in handler")

            # Start background task
            background_task_handler.start_background_task(
                job_id,
                run_orthomosaic_task,
                job_id,
                request.dataset_id,
                request.dataset_path,
                request.parameters or {},
            )
            logger.info(f"[ORTHOMOSAIC] Background task started for job {job_id}")

            response = OrthomosaicJobResponse(
                job_id=job_id,
                status="running",
                message="Orthomosaic generation job started",
            )
            logger.info(f"[ORTHOMOSAIC] Sending response for job {job_id}: status=running")
            return response

        @self._router.get(
            "/jobs/{job_id}/status",
            response_model=OrthomosaicJobStatusResponse,
        )
        async def get_job_status(
            job_id: str,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
        ):
            """Get orthomosaic job status"""
            task_status = background_task_handler.get_task_status(job_id)
            return OrthomosaicJobStatusResponse(
                job_id=job_id,
                status=task_status.get("status", "not_found"),
                progress=task_status.get("progress"),
                result=task_status.get("result"),
                error=task_status.get("error"),
            )

        @self._router.post(
            "/jobs/{job_id}/cancel",
            response_model=OrthomosaicJobResponse,
        )
        async def cancel_job(
            job_id: str,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
        ):
            """Cancel orthomosaic job"""
            cancelled = background_task_handler.cancel_job(job_id)
            return OrthomosaicJobResponse(
                job_id=job_id,
                status="cancelled" if cancelled else "not_found",
                message="Job cancelled"
                if cancelled
                else "Job not found or not running",
            )

        @self._router.get(
            "/jobs/{job_id}/result",
        )
        async def get_job_result(
            job_id: str,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
        ):
            """Get orthomosaic job result"""
            task_status = background_task_handler.get_task_status(job_id)
            if task_status.get("status") == "completed":
                return task_status.get("result", {})
            return {"error": "Job not completed or not found"}


async def run_orthomosaic_task(
    job_id: str,
    dataset_id: str,
    dataset_path: str,
    parameters: dict,
):
    """Execute orthomosaic generation task - runs blocking operations in thread pool."""
    import asyncio
    import os
    
    # Get settings
    temp_settings = TempStorageSettings()
    callback_settings = CallbackSettings()
    
    dataset_path_obj = Path(dataset_path)
    
    # Create job-specific workspace for orthomosaic outputs
    job_workspace = Path(temp_settings.base_path) / "jobs" / "orthomosaic" / job_id
    job_workspace.mkdir(parents=True, exist_ok=True)
    
    # Symlink SFM dense/ directory into workspace so pipeline finds its inputs.
    # The dense/ directory contains both fused.ply (local SFM, for 3D viewer)
    # and fused_georef.ply (ECEF-transformed, used here for PDAL → UTM DSM).
    dense_link = job_workspace / "dense"
    dense_source = dataset_path_obj / "dense"
    if dense_source.exists() and not dense_link.exists():
        os.symlink(str(dense_source), str(dense_link))
        logger.info(f"Symlinked {dense_source} → {dense_link}")

    # Symlink geo_reference.json so the orthomosaic service can find it via rglob
    geo_ref_source = dataset_path_obj / "geo_reference.json"
    geo_ref_link = job_workspace / "geo_reference.json"
    if geo_ref_source.exists() and not geo_ref_link.exists():
        os.symlink(str(geo_ref_source), str(geo_ref_link))
        logger.info(f"Symlinked {geo_ref_source} → {geo_ref_link}")
    elif not geo_ref_source.exists():
        logger.warning(
            f"geo_reference.json not found at {geo_ref_source} — "
            "DSM and orthomosaic will be generated without CRS (no geo-registration)"
        )
    
    # Check if orthomosaic results already exist (for resumability)
    orthomosaic_complete_markers = [
        job_workspace / "orthomosaic_rgb.tif",
        job_workspace / "dsm.tif",
    ]
    
    results_exist = all(marker.exists() for marker in orthomosaic_complete_markers)
    
    if results_exist:
        logger.info(f"[ORTHOMOSAIC] Results already exist for job {job_id} at {job_workspace}, skipping processing")
        
        result = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "dataset_path": str(dataset_path),
            "workspace_path": str(job_workspace),
            "outputs": _collect_outputs(job_workspace),
            "status": "completed",
            "skipped_processing": True,
        }
        
        await _send_orthomosaic_callback(callback_settings, job_id, result)
        return result
    
    logger.info(f"[ORTHOMOSAIC] No existing results found, starting full processing for job {job_id}")
    
    # Create service and pipeline, honouring the user-selected GSD (cm → m)
    additional_settings: dict = {}
    resolution_gsd_cm = parameters.get("resolution_gsd")
    if resolution_gsd_cm is not None:
        resolution_m = float(resolution_gsd_cm) / 100.0
        additional_settings["dsm_resolution"] = resolution_m
        additional_settings["ortho_resolution"] = resolution_m
        logger.info(f"Using user-selected GSD: {resolution_gsd_cm} cm/px ({resolution_m} m/px)")
    service = OrthomosaicService(additional_settings=additional_settings or None)
    pipeline = OrthomosaicPipeline(service)

    generate_cog = parameters.get("generate_cog", True)
    
    logger.info(f"Orthomosaic workspace: {job_workspace}")
    logger.info(f"Input dataset path (SFM): {dataset_path}")

    # Run pipeline using workspace (outputs go here, inputs via dense/ symlink)
    try:
        mr_products = await asyncio.to_thread(pipeline.run_pipeline, job_workspace, generate_cog=generate_cog)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.error(
            f"[ORTHOMOSAIC] Pipeline failed for job {job_id}: {error_msg}",
            exc_info=True,
        )
        await _send_orthomosaic_failure_callback(callback_settings, job_id, error_msg)
        raise

    # Multispectral analysis (full mode only)
    analysis_mode = parameters.get("analysis_mode", "fast")
    is_multispectral = parameters.get("is_multispectral", False)
    calibration_path = parameters.get("calibration_path")
    sfm_run_path = parameters.get("sfm_run_path", str(dataset_path_obj))
    band_manifest = parameters.get("band_manifest")

    ms_products: dict[str, str] = {}
    if analysis_mode == "full" and is_multispectral and calibration_path:
        logger.info(
            f"[ORTHOMOSAIC] Full mode: running multispectral analysis for job {job_id}"
        )
        try:
            ms_products = await asyncio.to_thread(
                pipeline.run_multispectral_analysis,
                job_workspace,
                calibration_path,
                sfm_run_path,
                band_manifest,
            )
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error(
                f"[ORTHOMOSAIC] Multispectral analysis failed for job {job_id}: {error_msg}",
                exc_info=True,
            )
            await _send_orthomosaic_failure_callback(callback_settings, job_id, error_msg)
            raise
        logger.info(
            f"[ORTHOMOSAIC] Multispectral analysis complete: {list(ms_products.keys())}"
        )
    elif analysis_mode == "full":
        logger.warning(
            f"[ORTHOMOSAIC] Full mode requested but missing data: "
            f"is_multispectral={is_multispectral}, calibration_path={calibration_path}"
        )
    
    # Collect output paths from workspace
    outputs = _collect_outputs(job_workspace)
    outputs.update(ms_products)
    if mr_products:
        outputs.update(mr_products)

    result = {
        "job_id": job_id,
        "dataset_id": dataset_id,
        "dataset_path": str(dataset_path),
        "workspace_path": str(job_workspace),
        "outputs": outputs,
        "status": "completed",
    }
    
    await _send_orthomosaic_callback(callback_settings, job_id, result)
    
    return result


def _collect_outputs(workspace: Path) -> dict[str, str]:
    """
    Collect standard orthomosaic output paths from workspace.

    Args:
        workspace: Orthomosaic workspace directory

    Returns:
        Mapping of output key to file path string
    """
    return {
        "dsm": str(workspace / "dsm.tif"),
        "dsm_filled": str(workspace / "dsm_filled.tif"),
        "dsm_filled_cog": str(workspace / "dsm_filled_cog.tif"),
        "orthomosaic_rgb": str(workspace / "orthomosaic_rgb.tif"),
        "hillshade": str(workspace / "hillshade.tif"),
        "statistics": str(workspace / "orthomosaic_statistics.json"),
    }


async def _send_orthomosaic_callback(callback_settings: CallbackSettings, job_id: str, result: dict):
    """Helper function to send orthomosaic callback to API Gateway."""
    try:
        callback_url = callback_settings.callback_url
        logger.info(f"[ORTHOMOSAIC CALLBACK] Sending callback to {callback_url} for job {job_id}")
        logger.debug(f"[ORTHOMOSAIC CALLBACK] Callback payload: service=orthomosaic, status=completed, result keys={list(result.keys())}")
        
        async with httpx.AsyncClient(timeout=callback_settings.timeout_seconds) as client:
            response = await client.post(
                callback_url,
                json={
                    "service": "orthomosaic",
                    "job_id": job_id,
                    "status": "completed",
                    "result": result,
                }
            )
            logger.info(f"[ORTHOMOSAIC CALLBACK] API Gateway response: status_code={response.status_code}, body={response.text[:200] if response.text else 'empty'}")
            
            if response.status_code != 200:
                logger.error(f"[ORTHOMOSAIC CALLBACK] API Gateway returned non-200 status: {response.status_code}")
            else:
                logger.info(f"[ORTHOMOSAIC CALLBACK] Successfully sent completion callback for job {job_id}")
    except httpx.TimeoutException as e:
        logger.error(f"[ORTHOMOSAIC CALLBACK] Timeout sending callback to API Gateway: {e}")
    except httpx.ConnectError as e:
        logger.error(f"[ORTHOMOSAIC CALLBACK] Connection error sending callback to API Gateway: {e}")
    except Exception as e:
        logger.error(f"[ORTHOMOSAIC CALLBACK] Failed to send callback to API Gateway: {type(e).__name__}: {e}")


async def _send_orthomosaic_failure_callback(callback_settings: CallbackSettings, job_id: str, error_msg: str):
    """Send failure callback to API Gateway when orthomosaic pipeline fails."""
    try:
        callback_url = callback_settings.callback_url
        logger.info(f"[ORTHOMOSAIC CALLBACK] Sending failure callback for job {job_id}")
        async with httpx.AsyncClient(timeout=callback_settings.timeout_seconds) as client:
            response = await client.post(
                callback_url,
                json={
                    "service": "orthomosaic",
                    "job_id": job_id,
                    "status": "failed",
                    "error": error_msg,
                }
            )
            logger.info(
                f"[ORTHOMOSAIC CALLBACK] Failure callback response: "
                f"status_code={response.status_code}"
            )
    except Exception as e:
        logger.error(f"[ORTHOMOSAIC CALLBACK] Failed to send failure callback: {type(e).__name__}: {e}")
