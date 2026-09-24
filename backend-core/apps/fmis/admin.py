from django.contrib import admin
from .models import WebhookEndpoint, FMISIntegration

@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ('org', 'url', 'active', 'created_at')
    list_filter = ('active', 'created_at')
    search_fields = ('url', 'org__name')

@admin.register(FMISIntegration)
class FMISIntegrationAdmin(admin.ModelAdmin):
    list_display = ('org', 'provider_name', 'base_url', 'status', 'last_connected_at')
    list_filter = ('status', 'provider_name')
    search_fields = ('org__name', 'provider_name')
    readonly_fields = ('last_connected_at', 'last_error_message')

