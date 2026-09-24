from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.fmis.api.views import (
    WebhookViewSet,
    FMISIntegrationViewSet,
    JobViewSet
)

app_name = 'fmis'

router = DefaultRouter()

router.register(r'webhooks', WebhookViewSet, basename='webhook')

router.register(r'integrations', FMISIntegrationViewSet, basename='integration')

router.register(r'jobs', JobViewSet, basename='job')

urlpatterns = [
    path('', include(router.urls)),
]