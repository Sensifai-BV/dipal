from django.contrib import admin
from django.urls import path, include
from config.views import api_root
from config.api_docs import api_documentation
from apps.jobs.api.views.health import HealthCheckView
from apps.jobs.api.views.metrics import MetricsView, DetailedMetricsView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('', api_root, name='api-root'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('metrics/', MetricsView.as_view(), name='metrics'),
    path('detailed-metrics/', DetailedMetricsView.as_view(), name='detailed-metrics'),
    path('docs/', api_documentation, name='api-docs'),
    path('admin/', admin.site.urls),
    path('v1/', include("config.api_v1")),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
