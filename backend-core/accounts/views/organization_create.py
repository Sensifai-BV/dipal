from adrf.views import APIView
from django.db import IntegrityError
from rest_framework import status
from drf_spectacular.utils import extend_schema

from accounts.serializers.organization_create import OrganizationCreateInputSerializer
from accounts.serializers.organization_model import OrganizationModelSerializer
from config.logging_config import LoggingConfig, container
from utils.custom_response import CustomResponse
from utils.exceptions import ConflictError, DatabaseError, ValidationError


class OrganizationCreateAPIView(APIView):
    """
    Register new organizations
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging_config = container[LoggingConfig]
        self.logger = logging_config.get_logger(self.__class__.__name__)

    @extend_schema(
        summary="Create Organization",
        description="Create a new organization.",
        tags=['Accounts'],
        request=OrganizationCreateInputSerializer,
        responses={
            201: OrganizationModelSerializer,
            400: "Bad Request",
            409: "Organization already exists"
        }
    )
    async def post(self, request):
        try:
            serializer = OrganizationCreateInputSerializer(
                data=request.data,
                context={"user": request.user},
            )
            serializer.is_valid(raise_exception=True)

            org_name = serializer.validated_data.get("name")
            self.logger.info(f"Creating organizations: {org_name} for user: {request.user.email}")

            organization_obj = await serializer.save()
            data = OrganizationModelSerializer(organization_obj).data

            self.logger.info(f"Organization created successfully: {org_name} (ID: {organization_obj.id})")

            return CustomResponse.success(data=data, status_code=status.HTTP_201_CREATED)

        except IntegrityError as e:
            self.logger.warning(f"Organization creation failed - integrity error: {str(e)}")
            raise ConflictError("Organization with this name may already exist")
        except ValidationError as e:
            self.logger.warning(f"Validation error during organizations creation: {e.message}")
            return CustomResponse.error(error=e.message, status_code=e.status_code)
        except ConflictError as e:
            self.logger.warning(f"Conflict error during organizations creation: {e.message}")
            return CustomResponse.error(error=e.message, status_code=e.status_code)
        except DatabaseError as e:
            self.logger.error(f"Database error during organizations creation: {e.message}")
            return CustomResponse.error(error=e.message, status_code=e.status_code)
        except Exception as e:
            self.logger.error(f"Unexpected error during organizations creation: {str(e)}", exc_info=True)
            return CustomResponse.error(
                error="Organization creation failed. Please try again.", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
