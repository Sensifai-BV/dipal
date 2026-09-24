from django.urls import path
from apps.uploads.presentation.views import (
    UserUploadsView,
    UserDatasetsStatsView,
    UploadStatusListView,
    InitiateMultipartUploadView,
    SignMultipartPartView,
    CompleteMultipartUploadView,
    UploadFromUrlView,
    DatasetExportStatusView
)
from .presentation.aiviews import DatasetFullImagesListView
from .presentation.exportviews import ExportDatasetView, ExportStatusView
from .presentation.dataset_management_views import (
    DatasetDetailView,
    DatasetListView,
    DatasetDeleteView
)

app_name = 'uploads'

urlpatterns = [
    path('list/', UserUploadsView.as_view(), name='user-uploads-list'),
    path('datasets/stats/', UserDatasetsStatsView.as_view(), name='datasets-stats'),
    path('statuses/', UploadStatusListView.as_view(), name='upload-statuses-list'),
    
    # Dataset Management
    path('datasets/', DatasetListView.as_view(), name='datasets-list'),
    path('datasets/<uuid:dataset_id>/', DatasetDetailView.as_view(), name='dataset-detail'),
    path('datasets/<uuid:dataset_id>/delete/', DatasetDeleteView.as_view(), name='dataset-delete'),
    # Note: To get products for a dataset, use /v1/api/products/?dataset_id={dataset_id}
    
    path('multipart/init/', InitiateMultipartUploadView.as_view(), name='multipart-init'),
    path('multipart/sign-part/', SignMultipartPartView.as_view(), name='multipart-sign'),
    path('multipart/complete/', CompleteMultipartUploadView.as_view(), name='multipart-complete'),
    path('export/dataset/<uuid:dataset_id>/', ExportDatasetView.as_view(), name='export-dataset'),
    path('export/status/<uuid:job_id>/', ExportStatusView.as_view(), name='export-status'),
    path('upload/url/', UploadFromUrlView.as_view(), name='upload_from_url'),
    path('ai/datasets/<uuid:dataset_id>/manifest/', DatasetFullImagesListView.as_view(), name='dataset-full-manifest'),
    # uploads/urls.py
    path('datasets/export/status/<uuid:dataset_id>/', DatasetExportStatusView.as_view(), name='dataset-export-status'),

]
