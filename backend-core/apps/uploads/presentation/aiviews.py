from rest_framework import generics, permissions
from drf_spectacular.utils import extend_schema
from ..infrastructure.models import Image
from .serializers import DatasetImagesManifestSerializer
from rest_framework.pagination import PageNumberPagination
from ..domain.constants import UploadStatusName

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

class DatasetFullImagesListView(generics.ListAPIView):
    """
    Returns a paginated manifest of ALL completed images in a dataset.
    The AI Service uses 's3_key' from this list to download files directly.
    """
    serializer_class = DatasetImagesManifestSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination


    @extend_schema(
        tags=['AI Operations'],
        summary="Get Manifest of All Images in Dataset",
        description=(
            "Returns a list of s3_keys for the AI service to download directly. "
            "Supports pagination to handle large datasets."
        ),
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        dataset_id = self.kwargs.get('dataset_id')
        return Image.objects.filter(
            dataset_id=dataset_id,
            status__name=UploadStatusName.COMPLETED
        ).order_by('created_at')
