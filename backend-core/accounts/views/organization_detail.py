from rest_framework import status
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from accounts.serializers.organization_model import OrganizationModelSerializer
from accounts.services.organization import OrganizationQueryService
from config.logging_config import LoggingConfig, container
from utils.custom_response import CustomResponse
from utils.exceptions import DatabaseError, NotFoundError


class OrganizationDetailAPIView(APIView):
    """
    Organization detail
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.query_service = OrganizationQueryService()
        logging_config = container[LoggingConfig]
        self.logger = logging_config.get_logger(self.__class__.__name__)

    @extend_schema(
        summary="Get Organization Details",
        description="Retrieve detailed information about a specific organization.",
        tags=['Accounts'],
        parameters=[
            OpenApiParameter(
                name='object_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Organization ID'
            )
        ],
        responses={
            200: OrganizationModelSerializer,
            404: "Organization not found"
        }
    )
    def get(self, request, object_id: int):
        try:
            self.logger.debug(f"Fetching organizations {object_id} for user: {request.user.email}")

            queryset = self.query_service.get_filtered_queryset(
                user=request.user, object_id=object_id, query_params=request.GET
            )

            if queryset:
                data = OrganizationModelSerializer(queryset).data

                self.logger.info(f"Organization {object_id} retrieved successfully")

                return CustomResponse.success(data=data, status_code=status.HTTP_200_OK)

            self.logger.warning(f"Organization {object_id} not found for user: {request.user.email}")
            raise NotFoundError(f"Organization with ID {object_id} not found")

        except NotFoundError as e:
            return CustomResponse.error(error=e.message, status_code=e.status_code)
        except DatabaseError as e:
            self.logger.error(f"Database error while fetching organizations: {e.message}")
            return CustomResponse.error(error=e.message, status_code=e.status_code)
        except Exception as e:
            self.logger.error(f"Unexpected error while fetching organizations: {str(e)}", exc_info=True)
            return CustomResponse.error(
                error="Failed to retrieve organizations. Please try again.", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
