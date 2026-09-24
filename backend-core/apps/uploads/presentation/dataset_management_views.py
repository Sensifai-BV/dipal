"""Dataset Management Views - CRUD operations and filtering"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.db.models import Count, Q, Sum
from datetime import datetime
from ..infrastructure.models import Dataset, Image
from apps.uploads.domain.constants import UploadStatusName
from apps.jobs.processing_stages import JobStatus


class DatasetDetailView(APIView):
    """Get detailed information about a specific dataset"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Dataset Details",
        description="Get comprehensive information about a dataset including image count, file types, total size",
        parameters=[
            OpenApiParameter(
                name='dataset_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Dataset UUID'
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'format': 'uuid'},
                    'name': {'type': 'string'},
                    'platform': {'type': 'string'},
                    'crs': {'type': 'string'},
                    'capture_start': {'type': 'string', 'format': 'date-time'},
                    'capture_end': {'type': 'string', 'format': 'date-time'},
                    'created_at': {'type': 'string', 'format': 'date-time'},
                    'updated_at': {'type': 'string', 'format': 'date-time'},
                    'notes': {'type': 'string'},
                    'statistics': {
                        'type': 'object',
                        'properties': {
                            'total_images': {'type': 'integer'},
                            'total_size_bytes': {'type': 'integer'},
                            'total_size_mb': {'type': 'number'},
                            'file_types': {
                                'type': 'object',
                                'additionalProperties': {'type': 'integer'}
                            },
                            'content_types': {
                                'type': 'object',
                                'additionalProperties': {'type': 'integer'}
                            }
                        }
                    }
                }
            }
        },
        tags=['Datasets']
    )
    def get(self, request, dataset_id):
        try:
            org_id = getattr(request.user, 'organization_id', None)
            
            # Get dataset with org filter
            query = Dataset.objects.filter(id=dataset_id)
            if org_id:
                query = query.filter(org_id=org_id)
            
            dataset = query.first()
            if not dataset:
                return Response(
                    {'error': 'Dataset not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get image statistics
            images_stats = Image.objects.filter(dataset=dataset).aggregate(
                total_images=Count('id'),
                total_size=Sum('file_size')
            )

            # Get file type breakdown
            file_types = {}
            images_by_type = Image.objects.filter(dataset=dataset).values('file_type').annotate(count=Count('id'))
            for item in images_by_type:
                file_types[item['file_type'] or 'UNKNOWN'] = item['count']

            # Get content type breakdown
            content_types = {}
            images_by_content = Image.objects.filter(dataset=dataset).values('content_type').annotate(count=Count('id'))
            for item in images_by_content:
                content_types[item['content_type'] or 'unknown'] = item['count']

            total_size_bytes = images_stats['total_size'] or 0
            
            return Response({
                'id': str(dataset.id),
                'name': dataset.name,
                'platform': dataset.platform or '',
                'crs': dataset.crs or 'EPSG:4326',
                'capture_start': dataset.capture_start.isoformat() if dataset.capture_start else None,
                'capture_end': dataset.capture_end.isoformat() if dataset.capture_end else None,
                'created_at': dataset.created_at.isoformat(),
                'updated_at': dataset.updated_at.isoformat(),
                'notes': dataset.notes or '',
                'statistics': {
                    'total_images': images_stats['total_images'] or 0,
                    'total_size_bytes': total_size_bytes,
                    'total_size_mb': round(total_size_bytes / (1024 * 1024), 2),
                    'file_types': file_types,
                    'content_types': content_types
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DatasetListView(APIView):
    """List datasets with filtering"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List Datasets with Filters",
        description="Get paginated list of datasets with filtering by date, name, platform, and processing status. Supports multiple values for platform and status (comma-separated).",
        parameters=[
            OpenApiParameter(name='page', type=OpenApiTypes.INT, description='Page number (default: 1)'),
            OpenApiParameter(name='page_size', type=OpenApiTypes.INT, description='Items per page (default: 20)'),
            OpenApiParameter(name='search', type=OpenApiTypes.STR, description='Search by dataset name (case-insensitive partial match)'),
            OpenApiParameter(name='platform', type=OpenApiTypes.STR, description='Filter by platform. Accepts multiple comma-separated values (e.g., platform=UAV,Satellite). Common platforms: UAV, Satellite, Aerial, Ground'),
            OpenApiParameter(name='status', type=OpenApiTypes.STR, description='Filter by processing status. Accepts multiple comma-separated values (e.g., status=PROCESSING,COMPLETED). Options: PENDING, PROCESSING, COMPLETED, FAILED, HAS_ERROR'),
            OpenApiParameter(name='created_after', type=OpenApiTypes.DATETIME, description='Filter datasets created after this date (UTC)'),
            OpenApiParameter(name='created_before', type=OpenApiTypes.DATETIME, description='Filter datasets created before this date (UTC)'),
            OpenApiParameter(name='capture_start_after', type=OpenApiTypes.DATETIME, description='Filter by capture start date after (UTC)'),
            OpenApiParameter(name='capture_start_before', type=OpenApiTypes.DATETIME, description='Filter by capture start date before (UTC)'),
            OpenApiParameter(name='order_by', type=OpenApiTypes.STR, description='Order by field: created_at, updated_at, name (prefix with - for descending)', default='-created_at'),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'count': {'type': 'integer'},
                    'next': {'type': 'string', 'nullable': True},
                    'previous': {'type': 'string', 'nullable': True},
                    'results': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'string', 'format': 'uuid'},
                                'name': {'type': 'string'},
                                'platform': {'type': 'string'},
                                'created_at': {'type': 'string', 'format': 'date-time'},
                                'updated_at': {'type': 'string', 'format': 'date-time'},
                                'image_count': {'type': 'integer'},
                                'total_size_mb': {'type': 'number'}
                            }
                        }
                    }
                }
            }
        },
        tags=['Datasets']
    )
    def get(self, request):
        try:
            org_id = getattr(request.user, 'organization_id', None)
            if not org_id:
                return Response(
                    {'error': 'User organization not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            query = Dataset.objects.filter(org_id=org_id)

            # Apply filters
            search = request.query_params.get('search')
            if search:
                query = query.filter(Q(name__icontains=search) | Q(notes__icontains=search))

            # Filter by platform - accepts comma-separated values
            platform = request.query_params.get('platform')
            if platform:
                platform_list = [p.strip() for p in platform.split(',')]
                # Use Q objects to match any of the platforms (case-insensitive)
                platform_query = Q()
                for p in platform_list:
                    platform_query |= Q(platform__icontains=p)
                query = query.filter(platform_query)
            
            # Note: Status filtering is done after queryset evaluation
            # because dataset status is derived from image statuses
            status_filter = request.query_params.get('status')
            status_list = []
            if status_filter:
                status_list = [s.strip().upper() for s in status_filter.split(',')]

            # Date filters (expecting UTC ISO format)
            created_after = request.query_params.get('created_after')
            if created_after:
                query = query.filter(created_at__gte=datetime.fromisoformat(created_after.replace('Z', '+00:00')))

            created_before = request.query_params.get('created_before')
            if created_before:
                query = query.filter(created_at__lte=datetime.fromisoformat(created_before.replace('Z', '+00:00')))

            capture_start_after = request.query_params.get('capture_start_after')
            if capture_start_after:
                query = query.filter(capture_start__gte=datetime.fromisoformat(capture_start_after.replace('Z', '+00:00')))

            capture_start_before = request.query_params.get('capture_start_before')
            if capture_start_before:
                query = query.filter(capture_start__lte=datetime.fromisoformat(capture_start_before.replace('Z', '+00:00')))

            # Ordering
            order_by = request.query_params.get('order_by', '-created_at')
            allowed_order_fields = ['created_at', '-created_at', 'updated_at', '-updated_at', 'name', '-name']
            if order_by in allowed_order_fields:
                query = query.order_by(order_by)

            # Annotate with statistics and status counts
            query = query.annotate(
                image_count=Count('images'),
                total_size=Sum('images__file_size'),
                # Count images by status for determining dataset status
                pending_count=Count('images', filter=Q(images__status__name=UploadStatusName.PENDING)),
                processing_count=Count('images', filter=Q(images__status__name=UploadStatusName.PROCESSING)),
                completed_count=Count('images', filter=Q(images__status__name=UploadStatusName.COMPLETED)),
                failed_count=Count('images', filter=Q(images__status__name=UploadStatusName.FAILED))
            )

            # Pagination
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            
            # If status filtering, we need to fetch more and filter in Python
            # This is not ideal for large datasets but works for moderate sizes
            if status_list:
                # Fetch all matching datasets (or a reasonable limit)
                all_datasets = list(query)
                filtered_datasets = []
                
                for dataset in all_datasets:
                    # Determine dataset status
                    if dataset.failed_count > 0:
                        dataset_status = 'HAS_ERROR'
                    elif dataset.processing_count > 0:
                        dataset_status = UploadStatusName.PROCESSING
                    elif dataset.image_count == dataset.completed_count and dataset.completed_count > 0:
                        dataset_status = UploadStatusName.COMPLETED
                    else:
                        dataset_status = UploadStatusName.PENDING
                    
                    if dataset_status in status_list:
                        filtered_datasets.append((dataset, dataset_status))
                
                total_count = len(filtered_datasets)
                start = (page - 1) * page_size
                end = start + page_size
                datasets_page = filtered_datasets[start:end]
            else:
                total_count = query.count()
                start = (page - 1) * page_size
                end = start + page_size
                datasets = query[start:end]
                datasets_page = [(d, None) for d in datasets]

            results = []
            for item in datasets_page:
                if status_list:
                    dataset, dataset_status = item
                else:
                    dataset = item[0]
                    # Calculate status
                    if dataset.failed_count > 0:
                        dataset_status = 'HAS_ERROR'
                    elif dataset.processing_count > 0:
                        dataset_status = UploadStatusName.PROCESSING
                    elif dataset.image_count == dataset.completed_count and dataset.completed_count > 0:
                        dataset_status = UploadStatusName.COMPLETED
                    else:
                        dataset_status = UploadStatusName.PENDING
                
                results.append({
                    'id': str(dataset.id),
                    'name': dataset.name,
                    'platform': dataset.platform or '',
                    'status': dataset_status,
                    'created_at': dataset.created_at.isoformat(),
                    'updated_at': dataset.updated_at.isoformat(),
                    'capture_start': dataset.capture_start.isoformat() if dataset.capture_start else None,
                    'capture_end': dataset.capture_end.isoformat() if dataset.capture_end else None,
                    'image_count': dataset.image_count,
                    'total_size_mb': round((dataset.total_size or 0) / (1024 * 1024), 2),
                    'status_breakdown': {
                        'pending': dataset.pending_count,
                        'processing': dataset.processing_count,
                        'completed': dataset.completed_count,
                        'failed': dataset.failed_count
                    }
                })

            has_next = (page * page_size) < total_count
            has_previous = page > 1

            return Response({
                'count': total_count,
                'page': page,
                'page_size': page_size,
                'next': f'?page={page + 1}&page_size={page_size}' if has_next else None,
                'previous': f'?page={page - 1}&page_size={page_size}' if has_previous else None,
                'results': results
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {'error': f'Invalid date format: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DatasetDeleteView(APIView):
    """Delete a dataset and all its related data"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Delete Dataset",
        description="Delete a dataset and all its associated images. This action cannot be undone.",
        parameters=[
            OpenApiParameter(
                name='dataset_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='Dataset UUID to delete'
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'deleted_dataset_id': {'type': 'string', 'format': 'uuid'},
                    'deleted_images_count': {'type': 'integer'}
                }
            },
            404: {'description': 'Dataset not found'},
            403: {'description': 'Cannot delete dataset with active jobs'}
        },
        tags=['Datasets']
    )
    def delete(self, request, dataset_id):
        try:
            org_id = getattr(request.user, 'organization_id', None)
            
            # Get dataset with org filter
            query = Dataset.objects.filter(id=dataset_id)
            if org_id:
                query = query.filter(org_id=org_id)
            
            dataset = query.first()
            if not dataset:
                return Response(
                    {'error': 'Dataset not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check if there are any active jobs for this dataset
            from apps.jobs.infra.db.models.models import ProcessingJob
            active_jobs = ProcessingJob.objects.filter(
                dataset_id=dataset_id,
                status__in=[JobStatus.PENDING, JobStatus.PROCESSING]
            ).count()

            if active_jobs > 0:
                return Response(
                    {
                        'error': 'Cannot delete dataset with active processing jobs',
                        'active_jobs_count': active_jobs
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Count images before deletion
            images_count = Image.objects.filter(dataset=dataset).count()

            # Delete dataset (cascade will delete images)
            dataset_name = dataset.name
            dataset.delete()

            return Response({
                'message': f'Dataset "{dataset_name}" deleted successfully',
                'deleted_dataset_id': str(dataset_id),
                'deleted_images_count': images_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
