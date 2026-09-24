import uuid

from django.contrib.auth.base_user import BaseUserManager


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Creates and saves a User with the given email and password.

        Assigns the ADMIN role by default when no role is provided.
        """
        if not email:
            raise ValueError("Users must have an email address")

        if 'role' not in extra_fields and 'role_id' not in extra_fields:
            from accounts.models.role import Role, RoleName
            extra_fields['role'] = Role.objects.filter(name=RoleName.ADMIN).first()

        user = self.model(
            email=self.normalize_email(email),
            username=uuid.uuid4(),
            **extra_fields,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(
            email,
            password=password,
        )
        user.is_admin = True
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user
