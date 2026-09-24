"""
OpenAPI Schema Filtering for PhotoGear API Documentation

This module provides preprocessing hooks for drf-spectacular to:
1. Filter out internal/AI endpoints from public documentation
2. Remove specific tags from the schema
3. Customize the schema for different audiences

Usage in settings.py:
    SPECTACULAR_SETTINGS = {
        ...
        'PREPROCESSING_HOOKS': ['config.schema_filtering.filter_schema'],
        'POSTPROCESSING_HOOKS': ['config.schema_filtering.filter_tags_postprocessing'],
        ...
    }

To hide an individual endpoint, use the decorator in your view:
    from drf_spectacular.utils import extend_schema
    
    @extend_schema(exclude=True)  # Hides from all docs
    def my_internal_view(request):
        ...

Or tag it with a hidden tag:
    @extend_schema(tags=['AI Callbacks'])  # Will be filtered out
    def my_callback_view(request):
        ...
"""

from typing import List, Dict, Any


# ============================================================================
# CONFIGURATION: Define which tags/endpoints to HIDE from public docs
# ============================================================================

# Tags to completely remove from public documentation
HIDDEN_TAGS = [
    'AI Callbacks',           # Internal AI system callbacks
    'AI Integration',         # Internal AI endpoints
    'FMIS Integration',       # Farm Management System internal
    'Webhooks',               # Internal webhook handlers
    'AI Product Upload',      # Internal AI product upload endpoints
    '3D (Deprecated)',        # Deprecated 3D processing endpoints
    'docs',                   # Documentation endpoints
]

# Specific operation IDs to exclude (if you need fine-grained control)
HIDDEN_OPERATION_IDS = [
    'ai_callback_create',
    'dataset_full_manifest_retrieve',
]

# URL patterns to exclude (regex patterns)
HIDDEN_URL_PATTERNS = [
    r'^/v1/api/jobs/ai-callback/',      # AI callback endpoint
    r'^/v1/api/uploads/ai/',            # AI-specific upload endpoints
    r'^/v1/api/fmis/webhooks/',         # FMIS webhooks
    r'^/v1/api/schema/',                # OpenAPI schema endpoint
    r'^/v1/api/public-schema/',         # Filtered schema endpoint
    r'^/v1/api/docs/',                  # Documentation UI endpoints
]


# ============================================================================
# PREPROCESSING HOOK: Filter endpoints before schema generation
# ============================================================================

def filter_schema(endpoints: List[tuple]) -> List[tuple]:
    """
    Preprocessing hook to filter endpoints from the OpenAPI schema.
    
    This runs BEFORE the schema is generated, so filtered endpoints
    won't appear in Swagger, ReDoc, or any exported schema.
    
    Args:
        endpoints: List of (path, path_regex, method, callback) tuples
        
    Returns:
        Filtered list of endpoints
    """
    import re
    
    filtered = []
    
    for path, path_regex, method, callback in endpoints:
        # Skip endpoints matching hidden URL patterns
        should_hide = False
        
        for pattern in HIDDEN_URL_PATTERNS:
            if re.match(pattern, path):
                should_hide = True
                break
        
        if not should_hide:
            filtered.append((path, path_regex, method, callback))
    
    return filtered


# ============================================================================
# POSTPROCESSING HOOK: Filter tags from generated schema
# ============================================================================

def filter_tags_postprocessing(result: Dict[str, Any], generator, request, public: bool) -> Dict[str, Any]:
    """
    Postprocessing hook to remove specific tags from the final schema.
    
    This runs AFTER the schema is generated, allowing you to remove
    entire tag categories from the documentation.
    
    Args:
        result: The generated OpenAPI schema dictionary
        generator: The schema generator instance
        request: The HTTP request
        public: Whether this is for public consumption
        
    Returns:
        Modified schema with filtered tags
    """
    # Remove hidden tags from the tags list
    if 'tags' in result:
        result['tags'] = [
            tag for tag in result['tags'] 
            if tag.get('name') not in HIDDEN_TAGS
        ]
    
    # Remove paths that belong to hidden tags
    if 'paths' in result:
        paths_to_remove = []
        
        for path, methods in result['paths'].items():
            for method, operation in methods.items():
                if isinstance(operation, dict):
                    operation_tags = operation.get('tags', [])
                    # If ALL tags of this operation are hidden, remove it
                    if operation_tags and all(tag in HIDDEN_TAGS for tag in operation_tags):
                        paths_to_remove.append((path, method))
        
        # Remove marked paths
        for path, method in paths_to_remove:
            if path in result['paths']:
                del result['paths'][path][method]
                # If path has no more methods, remove it entirely
                if not result['paths'][path]:
                    del result['paths'][path]
    
    return result


# ============================================================================
# CUSTOM SCHEMA CLASS: For per-endpoint control via decorators
# ============================================================================

def create_filtered_schema_view(hidden_tags: List[str] = None, hidden_patterns: List[str] = None):
    """
    Factory function to create a custom schema view with specific filters.
    
    Usage:
        from config.schema_filtering import create_filtered_schema_view
        
        # In urls.py
        path('api/public-schema/', create_filtered_schema_view(
            hidden_tags=['AI Callbacks', 'Internal'],
            hidden_patterns=[r'^/v1/internal/']
        ).as_view(), name='public-schema'),
    """
    from drf_spectacular.views import SpectacularAPIView
    
    class FilteredSchemaView(SpectacularAPIView):
        def _get_schema_response(self, request):
            # Get the base schema
            response = super()._get_schema_response(request)
            
            # Apply custom filtering
            if hasattr(response, 'data'):
                schema = response.data
                
                # Filter tags
                if hidden_tags and 'tags' in schema:
                    schema['tags'] = [
                        t for t in schema['tags'] 
                        if t.get('name') not in hidden_tags
                    ]
                
                # Filter paths
                if hidden_patterns and 'paths' in schema:
                    import re
                    paths_to_delete = []
                    for path in schema['paths']:
                        for pattern in hidden_patterns:
                            if re.match(pattern, path):
                                paths_to_delete.append(path)
                                break
                    for path in paths_to_delete:
                        del schema['paths'][path]
            
            return response
    
    return FilteredSchemaView


# ============================================================================
# EXAMPLE: Different schemas for different audiences
# ============================================================================

# Public API schema (for external developers)
PUBLIC_HIDDEN_TAGS = [
    'AI Callbacks',
    'AI Integration', 
    'FMIS Integration',
    'Webhooks',
    'Internal',
]

# Partner API schema (for trusted partners)
PARTNER_HIDDEN_TAGS = [
    'AI Callbacks',
    'Internal',
]

# Full API schema (for internal development)
INTERNAL_HIDDEN_TAGS = []  # Show everything
