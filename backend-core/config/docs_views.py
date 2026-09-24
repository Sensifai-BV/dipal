"""
Beautiful API Documentation Views for PhotoGear

This module provides multiple documentation UIs:
1. Scalar - Modern, Firecrawl-style docs (RECOMMENDED)
2. Stoplight Elements - Enterprise-grade docs
3. RapiDoc - Customizable docs

All use the same OpenAPI schema from drf-spectacular but with 
different, more polished UIs than the default Swagger/ReDoc.

VERSIONING:
- Each API version gets its own schema endpoint
- Scalar docs include a version switcher dropdown
- Old versions are preserved for backward compatibility
"""

from django.http import HttpResponse
from django.views import View
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes


class ScalarDocsView(View):
    """
    Scalar API Documentation with Version Switcher
    
    A modern, beautiful API documentation UI similar to Firecrawl and Stripe.
    Features:
    - Dark/light mode
    - Try-it-out functionality
    - Multiple language code examples
    - Search functionality
    - Version switcher dropdown
    
    URL: /v1/api/docs/scalar/
    """
    
    # API versions configuration
    API_VERSIONS = [
        {'version': 'v1', 'label': 'v1.0 (Current)', 'schema_url': '/v1/api/schema/'},
        # Add more versions as your API evolves:
        # {'version': 'v2', 'label': 'v2.0 (Beta)', 'schema_url': '/v2/api/schema/'},
        # {'version': 'v1-legacy', 'label': 'v1.0 (Deprecated)', 'schema_url': '/v1-legacy/api/schema/'},
    ]
    
    def get(self, request):
        # Get requested version from query param, default to latest
        requested_version = request.GET.get('version', self.API_VERSIONS[0]['version'])
        
        # Find the schema URL for requested version
        schema_url = '/v1/api/schema/'  # default
        current_label = 'v1.0 (Current)'
        for v in self.API_VERSIONS:
            if v['version'] == requested_version:
                schema_url = v['schema_url']
                current_label = v['label']
                break
        
        # Build version selector HTML
        version_options = '\n'.join([
            f'<option value="{v["version"]}" {"selected" if v["version"] == requested_version else ""}>{v["label"]}</option>'
            for v in self.API_VERSIONS
        ])
        
        # Only show version switcher if multiple versions exist
        version_switcher_html = ''
        if len(self.API_VERSIONS) > 1:
            version_switcher_html = f'''
            <div id="version-switcher" style="
                position: fixed;
                top: 12px;
                right: 20px;
                z-index: 1000;
                background: rgba(255,255,255,0.95);
                padding: 8px 12px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                display: flex;
                align-items: center;
                gap: 8px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 13px;
            ">
                <label style="color: #666; font-weight: 500;">API Version:</label>
                <select id="version-select" onchange="switchVersion(this.value)" style="
                    padding: 6px 10px;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    background: white;
                    font-size: 13px;
                    cursor: pointer;
                ">
                    {version_options}
                </select>
            </div>
            <script>
                function switchVersion(version) {{
                    window.location.href = '?version=' + version;
                }}
            </script>
            '''
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>PhotoGear API Documentation - {current_label}</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📷</text></svg>">
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
        /* Custom branding */
        .scalar-app {{
            --scalar-color-1: #6366f1;
            --scalar-color-accent: #6366f1;
        }}
        /* Dark mode version switcher */
        @media (prefers-color-scheme: dark) {{
            #version-switcher {{
                background: rgba(30,30,46,0.95) !important;
            }}
            #version-switcher label {{
                color: #cdd6f4 !important;
            }}
            #version-switcher select {{
                background: #313244 !important;
                border-color: #45475a !important;
                color: #cdd6f4 !important;
            }}
        }}
    </style>
</head>
<body>
    {version_switcher_html}
    <script id="api-reference" data-url="{schema_url}"></script>
    <script>
        var configuration = {{
            theme: 'purple',
            layout: 'modern',
            showSidebar: true,
            hideModels: false,
            hideDownloadButton: false,
            hideDarkModeToggle: false,
            darkMode: false,
            searchHotKey: 'k',
            hideAiButton: true,  // Set to true to hide "Ask AI" button
            metaData: {{
                title: 'PhotoGear API ({current_label})',
                description: 'Photogrammetry Processing Platform API',
                ogDescription: 'Build amazing drone imagery processing workflows with PhotoGear API',
                ogTitle: 'PhotoGear API Documentation',
            }},
            customCss: `
                [data-section-slug="ai-callbacks"],
                [data-section-slug="ai-integration"],
                [data-section-slug="fmis-integration"],
                [data-section-slug="webhooks"] {{
                    display: none !important;
                }}
            `,
        }}
        
        document.getElementById('api-reference').dataset.configuration = JSON.stringify(configuration)
    </script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>'''
        return HttpResponse(html, content_type='text/html')


class StoplightDocsView(View):
    """
    Stoplight Elements API Documentation
    
    Enterprise-grade documentation UI with:
    - Clean, professional design
    - Try-it-out console
    - Mock server integration
    - Multiple layout options
    
    URL: /v1/api/docs/stoplight/
    """
    
    def get(self, request):
        html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <title>PhotoGear API Documentation</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📷</text></svg>">
    <!-- Stoplight Elements CSS -->
    <link rel="stylesheet" href="https://unpkg.com/@stoplight/elements/styles.min.css">
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        }
        .sl-elements {
            height: 100vh;
        }
        /* Custom styling */
        .sl-elements-api {
            --color-primary: 99, 102, 241;  /* Indigo */
        }
        /* Hide internal tags via CSS */
        [data-test="tag-ai-callbacks"],
        [data-test="tag-ai-integration"],
        [data-test="tag-fmis-integration"],
        [data-test="tag-webhooks"] {
            display: none !important;
        }
    </style>
</head>
<body>
    <elements-api
        apiDescriptionUrl="/v1/api/schema/"
        router="hash"
        layout="sidebar"
        tryItCredentialsPolicy="same-origin"
        tryItCorsProxy=""
    />
    <script src="https://unpkg.com/@stoplight/elements/web-components.min.js"></script>
</body>
</html>'''
        return HttpResponse(html, content_type='text/html')


class RapiDocView(View):
    """
    RapiDoc API Documentation
    
    Highly customizable documentation with:
    - Multiple themes and layouts
    - Extensive configuration options
    - Fast rendering
    
    URL: /v1/api/docs/rapidoc/
    """
    
    def get(self, request):
        html = '''<!DOCTYPE html>
<html>
<head>
    <title>PhotoGear API Documentation</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📷</text></svg>">
    <style>
        rapi-doc {
            --nav-bg-color: #1e1e2e;
            --nav-text-color: #cdd6f4;
            --nav-hover-bg-color: #313244;
            --nav-accent-color: #89b4fa;
            --primary-color: #6366f1;
        }
    </style>
</head>
<body>
    <rapi-doc
        spec-url="/v1/api/schema/"
        theme="dark"
        bg-color="#1e1e2e"
        text-color="#cdd6f4"
        header-color="#313244"
        primary-color="#6366f1"
        nav-bg-color="#181825"
        nav-text-color="#cdd6f4"
        nav-hover-bg-color="#313244"
        nav-accent-color="#89b4fa"
        render-style="view"
        show-header="false"
        allow-authentication="true"
        allow-server-selection="true"
        allow-try="true"
        show-method-in-nav-bar="as-colored-block"
        use-path-in-nav-bar="true"
        show-components="true"
        schema-style="table"
    >
        <div slot="nav-logo" style="padding: 20px; text-align: center;">
            <span style="font-size: 24px;">📷</span>
            <h2 style="margin: 10px 0 0 0; color: #cdd6f4;">PhotoGear API</h2>
        </div>
    </rapi-doc>
    <script type="module" src="https://unpkg.com/rapidoc/dist/rapidoc-min.js"></script>
</body>
</html>'''
        return HttpResponse(html, content_type='text/html')


# ============================================================================
# Pre-filtered Schema Endpoint (removes internal endpoints at source)
# ============================================================================

from drf_spectacular.views import SpectacularAPIView
import re


class PublicSchemaView(SpectacularAPIView):
    """
    Filtered OpenAPI schema that excludes internal endpoints.
    
    Use this for public-facing documentation to hide:
    - AI callback endpoints
    - Internal integration endpoints
    - Webhook handlers
    - Admin-only endpoints
    
    URL: /v1/api/public-schema/
    """
    
    permission_classes = [AllowAny]
    
    # Tags to hide from public documentation
    HIDDEN_TAGS = {
        'AI Callbacks',
        'AI Integration',
        'FMIS Integration',
        'Webhooks',
        'Internal',
        'AI Product Upload',      # Internal AI product upload endpoints
        '3D (Deprecated)',        # Deprecated 3D processing endpoints
        'docs',                   # Documentation endpoints
    }
    
    # URL patterns to hide
    HIDDEN_PATTERNS = [
        r'^/v1/api/jobs/ai-callback/',
        r'^/v1/api/uploads/ai/',
        r'^/v1/api/fmis/webhooks/',
        r'^/v1/api/schema/',           # Hide schema endpoints from docs
        r'^/v1/api/public-schema/',    # Hide public schema endpoint
        r'^/v1/api/docs/',             # Hide docs endpoints themselves
    ]
    
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        
        if hasattr(response, 'data'):
            schema = response.data
            self._filter_schema(schema)
        
        return response
    
    def _filter_schema(self, schema):
        """Remove internal endpoints from the schema."""
        
        # Filter tags list
        if 'tags' in schema:
            schema['tags'] = [
                tag for tag in schema['tags']
                if tag.get('name') not in self.HIDDEN_TAGS
            ]
        
        # Filter paths
        if 'paths' in schema:
            paths_to_delete = []
            
            for path, path_item in schema['paths'].items():
                # Check URL patterns
                for pattern in self.HIDDEN_PATTERNS:
                    if re.match(pattern, path):
                        paths_to_delete.append(path)
                        break
                else:
                    # Check if all operations belong to hidden tags
                    all_hidden = True
                    for method in ['get', 'post', 'put', 'patch', 'delete']:
                        if method in path_item:
                            operation = path_item[method]
                            if isinstance(operation, dict):
                                tags = operation.get('tags', [])
                                if not tags or not all(t in self.HIDDEN_TAGS for t in tags):
                                    all_hidden = False
                                    break
                    
                    if all_hidden:
                        paths_to_delete.append(path)
            
            for path in paths_to_delete:
                del schema['paths'][path]
