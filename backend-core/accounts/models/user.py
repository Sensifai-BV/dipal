from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid
from accounts.manager.user import CustomUserManager
from accounts.models.role import Role


class UserModel(AbstractUser):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    organization = models.ForeignKey(
        "accounts.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='users'
    )

    email = models.EmailField(
        unique=True,
        db_index=True
    )

    auth_provider = models.CharField(max_length=50, default='email')

    role = models.ForeignKey(
        'accounts.Role',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users'
    )

    is_email_verified = models.BooleanField(
        default=False
    )

    username = models.UUIDField(
        unique=True,
        editable=False,
        default=uuid.uuid4,
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'accounts_users'

    def __str__(self):
        return self.email

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()
