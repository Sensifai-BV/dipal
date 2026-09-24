# PhotoGear AI Core Tests

## Overview
Unit tests for GSD conversion utilities and image analysis components.

## Test Structure

```
image-analysis-core/tests/
├── __init__.py
└── unit/
    ├── __init__.py
    └── test_gsd_conversion.py    # GSD to max_image_size conversion tests
```

## Running Tests

### Run all tests
```bash
cd image-analysis-core
python -m pytest tests/
```

Or with unittest:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### Run specific test file
```bash
python -m unittest tests.unit.test_gsd_conversion
```

### Run with coverage
```bash
pytest --cov=shared/utils tests/
pytest --cov=shared/utils --cov-report=html tests/
```

## Test Coverage

### GSD Conversion Tests (`test_gsd_conversion.py`)
- ✅ Basic GSD to max_image_size conversion
- ✅ Higher resolution (lower GSD) conversion
- ✅ Minimum bound enforcement (640px)
- ✅ Maximum bound enforcement (8192px)
- ✅ Custom base values
- ✅ Inverse proportional relationship
- ✅ COLMAP settings generation
- ✅ Integer value validation
- ✅ Formula accuracy verification
- ✅ Edge case handling (None, zero, negative)
- ✅ Typical GSD ranges (1-20 cm/px)
- ✅ Integration with COLMAP parameters
- ✅ Consistency across pipeline stages

## Key Test Cases

### GSD Conversion Formula
```python
# Formula: max_size = base_size * (base_gsd / target_gsd)
# Base: 2640px at GSD 5.0 cm/px

GSD 2.5 cm/px  → 5280px  (double resolution, double pixels)
GSD 5.0 cm/px  → 2640px  (base)
GSD 10.0 cm/px → 1320px  (half resolution, half pixels)
GSD 20.0 cm/px → 660px   (quarter resolution, quarter pixels)
```

### Bounds
- **Minimum**: 640px (very low resolution)
- **Maximum**: 8192px (very high resolution)

### COLMAP Parameters
All four parameters receive the same value:
- `feature_extraction_max_image_size`
- `undistort_max_image_size`
- `patch_match_max_image_size`
- `fusion_max_image_size`

## Requirements

- Python 3.8+
- pytest (recommended) or unittest
- pytest-cov (for coverage)

## Running in Docker

```bash
docker run -v $(pwd):/app -w /app python:3.13-slim \
  bash -c "pip install pytest pytest-cov && pytest tests/"
```

## Adding New Tests

1. Create test file in `tests/unit/` or `tests/integration/`
2. Name file with `test_` prefix
3. Import modules to test
4. Create test class inheriting from `unittest.TestCase`
5. Write test methods starting with `test_`
6. Use descriptive names
7. Add assertions

Example:
```python
import unittest
from shared.utils.gsd_conversion import gsd_to_max_image_size

class TestNewFeature(unittest.TestCase):
    def test_feature_works(self):
        result = gsd_to_max_image_size(10.0)
        self.assertEqual(result, 1320)
```

## CI/CD Integration

Tests run automatically on:
- Git push
- Pull requests
- Before deployment

## Test Output

```
Test GSD Conversion (test_gsd_conversion.TestGSDConversion) ... ok
Test COLMAP Integration (test_gsd_conversion.TestGSDConversionIntegration) ... ok

----------------------------------------------------------------------
Ran 14 tests in 0.021s

OK
```
