from django_filters.rest_framework.backends import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema
from apps.jobs.domains.use_cases import StartProcessingUseCase
from apps.jobs.domains.exceptions import BusinessRuleValidationException, ResourceNotFoundException
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.infra.db.repositories import DjangoJobRepository, CeleryQueueService
from apps.jobs.processing_stages import AnalysisMode
from apps.jobs.api.serializer import (
    StartProcessingRequestSerializer,
    JobResponseSerializer,
    ProcessingJobListSerializer
)
from rest_framework.permissions import IsAuthenticated
from utils.permissions import IsAIService, IsAIServiceOrAuthenticated


class StartProcessingView(APIView):
    permission_classes = [IsAIServiceOrAuthenticated]

    @extend_schema(
        summary="Start Processing Job",
        description="Creates a new processing job and triggers the AI pipeline.",
        request=StartProcessingRequestSerializer,
        responses={
            201: JobResponseSerializer,
            400: "Validation Error / Bad Request",
            404: "Dataset Not Found"
        },
        tags=['Processing Jobs']
    )
    def post(self, request):
        serializer = StartProcessingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        analysis_mode = data.get('analysis_mode', 'fast')
        calibration = data.get('radiometric_calibration')
        if calibration is None:
            calibration = analysis_mode == AnalysisMode.FULL

        repo = DjangoJobRepository()
        queue = CeleryQueueService()
        use_case = StartProcessingUseCase(job_repo=repo, queue_service=queue)

        try:
            result_entity = use_case.execute(
                dataset_id=data['dataset_id'],
                resolution=data['resolution_gsd'],
                calibration=calibration,
                analysis_mode=analysis_mode
            )

            response_serializer = JobResponseSerializer(result_entity)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except BusinessRuleValidationException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except ResourceNotFoundException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:

            return Response({"error": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=['Processing Jobs'])
class JobListView(ListAPIView):
    serializer_class = ProcessingJobListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    authentication_classes = []
    permission_classes = [IsAIService]

    search_fields = ['id', 'dataset__name', 'status']

    filterset_fields = ['status', 'stage', 'dataset__org_id']
    ordering_fields = ['created_at', 'progress']
    ordering = ['-created_at']

    def get_queryset(self):
        # Get org_id from query params for filtering
        # This endpoint is used by AI but should still respect org boundaries
        queryset = ProcessingJob.objects.select_related('dataset').all()
        
        # Filter by org_id if provided
        org_id = self.request.query_params.get('org_id')
        if org_id:
            queryset = queryset.filter(dataset__org_id=org_id)
        
        return queryset