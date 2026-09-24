from __future__ import annotations

from .colmap_service import ColmapService
from .interfaces import IService
from .opensfm_service import OpenSFMService


class ServiceFactory:
    services = {
        "opensfm": OpenSFMService,
        "colmap": ColmapService,
    }

    @classmethod
    def create_service(cls, service_class: str, settings: dict) -> IService:
        try:
            return cls.services[service_class](settings)
        except KeyError:
            raise ValueError(f"Service '{service_class}' not found in ServiceFactory.")
