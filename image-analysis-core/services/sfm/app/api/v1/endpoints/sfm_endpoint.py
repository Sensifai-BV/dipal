from __future__ import annotations

import httpx
from pathlib import Path

from fastapi import APIRouter
from lagom.integrations.fast_api import FastApiIntegration

from infrastructure.message_queue import BackgroundTaskHandler
from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.factory import StorageDriverFactory
from infrastructure.storage.s3_settings import TempStorageSettings
from infrastructure.logging import get_logger
from shared.utils import get_colmap_settings_for_gsd

from ....core.algorithms.algorithm_factory import AlgorithmFactory
from ....core.services.service_factory import ServiceFactory
from ....core.settings import CallbackSettings
from ....entities import SFMJobRequest, SFMJobResponse, SFMJobStatusResponse
from ...base_endpoint import BaseEndpoint

logger = get_logger(__name__)


class SFMEndpoint(BaseEndpoint):
    def __init__(self, deps: FastApiIntegration):
        self.deps = deps
        self._router = APIRouter(
            prefix="/sfm",
            tags=["sfm"],
        )

    @property
    def router(self) -> APIRouter:
        return self._router

    def register_api(self):
        @self._router.post(
            "/run",
            response_model=SFMJobResponse,
        )
        async def run_sfm(
            request: SFMJobRequest,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
            service_factory: ServiceFactory = self.deps.depends(ServiceFactory),
            algorithm_factory: AlgorithmFactory = self.deps.depends(AlgorithmFactory),
        ):
            """Start SFM job"""
            job_id = request.job_id
            
            logger.info(f"[SFM] Received request for job {job_id}")
            logger.info(f"[SFM] Dataset: {request.dataset_id}")

            # Create job in handler
            background_task_handler.create_job(
                job_id,
                metadata={
                    "dataset_id": request.dataset_id,
                    "download_url": request.download_url,
                    "parameters": request.parameters,
                },
            )
            logger.info(f"[SFM] Job {job_id} created in handler")

            # Start background task
            background_task_handler.start_background_task(
                job_id,
                run_sfm_task,
                job_id,
                request.dataset_id,
                request.download_url,
                request.parameters or {},
                service_factory,
                algorithm_factory,
            )
            logger.info(f"[SFM] Background task started for job {job_id}")

            response = SFMJobResponse(
                job_id=job_id,
                status="running",
                message="SFM job started",
            )
            logger.info(f"[SFM] Sending response for job {job_id}: status=running")
            return response

        @self._router.get(
            "/jobs/{job_id}/status",
            response_model=SFMJobStatusResponse,
        )
        async def get_job_status(
            job_id: str,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
        ):
            """Get SFM job status"""
            task_status = background_task_handler.get_task_status(job_id)
            return SFMJobStatusResponse(
                job_id=job_id,
                status=task_status.get("status", "not_found"),
                progress=task_status.get("progress"),
                result=task_status.get("result"),
                error=task_status.get("error"),
            )

        @self._router.post(
            "/jobs/{job_id}/cancel",
            response_model=SFMJobResponse,
        )
        async def cancel_job(
            job_id: str,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
        ):
            """Cancel SFM job"""
            cancelled = background_task_handler.cancel_job(job_id)
            return SFMJobResponse(
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
            """Get SFM job result"""
            task_status = background_task_handler.get_task_status(job_id)
            if task_status.get("status") == "completed":
                return task_status.get("result", {})
            return {"error": "Job not completed or not found"}


async def run_sfm_task(
    job_id: str,
    dataset_id: str,
    download_url: str | list[dict],
    parameters: dict,
    service_factory: ServiceFactory,
    algorithm_factory: AlgorithmFactory,
):
    """Execute SFM pipeline task - runs blocking operations in thread pool."""
    import asyncio
    
    # Get settings
    temp_settings = TempStorageSettings()
    callback_settings = CallbackSettings()
    
    try:
        # Create job-specific directory for SFM processing
        # Structure: temp/jobs/sfm/{job_id}/  (job_id already has _sfm suffix from API Gateway)
        job_workspace = Path(temp_settings.base_path) / "jobs" / "sfm" / job_id
        run_path = job_workspace / "run_1"
        
        # Check if SFM results already exist (for resumability)
        # Both markers must exist to consider SFM complete
        sfm_complete_markers = [
            run_path / "dense" / "fused.ply",  # Dense point cloud
            run_path / "sparse" / "0" / "points3D.bin",  # Sparse reconstruction
        ]
        
        results_exist = all(marker.exists() for marker in sfm_complete_markers)
        
        if results_exist:
            logger.info(f"[SFM] Results already exist for job {job_id} at {run_path}, skipping processing")
            
            # Prepare result from existing data
            dataset_path = Path(temp_settings.base_path) / "datasets" / dataset_id
            rgb_path = dataset_path / "rgb"
            images_dir = rgb_path if rgb_path.is_dir() and any(rgb_path.iterdir()) else dataset_path / "images"
            result = {
                "job_id": job_id,
                "dataset_id": dataset_id,
                "run_path": str(run_path),
                "workspace_path": str(job_workspace),
                "images_path": str(images_dir),
                "output_path": str(run_path),
                "status": "completed",
                "skipped_processing": True,  # Flag to indicate we used existing results
            }
            
            # Send callback to API Gateway
            await _send_sfm_callback(callback_settings, job_id, "completed", result, None)
            return result
        
        logger.info(f"[SFM] No existing results found, starting full processing for job {job_id}")
        
        # Step 1: Download images using presigned URLs
        logger.info(f"[SFM] Step 1: Setting up storage driver for job {job_id}")
        if isinstance(download_url, list):
            # List of presigned URLs with filenames
            logger.info(f"[SFM] Using presigned URL list with {len(download_url)} images")
            driver = StorageDriverFactory.create(
                "presigned_url",
                {
                    "project_urls": {
                        dataset_id: {
                            "images": download_url,
                        },
                    },
                },
            )
        elif download_url.startswith("s3://"):
            # Parse S3 URI
            s3_parts = download_url.replace("s3://", "").split("/", 1)
            bucket_name = s3_parts[0]
            full_path = s3_parts[1].rstrip("/") if len(s3_parts) > 1 else ""
            prefix = "/".join(full_path.split("/")[:-1]) if "/" in full_path else ""
            
            logger.info(f"[SFM] Using S3 driver for bucket={bucket_name}, prefix={prefix}")
            driver = StorageDriverFactory.create(
                "s3",
                {
                    "bucket_name": bucket_name,
                    "prefix": prefix,
                },
            )
        else:
            # Use presigned URL driver for HTTP(S) URLs
            logger.info(f"[SFM] Using presigned URL driver for {download_url}")
            driver = StorageDriverFactory.create(
                "presigned_url",
                {
                    "project_urls": {
                        dataset_id: {
                            "download_url": download_url,
                        },
                    },
                },
            )
        
        # Run blocking driver.connect() in thread pool
        await asyncio.to_thread(driver.connect)

        # Use shared dataset directory for images (reused across jobs)
        # Images stored in: temp/datasets/{dataset_id}/images/
        dataset = Dataset(
            project_id=dataset_id,
            storage_driver=driver,
            temp_base_path=Path(temp_settings.base_path),
        )
        
        # Run blocking operations in thread pool to not block event loop
        await asyncio.to_thread(dataset.initialize_dataset)
        logger.info(f"[SFM] Step 2: Downloading images for dataset {dataset_id}")
        await asyncio.to_thread(dataset.fetch_images)
        logger.info(f"[SFM] Step 2 complete: Downloaded images to {dataset.images_path}")
        logger.info(f"[SFM] Step 2b: Downloading PPK auxiliary files for dataset {dataset_id}")
        await asyncio.to_thread(dataset.fetch_ppk_files)
        logger.info(f"[SFM] Step 2b complete: PPK auxiliary files resolved for {dataset_id}")

        # Create directories (job_workspace and run_path already defined above)
        job_workspace.mkdir(parents=True, exist_ok=True)
        run_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[SFM] Workspace: {job_workspace}")
        logger.info(f"[SFM] Run path: {run_path}")

        # Get GSD from parameters and convert to COLMAP settings
        resolution_gsd = parameters.get("resolution_gsd")
        analysis_mode = parameters.get("analysis_mode", "fast")

        if analysis_mode == "fast" and resolution_gsd:
            effective_gsd = resolution_gsd * 2.0
            logger.info(
                f"[SFM] Fast mode: effective GSD {effective_gsd} cm/px "
                f"(input {resolution_gsd} × 2)"
            )
        else:
            effective_gsd = resolution_gsd

        colmap_gsd_settings = get_colmap_settings_for_gsd(effective_gsd)
        
        # Setup COLMAP service with GSD-based max_image_size
        # After calibration, organize_by_band(move=True) places all RGB images flat in rgb/.
        # For multispectral datasets: rgb/ has 119 RGB images (from the wide camera).
        # For RGB-only datasets: rgb/ also has the images moved there by calibration.
        # The raw images/ dir is emptied by calibration, so we always use rgb/.
        is_multispectral = parameters.get("is_multispectral", False)
        colmap_settings = {
            "run_path": run_path,
            "images_subdir": "rgb",
            **colmap_gsd_settings
        }
        service = service_factory.create_service("colmap", colmap_settings)

        # Run SFM pipeline using dataset directory (contains images/)
        # Workspace structure:
        # - Images: temp/datasets/{dataset_id}/images/
        # - Processing: temp/jobs/sfm/{job_id}/run_1/  (job_id already has _sfm suffix)
        pipeline = algorithm_factory.create_sfm_pipeline(service)
        
        # Run blocking COLMAP pipeline in thread pool to not block event loop
        logger.info(f"[SFM] Step 3: Running COLMAP/GLOMAP pipeline for job {job_id}")
        await asyncio.to_thread(pipeline.run_pipeline, dataset_path=dataset.dataset_path.absolute())
        logger.info(f"[SFM] Step 3 complete: COLMAP/GLOMAP pipeline finished for job {job_id}")

        # Prepare result
        result = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "run_path": str(run_path),
            "workspace_path": str(job_workspace),
            "images_path": str(dataset.images_path),
            "output_path": str(run_path),  # Main output is in run_path
            "status": "completed",
        }
        
        # Send success callback to API Gateway
        await _send_sfm_callback(callback_settings, job_id, "completed", result, None)
        
        return result
        
    except Exception as e:
        # Log the error
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"[SFM] Job {job_id} failed with error: {error_msg}", exc_info=True)
        
        # Send failure callback to API Gateway
        await _send_sfm_callback(callback_settings, job_id, "failed", None, error_msg)
        
        # Re-raise the exception so BackgroundTaskHandler can update Redis status
        raise


async def _send_sfm_callback(
    callback_settings: CallbackSettings, 
    job_id: str, 
    status: str,
    result: dict | None = None,
    error: str | None = None,
):
    """Helper function to send SFM callback to API Gateway."""
    try:
        callback_url = callback_settings.callback_url
        logger.info(f"[SFM CALLBACK] Sending {status} callback to {callback_url} for job {job_id}")
        
        # Build payload based on status
        payload = {
            "service": "sfm",
            "job_id": job_id,
            "status": status,
        }
        
        if status == "completed" and result:
            payload["result"] = result
            payload["error"] = None
            logger.debug(f"[SFM CALLBACK] Success payload - result keys={list(result.keys())}")
        elif status == "failed" and error:
            payload["result"] = None
            payload["error"] = error
            logger.debug(f"[SFM CALLBACK] Failure payload - error={error[:200]}")
        
        async with httpx.AsyncClient(timeout=callback_settings.timeout_seconds) as client:
            response = await client.post(
                callback_url,
                json=payload,
            )
            logger.info(f"[SFM CALLBACK] API Gateway response: status_code={response.status_code}, body={response.text[:200] if response.text else 'empty'}")
            
            if response.status_code != 200:
                logger.error(f"[SFM CALLBACK] API Gateway returned non-200 status: {response.status_code}")
            else:
                logger.info(f"[SFM CALLBACK] Successfully sent {status} callback for job {job_id}")
    except httpx.TimeoutException as e:
        logger.error(f"[SFM CALLBACK] Timeout sending callback to API Gateway: {e}")
    except httpx.ConnectError as e:
        logger.error(f"[SFM CALLBACK] Connection error sending callback to API Gateway: {e}")
    except Exception as e:
        logger.error(f"[SFM CALLBACK] Failed to send callback to API Gateway: {type(e).__name__}: {e}")

