from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from accounts.serializers.organization_model import OrganizationModelSerializer
from accounts.services.organization import OrganizationQueryService
from config.logging_config import LoggingConfig, container
from utils.custom_response import CustomResponse
from utils.exceptions import DatabaseError


class OrganizationListAPIView(APIView):
    """
    Organization list
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.paginator = PageNumberPagination()
        self.query_service = OrganizationQueryService()
        logging_config = container[LoggingConfig]
        self.logger = logging_config.get_logger(self.__class__.__name__)

    @extend_schema(
        summary="List Organizations",
        description="Retrieve a paginated list of organizations.",
        tags=['Accounts'],
        responses={
            200: OrganizationModelSerializer(many=True),
            401: "Unauthorized"
        }
    )
    def get(self, request):
        try:
            self.logger.debug(f"Fetching organizations list for user: {request.user.email}")

            queryset = self.query_service.all_filtered_queryset(user=request.user, query_params=request.GET)

            if ordering := request.GET.get("ordering"):
                queryset = self.query_service.apply_ordering(queryset=queryset, ordering_param=ordering)

            paginated_queryset = self.paginator.paginate_queryset(queryset, request)

            serializer = OrganizationModelSerializer(paginated_queryset, many=True)
            data = self.paginator.get_paginated_response(serializer.data).data

            self.logger.info(f"Successfully retrieved organizations list for user: {request.user.email}")

            return CustomResponse.success(data=data, status_code=status.HTTP_200_OK)

        except DatabaseError as e:
            self.logger.error(f"Database error while fetching organizations: {e.message}")
            return CustomResponse.error(error=e.message, status_code=e.status_code)
        except Exception as e:
            self.logger.error(f"Unexpected error while fetching organizations: {str(e)}", exc_info=True)
            return CustomResponse.error(
                error="Failed to retrieve organizations. Please try again.", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
