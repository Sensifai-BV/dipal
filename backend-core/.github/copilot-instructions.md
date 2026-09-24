# Copilot Custom Instructions
_These guidelines apply to every suggestion Copilot makes in this repository._

---

## 1. High-level Architecture

This is a **Django REST Framework** backend for a photogrammetry platform with **Layered Architecture**:

### Application Structure (`apps/`)
Each Django app follows this internal structure:
* `api/` ⇢ REST API layer (views, serializers, viewsets)
* `api/views/` ⇢ DRF views and viewsets
* `domains/` ⇢ Business logic and domain services
* `infra/` ⇢ Infrastructure concerns
  * `infra/db/` ⇢ Database models
  * `infra/services/` ⇢ External service clients (AI Gateway, S3, etc.)

### Core Apps
* `accounts/` ⇢ User authentication and organization management
* `uploads/` ⇢ Dataset and image upload handling
* `jobs/` ⇢ Processing job management and AI Gateway integration
* `organizations/` ⇢ Multi-tenant organization management

### Configuration (`config/`)
* `settings.py` ⇢ Django settings (uses environment variables)
* `celery.py` ⇢ Celery configuration for async tasks
* `api_v1.py` ⇢ API URL routing
* `logging_config.py` ⇢ Centralized logging configuration

---

## 2. Coding Style

* Conform to **PEP 8** and Django coding conventions
* **Inside every function: no inline comments**
  * Provide **one concise docstring** describing purpose, parameters, return type
  * All parameters and returns **must be type-annotated**
* Use `pathlib.Path` over raw strings for file paths
* Use timezone-aware `datetime` objects (`django.utils.timezone`)

### Naming Conventions
* **snake_case** for: variables, functions, module names
* **PascalCase** for: classes, exceptions
* **SCREAMING_SNAKE_CASE** for: constants, environment variables
* **lowercase** with underscores for: file names, package names

### Django-Specific Conventions
* ViewSets over APIViews when CRUD operations are needed
* Use `@extend_schema` decorator for API documentation
* Serializers must validate all input data
* Use `select_related()` and `prefetch_related()` to avoid N+1 queries

---

## 3. Models & Database

* Models live in `apps/<app_name>/infra/db/models/`
* Use `AbstractBaseModel` from `utils/abstract_base_model.py` for common fields (id, created_at, updated_at)
* All models must have:
  * UUID primary key (`id = models.UUIDField(primary_key=True, default=uuid.uuid4)`)
  * Timestamps (`created_at`, `updated_at`)
* Use Django migrations for all schema changes
* Foreign keys should use `on_delete=models.CASCADE` or `on_delete=models.PROTECT` appropriately

### Example Model
```python
from utils.abstract_base_model import AbstractBaseModel

class ProcessingJob(AbstractBaseModel):
    """Processing job for drone imagery."""
    
    dataset = models.ForeignKey(
        'uploads.Dataset',
        on_delete=models.CASCADE,
        related_name='jobs'
    )
    status = models.CharField(max_length=20, default='pending')
    
    class Meta:
        db_table = 'processing_jobs'
        ordering = ['-created_at']
```

---

## 4. API Views & Serializers

### Views Location
* `apps/<app_name>/api/views/` ⇢ One file per resource or feature

### Serializer Patterns
```python
class ProcessingJobSerializer(serializers.ModelSerializer):
    """Serializer for ProcessingJob model."""
    
    class Meta:
        model = ProcessingJob
        fields = ['id', 'dataset', 'status', 'progress', 'created_at']
        read_only_fields = ['id', 'created_at']
```

### View Patterns
```python
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

class JobRerunView(APIView):
    """Re-run an existing processing job."""
    
    @extend_schema(
        summary="Rerun a job",
        responses={200: JobResponseSerializer}
    )
    def post(self, request, job_id):
        # Implementation
        pass
```

---

## 5. Celery Tasks

* Task definitions: `apps/<app_name>/infra/services/tasks/tasks.py`
* Use `@shared_task` decorator
* Tasks should be idempotent when possible
* Always handle exceptions and update job status on failure

### Task Pattern
```python
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_drone_imagery(job_db_id: str, starting_stage: str = None):
    """
    Process drone imagery through AI pipeline.
    
    Args:
        job_db_id: UUID of the ProcessingJob
        starting_stage: Optional stage to resume from
    """
    try:
        job = ProcessingJob.objects.get(id=job_db_id)
        # Processing logic
    except Exception as e:
        logger.error(f"Failed to process job {job_db_id}: {e}")
        raise
```

---

## 6. External Service Clients

* Located in `apps/<app_name>/infra/services/`
* Use `requests` for synchronous HTTP calls
* Use `aiohttp` for async HTTP calls (if needed)
* Always include timeout configuration
* Log all external API calls

### Client Pattern
```python
class AIGatewayClient:
    """Client for AI Gateway service communication."""
    
    def __init__(self):
        self.base_url = settings.AI_GATEWAY_URL
        self.timeout = 30
    
    def start_processing_job(
        self,
        job_id: str,
        dataset_id: str,
        download_url: str,
        parameters: dict | None = None,
        starting_stage: str | None = None
    ) -> dict:
        """Submit a processing job to AI Gateway."""
        # Implementation
```

---

## 7. Testing

* Use **pytest** with `pytest-django`
* Tests location: `tests/` mirroring app structure
* Use factories (`factory_boy`) for test data
* Mock external services

### Test Structure
```
tests/
├── conftest.py          # Shared fixtures
├── factories.py         # Factory definitions
├── apps/
│   └── jobs/
│       ├── test_views.py
│       ├── test_serializers.py
│       └── test_tasks.py
```

### Test Pattern
```python
import pytest
from unittest.mock import patch

@pytest.mark.django_db
class TestJobRerunView:
    """Tests for JobRerunView."""
    
    def test_rerun_job_success(self, client, job_factory):
        """Test successful job rerun."""
        job = job_factory.create(status='failed')
        
        response = client.post(f'/v1/api/jobs/{job.id}/rerun/')
        
        assert response.status_code == 200
        assert response.data['status'] == 'queued'
```

---

## 8. Environment & Settings

* All configuration via environment variables
* Use `.env` file for local development (never commit)
* Settings accessed via `django.conf.settings`

### Required Environment Variables
```
DATABASE_URL=postgres://...
REDIS_URL=redis://...
AI_GATEWAY_URL=http://...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_REGION_NAME=...
```

---

## 9. Error Handling

* Custom exceptions in `utils/exceptions.py`
* Use DRF's exception handling
* Always return proper HTTP status codes
* Log errors with appropriate severity

### Custom Response Pattern
```python
from utils.custom_response import CustomResponse

return CustomResponse.success(
    data={'job_id': str(job.id)},
    message='Job created successfully'
)

return CustomResponse.error(
    message='Job not found',
    status_code=404
)
```

---

## 10. Logging

* Use `logging` module (not `print`)
* Logger per module: `logger = logging.getLogger(__name__)`
* Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
* Include context in log messages

```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"Processing job {job_id} for dataset {dataset.name}")
logger.error(f"Failed to process job {job_id}: {e}", exc_info=True)
```

---

## 11. S3 & File Storage

* Use `boto3` for S3 operations
* Generate presigned URLs for secure access
* Bucket configuration in settings
* Use `smart_open` for streaming large files

---

## 12. Things to Avoid

* ❌ No inline comments in code; use docstrings
* ❌ Never use `print()` for logging
* ❌ No magic numbers/strings; use constants or settings
* ❌ No hardcoded URLs or credentials
* ❌ Avoid N+1 queries; use `select_related()`/`prefetch_related()`
* ❌ Don't commit `.env` files or secrets
* ❌ Avoid synchronous operations in async contexts
* ❌ Functions longer than 30 lines should be broken down

---

## 13. Function Template

```python
def create_processing_job(
    dataset_id: str,
    parameters: dict,
    user: User
) -> ProcessingJob:
    """
    Create a new processing job for a dataset.

    Args:
        dataset_id: UUID of the dataset to process
        parameters: Processing parameters (gsd, calibration, etc.)
        user: User creating the job

    Returns:
        Created ProcessingJob instance

    Raises:
        ValidationError: If parameters are invalid
        PermissionDenied: If user lacks access to dataset
    """
    dataset = get_object_or_404(Dataset, id=dataset_id)
    validate_user_access(user, dataset)
    
    return ProcessingJob.objects.create(
        dataset=dataset,
        parameters=parameters,
        created_by=user
    )
```

---

## 14. Versioning & Changelogs

### Semantic Versioning

The project uses **Semantic Versioning** (`MAJOR.MINOR.PATCH`):

| Bump | When |
|---|---|
| **MAJOR** (`X.0.0`) | Breaking API changes (removed/renamed endpoints, changed request/response schemas) |
| **MINOR** (`0.X.0`) | New features, new endpoints, non-breaking additions |
| **PATCH** (`0.0.X`) | Bug fixes, internal refactors, documentation updates |

* The canonical version lives in `pyproject.toml` under `[project] version`.
* **Every** code change that reaches `main` / `mvp` must bump the version.

### Changelog Rules

* Changelogs live in `docs/changelogs/`, one file per version: `v{MAJOR}.{MINOR}.{PATCH}.md`.
* `docs/changelogs/README.md` is the index — add every new version to its table.
* Each changelog file **must** contain:
  1. **Summary** — One-paragraph release overview.
  2. **All Changes** — Grouped by `Bug Fixes`, `Features`, `Infrastructure`, `Breaking Changes` (if any).
  3. **🗄️ Database Changelog** — Table of schema migrations in this release (migration name, change type, details). If no schema changes, state "No changes."
  4. **🤖 AI Service Changelog** — Table of changes affecting the AI ↔ Backend contract (endpoint changes, payload changes, new/removed fields). State the **impact** and **action required** for the AI team.
  5. **🖥️ Frontend Changelog** — Table of changes affecting the Frontend ↔ Backend contract (endpoint changes, response schema changes, new query params). State the **impact** and **action required** for the frontend team.
* If a section has no changes, include it with "No changes." — never omit the section.
* Use commit-style prefixes in change descriptions: `fix(scope)`, `feat(scope)`, `refactor(scope)`, `docs(scope)`, `ci(scope)`.

---

**Remember:** Suggestions that violate any rule above should be suppressed or rewritten automatically.
