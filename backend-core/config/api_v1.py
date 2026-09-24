from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

# Import beautiful documentation views
from config.docs_views import (
    ScalarDocsView,
    StoplightDocsView, 
    RapiDocView,
    PublicSchemaView,
)

urlpatterns = [
    path('accounts/', include("accounts.urls")),
    #path('datasets/', include("datasets.urls")),
    path('api/products/', include("products.urls")),

    path('api/fmis/', include('apps.fmis.urls')),
    path('api/uploads/', include('apps.uploads.urls')),
    path('api/jobs/', include('apps.jobs.urls')),
    path('api/processings/', include('apps.processings.urls', namespace='processings')),
    path('api/organizations/', include('apps.organizations.urls')),
    path('api/dashboard/', include('apps.dashboard.urls')),
    
    # ===== API Schema Endpoints =====
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),              # Full schema (internal)
    path('api/public-schema/', PublicSchemaView.as_view(), name='public-schema'),  # Filtered schema (public)
    
    # ===== Documentation UIs =====
    # Default Swagger/ReDoc (original)
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Beautiful Modern Documentation (Recommended!)
    path('api/docs/scalar/', ScalarDocsView.as_view(), name='scalar-docs'),        # 🌟 Firecrawl-style
    path('api/docs/stoplight/', StoplightDocsView.as_view(), name='stoplight-docs'),  # Enterprise-style
    path('api/docs/rapidoc/', RapiDocView.as_view(), name='rapidoc'),              # Customizable
]
