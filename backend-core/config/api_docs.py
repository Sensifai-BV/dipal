from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def api_documentation(request):
    """
    PhotoGear Backend API Documentation
    """
    return Response({
        'title': 'PhotoGear Backend API',
        'version': '1.0.0',
        'description': 'REST API for PhotoGear photogrammetry platform',
        
        'base_url': request.build_absolute_uri('/v1/'),
        
        'authentication': {
            'type': 'JWT (JSON Web Token)',
            'header': 'Authorization: Bearer <token>',
            'endpoints': {
                'POST /v1/accounts/login/': {
                    'description': 'Login with email and password',
                    'auth_required': False,
                    'body': {
                        'email': 'user@example.com',
                        'password': 'password123'
                    },
                    'response': {
                        'access': 'jwt_access_token',
                        'refresh': 'jwt_refresh_token',
                        'access_expires_in': 432000,
                        'refresh_expires_in': 86400
                    }
                },
                'POST /v1/accounts/register/': {
                    'description': 'Register new user account',
                    'auth_required': False,
                    'body': {
                        'email': 'user@example.com',
                        'password': 'password123',
                        'confirm_password': 'password123',
                        'first_name': 'John (optional)',
                        'last_name': 'Doe (optional)'
                    }
                },
                'GET /v1/accounts/profile/': {
                    'description': 'Get current user profile',
                    'auth_required': True
                }
            }
        },
        
        'organizations': {
            'endpoints': {
                'POST /v1/accounts/organizations/create/': {
                    'description': 'Create new organization',
                    'auth_required': True,
                    'body': {
                        'name': 'Organization Name',
                        'description': 'Optional description'
                    }
                },
                'GET /v1/accounts/organizations/list/': {
                    'description': 'List all organizations for current user',
                    'auth_required': True,
                    'query_params': {
                        'page': 'Page number for pagination',
                        'ordering': 'Field to order by (e.g., -created_at)'
                    }
                },
                'GET /v1/accounts/organizations/detail/{id}/': {
                    'description': 'Get organization details by ID',
                    'auth_required': True
                }
            }
        },
        
        'datasets': {
            'endpoints': {
                'POST /v1/datasets/create/': {
                    'description': 'Create new dataset',
                    'auth_required': True,
                    'body': {
                        'name': 'Dataset Name',
                        'organization': 1,
                        'platform': 'DJI Mavic 3M',
                        'capture_start': '2025-10-01T10:00:00Z',
                        'capture_end': '2025-10-01T12:00:00Z',
                        'crs': 'EPSG:32639',
                        'bbox': {'type': 'Polygon', 'coordinates': []},
                        'notes': 'Optional notes'
                    }
                },
                'GET /v1/datasets/list/': {
                    'description': 'List all datasets for current user',
                    'auth_required': True,
                    'query_params': {
                        'page': 'Page number for pagination',
                        'ordering': 'Field to order by (e.g., -created_at)',
                        'platform': 'Filter by platform',
                        'name': 'Filter by name'
                    }
                },
                'GET /v1/datasets/detail/{id}/': {
                    'description': 'Get dataset details by ID',
                    'auth_required': True
                }
            }
        },
        
        'usage_examples': {
            'login': {
                'curl': '''curl -X POST http://localhost:8000/v1/accounts/login/ \\
  -H "Content-Type: application/json" \\
  -d '{"email": "user@example.com", "password": "password123"}'
''',
                'python': '''import requests
response = requests.post('http://localhost:8000/v1/accounts/login/', 
    json={'email': 'user@example.com', 'password': 'password123'})
token = response.json()['access']
'''
            },
            'authenticated_request': {
                'curl': '''curl -X GET http://localhost:8000/v1/accounts/profile/ \\
  -H "Authorization: Bearer <your_access_token>"
''',
                'python': '''import requests
headers = {'Authorization': 'Bearer <your_access_token>'}
response = requests.get('http://localhost:8000/v1/accounts/profile/', headers=headers)
'''
            }
        },
        
        'response_format': {
            'success': {
                'data': 'Response data here',
                'error': None,
                'is_success': True
            },
            'error': {
                'data': None,
                'error': 'Error message here',
                'is_success': False
            }
        },
        
        'links': {
            'admin_panel': request.build_absolute_uri('/admin/'),
            'detailed_docs': 'See docs/backend-api-spec.md in the repository'
        }
    })
