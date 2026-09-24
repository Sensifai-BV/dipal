from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from lagom.integrations.fast_api import FastApiIntegration

from ...base_endpoint import BaseEndpoint

_startup_time = time.monotonic()

_SERVICE_NAME = "photogear-sfm"


class HealthAPIEndpoint(BaseEndpoint):
    """Health check endpoint returning service status."""

    def __init__(self, deps: FastApiIntegration):
        self.deps = deps
        self._router = APIRouter(tags=["health"])

    @property
    def router(self) -> APIRouter:
        return self._router

    def register_api(self):
        @self._router.get("/health/")
        async def health_check():
            uptime = time.monotonic() - _startup_time
            return JSONResponse(
                content={
                    "status": "healthy",
                    "service": _SERVICE_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "uptime_seconds": round(uptime),
                },
                status_code=200,
            )
