from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    #  ws://domain.com/ws/datasets/<dataset_id>/
    re_path(r'ws/datasets/(?P<dataset_id>[^/]+)/$', consumers.DatasetNotificationConsumer.as_asgi()),
]
