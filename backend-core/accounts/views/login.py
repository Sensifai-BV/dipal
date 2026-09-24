from adrf.generics import GenericAPIView
from asgiref.sync import sync_to_async
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from drf_spectacular.utils import extend_schema

from accounts.serializers.login import AccountLoginSerializer
from config.logging_config import LoggingConfig, container
from utils.custom_response import CustomResponse
from utils.exceptions import AuthenticationError
from apps.jobs.api.views.metrics import record_auth_failure


class AccountLoginUserAPIView(GenericAPIView):
    """
    Login user and return JWT tokens with expiration times
    """

    permission_classes = (AllowAny,)
    serializer_class = AccountLoginSerializer

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging_config = container[LoggingConfig]
        self.logger = logging_config.get_logger(self.__class__.__name__)

    @extend_schema(
        summary="User Login",
        description="Authenticate user and return JWT tokens (access and refresh).",
        tags=['Login'],
        request=AccountLoginSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'access': {'type': 'string', 'description': 'JWT access token'},
                    'refresh': {'type': 'string', 'description': 'JWT refresh token'},
                    'access_expires_in': {'type': 'integer', 'description': 'Access token lifetime in seconds'},
                    'refresh_expires_in': {'type': 'integer', 'description': 'Refresh token lifetime in seconds'},
                },
                'example': {
                    'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                    'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                    'access_expires_in': 432000,
                    'refresh_expires_in': 86400,
                }
            },
            401: {'description': 'Invalid credentials'}
        },
    )
    async def post(self, request, *args, **kwargs):
        try:
            serializer = AccountLoginSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            email = serializer.validated_data["email"]
            password = serializer.validated_data["password"]

            self.logger.info(f"Login attempt for user: {email}")

            user_obj = await sync_to_async(authenticate)(email=email, password=password)

            if user_obj is not None:
                refresh = RefreshToken.for_user(user_obj)
                access = AccessToken.for_user(user_obj)

                self.logger.info(f"User logged in successfully: {email}")

                return CustomResponse.success(
                    data={
                        "refresh": str(refresh),
                        "access": str(access),
                        "refresh_expires_in": refresh.access_token.payload["exp"] - refresh.payload["iat"],
                        "access_expires_in": access.payload["exp"] - access.payload["iat"],
                    },
                    status_code=status.HTTP_200_OK,
                )

            self.logger.warning(f"Failed login attempt for user: {email}")
            record_auth_failure()
            raise AuthenticationError("Invalid credentials")

        except AuthenticationError as e:
            self.logger.warning(f"Authentication error: {e.message}")
            return CustomResponse.error(error=e.message, status_code=e.status_code)
        except Exception as e:
            self.logger.error(f"Unexpected error during login: {str(e)}", exc_info=True)
            return CustomResponse.error(error="Login failed. Please try again.", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
