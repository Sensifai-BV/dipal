from django.db import models


class RoleName(models.TextChoices):
    """Canonical role identifiers — use these instead of raw strings."""

    ADMIN = "admin", "Admin"
    USER = "user", "Owner"


class Role(models.Model):

    name = models.CharField(max_length=50, unique=True, choices=RoleName.choices)
    label = models.CharField(max_length=50)

    def __str__(self):
        return self.label
