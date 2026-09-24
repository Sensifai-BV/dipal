from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse


def api_root_html(request):
    """
    HTML version of API root for browser viewing
    """
    return render(request, 'api_index.html')


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request, format=None):
    """
    PhotoGear Backend API Root
    
    Welcome to the PhotoGear API!
    """
    # If browser request, show HTML
    if request.accepted_renderer.format == 'html':
        return render(request, 'api_index.html')
    
    return Response({
        'message': 'Welcome to PhotoGear Backend API',
        'version': 'v1',
        'documentation': request.build_absolute_uri('/docs/'),
        'endpoints': {
            'authentication': {
                'login': request.build_absolute_uri(reverse('account-login')),
                'register': request.build_absolute_uri(reverse('account-register')),
                'profile': request.build_absolute_uri(reverse('account-profile')),
            },
            'organizations': {
                'create': request.build_absolute_uri(reverse('organization-list')),
                'list': request.build_absolute_uri(reverse('organization-list')),
                'detail': request.build_absolute_uri('/v1/accounts/organizations/detail/{id}/'),
            },
            'datasets': {
                'create': request.build_absolute_uri(reverse('dataset-create')),
                'list': request.build_absolute_uri(reverse('dataset-list')),
                'detail': request.build_absolute_uri('/v1/datasets/detail/{id}/'),
            },
        },
        'admin': request.build_absolute_uri('/admin/'),
    })
