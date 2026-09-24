from __future__ import annotations

from ..services.interfaces import IService
from .sfm_pipeline import SFMPipeline


class AlgorithmFactory:
    @classmethod
    def create_sfm_pipeline(cls, service: IService) -> SFMPipeline:
        return SFMPipeline(service=service)
