import os
from pathlib import Path
import glob
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv
import warnings


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, '.env'))

#DEFAULT_SECRET = ""

SECRET_KEY = os.environ.get("SECRET_KEY")

# if SECRET_KEY == DEFAULT_SECRET:
#     warnings.warn(
#         "Using default SECRET_KEY! Set a secure key in .env for production.",
#         RuntimeWarning
#     )

if not SECRET_KEY:
    raise ValueError("SECRET_KEY not found in environment variables!")

DEBUG = os.environ.get("DEBUG", "False") == "True"

# ======================
# JWT Configuration
# ======================
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 10080))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', 7))

# ======================
# AWS Configuration
# ======================
# When USE_AWS_ROLE=true, boto3 will automatically use ECS Task Role or IAM Instance Profile
# This is the recommended approach for AWS environments (ECS, EC2, Lambda)
# When false or not set, explicit credentials will be used (for local development)
USE_AWS_ROLE = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'

if USE_AWS_ROLE:
    # Let boto3 use ECS Task Role / IAM Instance Profile automatically
    # Don't set explicit credentials - boto3 will use the attached role
    AWS_ACCESS_KEY_ID = None
    AWS_SECRET_ACCESS_KEY = None
else:
    # Use explicit credentials for local development
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL')
AWS_S3_RAW_IMAGES_BUCKET = os.getenv('AWS_S3_RAW_IMAGES_BUCKET')
AWS_S3_AI_BUCKET = os.getenv('AWS_S3_AI_BUCKET')
AWS_S3_RESULTS_BUCKET = os.getenv('AWS_S3_RESULTS_BUCKET')

# ---------------------------------------------------------------------------
# Dataset file extension configuration (dynamic, configurable via env vars)
# ---------------------------------------------------------------------------
DATASET_IMAGE_EXTENSIONS = [
    ext.strip().lower()
    for ext in os.getenv(
        'DATASET_IMAGE_EXTENSIONS',
        '.jpg,.jpeg,.png,.tiff,.tif,.webp,.bmp,.gif,.dng'
    ).split(',')
]
DATASET_METADATA_EXTENSIONS = [
    ext.strip().lower()
    for ext in os.getenv(
        'DATASET_METADATA_EXTENSIONS',
        '.nav,.obs,.mrk,.bin,.pos,.csv,.txt,.log,.rtcm,.ubx,.rinex,.json,.xml'
    ).split(',')
]
DATASET_ALL_ALLOWED_EXTENSIONS = DATASET_IMAGE_EXTENSIONS + DATASET_METADATA_EXTENSIONS

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")
AUTH_USER_MODEL = "accounts.UserModel"

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = os.environ.get("CORS_ALLOW_ALL_ORIGINS", "True") == "True"
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
).split(",")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-request-id',
]

# Allow all origins from local network (192.168.x.x)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?$",
    r"^http://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$",
    r"^http://172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}(:\d+)?$",
]

# URL Configuration - Disable APPEND_SLASH to avoid POST redirect issues
APPEND_SLASH = False

INSTALLED_APPS = [
    'daphne',
    'channels',
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # PostGis
    'django.contrib.gis',
    'django.contrib.postgres',
    # apps
    "accounts.apps.AccountsConfig",
    #"datasets.apps.DatasetsConfig",
    "products.apps.ProductsConfig",
    'drf_spectacular',
    # third-party
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "adrf",
    "django_filters",
    'apps.fmis.apps.WebhooksConfig',
    'apps.uploads.apps.UploadsConfig',
    'apps.organizations.apps.OrganizationsConfig',
    'apps.jobs.apps.JobsConfig',
    'apps.processings.apps.ProcessingsConfig',
    'django_prometheus',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'chromatrace.django.RequestIdMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database configuration with environment variables
DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DB_ENGINE", "django.contrib.gis.db.backends.postgis"),
        "NAME": os.environ.get("DB_NAME", BASE_DIR / "db.postgresql"),
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", ""),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated"
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,

    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DATETIME_FORMAT': '%m/%d/%Y %H:%M:%S',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'PhotoGear API',
    'DESCRIPTION': '''
# PhotoGear Photogrammetry Platform API

PhotoGear is a comprehensive photogrammetry processing platform that transforms drone imagery into actionable geospatial products.

## Features
- 🔐 **JWT Authentication** - Secure token-based authentication
- 📦 **Dataset Management** - Upload and organize drone imagery
- 🚀 **Processing Jobs** - Generate orthomosaics, DSMs, and 3D models
- 📥 **Product Downloads** - Access processing results via presigned URLs

## Quick Start
1. Register an account via `POST /v1/accounts/register/`
2. Login to get JWT token via `POST /v1/accounts/login/`
3. Upload images via multipart upload or S3 URL import
4. Start a processing job via `POST /v1/api/jobs/start-job/`
5. Download results via `GET /v1/api/products/?job_id={id}`

## Authentication
All endpoints (except register/login) require a Bearer token:
```
Authorization: Bearer <your_access_token>
```
    ''',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [{'Bearer': []}],
    
    # Schema filtering - hide internal endpoints from docs
    'PREPROCESSING_HOOKS': [
        'config.schema_filtering.filter_schema',  # Filter by URL patterns
    ],
    'POSTPROCESSING_HOOKS': [
        'config.schema_filtering.filter_tags_postprocessing',  # Filter by tags
    ],
    
    # Tag ordering (controls sidebar order)
    'TAGS': [
        {'name': 'Authentication', 'description': 'User registration and login'},
        {'name': 'Login', 'description': 'JWT token authentication'},
        {'name': 'Upload Flow (Multipart)', 'description': 'Chunked file upload for large datasets'},
        {'name': 'Uploads-URL', 'description': 'Import files from S3 presigned URLs'},
        {'name': 'Uploads - Status & Management', 'description': 'Monitor and manage uploads'},
        {'name': 'Processing Jobs', 'description': 'Start and monitor photogrammetry processing'},
        {'name': 'Product Visualization', 'description': 'Access and download processing results'},
        {'name': 'Download', 'description': 'Export datasets as ZIP archives'},
        {'name': 'Dashboard', 'description': 'Statistics and overview data'},
        {'name': 'Metrics', 'description': 'Service health, KPI, and Prometheus metrics'},
        {'name': 'Organizations', 'description': 'Multi-tenant organization management'},
    ],
    
    # External documentation links
    'EXTERNAL_DOCS': {
        'description': 'Full API Guide with Examples',
        'url': 'https://github.com/your-org/photogear/blob/main/backend/README_API_GUIDE.md',
    },
    
    # Contact info
    'CONTACT': {
        'name': 'PhotoGear API Support',
        'email': 'api-support@photogear.io',
    },
    
    # License
    'LICENSE': {
        'name': 'Proprietary',
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    "ALGORITHM": JWT_ALGORITHM,
    "SIGNING_KEY": JWT_SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ======================
# Redis Configuration
# ======================
REDIS_URL = os.getenv('REDIS_URL')
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

_DEFAULT_REDIS_URL = REDIS_URL or f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', _DEFAULT_REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', _DEFAULT_REDIS_URL)

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
#CELERY_TASK_ALWAYS_EAGER = True

# ======================
# AI Gateway Configuration
# ======================
AI_GATEWAY_URL = os.getenv('AI_GATEWAY_URL', 'http://api_gateway:8080')
AI_GATEWAY_SECRET_KEY = os.getenv('AI_GATEWAY_SECRET_KEY', SECRET_KEY)


if REDIS_URL:
    _channel_hosts = [REDIS_URL]
else:
    _channel_hosts = [(REDIS_HOST, REDIS_PORT)]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": _channel_hosts,
        },
    },
}

#GDAL Configuration for Windows
if os.name == 'nt':
    VENV_BASE = os.environ['VIRTUAL_ENV']
    os.environ['PATH'] = os.path.join(VENV_BASE, 'Lib', 'site-packages', 'osgeo') + ';' + os.environ['PATH']
    os.environ['PROJ_LIB'] = os.path.join(VENV_BASE, 'Lib', 'site-packages', 'osgeo', 'data', 'proj')
    GDAL_LIBRARY_PATH = os.path.join(VENV_BASE, 'Lib', 'site-packages', 'osgeo', 'gdal.dll')

# ======================
# Logging Configuration
# ======================
# Suppress DRF Spectacular warnings for cleaner logs
import logging
logging.getLogger('drf_spectacular.openapi').setLevel(logging.WARNING)