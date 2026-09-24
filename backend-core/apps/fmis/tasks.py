# fmis/tasks.py
from celery import shared_task
import requests
import json
import time
from apps.fmis.models import WebhookEndpoint, Job, FMISJobStatus
from apps.fmis.services.sender import WebhookService
from apps.fmis.selectors import webhook_get_active_subscribers
from config.logging_config import get_logger

logger = get_logger(__name__)


@shared_task
def dispatch_webhook_event(event_type, payload_data, specific_org_id=None):
    """
    Find subscribers for the event and queue sending tasks.

    Args:
        event_type: The event type to dispatch (e.g., 'job.completed')
        payload_data: The webhook payload data
        specific_org_id: Optional org ID to limit dispatch to
    """
    subscribers = webhook_get_active_subscribers(event_type=event_type)

    if specific_org_id:
        subscribers = subscribers.filter(org_id=specific_org_id)

    count = 0
    for endpoint in subscribers:
        send_single_webhook.delay(endpoint.id, event_type, payload_data)
        count += 1

    logger.info(f"Dispatched {event_type} webhook to {count} subscriber(s)")


@shared_task(
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=3
)
def send_single_webhook(endpoint_id, event_type, payload_data):
    """
    Send a single webhook notification to an endpoint.

    Args:
        endpoint_id: The webhook endpoint UUID
        event_type: The event type being sent
        payload_data: The payload dictionary

    Returns:
        Status message string
    """
    try:
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
    except WebhookEndpoint.DoesNotExist:
        logger.warning(f"Webhook endpoint {endpoint_id} no longer exists")
        return "Endpoint Removed"

    payload_json = json.dumps(payload_data, sort_keys=True)
    signature = WebhookService.generate_signature(endpoint.secret, payload_json)

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": signature,
        "X-Event-Type": event_type
    }

    if endpoint.headers:
        headers.update(endpoint.headers)

    logger.info(f"Sending {event_type} webhook to {endpoint.url}")
    response = requests.post(
        endpoint.url,
        data=payload_json,
        headers=headers,
        timeout=10
    )
    response.raise_for_status()

    logger.info(f"Webhook {event_type} sent to {endpoint.url}: {response.status_code}")
    return f"Sent {event_type} to {endpoint.url}: {response.status_code}"


@shared_task
def process_job_task(job_id):
    """
    Handle asynchronous FMIS job processing.

    Args:
        job_id: The UUID of the FMIS Job to process
    """
    job = None
    try:
        job = Job.objects.get(id=job_id)

        job.status = FMISJobStatus.PROCESSING
        job.save()
        logger.info(f"FMIS job {job_id} status set to processing")

        time.sleep(5)

        final_result = {
            "analysis": "Success",
            "score": 98,
            "details": "Processed input_data successfully."
        }

        job.result_data = final_result
        job.status = FMISJobStatus.COMPLETED
        job.save()
        logger.info(f"FMIS job {job_id} completed")

        webhook_payload = {
            "job_id": str(job.id),
            "status": FMISJobStatus.COMPLETED,
            "result": final_result,
            "created_at": str(job.created_at),
            "completed_at": str(job.updated_at)
        }

        dispatch_webhook_event.delay(
            event_type='job.completed',
            payload_data=webhook_payload,
            specific_org_id=job.org.id
        )

    except Job.DoesNotExist:
        logger.error(f"FMIS job {job_id} not found")
    except Exception as e:
        logger.error(f"FMIS job {job_id} failed: {e}")
        if job:
            job.status = FMISJobStatus.FAILED
            job.result_data = {"error": str(e)}
            job.save()

            dispatch_webhook_event.delay(
                event_type='job.failed',
                payload_data={
                    "job_id": str(job.id),
                    "status": FMISJobStatus.FAILED,
                    "error": str(e)
                },
                specific_org_id=job.org.id
            )
        # Re-raise to log in Celery
        raise e
