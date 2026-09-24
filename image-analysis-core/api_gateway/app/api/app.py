from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

from chromatrace.fastapi import RequestIdMiddleware

from .base_endpoint import BaseEndpoint
from .settings import APISettings, fastapi_tags_metadata


class ExceptionContent(BaseModel):
    status: str
    message: str
    error: str


class CustomException(Exception):
    def __init__(self, status_code: int, content: ExceptionContent):
        self.status_code = status_code
        self.content = content


class APIEndpoint:
    def __init__(
        self,
        api_config: APISettings,
        lifespan=None,
    ):
        self.api_config = api_config
        self._app = FastAPI(
            version=self.api_config.version,
            title=self.api_config.title,
            description=self.api_config.description,
            summary=self.api_config.summary,
            openapi_tags=fastapi_tags_metadata,
            lifespan=lifespan,
        )
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._app.add_middleware(RequestIdMiddleware)

        # Prometheus metrics instrumentation
        self._instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=[".*health.*", "/detailed-metrics"],
        )
        self._instrumentator.instrument(self._app)
        self._instrumentator.expose(
            self._app,
            endpoint="/detailed-metrics",
            include_in_schema=True,
            should_gzip=True,
        )

    def register_endpoint(self, router_endpoint: BaseEndpoint):
        router_endpoint.register_api()
        self._app.include_router(router_endpoint.router)

    def add_exception_handler(
        self,
    ):
        @self.app.exception_handler(CustomException)
        async def exception_handler(request, exc: CustomException):
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.content.model_dump(),  # {"message": f"Oops! There was an error with {exc.name}."},
            )

    def add_middleware(self, middleware):
        self.app.add_middleware(middleware)

    def mount_statics(self, static_dir: str = "assets"):
        self._app.mount(
            f"/{static_dir}",
            StaticFiles(directory=static_dir, html=True),
            name="static",
        )

    @property
    def app(self) -> FastAPI:
        return self._app
