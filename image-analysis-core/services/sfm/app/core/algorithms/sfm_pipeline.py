from __future__ import annotations

from pathlib import Path

from ..services.interfaces import IService


class SFMPipeline:
    def __init__(self, service: IService):
        self.service = service

    def run_pipeline(self, dataset_path: Path):
        container_name = self.service.start(dataset_path)

        try:
            self.service.create_processing_config()
            self.service.extract_metadata(container_name)
            self.service.extract_features(container_name)
            self.service.match_features(container_name)
            self.service.create_tracks(container_name)
            self.service.compute_reconstruct(container_name)
            self.service.bundle_reconstruction(container_name)
            self.service.undistort(container_name)
            self.service.compute_depthmaps(container_name)
            self.service.geo_register(container_name)
            self.service.mesh(container_name)
            self.service.compute_statistics(container_name)
            self.service.export_report(container_name)
        finally:
            self.service.stop(container_name)
            self.service.clean(container_name)

    def log_explorer(self, process_name: str, input_log: str): ...
