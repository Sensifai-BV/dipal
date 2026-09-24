"""URLs for Products API"""
from django.urls import path
from products.views import (
    ProductUploadInitView,
    ProductChunkUploadView,
    ProductUploadCompleteView,
    ProductUploadAbortView,
)
from products.visualization_views import (
    ProductListView,
    ProductDetailView,
)

urlpatterns = [
    # Product upload endpoints for AI Gateway
    path('upload/init/', ProductUploadInitView.as_view(), name='product-upload-init'),
    path('upload/chunk/', ProductChunkUploadView.as_view(), name='product-upload-chunk'),
    path('upload/complete/', ProductUploadCompleteView.as_view(), name='product-upload-complete'),
    path('upload/abort/', ProductUploadAbortView.as_view(), name='product-upload-abort'),
    
    # Product visualization endpoints for Frontend (unified API)
    # Use query parameters for filtering: ?job_id=... or ?dataset_id=...
    path('', ProductListView.as_view(), name='product-list'),
    path('<uuid:product_id>/', ProductDetailView.as_view(), name='product-detail'),
]
