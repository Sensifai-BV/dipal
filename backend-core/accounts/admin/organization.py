from django.contrib import admin
from accounts.models.organization import Organization

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'description',
        'user',
        'created_at',
        'updated_at',
    )
    list_display_links = (
        'name',
    )
    search_fields = (
        'name',
        'description',
    )
    raw_id_fields = (
        "user",
    )
    list_per_page = 25
