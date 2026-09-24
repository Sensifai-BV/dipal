from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SQSSettings(BaseSettings):
    """
    AWS SQS configuration for job dispatch.

    When DISPATCH_MODE=sqs, the API gateway publishes job messages to SQS
    queues instead of calling services via HTTP. Each processing service
    runs an SQS consumer that polls its queue.
    """

    enabled: bool = False
    region_name: str = "eu-north-1"
    access_key_id: str = ""
    secret_access_key: str = ""
    use_aws_role: bool = False

    calibration_queue_url: str = ""
    sfm_queue_url: str = ""
    orthomosaic_queue_url: str = ""

    calibration_dlq_url: str = ""
    sfm_dlq_url: str = ""
    orthomosaic_dlq_url: str = ""

    poll_interval_seconds: int = 5
    visibility_timeout: int = 3600
    max_messages_per_poll: int = 1
    wait_time_seconds: int = 20

    model_config = SettingsConfigDict(
        env_prefix="SQS_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )
