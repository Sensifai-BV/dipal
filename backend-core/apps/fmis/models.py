import uuid
import secrets
from django.db import models
from django.contrib.postgres.fields import ArrayField
from accounts.models import Organization


class FMISIntegrationStatus(models.TextChoices):
    """Status choices for FMIS external integrations."""

    CONNECTED = "connected", "Connected"
    FAILED = "failed", "Failed"
    PENDING = "pending", "Pending"


class FMISJobStatus(models.TextChoices):
    """Status choices for FMIS processing jobs."""

    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class WebhookEndpoint(models.Model):
    AVAILABLE_EVENTS = [
        ('job.completed', 'Job Completed'),
        ('job.failed', 'Job Failed'),
        ('upload.completed', 'Upload Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='webhooks',
        db_column='org_id',
        verbose_name="Organization"
    )

    url = models.URLField(max_length=500)
    secret = models.CharField(max_length=255, blank=True, verbose_name="Secret Key")

    events = ArrayField(
        models.CharField(max_length=100),
        blank=True,
        default=list,
        help_text="List of events this webhook subscribes to."
    )

    headers = models.JSONField(default=dict, blank=True, verbose_name="Custom Headers")

    active = models.BooleanField(default=True, verbose_name="Is Active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fmis_webhook'
        ordering = ['-created_at']
        verbose_name = 'Webhook Endpoint'
        verbose_name_plural = 'Webhook Endpoints'

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = secrets.token_hex(24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.org_id} -> {self.url}"


class FMISIntegration(models.Model):
    PROVIDER_CHOICES = [
        ('farm_b', 'Farm-b'),
        ('leaf', 'Leaf Agriculture'),
        ('timberlee', 'Timberlee'),
        ('generic', 'Generic / Custom'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='fmis_integrations'
    )

    provider_name = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        default='generic',
        help_text="Select the external system provider"
    )

    base_url = models.URLField(help_text="Base API URL provided by the external system")
    api_token = models.CharField(max_length=500, help_text="Authentication Token / API Key")
    extra_headers = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=FMISIntegrationStatus.choices, default=FMISIntegrationStatus.PENDING)
    last_connected_at = models.DateTimeField(null=True, blank=True)
    last_error_message = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('org', 'provider_name')
        verbose_name = "External Integration"
        verbose_name_plural = "External Integrations"

    def __str__(self):
        return f"{self.get_provider_name_display()} ({self.org})"


# --- NEW MODEL ADDED FOR PROCESSING SCENARIO ---
class Job(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='fmis_jobs'
    )

    # Input data from client
    input_data = models.JSONField(default=dict, blank=True)

    # Result data after processing
    result_data = models.JSONField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=FMISJobStatus.choices, default=FMISJobStatus.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Processing Job'

    def __str__(self):
        return f"Job {self.id} ({self.status})"
