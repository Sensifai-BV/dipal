from django.apps import AppConfig

class WebhooksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.fmis'
    label = "fmis"

    def ready(self):
        import apps.fmis.signals

