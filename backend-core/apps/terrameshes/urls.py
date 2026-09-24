from django.urls import path
from apps.processings.views.views import StartProcessingView, AICallbackView

app_name = 'terrameshes'

urlpatterns = [
    path(
        'start/<uuid:dataset_id>/',
        StartProcessingView.as_view(),
        name='start_processing'
    ),
    path(
        'callback/',
        AICallbackView.as_view(),
        name='ai_callback'
    ),
]