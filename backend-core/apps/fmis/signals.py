from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import WebhookEndpoint, FMISIntegration

@receiver(post_save, sender=FMISIntegration)
def log_integration_change(sender, instance, created, **kwargs):
    pass
