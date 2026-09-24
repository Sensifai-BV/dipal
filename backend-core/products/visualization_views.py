"""
Product Visualization Views for Frontend UI/UX
Provides endpoints for accessing and visualizing processing results (orthomosaics, DSMs, meshes, etc.)
"""

from datetime import timedelta, datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from drf_spectacular.types import OpenApiTypes as Types

from products.models import Product
from apps.uploads.infrastructure.models import Dataset
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.uploads.domain.services import S3Service
from config.logging_config import get_logger

logger = get_logger(__name__)


class ProductListView(APIView):
    """
    GET /v1/api/products/
    Unified endpoint for listing all products with comprehensive filtering
    
    **Query Parameters:**
    - dataset_id: Filter by dataset UUID
    - job_id: Filter by job UUID  
    - type: Filter by product type (orthomosaic, dsm, dem, pointcloud, mesh, hillshade, dtm)
    - created_after: Filter products created after this UTC datetime (ISO 8601)
    - created_before: Filter products created before this UTC datetime (ISO 8601)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    
    **Examples:**
    - All products: `/v1/api/products/`
    - Job products: `/v1/api/products/?job_id=fe566e35-189c-49fa-acec-a3568a21176a`
    - Dataset products: `/v1/api/products/?dataset_id=123e4567-e89b-12d3-a456-426614174000`
    - Filtered by type: `/v1/api/products/?type=orthomosaic&job_id={job_id}`
    """
    
    permission_classes = [IsAuthenticated]
    s3_service = S3Service()  # Reuse across requests
    
    @extend_schema(
        summary="List Products with Filters",
        description="""Retrieve paginated list of processing products with comprehensive filtering options.
        
        **This is the unified endpoint for all product queries:**
        - Get all products: `/v1/api/products/`
        - Products for a job: `/v1/api/products/?job_id={job_id}`
        - Products for a dataset: `/v1/api/products/?dataset_id={dataset_id}`
        - Filter by type: `/v1/api/products/?type=orthomosaic`
        - Combine filters: `/v1/api/products/?job_id={job_id}&type=orthomosaic`
        """,
        parameters=[
            OpenApiParameter(name='dataset_id', type=Types.UUID, description='Filter by dataset UUID', required=False),
            OpenApiParameter(name='job_id', type=Types.UUID, description='Filter by job UUID', required=False),
            OpenApiParameter(name='type', type=str, description='Filter by product type (orthomosaic, dsm, dem, pointcloud, mesh, hillshade, dtm)', required=False),
            OpenApiParameter(name='created_after', type=Types.DATETIME, description='Filter products created after this datetime (ISO 8601 format)', required=False),
            OpenApiParameter(name='created_before', type=Types.DATETIME, description='Filter products created before this datetime (ISO 8601 format)', required=False),
            OpenApiParameter(name='page', type=int, description='Page number for pagination (default: 1)', required=False),
            OpenApiParameter(name='page_size', type=int, description='Number of items per page (default: 20, max: 100)', required=False),
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
                                'job_id': {'type': 'string', 'format': 'uuid', 'nullable': True},
                                'type': {'type': 'string'},
                                'type_display': {'type': 'string'},
                                'category': {'type': 'string'},
                                'uri': {'type': 'string'},
                                'download_url': {'type': 'string', 'nullable': True, 'description': 'Presigned URL for downloading the product (null if URI is missing)'},
                                'download_expires_in_seconds': {'type': 'integer', 'description': 'Download URL expiration time in seconds'},
                                'resolution_cm': {'type': 'number', 'nullable': True},
                                'bands': {'type': 'array', 'items': {'type': 'string'}, 'nullable': True},
                                'created_at': {'type': 'string', 'format': 'date-time'},
                            }
                        }
                    },
                    'summary': {
                        'type': 'object',
                        'properties': {
                            'total_products': {'type': 'integer'},
                            'by_type': {'type': 'object'},
                            'by_category': {'type': 'object'},
                        }
                    }
                }
            }
        },
        tags=['Product Visualization']
    )
    def get(self, request):
        # Get organization_id from user
        org_id = getattr(request.user, 'organization_id', None)
        if not org_id:
            return Response(
                {'error': 'User organization not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Start with products from user's organization
        queryset = Product.objects.filter(
            dataset__org_id=org_id
        ).select_related('dataset', 'job')
        
        # Apply filters
        dataset_id = request.GET.get('dataset_id')
        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        
        job_id = request.GET.get('job_id')
        if job_id:
            queryset = queryset.filter(job_id=job_id)
        
        product_type = request.GET.get('type')
        if product_type:
            queryset = queryset.filter(type=product_type)
        
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
        
        # Summary statistics (before pagination)
        summary = {
            'total_products': queryset.count(),
            'by_type': dict(queryset.values_list('type').annotate(count=Count('id'))),
            'by_category': {},
        }
        
        # Calculate by_category
        for product_type_key, _ in Product.PRODUCT_TYPE_CHOICES:
            products = queryset.filter(type=product_type_key)
            if products.exists():
                category = products.first().get_category()
                summary['by_category'][category] = summary['by_category'].get(category, 0) + products.count()
        
        # Ordering (most recent first)
        queryset = queryset.order_by('-created_at')
        
        # Pagination
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 20)), 100)
        
        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = queryset.count()
        products = queryset[start:end]
        
        # Serialize results
        expiration = 3600  # 1 hour
        results = []
        for product in products:
            # Skip products with empty/null URI or generate placeholder
            if not product.uri or not product.uri.strip():
                download_url = None
            else:
                try:
                    download_url = self.s3_service.generate_presigned_download_url(product.uri, expires_in=expiration)
                except Exception as e:
                    logger.error(f"Failed to generate presigned URL for product {product.id}: {str(e)}")
                    download_url = None
            
            results.append({
                'id': str(product.id),
                'dataset_id': str(product.dataset_id),
                'dataset_name': product.dataset.name if product.dataset else 'Unknown',
                'job_id': str(product.job_id) if product.job_id else None,
                'type': product.type,
                'type_display': product.get_type_display(),
                'category': product.get_category(),
                'uri': product.uri,
                'download_url': download_url,
                'download_expires_in_seconds': expiration,
                'resolution_cm': product.resolution_cm,
                'bands': product.bands,
                'created_at': product.created_at.isoformat(),
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


class ProductDetailView(APIView):
    """
    GET /api/products/{product_id}/
    Get detailed information about a specific product including download URL
    """
    
    permission_classes = [IsAuthenticated]
    s3_service = S3Service()  # Reuse across requests
    
    @extend_schema(
        summary="Get Product Details",
        description="Retrieve comprehensive details about a specific product including presigned download URL",
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
                        }
                    },
                    'job': {
                        'type': 'object',
                        'nullable': True,
                        'properties': {
                            'id': {'type': 'string', 'format': 'uuid'},
                            'status': {'type': 'string'},
                            'progress': {'type': 'integer'},
                        }
                    },
                    'type': {'type': 'string'},
                    'type_display': {'type': 'string'},
                    'category': {'type': 'string'},
                    'uri': {'type': 'string'},
                    'resolution_cm': {'type': 'number', 'nullable': True},
                    'bands': {'type': 'array', 'items': {'type': 'string'}, 'nullable': True},
                    'stats': {'type': 'object', 'nullable': True},
                    'footprint': {'type': 'object', 'nullable': True},
                    'download_url': {'type': 'string'},
                    'download_expires_in_seconds': {'type': 'integer'},
                    'created_at': {'type': 'string', 'format': 'date-time'},
                }
            },
            404: {'type': 'object', 'properties': {'error': {'type': 'string'}}}
        },
        tags=['Product Visualization']
    )
    def get(self, request, product_id):
        org_id = getattr(request.user, 'organization_id', None)
        if not org_id:
            return Response(
                {'error': 'User organization not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            product = Product.objects.select_related('dataset', 'job').get(
                id=product_id,
                dataset__org_id=org_id
            )
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate presigned URL for download using S3Service (1 hour expiration)
        if not product.uri or not product.uri.strip():
            download_url = None
        else:
            try:
                download_url = self.s3_service.generate_presigned_download_url(product.uri, expires_in=3600)
            except Exception as e:
                logger.error(f"Failed to generate presigned URL for product {product.id}: {str(e)}")
                download_url = None
        
        # Prepare footprint (GeoJSON)
        footprint = None
        if product.footprint:
            from django.contrib.gis.geos import GEOSGeometry
            footprint = {
                'type': 'Polygon',
                'coordinates': list(product.footprint.coords)
            }
        
        data = {
            'id': str(product.id),
            'dataset': {
                'id': str(product.dataset_id),
                'name': product.dataset.name if product.dataset else 'Unknown',
            },
            'job': None,
            'type': product.type,
            'type_display': product.get_type_display(),
            'category': product.get_category(),
            'uri': product.uri,
            'resolution_cm': product.resolution_cm,
            'bands': product.bands,
            'stats': product.stats,
            'footprint': footprint,
            'download_url': download_url,
            'download_expires_in_seconds': 3600,
            'created_at': product.created_at.isoformat(),
        }
        
        # Add job info if available
        if product.job:
            data['job'] = {
                'id': str(product.job_id),
                'status': product.job.status,
                'progress': product.job.progress,
            }
        
        return Response(data, status=status.HTTP_200_OK)


class ProductsByJobView(APIView):
    """
    GET /api/jobs/{job_id}/products/
    List all products for a specific job
    """
    
    permission_classes = [IsAuthenticated]
    s3_service = S3Service()  # Reuse across requests
    
    @extend_schema(
        summary="Get Products by Job",
        description="Retrieve all products generated by a specific processing job",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'job_id': {'type': 'string', 'format': 'uuid'},
                    'job_status': {'type': 'string'},
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
                                'download_url': {'type': 'string'},
                                'resolution_cm': {'type': 'number', 'nullable': True},
                                'created_at': {'type': 'string', 'format': 'date-time'},
                            }
                        }
                    }
                }
            },
            404: {'type': 'object', 'properties': {'error': {'type': 'string'}}}
        },
        tags=['Product Visualization']
    )
    def get(self, request, job_id):
        logger.info(f"ProductsByJobView: User {request.user.email} requesting products for job {job_id}")
        
        org_id = getattr(request.user, 'organization_id', None)
        logger.info(f"ProductsByJobView: User organization_id = {org_id}")
        
        if not org_id:
            logger.error(f"ProductsByJobView: User {request.user.email} has no org_id")
            return Response(
                {'error': 'User organization not found', 'user_email': request.user.email},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify job exists and belongs to user's org
        try:
            job = ProcessingJob.objects.get(
                id=job_id,
                dataset__org_id=org_id
            )
            logger.info(f"ProductsByJobView: Found job {job_id} with status {job.status}")
        except ProcessingJob.DoesNotExist:
            logger.error(f"ProductsByJobView: Job {job_id} not found for org {org_id}")
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all products for this job
        products = Product.objects.filter(job_id=job_id).order_by('-created_at')
        logger.info(f"ProductsByJobView: Found {products.count()} products for job {job_id}")
        
        # Serialize products with download URLs
        products_data = []
        for product in products:
            if not product.uri or not product.uri.strip():
                download_url = None
            else:
                try:
                    download_url = self.s3_service.generate_presigned_download_url(product.uri, expires_in=3600)
                except Exception as e:
                    logger.error(f"Failed to generate presigned URL for product {product.id}: {str(e)}")
                    download_url = None
            
            products_data.append({
                'id': str(product.id),
                'type': product.type,
                'type_display': product.get_type_display(),
                'category': product.get_category(),
                'uri': product.uri,
                'download_url': download_url,
                'resolution_cm': product.resolution_cm,
                'bands': product.bands,
                'created_at': product.created_at.isoformat(),
            })
        
        logger.info(f"ProductsByJobView: Returning {len(products_data)} products for job {job_id}")
        
        return Response({
            'job_id': str(job_id),
            'job_status': job.status,
            'job_progress': job.progress,
            'products': products_data,
        }, status=status.HTTP_200_OK)


class ProductsByDatasetView(APIView):
    """
    GET /api/datasets/{dataset_id}/products/
    List all products for a specific dataset
    """
    
    permission_classes = [IsAuthenticated]
    s3_service = S3Service()  # Reuse across requests
    
    @extend_schema(
        summary="Get Products by Dataset",
        description="Retrieve all products generated for a specific dataset",
        parameters=[
            OpenApiParameter(name='type', type=str, description='Filter by product type'),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'dataset_id': {'type': 'string', 'format': 'uuid'},
                    'dataset_name': {'type': 'string'},
                    'products': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'string', 'format': 'uuid'},
                                'job_id': {'type': 'string', 'format': 'uuid', 'nullable': True},
                                'type': {'type': 'string'},
                                'type_display': {'type': 'string'},
                                'category': {'type': 'string'},
                                'uri': {'type': 'string'},
                                'download_url': {'type': 'string'},
                                'created_at': {'type': 'string', 'format': 'date-time'},
                            }
                        }
                    },
                    'summary': {
                        'type': 'object',
                        'properties': {
                            'total_products': {'type': 'integer'},
                            'by_type': {'type': 'object'},
                        }
                    }
                }
            },
            404: {'type': 'object', 'properties': {'error': {'type': 'string'}}}
        },
        tags=['Product Visualization']
    )
    def get(self, request, dataset_id):
        org_id = getattr(request.user, 'organization_id', None)
        if not org_id:
            return Response(
                {'error': 'User organization not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify dataset exists and belongs to user's org
        try:
            dataset = Dataset.objects.get(
                id=dataset_id,
                org_id=org_id
            )
        except Dataset.DoesNotExist:
            return Response(
                {'error': 'Dataset not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all products for this dataset
        products = Product.objects.filter(dataset_id=dataset_id).select_related('job')
        
        # Apply type filter if provided
        product_type = request.GET.get('type')
        if product_type:
            products = products.filter(type=product_type)
        
        products = products.order_by('-created_at')
        
        # Summary
        summary = {
            'total_products': products.count(),
            'by_type': dict(products.values_list('type').annotate(count=Count('id'))),
        }
        
        # Serialize products with download URLs
        products_data = []
        for product in products:
            if not product.uri or not product.uri.strip():
                download_url = None
            else:
                try:
                    download_url = self.s3_service.generate_presigned_download_url(product.uri, expires_in=3600)
                except Exception as e:
                    logger.error(f"Failed to generate presigned URL for product {product.id}: {str(e)}")
                    download_url = None
            
            products_data.append({
                'id': str(product.id),
                'job_id': str(product.job_id) if product.job_id else None,
                'type': product.type,
                'type_display': product.get_type_display(),
                'category': product.get_category(),
                'uri': product.uri,
                'download_url': download_url,
                'resolution_cm': product.resolution_cm,
                'created_at': product.created_at.isoformat(),
            })
        
        return Response({
            'dataset_id': str(dataset_id),
            'dataset_name': dataset.name,
            'products': products_data,
            'summary': summary,
        }, status=status.HTTP_200_OK)
