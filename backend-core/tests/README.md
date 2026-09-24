# PhotoGear Backend Tests

## Overview
Comprehensive unit tests for the Product upload system and related functionality.

## Test Structure

```
backend/tests/
├── __init__.py
└── products/
    ├── __init__.py
    ├── test_models.py       # Product model tests
    └── test_views.py        # Product upload API tests
```

## Running Tests

### Run all tests
```bash
cd backend
python manage.py test tests
```

### Run specific test module
```bash
python manage.py test tests.products.test_models
python manage.py test tests.products.test_views
```

### Run specific test case
```bash
python manage.py test tests.products.test_models.ProductModelTest
python manage.py test tests.products.test_models.ProductModelTest.test_create_product
```

### Run with coverage
```bash
coverage run --source='products' manage.py test tests.products
coverage report
coverage html  # Generate HTML report
```

## Test Coverage

### Product Model Tests (`test_models.py`)
- ✅ Product creation
- ✅ Product type choices validation
- ✅ Display name generation (`get_type_display`)
- ✅ Category classification (`get_category`)
- ✅ PostGIS footprint geometry
- ✅ Spectral bands array
- ✅ Statistics JSON field
- ✅ String representation
- ✅ Auto-generated timestamps
- ✅ Multiple products per job
- ✅ Dataset relationship

### Product Upload API Tests (`test_views.py`)
- ✅ Upload initialization (success)
- ✅ Upload initialization (unauthorized)
- ✅ Upload initialization (job not found)
- ✅ Chunk upload (success)
- ✅ Chunk upload (session not found)
- ✅ Upload completion (success)
- ✅ S3 service integration (mocked)
- ✅ Upload session management

## Test Database

Tests use Django's test database which is:
- Created automatically before tests run
- Destroyed automatically after tests complete  
- Isolated from production/development databases

## Mocking

S3Service calls are mocked using `unittest.mock` to:
- Avoid actual S3 API calls during testing
- Speed up test execution
- Enable testing without AWS credentials

## Requirements

- Django test framework
- unittest.mock
- PostGIS (for geometry fields)
- All product app dependencies

## Continuous Integration

Tests should be run:
- Before committing code
- In CI/CD pipeline
- Before deploying to production

## Adding New Tests

1. Create test file in appropriate directory
2. Import necessary modules and models
3. Create test class inheriting from `TestCase`
4. Add `setUp()` method for test data
5. Write test methods starting with `test_`
6. Use descriptive test names
7. Add assertions to verify expected behavior

Example:
```python
from django.test import TestCase
from products.models import Product

class MyNewTest(TestCase):
    def setUp(self):
        # Set up test data
        pass
    
    def test_my_feature(self):
        # Test implementation
        self.assertEqual(expected, actual)
```
