from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from accounts.models.user import UserModel

@admin.register(UserModel)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = (
        "email",
        "username",
        "is_active",
        "is_superuser",
        "is_staff",
        "is_email_verified",
    )
    search_fields = (
        "email",
    )
    list_filter = (
        "is_active",
        "is_superuser",
        "is_staff",
        "is_email_verified",
    )
    fieldsets = [
        ("Personal info", {"fields": [
            "first_name",
            "last_name",
            "email",
            "password",
            "date_joined",
        ]}),
        ("Status", {"fields": [
            "is_active",
            "is_staff",
            "is_superuser",
            "is_email_verified",
        ]}),
        ("Permissions", {"fields": ["groups", "user_permissions"]}),
    ]
    add_fieldsets = [
        ("Personal info", {"fields": [
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        ]}),
        ("Status", {"fields": [
            "is_active",
            "is_staff",
            "is_superuser",
            "is_email_verified",
        ]}),
        ("Permissions", {"fields": ["groups", "user_permissions"]}),
    ]
    ordering = ["email"]
    filter_horizontal = ["groups", "user_permissions"]
