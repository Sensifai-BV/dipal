from typing import Union, Dict, List

from rest_framework import status
from rest_framework.response import Response


class CustomResponse:
    """
    Custom API response handler with data and error fields
    """

    @staticmethod
    def success(*, data: Union[List, Dict, None] = None, status_code=status.HTTP_200_OK):
        """
        Create a success response with data field
        """
        return Response({
            'data': data,
            'error': None,
            'is_success': True,
        }, status=status_code)

    @staticmethod
    def error(*, error: Union[str, List, Dict], status_code=status.HTTP_400_BAD_REQUEST):
        """
        Create an error response with error field
        """
        return Response({
            'data': None,
            'error': error,
            'is_success': False,
        }, status=status_code)

    @staticmethod
    def custom(*, data: Union[List, Dict, None] = None,
               error: Union[str, List, Dict, None] = None,
               status_code=status.HTTP_200_OK):
        """
        Create a custom response with both data and error fields
        """
        return Response({
            'data': data,
            'error': error,
            'is_success': error is None,
        }, status=status_code)
