from __future__ import annotations

from lagom import Container, Singleton
from lagom.integrations.fast_api import FastApiIntegration

from infrastructure.message_queue import BackgroundTaskHandler, SQSClient, SQSSettings
from infrastructure.redis import RedisClient, RedisSettings
from infrastructure.state import JobStateManager, JobStateSettings
from infrastructure.storage.s3_settings import S3StorageSettings, TempStorageSettings
from infrastructure.storage.s3_uploader import S3ResultsUploader
from infrastructure.storage.temp_manager import TempStorageManager

from . import clients
from .api.app import APIEndpoint
from .api.settings import APISettings
from .api.v1.endpoints import DefaultsAPIEndpoint, HealthAPIEndpoint, JobsAPIEndpoint, MetricsAPIEndpoint

container = Container()

# Redis and state management
container[RedisSettings] = Singleton(lambda: RedisSettings())
container[RedisClient] = Singleton(
    lambda c: RedisClient(c[RedisSettings])
)
container[JobStateSettings] = Singleton(lambda: JobStateSettings())
container[JobStateManager] = Singleton(
    lambda c: JobStateManager(c[RedisClient], c[JobStateSettings])
)

# Background task handler with Redis support
container[BackgroundTaskHandler] = Singleton(
    lambda c: BackgroundTaskHandler(redis_client=c[RedisClient])
)

# Service clients (only needed when DISPATCH_MODE=http)
_dispatch_settings = clients.DispatchSettings()
if _dispatch_settings.mode != "sqs":
    container[clients.SFMClient] = Singleton(
        lambda: clients.SFMClient(clients.SFMClientSettings()),
    )
    container[clients.OrthomosaicClient] = Singleton(
        lambda: clients.OrthomosaicClient(clients.OrthomosaicClientSettings()),
    )
    container[clients.CalibrationClient] = Singleton(
        lambda: clients.CalibrationClient(clients.CalibrationClientSettings()),
    )
container[clients.BackendClient] = Singleton(
    lambda: clients.BackendClient(clients.BackendClientSettings()),
)
container[clients.ProductUploadClient] = Singleton(
    lambda: clients.ProductUploadClient(clients.ProductUploadClientSettings()),
)

# Storage and infrastructure
container[S3StorageSettings] = Singleton(lambda: S3StorageSettings())
container[TempStorageSettings] = Singleton(lambda: TempStorageSettings())
container[S3ResultsUploader] = Singleton(
    lambda: S3ResultsUploader(S3StorageSettings())
)
container[TempStorageManager] = Singleton(
    lambda: TempStorageManager(TempStorageSettings())
)

# Dispatch mode (http or sqs)
container[clients.DispatchSettings] = Singleton(lambda: clients.DispatchSettings())
container[SQSSettings] = Singleton(lambda: SQSSettings())
container[SQSClient] = Singleton(lambda c: SQSClient(c[SQSSettings]))
container[clients.SQSDispatcher] = Singleton(
    lambda c: clients.SQSDispatcher(c[SQSClient])
)

deps = FastApiIntegration(container=container)

# Endpoints
default_endpoint = DefaultsAPIEndpoint(deps)
jobs_endpoint = JobsAPIEndpoint(deps)
health_endpoint = HealthAPIEndpoint(deps)
metrics_endpoint = MetricsAPIEndpoint(deps)

api_endpoint = APIEndpoint(
    APISettings(),
)
api_endpoint.register_endpoint(default_endpoint)
api_endpoint.register_endpoint(jobs_endpoint)
api_endpoint.register_endpoint(health_endpoint)
api_endpoint.register_endpoint(metrics_endpoint)

app = api_endpoint.app
