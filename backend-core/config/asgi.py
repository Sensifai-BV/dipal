import os
from django.core.asgi import get_asgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django_asgi_app = get_asgi_application()
from channels.routing import ProtocolTypeRouter, URLRouter
from apps.uploads.middleware import JwtAuthMiddleware
from apps.uploads.routing import websocket_urlpatterns

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,

    "websocket": JwtAuthMiddleware(
        URLRouter(websocket_urlpatterns)

    ),
})
