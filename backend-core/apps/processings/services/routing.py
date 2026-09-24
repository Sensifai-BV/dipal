from django.urls import re_path
from .services import consumers

websocket_urlpatterns = [
    # Route for: ws/processing/<job_id>/
    # Using (?P<job_id>[^/]+) to allow UUID strings with hyphens
    re_path(r'ws/processing/(?P<job_id>[^/]+)/$', consumers.ProcessingConsumer.as_asgi()),
]
