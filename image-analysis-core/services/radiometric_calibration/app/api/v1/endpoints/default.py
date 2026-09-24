from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from lagom.integrations.fast_api import FastApiIntegration

from ...base_endpoint import BaseEndpoint


class DefaultsAPIEndpoint(BaseEndpoint):
    def __init__(self, deps: FastApiIntegration):
        self.deps = deps
        self._router = APIRouter()

    def register_api(self):
        @self.router.get("/")
        async def root():
            return RedirectResponse(url="/docs")

    @property
    def router(self) -> APIRouter:
        return self._router
