import uuid
from django.db import models
from django.conf import settings

from utils.abstract_base_model import AbstractBaseModel


class Organization(AbstractBaseModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_organization_related",
        db_column='user_id'
    )
    name = models.CharField(
        max_length=255,
    )
    description = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = "accounts_organization"
        verbose_name_plural = "Organization"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
