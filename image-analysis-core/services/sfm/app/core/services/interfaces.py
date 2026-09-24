from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class IService(ABC):
    @abstractmethod
    def extract_metadata(self, container_name: str): ...

    @abstractmethod
    def extract_features(self, container_name: str): ...

    @abstractmethod
    def match_features(self, container_name: str): ...

    @abstractmethod
    def create_tracks(self, container_name: str): ...

    @abstractmethod
    def create_processing_config(self): ...

    @abstractmethod
    def create_rig(self, container_name: str): ...

    @abstractmethod
    def compute_reconstruct(self, container_name: str): ...

    @abstractmethod
    def reconstruct_from_prior(self, container_name: str): ...

    @abstractmethod
    def bundle_reconstruction(self, container_name: str): ...

    @abstractmethod
    def geo_register(self, container_name: str): ...

    @abstractmethod
    def mesh(self, container_name: str): ...

    @abstractmethod
    def undistort(self, container_name: str): ...

    @abstractmethod
    def compute_depthmaps(self, container_name: str): ...

    @abstractmethod
    def compute_statistics(self, container_name: str): ...

    @abstractmethod
    def export_report(self, container_name: str): ...

    @abstractmethod
    def start(self, dataset_path: Path) -> str: ...

    @abstractmethod
    def stop(self, container_name: str): ...

    @abstractmethod
    def clean(self, container_name: str): ...
