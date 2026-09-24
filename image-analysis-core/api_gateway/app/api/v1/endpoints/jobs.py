from __future__ import annotations

import asyncio
import traceback
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from lagom.integrations.fast_api import FastApiIntegration

from infrastructure.message_queue import BackgroundTaskHandler, JobStatus
from infrastructure.state import JobStateManager, ProcessingStage as StateProcessingStage
from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.factory import StorageDriverFactory
from infrastructure.storage.temp_manager import TempStorageManager
from infrastructure.logging import get_logger

from ....clients import (
    CalibrationClient,
    DispatchSettings,
    OrthomosaicClient,
    SFMClient,
    SQSDispatcher,
    BackendClient,
    ProductUploadClient,
)
from ....entities.jobs import (
    JobCancelResponse,
    JobRunRequest,
    JobStatusResponse,
    ProcessingStage,
)
from .metrics import record_job_completion, record_job_failure, record_queue_wait
from ...base_endpoint import BaseEndpoint

logger = get_logger(__name__)


class JobsAPIEndpoint(BaseEndpoint):
    def __init__(self, deps: FastApiIntegration):
        self.deps = deps
        self._router = APIRouter(
            prefix="/jobs",
            tags=["jobs"],
        )

    @property
    def router(self) -> APIRouter:
        return self._router

    def register_api(self):
        @self._router.post(
            "/run",
            response_model=JobStatusResponse,
        )
        async def run_job(
            request: JobRunRequest,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
            job_state_manager: JobStateManager = self.deps.depends(
                JobStateManager,
            ),
            calibration_client: CalibrationClient = self.deps.depends(
                CalibrationClient,
            ),
            sfm_client: SFMClient = self.deps.depends(SFMClient),
            orthomosaic_client: OrthomosaicClient = self.deps.depends(
                OrthomosaicClient,
            ),
            backend_client: BackendClient = self.deps.depends(BackendClient),
            product_upload_client: ProductUploadClient = self.deps.depends(
                ProductUploadClient,
            ),
            temp_manager: TempStorageManager = self.deps.depends(TempStorageManager),
            dispatch_settings: DispatchSettings = self.deps.depends(DispatchSettings),
            sqs_dispatcher: SQSDispatcher = self.deps.depends(SQSDispatcher),
        ):
            """Run complete processing pipeline."""
            job_id = request.job_id or str(uuid.uuid4())
            
            logger.info(f"API Gateway: Starting job {job_id} (backend_job_id: {request.job_id or 'N/A'})")

            # Create persistent job state in Redis
            job_state = job_state_manager.create_job(
                job_id=job_id,
                backend_job_id=request.job_id,
                dataset_id=request.dataset_id,
                download_url=request.download_url,
                parameters=request.parameters or {},
                starting_stage=request.starting_stage,
            )

            # Also create in background task handler for local task tracking
            background_task_handler.create_job(
                job_id,
                metadata={
                    "backend_job_id": request.job_id,
                    "dataset_id": request.dataset_id,
                    "download_url": request.download_url,
                    "parameters": request.parameters,
                },
            )

            # Send immediate "job accepted" callback to backend
            if request.job_id:
                try:
                    await backend_client.send_progress_update(
                        job_id=request.job_id,
                        progress=0.0,
                        current_stage="queued",
                        message="Job accepted by AI Gateway"
                    )
                except Exception as e:
                    logger.warning(f"Failed to send initial callback: {e}")

            # Start pipeline - only triggers the first applicable stage
            background_task_handler.start_background_task(
                job_id,
                run_pipeline_task,
                job_id,
                job_state_manager,
                calibration_client,
                sfm_client,
                orthomosaic_client,
                backend_client,
                product_upload_client,
                temp_manager,
                dispatch_settings,
                sqs_dispatcher,
                background_task_handler,
            )

            return JobStatusResponse(
                job_id=job_id,
                status=JobStatus.RUNNING,
                progress=0.0,
                current_stage=ProcessingStage.RADIOMETRIC_CALIBRATION,
                result=None,
                error=None,
                created_at=None,
                updated_at=None,
            )

        @self._router.get(
            "/{job_id}/status",
            response_model=JobStatusResponse,
        )
        async def job_status(
            job_id: str,
            job_state_manager: JobStateManager = self.deps.depends(
                JobStateManager,
            ),
        ):
            """Get job status from persistent state."""
            job_state = job_state_manager.get_job(job_id)
            
            if not job_state:
                return JobStatusResponse(
                    job_id=job_id,
                    status=JobStatus.NOT_FOUND,
                    progress=None,
                    current_stage=None,
                    result=None,
                    error=None,
                    created_at=None,
                    updated_at=None,
                )

            return JobStatusResponse(
                job_id=job_id,
                status=JobStatus(job_state.status) if job_state.status in [s.value for s in JobStatus] else JobStatus.NOT_FOUND,
                progress=job_state.progress,
                current_stage=job_state.current_stage.value if job_state.current_stage else None,
                result=job_state.stage_results,
                error=job_state.error,
                created_at=job_state.created_at,
                updated_at=job_state.updated_at,
            )

        @self._router.post(
            "/{job_id}/cancel",
            response_model=JobCancelResponse,
        )
        async def cancel_job(
            job_id: str,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
            job_state_manager: JobStateManager = self.deps.depends(
                JobStateManager,
            ),
            sfm_client: SFMClient = self.deps.depends(SFMClient),
            orthomosaic_client: OrthomosaicClient = self.deps.depends(
                OrthomosaicClient,
            ),
            calibration_client: CalibrationClient = self.deps.depends(
                CalibrationClient,
            ),
        ):
            """Cancel a job and propagate to active sub-services."""
            cancelled = background_task_handler.cancel_job(job_id)

            if cancelled:
                job_state_manager.update_job(
                    job_id,
                    status="cancelled",
                    error="Job cancelled by user",
                )
                await _cancel_sub_services(
                    job_id, job_state_manager,
                    sfm_client, orthomosaic_client, calibration_client,
                )

            return JobCancelResponse(
                job_id=job_id,
                cancelled=cancelled,
                message="Job cancelled successfully"
                if cancelled
                else "Job not found or already completed",
            )
        
        @self._router.post(
            "/{job_id}/resume",
        )
        async def resume_job(
            job_id: str,
            stage: str | None = None,
            background_tasks: BackgroundTasks = None,
            job_state_manager: JobStateManager = self.deps.depends(JobStateManager),
            sfm_client: SFMClient = self.deps.depends(SFMClient),
            orthomosaic_client: OrthomosaicClient = self.deps.depends(OrthomosaicClient),
            backend_client: BackendClient = self.deps.depends(BackendClient),
            product_upload_client: ProductUploadClient = self.deps.depends(ProductUploadClient),
            temp_manager: TempStorageManager = self.deps.depends(TempStorageManager),
            dispatch_settings: DispatchSettings = self.deps.depends(DispatchSettings),
            sqs_dispatcher: SQSDispatcher = self.deps.depends(SQSDispatcher),
        ):
            """
            Resume a job from a specific stage.
            
            Use this endpoint to manually trigger the next stage when a callback was missed
            or to retry a failed stage. If stage is not specified, it will resume from the
            current stage in job state.
            
            Stages: calibration, sfm, orthomosaic
            """
            logger.info(f"[RESUME] Resume request for job {job_id}, requested stage: {stage}")
            
            job_state = job_state_manager.get_job(job_id)
            if not job_state:
                logger.error(f"[RESUME] Job state not found for {job_id}")
                return {"status": "error", "message": f"Job {job_id} not found"}
            
            logger.info(f"[RESUME] Current job state: current_stage={job_state.current_stage}, status={job_state.status}")
            logger.info(f"[RESUME] Stage results: {list(job_state.stage_results.keys()) if job_state.stage_results else 'none'}")
            
            # Determine which stage to resume from
            if stage:
                stage_map = {
                    "calibration": StateProcessingStage.RADIOMETRIC_CALIBRATION,
                    "sfm": StateProcessingStage.SFM,
                    "orthomosaic": StateProcessingStage.ORTHOMOSAIC,
                }
                target_stage = stage_map.get(stage.lower())
                if not target_stage:
                    return {"status": "error", "message": f"Invalid stage: {stage}"}
            else:
                # Use current stage from job state
                target_stage = job_state.current_stage
            
            logger.info(f"[RESUME] Target stage: {target_stage.value}")
            
            try:
                # Notify backend that job is resuming
                if job_state.backend_job_id:
                    try:
                        await backend_client.send_progress_update(
                            job_id=job_state.backend_job_id,
                            progress=job_state.progress or 0.0,
                            current_stage=target_stage.value,
                            message=f"Job resumed from {target_stage.value} stage",
                        )
                    except Exception as e:
                        logger.warning(f"[RESUME] Failed to notify backend: {e}")

                if target_stage == StateProcessingStage.SFM:
                    # Trigger SFM
                    job_state_manager.start_stage(job_id, StateProcessingStage.SFM)
                    
                    sfm_job_id = f"{job_id}_sfm"
                    if dispatch_settings.mode == "sqs":
                        await sqs_dispatcher.dispatch_sfm(
                            job_id=sfm_job_id,
                            dataset_id=job_state.dataset_id,
                            download_url=job_state.download_url,
                            parameters=job_state.parameters,
                        )
                    else:
                        await sfm_client.run_sfm(
                            job_id=sfm_job_id,
                            dataset_id=job_state.dataset_id,
                            download_url=job_state.download_url,
                            parameters=job_state.parameters,
                        )
                    logger.info(f"[RESUME] SFM triggered for {sfm_job_id}")
                    return {"status": "resumed", "stage": "sfm", "job_id": sfm_job_id}
                
                elif target_stage == StateProcessingStage.ORTHOMOSAIC:
                    # Check if SFM results exist
                    sfm_result = job_state.stage_results.get("sfm", {})
                    sfm_output_path = sfm_result.get("run_path")
                    
                    if not sfm_output_path:
                        # Fallback: construct expected path
                        from infrastructure.storage.s3_settings import TempStorageSettings
                        temp_settings = TempStorageSettings()
                        sfm_output_path = str(
                            Path(temp_settings.base_path) / "jobs" / "sfm" / f"{job_id}_sfm" / "run_1"
                        )
                        logger.info(f"[RESUME] Using fallback SFM path: {sfm_output_path}")
                    
                    # Verify path exists
                    if not Path(sfm_output_path).exists():
                        logger.error(f"[RESUME] SFM output path does not exist: {sfm_output_path}")
                        return {"status": "error", "message": f"SFM output path not found: {sfm_output_path}"}
                    
                    job_state_manager.start_stage(job_id, StateProcessingStage.ORTHOMOSAIC)

                    ortho_params = dict(job_state.parameters) if job_state.parameters else {}
                    calibration_result = job_state.stage_results.get("radiometric_calibration", {})
                    if calibration_result:
                        ortho_params["is_multispectral"] = calibration_result.get("is_multispectral", False)
                        ortho_params["calibration_path"] = calibration_result.get("calibration_path")
                        ortho_params["band_manifest"] = calibration_result.get("band_manifest")
                        ortho_params["has_reflectance"] = calibration_result.get("has_reflectance", False)
                        ortho_params["sfm_run_path"] = sfm_output_path

                    orthomosaic_job_id = f"{job_id}_orthomosaic"
                    if dispatch_settings.mode == "sqs":
                        await sqs_dispatcher.dispatch_orthomosaic(
                            job_id=orthomosaic_job_id,
                            dataset_id=job_state.dataset_id,
                            dataset_path=sfm_output_path,
                            parameters=ortho_params,
                        )
                    else:
                        await orthomosaic_client.run_orthomosaic(
                            job_id=orthomosaic_job_id,
                            dataset_id=job_state.dataset_id,
                            dataset_path=sfm_output_path,
                            parameters=ortho_params,
                        )
                    logger.info(f"[RESUME] Orthomosaic triggered for {orthomosaic_job_id}")
                    return {"status": "resumed", "stage": "orthomosaic", "job_id": orthomosaic_job_id}
                
                else:
                    return {"status": "error", "message": f"Cannot resume from stage: {target_stage.value}"}
                    
            except Exception as e:
                logger.error(f"[RESUME] Error resuming job {job_id}: {e}", exc_info=True)
                return {"status": "error", "message": str(e)}
        
        @self._router.post(
            "/{job_id}/simulate-callback",
        )
        async def simulate_callback(
            job_id: str,
            service: str,
            status: str = "completed",
            background_tasks: BackgroundTasks = None,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
            job_state_manager: JobStateManager = self.deps.depends(JobStateManager),
            sfm_client: SFMClient = self.deps.depends(SFMClient),
            orthomosaic_client: OrthomosaicClient = self.deps.depends(OrthomosaicClient),
            backend_client: BackendClient = self.deps.depends(BackendClient),
            product_upload_client: ProductUploadClient = self.deps.depends(ProductUploadClient),
            temp_manager: TempStorageManager = self.deps.depends(TempStorageManager),
            dispatch_settings: DispatchSettings = self.deps.depends(DispatchSettings),
            sqs_dispatcher: SQSDispatcher = self.deps.depends(SQSDispatcher),
        ):
            """
            Simulate a callback from a service that completed but failed to send callback.
            
            This reconstructs the callback data from disk and triggers the next stage.
            Use when a service (like SFM) completed but the callback was lost (e.g., 404 error).
            
            Services: calibration, sfm, orthomosaic
            """
            logger.info(f"[SIMULATE CALLBACK] Simulating {service} callback for job {job_id}")
            
            job_state = job_state_manager.get_job(job_id)
            if not job_state:
                return {"status": "error", "message": f"Job {job_id} not found"}
            
            # Build callback data based on service
            from infrastructure.storage.s3_settings import TempStorageSettings
            temp_settings = TempStorageSettings()
            
            if service.lower() == "sfm":
                # Construct SFM result from expected paths
                sfm_job_id = f"{job_id}_sfm"
                run_path = Path(temp_settings.base_path) / "jobs" / "sfm" / f"{sfm_job_id}" / "run_1"
                
                if not run_path.exists():
                    return {"status": "error", "message": f"SFM run path not found: {run_path}"}
                
                result = {
                    "job_id": sfm_job_id,
                    "dataset_id": job_state.dataset_id,
                    "run_path": str(run_path),
                    "workspace_path": str(run_path.parent),
                    "output_path": str(run_path),
                    "status": "completed",
                }
                sub_job_id = sfm_job_id
                
            elif service.lower() == "orthomosaic":
                orthomosaic_job_id = f"{job_id}_orthomosaic"
                # Get dataset path from SFM result
                sfm_result = job_state.stage_results.get("sfm", {})
                dataset_path = Path(sfm_result.get("run_path", ""))
                
                result = {
                    "job_id": orthomosaic_job_id,
                    "dataset_id": job_state.dataset_id,
                    "dataset_path": str(dataset_path),
                    "outputs": {
                        "dsm": str(dataset_path / "dsm.tif"),
                        "dsm_filled": str(dataset_path / "dsm_filled.tif"),
                        "dsm_filled_cog": str(dataset_path / "dsm_filled_cog.tif"),
                        "orthomosaic_rgb": str(dataset_path / "orthomosaic_rgb.tif"),
                        "hillshade": str(dataset_path / "hillshade.tif"),
                    },
                    "status": "completed",
                }
                sub_job_id = orthomosaic_job_id
            else:
                return {"status": "error", "message": f"Unsupported service: {service}"}
            
            # Build callback data
            callback_data = {
                "service": service.lower(),
                "job_id": sub_job_id,
                "status": status,
                "result": result,
            }
            
            logger.info(f"[SIMULATE CALLBACK] Constructed callback data: {callback_data}")
            
            # Process the callback directly
            await process_callback_async(
                callback_data=callback_data,
                job_state_manager=job_state_manager,
                backend_client=backend_client,
                sfm_client=sfm_client,
                orthomosaic_client=orthomosaic_client,
                product_upload_client=product_upload_client,
                temp_manager=temp_manager,
                dispatch_settings=dispatch_settings,
                sqs_dispatcher=sqs_dispatcher,
                background_task_handler=background_task_handler,
            )
            
            return {
                "status": "callback_simulated",
                "service": service,
                "message": f"Callback for {service} has been simulated and processed"
            }
        
        @self._router.post(
            "/subservice-callback",
        )
        async def subservice_callback(
            callback_data: dict,
            background_tasks: BackgroundTasks,
            background_task_handler: BackgroundTaskHandler = self.deps.depends(
                BackgroundTaskHandler,
            ),
            job_state_manager: JobStateManager = self.deps.depends(JobStateManager),
            backend_client: BackendClient = self.deps.depends(BackendClient),
            sfm_client: SFMClient = self.deps.depends(SFMClient),
            orthomosaic_client: OrthomosaicClient = self.deps.depends(OrthomosaicClient),
            product_upload_client: ProductUploadClient = self.deps.depends(
                ProductUploadClient,
            ),
            temp_manager: TempStorageManager = self.deps.depends(TempStorageManager),
            dispatch_settings: DispatchSettings = self.deps.depends(DispatchSettings),
            sqs_dispatcher: SQSDispatcher = self.deps.depends(SQSDispatcher),
        ):
            """
            Callback endpoint for sub-services (SFM, Orthomosaic, etc.) to report results.
            
            Returns immediately to avoid timeout, processes callback in background.
            """
            service_name = callback_data.get("service")
            sub_job_id = callback_data.get("job_id")  # e.g., "abc123_sfm"
            status = callback_data.get("status")
            
            # Extract main job ID from sub-job ID (e.g., "abc123_sfm" -> "abc123")
            main_job_id = sub_job_id.rsplit("_", 1)[0] if "_" in sub_job_id else sub_job_id
            
            logger.info(f"Received callback from {service_name} for job {main_job_id}: {status}")
            
            # Get job state - quick validation
            job_state = job_state_manager.get_job(main_job_id)
            if not job_state:
                logger.error(f"Job state not found for {main_job_id}")
                return {"status": "error", "message": "Job not found"}
            
            # Process callback in background - return immediately to avoid timeout
            background_tasks.add_task(
                process_callback_async,
                callback_data=callback_data,
                job_state_manager=job_state_manager,
                backend_client=backend_client,
                sfm_client=sfm_client,
                orthomosaic_client=orthomosaic_client,
                product_upload_client=product_upload_client,
                temp_manager=temp_manager,
                dispatch_settings=dispatch_settings,
                sqs_dispatcher=sqs_dispatcher,
                background_task_handler=background_task_handler,
            )
            
            return {"status": "callback_received", "message": "Processing in background"}


# Helper functions for callback-driven pipeline orchestration


class UploadResult:
    """Result of product upload operation."""
    
    def __init__(self):
        self.uploaded: list[dict] = []
        self.failed: list[dict] = []
    
    @property
    def has_failures(self) -> bool:
        return len(self.failed) > 0
    
    @property
    def has_critical_failure(self) -> bool:
        """Check if critical products (orthomosaic) failed to upload."""
        critical_types = {"orthomosaic"}
        return any(f["product_type"] in critical_types for f in self.failed)


async def process_callback_async(
    callback_data: dict,
    job_state_manager: JobStateManager,
    backend_client: BackendClient,
    sfm_client: SFMClient,
    orthomosaic_client: OrthomosaicClient,
    product_upload_client: ProductUploadClient,
    temp_manager: TempStorageManager,
    dispatch_settings: DispatchSettings | None = None,
    sqs_dispatcher: SQSDispatcher | None = None,
    background_task_handler: BackgroundTaskHandler | None = None,
):
    """
    Process callback in background to avoid blocking response.
    
    This is the core of callback-driven orchestration:
    1. Receives completion/failure from a service
    2. Updates persistent job state
    3. Triggers the next stage if applicable
    4. Uploads products to backend when appropriate
    """
    service_name = callback_data.get("service")
    sub_job_id = callback_data.get("job_id")
    status = callback_data.get("status")
    result = callback_data.get("result", {})
    error = callback_data.get("error")
    
    main_job_id = sub_job_id.rsplit("_", 1)[0] if "_" in sub_job_id else sub_job_id
    
    logger.info(f"[CALLBACK PROCESSOR] Processing callback: service={service_name}, job={main_job_id}, status={status}")
    logger.debug(f"[CALLBACK PROCESSOR] Full callback data: {callback_data}")
    
    job_state = job_state_manager.get_job(main_job_id)
    if not job_state:
        logger.error(f"[CALLBACK PROCESSOR] Job state not found for {main_job_id}")
        return
    
    logger.debug(f"[CALLBACK PROCESSOR] Current job state: current_stage={job_state.current_stage}, progress={job_state.progress}")
    
    backend_job_id = job_state.backend_job_id
    
    try:
        if status == "completed":
            # Map service name to stage
            stage_map = {
                "calibration": StateProcessingStage.RADIOMETRIC_CALIBRATION,
                "sfm": StateProcessingStage.SFM,
                "orthomosaic": StateProcessingStage.ORTHOMOSAIC,
            }
            stage = stage_map.get(service_name)
            logger.info(f"[CALLBACK PROCESSOR] Mapped service '{service_name}' to stage: {stage}")
            
            if stage:
                # Complete the stage and get next stage
                logger.info(f"[CALLBACK PROCESSOR] Completing stage {stage.value} for job {main_job_id}")
                job_state, next_stage = job_state_manager.complete_stage(
                    main_job_id,
                    stage,
                    result=result,
                )
                logger.info(f"[CALLBACK PROCESSOR] Stage {stage.value} completed, next_stage: {next_stage}")
                
                # Send progress update to backend
                await backend_client.send_progress_update(
                    job_id=backend_job_id,
                    progress=job_state.progress if job_state else 0.0,
                    current_stage=next_stage.value if next_stage else "completed",
                    message=f"{service_name} completed successfully",
                )
                
                # Trigger next stage FIRST (don't block on uploads)
                if next_stage:
                    await trigger_next_stage(
                        next_stage=next_stage,
                        job_state=job_state,
                        job_state_manager=job_state_manager,
                        sfm_client=sfm_client,
                        orthomosaic_client=orthomosaic_client,
                        backend_client=backend_client,
                        temp_manager=temp_manager,
                        dispatch_settings=dispatch_settings,
                        sqs_dispatcher=sqs_dispatcher,
                    )
                    # Signal pipeline complete for terminal stages
                    if next_stage in (
                        StateProcessingStage.UPLOADING,
                        StateProcessingStage.PUBLISHING,
                        StateProcessingStage.COMPLETED,
                    ) and background_task_handler:
                        background_task_handler.signal_pipeline_complete(main_job_id)
                else:
                    # Pipeline complete
                    logger.info(f"Pipeline completed for job {main_job_id}")
                    if job_state.created_at:
                        from datetime import datetime, timezone
                        try:
                            start = datetime.fromisoformat(job_state.created_at)
                            duration = (datetime.now(timezone.utc) - start).total_seconds()
                            record_job_completion(duration)
                        except (ValueError, TypeError):
                            record_job_completion(0.0)
                    else:
                        record_job_completion(0.0)
                    await backend_client.send_completion(
                        job_id=backend_job_id,
                        dataset_id=job_state.dataset_id,
                        outputs=job_state.stage_results,
                        metadata={"total_stages": len(job_state.stage_results)},
                    )
                    if background_task_handler:
                        background_task_handler.signal_pipeline_complete(main_job_id)
                
                # Upload products AFTER triggering next stage (fire-and-forget)
                asyncio.create_task(
                    _upload_stage_products_background(
                        service_name=service_name,
                        job_id=backend_job_id,
                        result=result,
                        product_upload_client=product_upload_client,
                        backend_client=backend_client,
                        job_state_manager=job_state_manager,
                        main_job_id=main_job_id,
                    )
                )
            
        elif status == "failed":
            record_job_failure()
            # Mark stage and job as failed
            stage_map = {
                "calibration": StateProcessingStage.RADIOMETRIC_CALIBRATION,
                "sfm": StateProcessingStage.SFM,
                "orthomosaic": StateProcessingStage.ORTHOMOSAIC,
            }
            stage = stage_map.get(service_name)
            
            if stage:
                job_state_manager.fail_stage(main_job_id, stage, error or "Service failed")
            
            # Send failure notification to backend
            await backend_client.send_failure(
                job_id=backend_job_id,
                error_message=error or "Service failed",
                error_details={"service": service_name, "stage": stage.value if stage else None},
            )
            if background_task_handler:
                background_task_handler.signal_pipeline_complete(main_job_id)
            
    except Exception as e:
        logger.error(f"Error processing callback for job {main_job_id}: {e}", exc_info=True)
        # Try to notify backend of the failure
        try:
            # Determine which stage failed based on error context
            error_str = str(e).lower()
            failed_service = service_name  # Default to callback source
            if "sfm" in error_str:
                failed_service = "sfm"
            elif "orthomosaic" in error_str:
                failed_service = "orthomosaic"
            elif "calibration" in error_str:
                failed_service = "calibration"
            
            await backend_client.send_failure(
                job_id=backend_job_id,
                error_message=f"Pipeline error after {service_name} stage: {str(e)}",
                error_details={
                    "callback_from": service_name,
                    "failed_while": f"triggering next stage after {service_name}",
                    "error_type": type(e).__name__,
                },
            )
        except Exception as notify_error:
            logger.error(f"Failed to notify backend of callback error: {notify_error}")
        finally:
            if background_task_handler:
                background_task_handler.signal_pipeline_complete(main_job_id)


async def _upload_stage_products_background(
    service_name: str,
    job_id: str,
    result: dict,
    product_upload_client: ProductUploadClient,
    backend_client: BackendClient,
    job_state_manager: JobStateManager | None = None,
    main_job_id: str | None = None,
) -> None:
    """
    Fire-and-forget wrapper for product uploads so they don't block the pipeline.

    Args:
        service_name: Name of the completed service stage
        job_id: Backend job ID for product association
        result: Stage result containing output paths
        product_upload_client: Client for uploading to backend
        backend_client: Client for sending upload status callback
        job_state_manager: Optional state manager to track upload failures
        main_job_id: Main job ID for state updates
    """
    logger.info(f"[UPLOAD BG] Starting background upload for {service_name}, job {main_job_id}")
    try:
        upload_result = await upload_stage_products(
            service_name=service_name,
            job_id=job_id,
            result=result,
            product_upload_client=product_upload_client,
            job_state_manager=job_state_manager,
            main_job_id=main_job_id,
        )
        await backend_client.send_upload_status(
            job_id=job_id,
            uploaded=upload_result.uploaded,
            failed=upload_result.failed,
        )
        # Store upload results in job state for retry capability
        if job_state_manager and main_job_id:
            _store_upload_results_in_state(
                job_state_manager, main_job_id, service_name, upload_result,
            )
        if upload_result.has_failures:
            logger.warning(
                f"[UPLOAD BG] Some uploads failed for job {main_job_id}: "
                f"{[f['product_type'] for f in upload_result.failed]}. "
                f"Pipeline continues — uploads can be retried."
            )
        else:
            logger.info(f"[UPLOAD BG] All uploads succeeded for {service_name}, job {main_job_id}")
    except Exception as exc:
        logger.error(
            f"[UPLOAD BG] Upload failed for job {main_job_id}: {exc}. "
            f"Pipeline continues — uploads can be retried.",
            exc_info=True,
        )


def _store_upload_results_in_state(
    job_state_manager: JobStateManager,
    job_id: str,
    service_name: str,
    upload_result: UploadResult,
) -> None:
    """Persist upload results into Redis job state so retry knows what succeeded/failed."""
    job = job_state_manager.get_job(job_id)
    if not job:
        return
    existing = job.stage_results.get("upload_results", {})
    existing[service_name] = {
        "uploaded": upload_result.uploaded,
        "failed": upload_result.failed,
    }
    job_state_manager.update_stage_result(job_id, "upload_results", existing)


async def _cancel_sub_services(
    job_id: str,
    job_state_manager: JobStateManager,
    sfm_client: SFMClient,
    orthomosaic_client: OrthomosaicClient,
    calibration_client: CalibrationClient,
) -> None:
    """
    Propagate cancellation to the sub-service running the current stage.

    Args:
        job_id: Main pipeline job ID
        job_state_manager: For reading current stage
        sfm_client: SFM service client
        orthomosaic_client: Orthomosaic service client
        calibration_client: Calibration service client
    """
    job_state = job_state_manager.get_job(job_id)
    if not job_state:
        return

    stage = job_state.current_stage
    stage_value = stage.value if isinstance(stage, StateProcessingStage) else stage

    stage_clients = {
        "radiometric_calibration": (calibration_client, f"{job_id}_calibration"),
        "sfm": (sfm_client, f"{job_id}_sfm"),
        "orthomosaic": (orthomosaic_client, f"{job_id}_orthomosaic"),
    }

    entry = stage_clients.get(stage_value)
    if not entry:
        return

    client, sub_job_id = entry
    try:
        await client.cancel_job(sub_job_id)
        logger.info(f"Cancelled {stage_value} sub-service for job {job_id}")
    except Exception as e:
        logger.warning(
            f"Failed to cancel {stage_value} sub-service for job {job_id}: {e}"
        )


ORTHO_OUTPUT_KEY_MAP = {
    "orthomosaic_rgb": "orthomosaic",
    "dsm_filled_cog": "dsm",
    "hillshade": "hillshade",
    "ndvi": "ndvi",
    "ndre": "ndre",
    "gndvi": "gndvi",
    "multiband_reflectance": "calibrated_reflectance",
}


def _extract_orthomosaic_metadata(outputs: dict) -> dict[str, dict]:
    """
    Extract product metadata from orthomosaic statistics file.

    Args:
        outputs: Stage outputs dict containing file paths and statistics path

    Returns:
        Dict mapping product_type to metadata (resolution_cm, bands, stats)
    """
    import json

    product_metadata: dict[str, dict] = {}
    stats_path_str = outputs.get("statistics")
    if not stats_path_str:
        return product_metadata

    stats_path = Path(stats_path_str)
    if not stats_path.exists():
        logger.warning(f"Statistics file not found: {stats_path}")
        return product_metadata

    try:
        stats_data = json.loads(stats_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read statistics file: {e}")
        return product_metadata

    stats_outputs = stats_data.get("outputs", {})

    for file_key, file_info in stats_outputs.items():
        product_type = ORTHO_OUTPUT_KEY_MAP.get(
            file_key.replace(".tif", ""),
            file_key.replace(".tif", ""),
        )

        meta: dict = {}

        geotransform = file_info.get("geotransform")
        if geotransform and len(geotransform) >= 2:
            pixel_size_m = abs(geotransform[1])
            meta["resolution_cm"] = round(pixel_size_m * 100, 4)

        num_bands = file_info.get("bands")
        if num_bands:
            meta["bands"] = [f"band_{i+1}" for i in range(num_bands)]

        file_stats = {}
        for key in ("width", "height", "crs", "size_mb"):
            if key in file_info:
                file_stats[key] = file_info[key]
        if file_stats:
            meta["stats"] = file_stats

        if meta:
            product_metadata[product_type] = meta

    return product_metadata


async def upload_stage_products(
    service_name: str,
    job_id: str,
    result: dict,
    product_upload_client: ProductUploadClient,
    job_state_manager: JobStateManager | None = None,
    main_job_id: str | None = None,
) -> UploadResult:
    """
    Upload products from a completed stage to backend.
    
    Args:
        service_name: Name of the service (sfm, orthomosaic)
        job_id: Backend job ID for product association
        result: Stage result containing output paths
        product_upload_client: Client for uploading to backend
        job_state_manager: Optional state manager to track upload failures
        main_job_id: Main job ID for state updates
    
    Returns:
        UploadResult with uploaded and failed products
    """
    upload_result = UploadResult()
    outputs = result.get("outputs", {})
    dataset_id = result.get("dataset_id")
    
    async def _upload_product(
        product_type: str,
        file_path: Path,
        resolution_cm: float | None = None,
        bands: list[str] | None = None,
        stats: dict | None = None,
    ) -> bool:
        """Upload a single product and track result."""
        logger.info(
            f"[UPLOAD] Attempting upload: product_type={product_type}, "
            f"file_path={file_path}, job_id={job_id}, dataset_id={dataset_id}"
        )
        
        if not file_path.exists():
            logger.error(
                f"File not found for {product_type}: {file_path}. "
                f"This may indicate a volume mount issue between containers."
            )
            upload_result.failed.append({
                "product_type": product_type,
                "file_path": str(file_path),
                "error": "File not found - check shared volume mounts",
            })
            return False
        
        file_size = file_path.stat().st_size
        logger.info(f"File exists: {file_path} ({file_size / 1024 / 1024:.1f} MB)")
        
        try:
            logger.info(
                f"[UPLOAD] Calling product_upload_client.upload_product: "
                f"job_id={job_id}, dataset_id={dataset_id}, "
                f"product_type={product_type}, file={file_path.name}"
            )
            product_info = await product_upload_client.upload_product(
                job_id=job_id,
                dataset_id=dataset_id,
                product_type=product_type,
                file_path=file_path,
                resolution_cm=resolution_cm,
                bands=bands,
                stats=stats,
            )
            upload_result.uploaded.append({
                "product_type": product_type,
                "product_id": product_info.get("product_id"),
                "s3_uri": product_info.get("s3_uri"),
            })
            logger.info(f"[UPLOAD] Successfully uploaded {product_type}: {product_info.get('product_id')}")
            return True
        except Exception as e:
            logger.error(
                f"[UPLOAD] Failed to upload {product_type}: {e}\n"
                f"  job_id={job_id}, dataset_id={dataset_id}, file={file_path}",
                exc_info=True,
            )
            upload_result.failed.append({
                "product_type": product_type,
                "file_path": str(file_path),
                "error": str(e),
            })
            return False
    
    if service_name == "calibration":
        band_manifest = result.get("band_manifest")
        logger.info(
            f"[UPLOAD] Calibration upload: dataset_id={dataset_id}, "
            f"band_manifest={'present (' + str(type(band_manifest).__name__) + ')' if band_manifest else 'MISSING'}, "
            f"result keys={list(result.keys())}"
        )
        if band_manifest:
            import json
            import tempfile

            manifest_json = json.dumps(band_manifest, indent=2)
            tmp_dir = Path(tempfile.mkdtemp())
            manifest_tmp = tmp_dir / "band_manifest.json"
            manifest_tmp.write_text(manifest_json)
            logger.info(
                f"[UPLOAD] band_manifest temp file created: {manifest_tmp}, "
                f"size={len(manifest_json)} bytes, exists={manifest_tmp.exists()}, "
                f"bands_count={len(band_manifest) if isinstance(band_manifest, (list, dict)) else 'N/A'}"
            )
            success = await _upload_product("band_manifest", manifest_tmp)
            if success:
                logger.info(f"[UPLOAD] band_manifest uploaded successfully for job {job_id}")
            else:
                logger.error(
                    f"[UPLOAD] band_manifest upload FAILED for job {job_id}, "
                    f"dataset_id={dataset_id}. Check product_upload_client connectivity "
                    f"and backend availability."
                )
            manifest_tmp.unlink(missing_ok=True)
            tmp_dir.rmdir()
        else:
            logger.warning(
                f"[UPLOAD] No band_manifest in calibration result for job {job_id} — "
                f"skipping upload. Result keys present: {list(result.keys())}"
            )

    elif service_name == "sfm":
        run_path = Path(result.get("run_path", ""))
        logger.info(f"SFM upload: checking run_path={run_path}")
        
        if not run_path.exists():
            logger.error(f"SFM run_path does not exist: {run_path}")
        else:
            dense_path = run_path / "dense"

            await asyncio.gather(
                _upload_product("pointcloud", dense_path / "fused.ply"),
                _upload_product("pointcloud_utm", dense_path / "fused_utm.ply"),
                _upload_product("mesh", dense_path / "meshed-poisson.ply"),
            )

    elif service_name == "orthomosaic":
        product_metadata = _extract_orthomosaic_metadata(outputs)
        upload_tasks: list = []
        for product_type, output_key in [
            ("orthomosaic", "orthomosaic_rgb"),
            ("dsm", "dsm_filled_cog"),
            ("hillshade", "hillshade"),
        ]:
            if output_key in outputs:
                meta = product_metadata.get(product_type, {})
                upload_tasks.append(_upload_product(
                    product_type,
                    Path(outputs[output_key]),
                    resolution_cm=meta.get("resolution_cm"),
                    bands=meta.get("bands"),
                    stats=meta.get("stats"),
                ))
            else:
                logger.warning(f"Output key '{output_key}' not found in results for {product_type}")

        for vi_type in ("ndvi", "ndre", "gndvi"):
            if vi_type in outputs:
                meta = product_metadata.get(vi_type, {})
                upload_tasks.append(_upload_product(
                    vi_type,
                    Path(outputs[vi_type]),
                    resolution_cm=meta.get("resolution_cm"),
                    bands=[vi_type],
                    stats=meta.get("stats"),
                ))

        if "multiband_reflectance" in outputs:
            meta = product_metadata.get("calibrated_reflectance", {})
            upload_tasks.append(
                _upload_product(
                    "calibrated_reflectance",
                    Path(outputs["multiband_reflectance"]),
                    resolution_cm=meta.get("resolution_cm"),
                    bands=meta.get("bands"),
                    stats=meta.get("stats"),
                )
            )

        for scale in (2, 4, 8):
            mr_key = f"orthomosaic_rgb_{scale}x"
            if mr_key in outputs:
                upload_tasks.append(
                    _upload_product(f"orthomosaic_{scale}x", Path(outputs[mr_key]))
                )

        for band in ("green", "red", "red_edge", "nir", "blue"):
            ortho_key = f"{band}_ortho"
            if ortho_key in outputs:
                upload_tasks.append(
                    _upload_product(f"band_{band}", Path(outputs[ortho_key]))
                )

        if upload_tasks:
            await asyncio.gather(*upload_tasks)
    
    # Issue 2: Track upload failures in job state
    if upload_result.has_failures and job_state_manager and main_job_id:
        logger.warning(
            f"Job {main_job_id}: {len(upload_result.failed)} upload(s) failed: "
            f"{[f['product_type'] for f in upload_result.failed]}"
        )
        # Store failure info in job state for retry capability
        job_state_manager.update_job(
            main_job_id,
            error=f"Upload failures: {[f['product_type'] for f in upload_result.failed]}",
        )
    
    logger.info(
        f"Upload summary for {service_name}: "
        f"{len(upload_result.uploaded)} succeeded, {len(upload_result.failed)} failed"
    )
    
    return upload_result


async def trigger_next_stage(
    next_stage: StateProcessingStage,
    job_state,
    job_state_manager: JobStateManager,
    sfm_client: SFMClient,
    orthomosaic_client: OrthomosaicClient,
    backend_client: BackendClient,
    temp_manager: TempStorageManager,
    dispatch_settings: DispatchSettings | None = None,
    sqs_dispatcher: SQSDispatcher | None = None,
):
    """Trigger the next processing stage based on callback-driven orchestration."""
    from infrastructure.storage.s3_settings import TempStorageSettings
    
    job_id = job_state.job_id
    backend_job_id = job_state.backend_job_id
    dataset_id = job_state.dataset_id
    download_url = job_state.download_url
    parameters = job_state.parameters
    
    logger.info(f"Triggering next stage: {next_stage.value} for job {job_id}")
    
    if next_stage == StateProcessingStage.SFM:
        # Send progress update
        await backend_client.send_progress_update(
            job_id=backend_job_id,
            progress=30.0,
            current_stage="sfm",
            message="Starting structure from motion",
        )
        
        sfm_job_id = f"{job_id}_sfm"
        use_sqs = dispatch_settings and dispatch_settings.mode == "sqs" and sqs_dispatcher
        if use_sqs:
            await sqs_dispatcher.dispatch_sfm(
                job_id=sfm_job_id,
                dataset_id=dataset_id,
                download_url=download_url,
                parameters=parameters,
            )
        else:
            await sfm_client.run_sfm(
                job_id=sfm_job_id,
                dataset_id=dataset_id,
                download_url=download_url,
                parameters=parameters,
            )
        logger.info(f"SFM triggered for {sfm_job_id}")
    
    elif next_stage == StateProcessingStage.ORTHOMOSAIC:
        # Get SFM output path from previous stage result
        sfm_result = job_state.stage_results.get("sfm", {})
        sfm_output_path = sfm_result.get("run_path")
        
        if not sfm_output_path:
            # Fallback: construct expected path
            temp_settings = TempStorageSettings()
            sfm_output_path = str(
                Path(temp_settings.base_path) / "jobs" / "sfm" / f"{job_id}_sfm" / "run_1"
            )
        
        await backend_client.send_progress_update(
            job_id=backend_job_id,
            progress=70.0,
            current_stage="orthomosaic",
            message="Starting orthomosaic generation",
        )

        ortho_params = dict(parameters) if parameters else {}

        calibration_result = job_state.stage_results.get("radiometric_calibration", {})
        if calibration_result:
            ortho_params["is_multispectral"] = calibration_result.get(
                "is_multispectral", False
            )
            ortho_params["calibration_path"] = calibration_result.get(
                "calibration_path"
            )
            ortho_params["band_manifest"] = calibration_result.get("band_manifest")
            ortho_params["has_reflectance"] = calibration_result.get(
                "has_reflectance", False
            )
            ortho_params["sfm_run_path"] = sfm_output_path

        logger.info(
            f"[ORTHOMOSAIC] Triggering for job {job_id} with "
            f"analysis_mode={ortho_params.get('analysis_mode')}, "
            f"is_multispectral={ortho_params.get('is_multispectral')}, "
            f"calibration_path={ortho_params.get('calibration_path')}, "
            f"has_reflectance={ortho_params.get('has_reflectance')}"
        )

        orthomosaic_job_id = f"{job_id}_orthomosaic"
        use_sqs = dispatch_settings and dispatch_settings.mode == "sqs" and sqs_dispatcher
        if use_sqs:
            await sqs_dispatcher.dispatch_orthomosaic(
                job_id=orthomosaic_job_id,
                dataset_id=dataset_id,
                dataset_path=sfm_output_path,
                parameters=ortho_params,
            )
        else:
            await orthomosaic_client.run_orthomosaic(
                job_id=orthomosaic_job_id,
                dataset_id=dataset_id,
                dataset_path=sfm_output_path,
                parameters=ortho_params,
            )
        logger.info(f"Orthomosaic triggered for {orthomosaic_job_id}")
    
    elif next_stage == StateProcessingStage.UPLOADING:
        # Uploads happen as fire-and-forget during callback processing.
        # Mark uploading stage as complete and move to completion.
        logger.info(f"[PIPELINE] Processing stages done, finalizing job {job_id}")
        
        # Complete the uploading stage
        job_state_manager.complete_stage(job_id, StateProcessingStage.UPLOADING)
        
        # Skip PUBLISHING (no-op) and complete the pipeline
        job_state_manager.complete_stage(job_id, StateProcessingStage.PUBLISHING)
        
        # Send completion callback to backend
        await backend_client.send_completion(
            job_id=backend_job_id,
            dataset_id=dataset_id,
            outputs=job_state.stage_results,
            metadata={"total_stages": len(job_state.stage_results)},
        )
        logger.info(f"[PIPELINE] Job {job_id} completed successfully")


async def run_pipeline_task(
    job_id: str,
    job_state_manager: JobStateManager,
    calibration_client: CalibrationClient,
    sfm_client: SFMClient,
    orthomosaic_client: OrthomosaicClient,
    backend_client: BackendClient,
    product_upload_client: ProductUploadClient | None = None,
    temp_manager: TempStorageManager = None,
    dispatch_settings: DispatchSettings | None = None,
    sqs_dispatcher: SQSDispatcher | None = None,
    background_task_handler: BackgroundTaskHandler | None = None,
):
    """
    Start the processing pipeline by triggering only the first applicable stage.
    
    Subsequent stages are triggered via callbacks from sub-services.
    This function only triggers the initial stage based on job state.
    When concurrency control is enabled, acquires a pipeline slot and holds it
    until the entire pipeline completes via callback-driven signaling.
    """
    if background_task_handler:
        await background_task_handler.acquire_pipeline_slot(job_id)
    try:
        # Get job state
        job_state = job_state_manager.get_job(job_id)
        if not job_state:
            raise ValueError(f"Job state not found for {job_id}")
        
        backend_job_id = job_state.backend_job_id
        dataset_id = job_state.dataset_id
        download_url = job_state.download_url
        parameters = job_state.parameters
        current_stage = job_state.current_stage
        
        logger.info(f"API Gateway: Starting pipeline for job {job_id}, initial stage: {current_stage.value}")
        temp_manager.update_job_timestamp(job_id)
        
        # Record queue wait time (created_at → now)
        if job_state.created_at:
            from datetime import datetime, timezone
            try:
                created = datetime.fromisoformat(job_state.created_at)
                wait = (datetime.now(timezone.utc) - created).total_seconds()
                record_queue_wait(wait)
            except (ValueError, TypeError):
                pass
        
        # Determine which stage to start based on job state
        if current_stage in [StateProcessingStage.PENDING, StateProcessingStage.RADIOMETRIC_CALIBRATION]:
            # Start with calibration
            job_state_manager.start_stage(job_id, StateProcessingStage.RADIOMETRIC_CALIBRATION)
            
            await backend_client.send_progress_update(
                job_id=backend_job_id,
                progress=10.0,
                current_stage="radiometric_calibration",
                message="Starting radiometric calibration",
            )
            
            calibration_job_id = f"{job_id}_calibration"
            use_sqs = dispatch_settings and dispatch_settings.mode == "sqs" and sqs_dispatcher
            if use_sqs:
                await sqs_dispatcher.dispatch_calibration(
                    job_id=calibration_job_id,
                    dataset_id=dataset_id,
                    download_url=download_url,
                    parameters=parameters,
                )
            else:
                await calibration_client.run_calibration(
                    job_id=calibration_job_id,
                    dataset_id=dataset_id,
                    download_url=download_url,
                    parameters=parameters,
                )
            logger.info(f"Calibration triggered for {calibration_job_id}")
        
        elif current_stage == StateProcessingStage.SFM:
            # Resume from SFM
            job_state_manager.start_stage(job_id, StateProcessingStage.SFM)
            
            await backend_client.send_progress_update(
                job_id=backend_job_id,
                progress=30.0,
                current_stage="sfm",
                message="Resuming from SFM stage",
            )
            
            sfm_job_id = f"{job_id}_sfm"
            use_sqs = dispatch_settings and dispatch_settings.mode == "sqs" and sqs_dispatcher
            if use_sqs:
                await sqs_dispatcher.dispatch_sfm(
                    job_id=sfm_job_id,
                    dataset_id=dataset_id,
                    download_url=download_url,
                    parameters=parameters,
                )
            else:
                await sfm_client.run_sfm(
                    job_id=sfm_job_id,
                    dataset_id=dataset_id,
                    download_url=download_url,
                    parameters=parameters,
                )
            logger.info(f"SFM triggered for {sfm_job_id}")
        
        elif current_stage == StateProcessingStage.ORTHOMOSAIC:
            job_state_manager.start_stage(job_id, StateProcessingStage.ORTHOMOSAIC)
            
            from infrastructure.storage.s3_settings import TempStorageSettings
            temp_settings = TempStorageSettings()
            sfm_output_path = str(
                Path(temp_settings.base_path) / "jobs" / "sfm" / f"{job_id}_sfm" / "run_1"
            )
            
            await backend_client.send_progress_update(
                job_id=backend_job_id,
                progress=70.0,
                current_stage="orthomosaic",
                message="Resuming from orthomosaic stage",
            )

            ortho_params = dict(parameters) if parameters else {}
            cal_result = job_state.stage_results.get("radiometric_calibration", {})
            if cal_result:
                ortho_params["is_multispectral"] = cal_result.get("is_multispectral", False)
                ortho_params["calibration_path"] = cal_result.get("calibration_path")
                ortho_params["band_manifest"] = cal_result.get("band_manifest")
                ortho_params["has_reflectance"] = cal_result.get("has_reflectance", False)
                ortho_params["sfm_run_path"] = sfm_output_path

            logger.info(
                f"[ORTHOMOSAIC-RESUME] Triggering for job {job_id} with "
                f"analysis_mode={ortho_params.get('analysis_mode')}, "
                f"is_multispectral={ortho_params.get('is_multispectral')}, "
                f"calibration_path={ortho_params.get('calibration_path')}, "
                f"has_reflectance={ortho_params.get('has_reflectance')}"
            )

            orthomosaic_job_id = f"{job_id}_orthomosaic"
            use_sqs = dispatch_settings and dispatch_settings.mode == "sqs" and sqs_dispatcher
            if use_sqs:
                await sqs_dispatcher.dispatch_orthomosaic(
                    job_id=orthomosaic_job_id,
                    dataset_id=dataset_id,
                    dataset_path=sfm_output_path,
                    parameters=ortho_params,
                )
            else:
                await orthomosaic_client.run_orthomosaic(
                    job_id=orthomosaic_job_id,
                    dataset_id=dataset_id,
                    dataset_path=sfm_output_path,
                    parameters=ortho_params,
                )
            logger.info(f"Orthomosaic triggered for {orthomosaic_job_id}")
        
        elif current_stage in (StateProcessingStage.UPLOADING, StateProcessingStage.PUBLISHING):
            # Retry uploads: re-upload products from all completed stages
            if not product_upload_client:
                raise ValueError("product_upload_client required to retry uploads")
            
            job_state_manager.start_stage(job_id, StateProcessingStage.UPLOADING)
            
            await backend_client.send_progress_update(
                job_id=backend_job_id,
                progress=90.0,
                current_stage="uploading",
                message="Retrying product uploads",
            )
            
            logger.info(f"[UPLOAD-RETRY] Re-uploading products for job {job_id}")
            
            # Re-upload products from each completed processing stage
            stage_service_map = {
                "radiometric_calibration": "calibration",
                "sfm": "sfm",
                "orthomosaic": "orthomosaic",
            }
            
            all_uploaded = []
            all_failed = []
            
            for stage_key, service_name in stage_service_map.items():
                stage_result = job_state.stage_results.get(stage_key)
                if not stage_result:
                    logger.info(f"[UPLOAD-RETRY] No result for {stage_key}, skipping")
                    continue
                
                logger.info(f"[UPLOAD-RETRY] Uploading products from {service_name}")
                try:
                    upload_result = await upload_stage_products(
                        service_name=service_name,
                        job_id=backend_job_id,
                        result=stage_result,
                        product_upload_client=product_upload_client,
                        job_state_manager=job_state_manager,
                        main_job_id=job_id,
                    )
                    all_uploaded.extend(upload_result.uploaded)
                    all_failed.extend(upload_result.failed)
                except Exception as exc:
                    logger.error(
                        f"[UPLOAD-RETRY] Failed to upload {service_name} products: {exc}",
                        exc_info=True,
                    )
                    all_failed.append({"product_type": service_name, "error": str(exc)})
            
            # Report upload status to backend
            await backend_client.send_upload_status(
                job_id=backend_job_id,
                uploaded=all_uploaded,
                failed=all_failed,
            )
            
            if all_failed:
                logger.warning(
                    f"[UPLOAD-RETRY] {len(all_failed)} upload(s) failed for job {job_id}: "
                    f"{[f.get('product_type', 'unknown') for f in all_failed]}"
                )
            else:
                logger.info(f"[UPLOAD-RETRY] All uploads succeeded for job {job_id}")
            
            # Complete uploading + publishing stages and finalize
            job_state_manager.complete_stage(job_id, StateProcessingStage.UPLOADING)
            job_state_manager.complete_stage(job_id, StateProcessingStage.PUBLISHING)
            
            await backend_client.send_completion(
                job_id=backend_job_id,
                dataset_id=dataset_id,
                outputs=job_state.stage_results,
                metadata={"total_stages": len(job_state.stage_results)},
            )
            logger.info(f"[UPLOAD-RETRY] Job {job_id} completed")
        
        else:
            logger.warning(f"Unexpected initial stage: {current_stage.value}")
        
        # This function returns after triggering the first stage
        # Subsequent stages are triggered via subservice_callback
        # Wait for pipeline completion (holds the pipeline slot)
        if background_task_handler:
            await background_task_handler.wait_for_pipeline(job_id)

        return {
            "job_id": job_id,
            "status": "stage_triggered",
            "initial_stage": current_stage.value,
            "message": "Initial stage triggered. Pipeline continues via callbacks.",
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Pipeline start failed for job {job_id}: {error_msg}")
        logger.error(traceback.format_exc())
        
        # Update job state
        job_state = job_state_manager.get_job(job_id)
        if job_state:
            job_state_manager.update_job(job_id, status="failed", error=error_msg)
            
            await backend_client.send_failure(
                job_id=job_state.backend_job_id,
                error_message=error_msg,
                error_details={"traceback": traceback.format_exc()},
            )
        
        raise
    finally:
        if background_task_handler:
            background_task_handler.release_pipeline_slot(job_id)
