from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import APIRouter
from lagom.integrations.fast_api import FastApiIntegration


class BaseEndpoint(ABC):
    @abstractmethod
    def __init__(
        self,
        deps: FastApiIntegration,
    ): ...

    @abstractmethod
    def register_api(self): ...

    @property
    @abstractmethod
    def router(self) -> APIRouter: ...
