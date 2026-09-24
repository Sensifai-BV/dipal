from adrf.views import APIView
from rest_framework import status
from drf_spectacular.utils import extend_schema

from accounts.serializers.user import AccountUserModelSerializer
from config.logging_config import LoggingConfig, container
from utils.custom_response import CustomResponse


class AccountProfileAPIView(APIView):
    """
    Account user profile
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging_config = container[LoggingConfig]
        self.logger = logging_config.get_logger(self.__class__.__name__)

    @extend_schema(
        summary="Get User Profile",
        description="Retrieve the authenticated user's profile information.",
        tags=['Accounts'],
        responses={
            200: AccountUserModelSerializer,
            401: "Unauthorized"
        }
    )
    async def get(self, request):
        try:
            self.logger.debug(f"Fetching profile for user: {request.user.email}")

            data = await AccountUserModelSerializer(request.user).adata

            self.logger.info(f"Profile retrieved successfully for user: {request.user.email}")

            return CustomResponse.success(data=data, status_code=status.HTTP_200_OK)

        except Exception as e:
            self.logger.error(f"Unexpected error while fetching profile: {str(e)}", exc_info=True)
            return CustomResponse.error(
                error="Failed to retrieve profile. Please try again.", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
