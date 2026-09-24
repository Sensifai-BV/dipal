# Installation Guide

## Quick Installation

Since this is a Django project, you can install dependencies directly without the editable install:

```bash
# Install main dependencies
pip install adrf>=0.1.9 \
    chromatrace>=0.2.13 \
    django>=5.2 \
    django-filter>=25.1 \
    djangorestframework>=3.16 \
    djangorestframework-simplejwt>=5.5 \
    lagom>=0.7.2 \
    psycopg2-binary>=2.9.9 \
    uvicorn[standard]>=0.37.0

# Install dev dependencies
pip install bandit[toml]>=1.7.10 \
    black>=24.10.0 \
    django-upgrade>=1.21.0 \
    flake8>=7.1.1 \
    flake8-bugbear>=24.10.31 \
    flake8-comprehensions>=3.16.0 \
    flake8-simplify>=0.21.0 \
    isort>=7.0.0 \
    mypy>=1.13.0 \
    pre-commit>=4.0.1 \
    django-stubs>=5.1.1 \
    djangorestframework-stubs>=3.15.1 \
    types-requests>=2.32.0
```

## Docker Installation (Recommended)

Update your Dockerfile to install from requirements file:

```bash
# In Docker container
docker compose exec web pip install -r requirements.txt
```

## Using requirements.txt

If you prefer requirements.txt, create it from pyproject.toml:

```bash
# Generate requirements.txt
pip-compile pyproject.toml

# Or manually create requirements.txt with the dependencies listed above
```

## Alternative: Use pip install with direct dependencies

```bash
# Install from pyproject.toml (this should work now)
pip install -e .

# If still having issues, install directly:
pip install \
    adrf \
    chromatrace \
    django \
    django-filter \
    djangorestframework \
    djangorestframework-simplejwt \
    lagom \
    psycopg2-binary \
    uvicorn[standard]
```

## Verify Installation

```bash
python -c "import chromatrace; print('chromatrace:', chromatrace.__version__)"
python -c "import lagom; print('lagom installed')"
python -c "import django; print('django:', django.__version__)"
```

## Setup Pre-commit

```bash
pre-commit install
pre-commit run --all-files
```

## Common Issues

### Issue: "Multiple top-level packages discovered"
**Solution**: This is fixed with the `[tool.setuptools.packages.find]` configuration in pyproject.toml

### Issue: Package not found after install
**Solution**: Since it's a Django project, packages are discovered by Django's INSTALLED_APPS, not Python's package system. You don't need editable install for development.

### Issue: Import errors for chromatrace or lagom
**Solution**: Install these packages individually first:
```bash
pip install chromatrace lagom
```

## Docker-specific Setup

For Docker users, update your docker-compose.yml command:

```yaml
web:
  command: sh -c "pip install -e . && python manage.py migrate && python manage.py runserver 0.0.0.0:8000"
```

Or create a requirements.txt file and use that instead of editable install.
