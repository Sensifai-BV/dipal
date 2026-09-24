from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from lagom.integrations.fast_api import FastApiIntegration

from infrastructure.message_queue.background_task import BackgroundTaskHandler
from infrastructure.storage.dataset import Dataset
from infrastructure.storage.drivers.factory import StorageDriverFactory

from ....core.algorithms.algorithm_factory import AlgorithmFactory
from ....core.services.service_factory import ServiceFactory
from ....entities import ColmapPipelineInput
from ...base_endpoint import BaseEndpoint


class AlgorithmEndpoint(BaseEndpoint):
    def __init__(
        self,
        deps: FastApiIntegration,
    ):
        self.deps = deps
        self._router = APIRouter(
            prefix="/algorithm",
            tags=["Algorithm"],
        )

    @property
    def router(self) -> APIRouter:
        return self._router

    def register_api(self):
        @self._router.post(
            "/initialize-dataset",
        )
        async def initialize_dataset(
            dataset_id: str,
            download_url: str,
        ):
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
            driver.connect()
            dataset = Dataset(
                project_id=dataset_id,
                storage_driver=driver,
                temp_base_path=Path("data/temp/"),
            )
            dataset.initialize_dataset()
            dataset.fetch_images()
            return {"message": "Dataset initialized successfully."}

        @self._router.post(
            "/run-pipeline",
        )
        async def run_pipeline(
            pipeline_input: ColmapPipelineInput,
            service_factory: ServiceFactory = self.deps.depends(ServiceFactory),
            algorithm_factory: AlgorithmFactory = self.deps.depends(AlgorithmFactory),
        ):
            driver = StorageDriverFactory.create(
                "local",
                {
                    "base_path": pipeline_input.storage_base_path,
                },
            )
            driver.connect()
            dataset = Dataset(
                project_id=pipeline_input.project_id,
                storage_driver=driver,
                temp_base_path=Path("data/temp/"),
            )
            dataset.initialize_dataset()
            dataset.fetch_images()
            run_path = dataset.create_run()
            colmap_settings = {
                "run_path": run_path,
            }
            service = service_factory.create_service("colmap", colmap_settings)
            pipeline = algorithm_factory.create_sfm_pipeline(service)
            pipeline.run_pipeline(dataset_path=dataset.project_temp_path.absolute())

        @self._router.get(
            "/{job_id}/status",
        )
        async def job_status(
            job_id: str,
            background_task_handler=self.deps.depends(BackgroundTaskHandler),
        ):
            return background_task_handler.get_task_status(job_id)

        @self._router.get(
            "/{job_id}/result",
        )
        async def job_result(
            job_id: str,
            background_task_handler=self.deps.depends(BackgroundTaskHandler),
        ):
            task_info = background_task_handler.get_task_status(job_id)
            if task_info["status"] == "completed":
                return {"result": task_info["result"]}
            elif task_info["status"] == "failed":
                return {"error": task_info["error"]}
            else:
                return {"status": task_info["status"]}
