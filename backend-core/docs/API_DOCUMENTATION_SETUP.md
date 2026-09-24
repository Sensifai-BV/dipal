# API Documentation Setup Guide

This guide explains the automated API documentation system for PhotoGear.

---

## 📍 Documentation URLs

After running the server, these documentation URLs are available:

| URL | Style | Best For |
|-----|-------|----------|
| `/v1/api/docs/scalar/` | **Modern/Firecrawl** ⭐ | Public documentation |
| `/v1/api/docs/stoplight/` | Enterprise | Enterprise clients |
| `/v1/api/docs/rapidoc/` | Customizable | Dark theme users |
| `/v1/api/docs/` | Swagger UI | Quick testing |
| `/v1/api/redoc/` | ReDoc | Traditional docs |

**Recommended:** Use **Scalar** (`/v1/api/docs/scalar/`) for the best user experience.

---

## 🔒 Hiding Endpoints from Documentation

### Method 1: Hide by Tag (Recommended)

In [config/schema_filtering.py](config/schema_filtering.py), add tags to the `HIDDEN_TAGS` list:

```python
HIDDEN_TAGS = [
    'AI Callbacks',           # Already hidden
    'AI Integration',         # Already hidden
    'FMIS Integration',       # Already hidden
    'Webhooks',               # Already hidden
    'My New Internal Tag',    # Add your tag here
]
```

Then tag your endpoint:

```python
from drf_spectacular.utils import extend_schema

class MyInternalView(APIView):
    @extend_schema(tags=['My New Internal Tag'])  # Will be hidden
    def post(self, request):
        ...
```

### Method 2: Hide by URL Pattern

In [config/schema_filtering.py](config/schema_filtering.py), add URL patterns:

```python
HIDDEN_URL_PATTERNS = [
    r'^/v1/api/jobs/ai-callback/',      # Already hidden
    r'^/v1/api/internal/',              # Add pattern here
    r'^/v1/admin/',                     # Hide all admin endpoints
]
```

### Method 3: Hide Individual Endpoint (Using Decorator)

Use `exclude=True` to hide a single endpoint:

```python
from drf_spectacular.utils import extend_schema

class MyView(APIView):
    @extend_schema(exclude=True)  # This endpoint won't appear in docs
    def get(self, request):
        ...
```

### Method 4: Hide Entire ViewSet

```python
from drf_spectacular.utils import extend_schema_view, extend_schema

@extend_schema_view(
    list=extend_schema(exclude=True),
    create=extend_schema(exclude=True),
    retrieve=extend_schema(exclude=True),
    update=extend_schema(exclude=True),
    destroy=extend_schema(exclude=True),
)
class InternalViewSet(viewsets.ModelViewSet):
    ...
```

---

## 🎨 Customizing the Documentation

### Change Theme Colors

In [config/docs_views.py](config/docs_views.py), modify the `ScalarDocsView`:

```python
configuration = {
    'theme': 'purple',  # Options: 'purple', 'blue', 'orange', 'green', 'default'
    ...
}
```

### Add Custom Branding

```python
'metaData': {
    'title': 'Your Company API',
    'description': 'Your API description',
    'ogTitle': 'Your Company API Documentation',
},
```

### Change Sidebar Order

In [config/settings.py](config/settings.py), modify the `TAGS` list:

```python
SPECTACULAR_SETTINGS = {
    ...
    'TAGS': [
        {'name': 'Authentication', 'description': 'User auth'},
        {'name': 'Uploads', 'description': 'File uploads'},
        # Tags appear in this order
    ],
}
```

---

## 📊 Two Schema Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/v1/api/schema/` | **Full schema** - All endpoints (for internal use) |
| `/v1/api/public-schema/` | **Filtered schema** - Hidden endpoints removed (for public) |

Use the filtered schema for public documentation:

```html
<!-- In your custom docs page -->
<script id="api-reference" data-url="/v1/api/public-schema/"></script>
```

---

## 🛠️ Advanced: Multiple Documentation Versions

Create different docs for different audiences:

```python
# In urls.py
from config.docs_views import PublicSchemaView

# Subclass and customize
class PartnerSchemaView(PublicSchemaView):
    HIDDEN_TAGS = {'AI Callbacks', 'Internal'}  # Show more to partners

urlpatterns = [
    path('api/partner-docs/', ScalarDocsView.as_view(), name='partner-docs'),
    # Point it to partner schema instead
]
```

---

## ✅ Currently Hidden Endpoints

These are automatically hidden from public documentation:

| Tag/Pattern | Reason |
|-------------|--------|
| `AI Callbacks` | Internal AI system communication |
| `AI Integration` | Internal service integration |
| `FMIS Integration` | Farm Management System internal |
| `Webhooks` | Internal webhook handlers |
| `/v1/api/jobs/ai-callback/` | AI callback receiver |
| `/v1/api/uploads/ai/` | AI manifest endpoints |
| `/v1/api/fmis/webhooks/` | FMIS webhook handlers |

---

## 📝 Documenting Your Endpoints

Use `extend_schema` to add descriptions:

```python
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

class MyView(APIView):
    @extend_schema(
        summary="Short title for sidebar",
        description="""
        Detailed description with **markdown** support.
        
        ## Usage
        1. First step
        2. Second step
        """,
        tags=['My Category'],
        parameters=[
            OpenApiParameter(
                name='filter',
                description='Filter results',
                required=False,
                type=str
            ),
        ],
        examples=[
            OpenApiExample(
                'Example Request',
                value={'key': 'value'},
                request_only=True
            ),
        ],
        responses={
            200: {'description': 'Success response'},
            400: {'description': 'Bad request'},
        }
    )
    def get(self, request):
        ...
```

---

## 🔗 Exporting OpenAPI Schema

```bash
# Export full schema
python manage.py spectacular --file schema.yaml

# Export as JSON
python manage.py spectacular --file schema.json --format openapi-json
```

Use the exported schema with:
- Postman (import collection)
- API clients generators (OpenAPI Generator)
- Mock servers
- API testing tools

---

## 🌐 Hosting on Static Site

For production, you can serve the docs from a CDN:

1. Export the filtered schema:
   ```bash
   curl http://localhost:8000/v1/api/public-schema/ > docs/openapi.json
   ```

2. Create a static HTML file using Scalar:
   ```html
   <!DOCTYPE html>
   <html>
   <head>
       <title>API Docs</title>
   </head>
   <body>
       <script id="api-reference" data-url="./openapi.json"></script>
       <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
   </body>
   </html>
   ```

3. Deploy to any static hosting (GitHub Pages, Netlify, S3, etc.)
