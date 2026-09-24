"""Dashboard statistics and recent activities views"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta

from apps.uploads.infrastructure.models import Dataset, Image
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import JobStatus
from products.models import Product


class DashboardStatsView(APIView):
    """Get dashboard statistics for current month"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Dashboard Statistics",
        description="""
        Returns statistics for the current month:
        - Total datasets uploaded
        - Total products created
        - Total completed jobs
        """,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'total_datasets': {'type': 'integer', 'description': 'Datasets uploaded this month'},
                    'total_products': {'type': 'integer', 'description': 'Products created this month'},
                    'total_completed_jobs': {'type': 'integer', 'description': 'Jobs completed this month'},
                }
            }
        },
        tags=['Dashboard']
    )
    def get(self, request):
        # Get current month's date range
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

        # Get user's organization
        org_id = getattr(request.user, 'organization_id', None)

        # Count datasets uploaded this month
        datasets_query = Dataset.objects.filter(
            created_at__gte=start_of_month,
            created_at__lte=end_of_month
        )
        if org_id:
            datasets_query = datasets_query.filter(org_id=org_id)
        
        total_datasets = datasets_query.count()

        # Count products created this month
        products_query = Product.objects.filter(
            created_at__gte=start_of_month,
            created_at__lte=end_of_month
        )
        if org_id:
            products_query = products_query.filter(dataset__org_id=org_id)
        
        total_products = products_query.count()

        # Count completed jobs this month
        jobs_query = ProcessingJob.objects.filter(
            status=JobStatus.COMPLETED,
            updated_at__gte=start_of_month,
            updated_at__lte=end_of_month
        )
        if org_id:
            jobs_query = jobs_query.filter(dataset__org_id=org_id)
        
        total_completed_jobs = jobs_query.count()

        return Response({
            'total_datasets': total_datasets,
            'total_products': total_products,
            'total_completed_jobs': total_completed_jobs,
        }, status=status.HTTP_200_OK)


class RecentActivitiesView(APIView):
    """Get recent activities (dataset uploads, job starts)"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Recent Activities",
        description="""
        Returns recent activities:
        - Dataset uploads
        - Processing job starts
        
        Activities are sorted by date (newest first).
        """,
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Number of activities to return (default: 20)",
                required=False
            ),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'activities': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'type': {'type': 'string', 'enum': ['dataset_upload', 'job_started']},
                                'description': {'type': 'string', 'description': 'Human-readable activity description'},
                                'date': {'type': 'string', 'format': 'date-time'},
                                'dataset_id': {'type': 'string', 'format': 'uuid', 'nullable': True},
                                'dataset_name': {'type': 'string', 'nullable': True},
                                'job_id': {'type': 'string', 'format': 'uuid', 'nullable': True},
                            }
                        }
                    }
                }
            }
        },
        tags=['Dashboard']
    )
    def get(self, request):
        limit = int(request.query_params.get('limit', 20))
        
        # Get user's organization
        org_id = getattr(request.user, 'organization_id', None)

        activities = []

        # Get recent dataset uploads
        datasets_query = Dataset.objects.all()
        if org_id:
            datasets_query = datasets_query.filter(org_id=org_id)
        datasets_query = datasets_query.order_by('-created_at')[:limit]
        
        for dataset in datasets_query:
            activities.append({
                'type': 'dataset_upload',
                'description': f'{dataset.name} uploaded',
                'date': dataset.created_at.isoformat(),
                'dataset_id': str(dataset.id),
                'dataset_name': dataset.name,
                'job_id': None,
            })

        # Get recent job starts
        jobs_query = ProcessingJob.objects.all()
        if org_id:
            jobs_query = jobs_query.filter(dataset__org_id=org_id)
        jobs_query = jobs_query.order_by('-created_at')[:limit]
        
        for job in jobs_query:
            activities.append({
                'type': 'job_started',
                'description': f'Processing job started for {job.dataset.name if job.dataset else "Unknown"}',
                'date': job.created_at.isoformat(),
                'dataset_id': str(job.dataset_id) if job.dataset_id else None,
                'dataset_name': job.dataset.name if job.dataset else None,
                'job_id': str(job.id),
            })

        # Sort all activities by date (newest first)
        activities.sort(key=lambda x: x['date'], reverse=True)
        
        # Limit to requested number
        activities = activities[:limit]

        return Response({
            'activities': activities
        }, status=status.HTTP_200_OK)
