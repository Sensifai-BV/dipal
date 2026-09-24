from rest_framework.permissions import BasePermission
from django.conf import settings


class IsAIServiceAuthenticated(BasePermission):


    def has_permission(self, request, view):

        secret_token = request.META.get('HTTP_X_AI_TOKEN')

        expected_token = getattr(settings, 'AI_GATEWAY_SECRET_KEY', None)

        if not expected_token:
            return False

        return secret_token == expected_token
