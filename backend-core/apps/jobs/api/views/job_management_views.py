"""
Job Management Views for Frontend UI/UX
Provides filtering, detailed stats, and deletion capabilities for processing jobs
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Avg, Max, Min
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from drf_spectacular.types import OpenApiTypes as Types
from datetime import datetime, timedelta

from apps.jobs.processing_stages import JobStatus

from apps.jobs.infra.db.models.models import ProcessingJob
from apps.uploads.infrastructure.models import Dataset
from products.models import Product
from config.logging_config import get_logger

logger = get_logger(__name__)


class JobListView(APIView):
    """
    GET /api/jobs/
    List all processing jobs with advanced filtering
    
    Filters:
    - status: Filter by job status (pending, queued, processing, completed, failed)
    - stage: Filter by processing stage (radiometric_calibration, sfm, orthomosaic, uploading, publishing)
    - dataset_id: Filter by specific dataset UUID
    - progress_min: Minimum progress percentage (0-100)
    - progress_max: Maximum progress percentage (0-100)
    - created_after: Filter jobs created after this UTC datetime (ISO 8601)
    - created_before: Filter jobs created before this UTC datetime (ISO 8601)
    - search: Search in dataset name
    - ordering: Order results (created_at, -created_at, progress, -progress, status)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="List Processing Jobs with Filters",
        description="Retrieve paginated list of processing jobs with advanced filtering options. Supports multiple values for status and stage (comma-separated).",
        parameters=[
            OpenApiParameter(name='status', type=str, description='Filter by status. Accepts multiple comma-separated values (e.g., status=completed,failed). Options: pending, queued, processing, completed, failed'),
            OpenApiParameter(name='stage', type=str, description='Filter by stage. Accepts multiple comma-separated values (e.g., stage=sfm,orthomosaic). Options: radiometric_calibration, sfm, orthomosaic, uploading, publishing'),
            OpenApiParameter(name='dataset_id', type=Types.UUID, description='Filter by dataset UUID'),
            OpenApiParameter(name='progress_min', type=int, description='Minimum progress (0-100)'),
            OpenApiParameter(name='progress_max', type=int, description='Maximum progress (0-100)'),
            OpenApiParameter(name='created_after', type=Types.DATETIME, description='Created after (ISO 8601)'),
            OpenApiParameter(name='created_before', type=Types.DATETIME, description='Created before (ISO 8601)'),
            OpenApiParameter(name='search', type=str, description='Search by dataset name or job ID'),
            OpenApiParameter(name='ordering', type=str, description='Order by field (created_at, -created_at, progress, -progress, status, -status)'),
            OpenApiParameter(name='page', type=int, description='Page number (default: 1)'),
            OpenApiParameter(name='page_size', type=int, description='Page size (default: 20, max: 100)'),
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
                                'dataset_id': {'type': 'string', 'format': 'uuid'},
                                'dataset_name': {'type': 'string'},
                                'status': {'type': 'string'},
                                'stage': {'type': 'string'},
                                'progress': {'type': 'integer'},
                                'resolution_gsd': {'type': 'number'},
                                'radiometric_calibration': {'type': 'boolean'},
                                'error_message': {'type': 'string', 'nullable': True},
                                'created_at': {'type': 'string', 'format': 'date-time'},
                                'updated_at': {'type': 'string', 'format': 'date-time'},
                                'started_at': {'type': 'string', 'format': 'date-time', 'nullable': True},
                                'completed_at': {'type': 'string', 'format': 'date-time', 'nullable': True},
                                'duration_seconds': {'type': 'integer', 'nullable': True},
                            }
                        }
                    },
                    'summary': {
                        'type': 'object',
                        'properties': {
                            'total_jobs': {'type': 'integer'},
                            'by_status': {'type': 'object'},
                            'avg_progress': {'type': 'number'},
                        }
                    }
                }
            }
        },
        tags=['Processing Jobs']
    )
    def get(self, request):
        # Get org_id from user
        org_id = request.user.organization_id if hasattr(request.user, 'organization_id') else None
        if not org_id:
            logger.warning(
                f"Job list request failed: User {request.user.username} (ID: {request.user.id}) "
                f"has no organization assigned. Email: {getattr(request.user, 'email', 'N/A')}"
            )
            return Response(
                {'error': 'User organization not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Start with jobs from user's organization
        queryset = ProcessingJob.objects.filter(
            dataset__org_id=org_id
        ).select_related('dataset')
        
        # Apply filters
        # Status filter - accepts comma-separated values
        status_filter = request.GET.get('status')
        if status_filter:
            status_list = [s.strip() for s in status_filter.split(',')]
            queryset = queryset.filter(status__in=status_list)
        
        # Stage filter - accepts comma-separated values
        stage_filter = request.GET.get('stage')
        if stage_filter:
            stage_list = [s.strip() for s in stage_filter.split(',')]
            queryset = queryset.filter(stage__in=stage_list)
        
        dataset_id = request.GET.get('dataset_id')
        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        
        # Progress range
        progress_min = request.GET.get('progress_min')
        if progress_min is not None:
            try:
                queryset = queryset.filter(progress__gte=int(progress_min))
            except ValueError:
                pass
        
        progress_max = request.GET.get('progress_max')
        if progress_max is not None:
            try:
                queryset = queryset.filter(progress__lte=int(progress_max))
            except ValueError:
                pass
        
        # Date range filters (UTC)
        created_after = request.GET.get('created_after')
        if created_after:
            try:
                dt = datetime.fromisoformat(created_after.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=dt)
            except ValueError:
                pass
        
        created_before = request.GET.get('created_before')
        if created_before:
            try:
                dt = datetime.fromisoformat(created_before.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=dt)
            except ValueError:
                pass
        
        # Search
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(dataset__name__icontains=search) |
                Q(id__icontains=search)
            )
        
        # Summary statistics (before pagination)
        summary = {
            'total_jobs': queryset.count(),
            'by_status': dict(queryset.values_list('status').annotate(count=Count('id'))),
            'avg_progress': queryset.aggregate(avg=Avg('progress'))['avg'] or 0,
        }
        
        # Ordering
        ordering = request.GET.get('ordering', '-created_at')
        allowed_ordering = ['created_at', '-created_at', 'progress', '-progress', 'status', '-status']
        if ordering in allowed_ordering:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')
        
        # Pagination
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 20)), 100)
        
        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = queryset.count()
        jobs = queryset[start:end]
        
        # Serialize results
        results = []
        for job in jobs:
            duration = None
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                duration_start = job.started_at or job.created_at
                duration_end = job.completed_at or job.updated_at
                duration = int((duration_end - duration_start).total_seconds())
            
            results.append({
                'id': str(job.id),
                'dataset_id': str(job.dataset_id),
                'dataset_name': job.dataset.name if job.dataset else 'Unknown',
                'status': job.status,
                'stage': job.stage,
                'progress': job.progress,
                'resolution_gsd': job.resolution_gsd,
                'radiometric_calibration': job.radiometric_calibration,
                'error_message': job.error_message,
                'created_at': job.created_at.isoformat(),
                'updated_at': job.updated_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'duration_seconds': duration,
            })
        
        # Build pagination response
        response_data = {
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'next': None,
            'previous': None,
            'results': results,
            'summary': summary,
        }
        
        # Add pagination links
        if end < total_count:
            response_data['next'] = f"?page={page + 1}&page_size={page_size}"
        if page > 1:
            response_data['previous'] = f"?page={page - 1}&page_size={page_size}"
        
        return Response(response_data, status=status.HTTP_200_OK)


class JobDetailView(APIView):
    """
    GET /api/jobs/{job_id}/
    Get detailed information about a specific job
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get Job Details",
        description="Retrieve comprehensive details about a specific processing job including all products",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'format': 'uuid'},
                    'dataset': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'string', 'format': 'uuid'},
                            'name': {'type': 'string'},
                            'image_count': {'type': 'integer'},
                        }
                    },
                    'status': {'type': 'string'},
                    'stage': {'type': 'string'},
                    'progress': {'type': 'integer'},
                    'resolution_gsd': {'type': 'number'},
                    'radiometric_calibration': {'type': 'boolean'},
                    'analysis_mode': {'type': 'string'},
                    'error_message': {'type': 'string', 'nullable': True},
                    'retry_info': {
                        'type': 'object',
                        'properties': {
                            'retry_count': {'type': 'integer'},
                            'can_retry': {'type': 'boolean'},
                            'original_job_id': {'type': 'string', 'format': 'uuid', 'nullable': True},
                            'last_successful_stage': {'type': 'string', 'nullable': True},
                        }
                    },
                    'products': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'string', 'format': 'uuid'},
                                'type': {'type': 'string'},
                                'type_display': {'type': 'string'},
                                'category': {'type': 'string'},
                                'uri': {'type': 'string'},
                                'resolution_cm': {'type': 'number', 'nullable': True},
                                'bands': {'type': 'array', 'items': {'type': 'string'}, 'nullable': True},
                            }
                        }
                    },
                    'created_at': {'type': 'string', 'format': 'date-time'},
                    'updated_at': {'type': 'string', 'format': 'date-time'},
                    'started_at': {'type': 'string', 'format': 'date-time', 'nullable': True},
                    'completed_at': {'type': 'string', 'format': 'date-time', 'nullable': True},
                    'duration': {
                        'type': 'object',
                        'properties': {
                            'seconds': {'type': 'integer'},
                            'formatted': {'type': 'string'},
                        }
                    },
                }
            },
            404: {'type': 'object', 'properties': {'error': {'type': 'string'}}}
        },
        tags=['Processing Jobs']
    )
    def get(self, request, job_id):
        org_id = request.user.organization_id if hasattr(request.user, 'organization_id') else None
        if not org_id:
            logger.warning(
                f"Job detail request failed: User {request.user.username} (ID: {request.user.id}) "
                f"has no organization assigned. Email: {getattr(request.user, 'email', 'N/A')}"
            )
            return Response(
                {'error': 'User organization not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            job = ProcessingJob.objects.select_related('dataset').get(
                id=job_id,
                dataset__org_id=org_id
            )
        except ProcessingJob.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Calculate duration using started_at/completed_at
        duration_start = job.started_at or job.created_at
        duration_end = job.completed_at if job.status in [JobStatus.COMPLETED, JobStatus.FAILED] else job.updated_at
        duration_end = duration_end or job.updated_at
        duration_seconds = int((duration_end - duration_start).total_seconds())
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        
        # Get image count for dataset
        image_count = job.dataset.images.count() if job.dataset else 0
        
        # Get products for this job
        products = Product.objects.filter(job_id=job.id).order_by('type')
        products_data = [
            {
                'id': str(p.id),
                'type': p.type,
                'type_display': p.get_type_display(),
                'category': p.get_category(),
                'uri': p.uri,
                'resolution_cm': p.resolution_cm,
                'bands': p.bands,
                'created_at': p.created_at.isoformat(),
            }
            for p in products
        ]
        
        data = {
            'id': str(job.id),
            'dataset': {
                'id': str(job.dataset_id),
                'name': job.dataset.name if job.dataset else 'Unknown',
                'image_count': image_count,
            },
            'status': job.status,
            'stage': job.stage,
            'progress': job.progress,
            'resolution_gsd': job.resolution_gsd,
            'radiometric_calibration': job.radiometric_calibration,
            'analysis_mode': job.analysis_mode,
            'error_message': job.error_message,
            'retry_info': {
                'retry_count': job.retry_count,
                'can_retry': job.can_retry,
                'original_job_id': str(job.original_job_id) if job.original_job_id else None,
                'last_successful_stage': job.last_successful_stage,
            },
            'products': products_data,
            'created_at': job.created_at.isoformat(),
            'updated_at': job.updated_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'duration': {
                'seconds': duration_seconds,
                'formatted': f"{hours}h {minutes}m {seconds}s",
            },
        }
        
        return Response(data, status=status.HTTP_200_OK)


class JobDeleteView(APIView):
    """
    DELETE /api/jobs/{job_id}/
    Delete a processing job
    
    Rules:
    - Cannot delete jobs with status 'processing' (must be cancelled first via AI Gateway)
    - Can delete pending, queued, completed, or failed jobs
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Delete Processing Job",
        description="Delete a processing job. Cannot delete jobs currently processing.",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'deleted_job_id': {'type': 'string', 'format': 'uuid'},
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'job_status': {'type': 'string'},
                }
            },
            404: {'type': 'object', 'properties': {'error': {'type': 'string'}}}
        },
        tags=['Processing Jobs']
    )
    def delete(self, request, job_id):
        org_id = request.user.organization_id if hasattr(request.user, 'organization_id') else None
        if not org_id:
            logger.warning(
                f"Job delete request failed: User {request.user.username} (ID: {request.user.id}) "
                f"has no organization assigned. Email: {getattr(request.user, 'email', 'N/A')}"
            )
            return Response(
                {'error': 'User organization not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            job = ProcessingJob.objects.get(
                id=job_id,
                dataset__org_id=org_id
            )
        except ProcessingJob.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if job is currently processing
        if job.status == JobStatus.PROCESSING:
            return Response(
                {
                    'error': 'Cannot delete job while processing. Please cancel the job first via AI Gateway.',
                    'job_status': job.status,
                    'job_stage': job.stage,
                    'progress': job.progress,
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        job_id_str = str(job.id)
        job.delete()
        
        return Response(
            {
                'message': f'Job deleted successfully',
                'deleted_job_id': job_id_str,
            },
            status=status.HTTP_200_OK
        )
