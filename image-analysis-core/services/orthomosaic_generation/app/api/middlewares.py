from __future__ import annotations

from fastapi import Request, status
from fastapi.logger import logger
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .app import APIEndpoint

__all__ = (
    "add_middlewares",
    "AlgorithmMiddleware",
)


def add_middlewares(
    endpoint: APIEndpoint,
    middlewares: list,
) -> None:
    for middleware in middlewares:
        endpoint.add_middleware(middleware)


class AlgorithmMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            json_response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error",
                    "message": "An internal server error occurred.",
                    "error": str(e),
                },
            )
            logger.error(e)
            return json_response
