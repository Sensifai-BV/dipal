from rest_framework.generics import GenericAPIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema

from accounts.serializers.register import AccountRegisterSerializer
from accounts.serializers.user import AccountUserModelSerializer
from config.logging_config import LoggingConfig, container
from utils.custom_response import CustomResponse


class AccountRegisterAPIView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = AccountRegisterSerializer

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging_config = container[LoggingConfig]
        self.logger = logging_config.get_logger(self.__class__.__name__)

    @extend_schema(
        summary="User Registration",
        request=AccountRegisterSerializer,
        responses={201: AccountRegisterSerializer},
        tags=['Authentication']
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            try:
                user = serializer.save()
                output_data = AccountUserModelSerializer(user).data

                self.logger.info(f"User registered: {user.email}")
                return CustomResponse.success(data=output_data, status_code=status.HTTP_201_CREATED)

            except Exception as e:
                self.logger.error(f"Registration Error: {str(e)}")
                return CustomResponse.error(error=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        return CustomResponse.error(error=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
