from typing import Iterable
from .models import WebhookEndpoint

def webhook_list(*, org_id: str) -> Iterable[WebhookEndpoint]:

    return WebhookEndpoint.objects.filter(org_id=org_id)

def webhook_get_active_subscribers(*, event_type: str) -> Iterable[WebhookEndpoint]:

    return WebhookEndpoint.objects.filter(
        active=True,
        events__contains=[event_type]
    ).select_related('org')
