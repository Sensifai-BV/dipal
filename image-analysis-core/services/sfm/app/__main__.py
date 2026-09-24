from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from lagom import Container, Singleton
from lagom.integrations.fast_api import FastApiIntegration

from infrastructure.message_queue import BackgroundTaskHandler, SQSClient, SQSConsumer, SQSSettings

from .api.app import APIEndpoint
from .api.settings import APISettings
from .api.v1.endpoints.algorithm_endpoint import AlgorithmEndpoint
from .api.v1.endpoints.default import DefaultsAPIEndpoint
from .api.v1.endpoints.health import HealthAPIEndpoint
from .api.v1.endpoints.sfm_endpoint import SFMEndpoint, run_sfm_task
from .core.algorithms.algorithm_factory import AlgorithmFactory
from .core.services.service_factory import ServiceFactory

container = Container()
container[ServiceFactory] = Singleton(ServiceFactory)
container[AlgorithmFactory] = Singleton(AlgorithmFactory)
container[BackgroundTaskHandler] = Singleton(BackgroundTaskHandler)

deps = FastApiIntegration(container=container)

sqs_settings = SQSSettings()
_sqs_consumer: SQSConsumer | None = None


async def _sqs_handler(message: dict) -> None:
    """
    Handle an SQS message by running the SFM task directly.

    Args:
        message: Deserialized SQS message body with job_id, dataset_id, etc.
    """
    service_factory = container[ServiceFactory]
    algorithm_factory = container[AlgorithmFactory]

    await run_sfm_task(
        job_id=message["job_id"],
        dataset_id=message["dataset_id"],
        download_url=message["download_url"],
        parameters=message.get("parameters", {}),
        service_factory=service_factory,
        algorithm_factory=algorithm_factory,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start SQS consumer on startup if enabled, stop on shutdown."""
    global _sqs_consumer
    if sqs_settings.enabled and sqs_settings.sfm_queue_url:
        sqs_client = SQSClient(sqs_settings)
        _sqs_consumer = SQSConsumer(
            sqs_client=sqs_client,
            queue_url=sqs_settings.sfm_queue_url,
            handler=_sqs_handler,
            service_name="sfm",
        )
        await _sqs_consumer.start()
    yield
    if _sqs_consumer:
        await _sqs_consumer.stop()


api_endpoint = APIEndpoint(
    api_config=APISettings(),
    lifespan=lifespan if sqs_settings.enabled else None,
)
default_api_endpoint = DefaultsAPIEndpoint(deps=deps)
algorithm_api_endpoint = AlgorithmEndpoint(deps=deps)
sfm_api_endpoint = SFMEndpoint(deps=deps)
health_api_endpoint = HealthAPIEndpoint(deps=deps)

api_endpoint.register_endpoint(default_api_endpoint)
api_endpoint.register_endpoint(algorithm_api_endpoint)
api_endpoint.register_endpoint(sfm_api_endpoint)
api_endpoint.register_endpoint(health_api_endpoint)
app = api_endpoint.app
