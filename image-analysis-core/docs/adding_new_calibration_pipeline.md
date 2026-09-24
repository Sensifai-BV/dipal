# Adding a New Radiometric Calibration Pipeline

This guide explains how to add support for a new drone's radiometric calibration to the image-analysis-core system.

---

## Architecture Overview

The calibration system uses a **Strategy + Factory** pattern:

```
IDroneImageProcessor          (abstract interface)
    └── BaseDroneCalibrator   (shared algorithms: vignetting, distortion, reflectance)
        ├── Mavic3MImageProcessor     (DJI Mavic 3M / P4 Multispectral)
        └── MicaSenseImageProcessor   (MicaSense RedEdge / Altum)
```

**Key files:**

| File | Purpose |
|------|---------|
| `services/radiometric_calibration/app/core/services/interfaces.py` | Abstract interface (`IDroneImageProcessor`) and result dataclasses |
| `services/radiometric_calibration/app/core/services/base_calibrator.py` | Shared algorithms (vignetting, distortion, reflectance, NDVI) |
| `services/radiometric_calibration/app/core/services/factory.py` | `DroneImageProcessorFactory` — maps drone types to processors |
| `shared/band_detection/models.py` | Band detection enums (`BandType`, `DroneManufacturer`) |
| `shared/band_detection/band_classifier.py` | XMP/filename-based band classification |

---

## Step-by-step Guide

### 1. Study the Drone's Calibration Spec

Before writing code, collect:

- **Band layout**: Which spectral bands does the camera produce? (e.g., Blue, Green, Red, RedEdge, NIR)
- **XMP namespace**: What XMP tags does the camera embed? Check with `exiftool -X sample_image.tif`
- **Calibration parameters**: Where does the camera store:
  - Vignetting coefficients (polynomial model)
  - Lens distortion (dewarp / intrinsics)
  - Black level / dark current
  - Sensor gain, exposure time
  - Irradiance / sun sensor data
  - Band-to-band alignment (homography)
- **File naming convention**: How are bands identified in filenames? (e.g., `_NIR`, `_RED`, suffix patterns)

### 2. Add Band Detection Support

Edit `shared/band_detection/models.py`:

```python
# 1. Add manufacturer enum if new
class DroneManufacturer(str, Enum):
    DJI = "dji"
    MICASENSE = "micasense"
    PARROT = "parrot"
    SENTERA = "sentera"  # <-- NEW
    UNKNOWN = "unknown"


# 2. Add band name mapping for the drone
SENTERA_BAND_NAME_MAP: dict[str, BandType] = {
    "Blue": BandType.BLUE,
    "Green": BandType.GREEN,
    "Red": BandType.RED,
    "NIR": BandType.NIR,
    "RedEdge": BandType.RED_EDGE,
}

# 3. Add filename patterns if the camera uses them
SENTERA_FILENAME_BAND_PATTERNS: dict[str, BandType] = {
    "_B": BandType.BLUE,
    "_G": BandType.GREEN,
    "_R": BandType.RED,
    "_N": BandType.NIR,
    "_RE": BandType.RED_EDGE,
}
```

Then edit `shared/band_detection/band_classifier.py` to use the new maps in the
`_classify_from_xmp_metadata()` and `_classify_from_filename()` methods. Add the
manufacturer's XMP namespace URI to the detection logic.

### 3. Create the Calibrator Class

Create a new file: `services/radiometric_calibration/app/core/services/sentera_calibration.py`

```python
"""Sentera multispectral image processor."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from infrastructure.logging import get_logger
from shared.band_detection.metadata_reader import extract_all_metadata

from .base_calibrator import BaseDroneCalibrator
from .interfaces import CalibrationMetadata

logger = get_logger(__name__)

SENTERA_BANDS = ["Blue", "Green", "Red", "RedEdge", "NIR"]


class SenteraImageProcessor(BaseDroneCalibrator):
    """
    Sentera multispectral image processor.

    Implements extract_calibration_metadata() to parse Sentera-specific
    XMP/EXIF fields and map them to the universal CalibrationMetadata
    dataclass used by BaseDroneCalibrator's correction algorithms.
    """

    def get_supported_bands(self) -> list[str]:
        """Return the spectral bands this processor handles."""
        return list(SENTERA_BANDS)

    def extract_calibration_metadata(
        self, image_path: str | Path
    ) -> CalibrationMetadata:
        """
        Extract Sentera-specific calibration metadata from XMP + EXIF.

        Args:
            image_path: Path to a single band image file.

        Returns:
            CalibrationMetadata populated with sensor parameters.
        """
        path = Path(image_path)
        raw_meta = extract_all_metadata(path)

        # --- Parse vendor-specific XMP fields ---
        # Replace these with the actual Sentera XMP tag names:
        vignetting_str = raw_meta.get("Sentera:VignettingPolynomial", "")
        vignetting_coefficients = _parse_float_list(vignetting_str)

        black_level = _safe_float(raw_meta.get("EXIF:BlackLevel", 0)) or 0.0
        sensor_gain = _safe_float(raw_meta.get("EXIF:ISOSpeed", 100)) or 100.0
        exposure_us = _safe_float(raw_meta.get("EXIF:ExposureTime", 0.001))
        if exposure_us and exposure_us < 1:
            exposure_us *= 1_000_000

        irradiance = _safe_float(raw_meta.get("Sentera:Irradiance", 1.0)) or 1.0
        band_name = raw_meta.get("Sentera:BandName", "Unknown")
        bit_depth = int(_safe_float(raw_meta.get("EXIF:BitsPerSample", 16)) or 16)

        img = Image.open(path)
        width, height = img.size

        return CalibrationMetadata(
            band_name=band_name,
            sensor_gain=sensor_gain / 100.0,
            exposure_time_us=exposure_us or 1000.0,
            black_level=black_level,
            sensor_gain_adjustment=1.0,
            irradiance=irradiance,
            bit_depth=bit_depth,
            vignetting_coefficients=vignetting_coefficients,
            image_width=width,
            image_height=height,
            raw_metadata=raw_meta,
        )


def _parse_float_list(value: str) -> list[float]:
    """Parse a comma or space separated string of floats."""
    if not value:
        return []
    parts = value.replace(",", " ").split()
    result = []
    for p in parts:
        try:
            result.append(float(p))
        except ValueError:
            continue
    return result


def _safe_float(value: object) -> float | None:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
```

**The key method** is `extract_calibration_metadata()`. This is the only required
override — it reads vendor-specific XMP/EXIF tags and maps them into the universal
`CalibrationMetadata` dataclass. The base class then uses these parameters in its
shared `vignetting_correction()`, `distortion_correction()`, `calculate_reflectance()`
etc.

### 4. Register in the Factory

Edit `services/radiometric_calibration/app/core/services/factory.py`:

```python
from .sentera_calibration import SenteraImageProcessor

# 1. Add to DroneType enum
class DroneType(Enum):
    DJI_MAVIC_3M = "dji_mavic_3_m"
    DJI_P4_MULTISPECTRAL = "dji_p4_multispectral"
    DJI_PHANTOM_4_RTK = "dji_phantom_4_rtk"
    MICASENSE_REDEDGE = "micasense_rededge"
    MICASENSE_ALTUM = "micasense_altum"
    SENTERA_6X = "sentera_6x"  # <-- NEW


# 2. Add to _REGISTRY
_REGISTRY: dict[DroneType, type[IDroneImageProcessor]] = {
    # ... existing entries ...
    DroneType.SENTERA_6X: SenteraImageProcessor,
}

# 3. Add model name aliases
_MODEL_NAME_MAP: dict[str, DroneType] = {
    # ... existing entries ...
    "sentera 6x": DroneType.SENTERA_6X,
    "6x": DroneType.SENTERA_6X,
}
```

Also add the manufacturer fallback in `create_from_manufacturer()`:

```python
if mfr == "sentera":
    return cls.create(DroneType.SENTERA_6X)
```

### 5. Add Manufacturer to Band Detection

Edit `shared/band_detection/band_classifier.py` to recognise the new manufacturer
in `_classify_from_xmp_metadata()`:

```python
# Add the manufacturer's typical XMP namespace prefix
if "sentera" in make_lower:
    manufacturer = DroneManufacturer.SENTERA
```

### 6. Write Tests

Create `tests/unit/test_sentera_calibration.py` using `unittest.TestCase`:

```python
"""Unit tests for Sentera calibration pipeline."""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from services.radiometric_calibration.app.core.services.factory import (
    DroneImageProcessorFactory,
    DroneType,
)
from services.radiometric_calibration.app.core.services.sentera_calibration import (
    SenteraImageProcessor,
)


class TestSenteraFactory(unittest.TestCase):
    """Test factory registration for Sentera."""

    def test_create_from_drone_type(self):
        """Factory creates SenteraImageProcessor for SENTERA_6X type."""
        processor = DroneImageProcessorFactory.create(DroneType.SENTERA_6X)
        self.assertIsInstance(processor, SenteraImageProcessor)

    def test_create_from_model_name(self):
        """Factory resolves 'sentera 6x' to correct processor."""
        processor = DroneImageProcessorFactory.create_from_model_name("Sentera 6X")
        self.assertIsInstance(processor, SenteraImageProcessor)

    def test_create_from_manufacturer(self):
        """Factory creates default Sentera processor from manufacturer."""
        processor = DroneImageProcessorFactory.create_from_manufacturer("sentera")
        self.assertIsInstance(processor, SenteraImageProcessor)


class TestSenteraMetadataExtraction(unittest.TestCase):
    """Test metadata extraction with mocked image data."""

    @patch("services.radiometric_calibration.app.core.services.sentera_calibration.extract_all_metadata")
    @patch("services.radiometric_calibration.app.core.services.sentera_calibration.Image")
    def test_extract_calibration_metadata(self, mock_pil, mock_extract):
        """Metadata is correctly parsed from Sentera XMP tags."""
        mock_extract.return_value = {
            "Sentera:VignettingPolynomial": "1.0 0.1 0.01 0.001",
            "EXIF:BlackLevel": "256",
            "EXIF:ISOSpeed": "200",
            "EXIF:ExposureTime": "0.002",
            "Sentera:Irradiance": "1.5",
            "Sentera:BandName": "NIR",
            "EXIF:BitsPerSample": "12",
        }
        mock_img = MagicMock()
        mock_img.size = (1280, 960)
        mock_pil.open.return_value = mock_img

        processor = SenteraImageProcessor()
        meta = processor.extract_calibration_metadata("/fake/img.tif")

        self.assertEqual(meta.band_name, "NIR")
        self.assertEqual(meta.bit_depth, 12)
        self.assertAlmostEqual(meta.irradiance, 1.5)
        self.assertEqual(len(meta.vignetting_coefficients), 4)


if __name__ == "__main__":
    unittest.main()
```

### 7. Test End-to-End

1. Place sample images from the new drone in a test directory
2. Run band detection: `python -c "from shared.band_detection import scan_dataset; print(scan_dataset('/path/to/samples').model_dump_json(indent=2))"`
3. Run calibration service with Docker: `docker-compose -f docker-compose.calibration.yml up`
4. Submit a job via API Gateway and verify the pipeline completes

---

## Checklist

- [ ] Studied drone's calibration specification and XMP namespace
- [ ] Added `DroneManufacturer` enum value in `shared/band_detection/models.py`
- [ ] Added band name map (e.g., `SENTERA_BAND_NAME_MAP`) in models.py
- [ ] Added filename patterns if applicable
- [ ] Updated `band_classifier.py` for manufacturer detection
- [ ] Created `<drone>_calibration.py` inheriting `BaseDroneCalibrator`
- [ ] Implemented `extract_calibration_metadata()` with vendor XMP parsing
- [ ] Implemented `get_supported_bands()`
- [ ] Added `DroneType` enum value in `factory.py`
- [ ] Registered processor class in `_REGISTRY`
- [ ] Added model name aliases in `_MODEL_NAME_MAP`
- [ ] Added manufacturer fallback in `create_from_manufacturer()`
- [ ] Written unit tests with `unittest.TestCase`
- [ ] Tested with real drone images end-to-end

---

## How the Base Class Helps

`BaseDroneCalibrator` provides these algorithms out of the box — you do **not** need
to re-implement them:

| Method | What it does |
|--------|-------------|
| `vignetting_correction()` | 6-coefficient polynomial light falloff correction |
| `distortion_correction()` | OpenCV `cv2.undistort` with camera matrix |
| `homography_alignment()` | Perspective warp for multi-band alignment |
| `exposure_alignment()` | ECC-based inter-band exposure matching |
| `calculate_camera_signal()` | Normalized signal (Eq. 9, DJI spec) |
| `calculate_reflectance_from_signal()` | Signal → reflectance using irradiance |
| `process_all_steps()` | Applies vignetting → distortion → alignment |
| `calculate_reflectance()` | End-to-end single band reflectance |
| `calculate_ndvi()` | NDVI from loaded NIR + Red bands |
| `calculate_ndre()` | NDRE from NIR + RedEdge |
| `calculate_gndvi()` | GNDVI from NIR + Green |

Your subclass only needs to implement **`extract_calibration_metadata()`** to parse
the vendor's specific XMP/EXIF tags into the universal `CalibrationMetadata` dataclass.
The base class algorithms consume `CalibrationMetadata` fields to apply corrections.

---

## Metadata Field Reference

The `CalibrationMetadata` dataclass fields that your `extract_calibration_metadata()`
should populate:

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `band_name` | str | Band name (e.g., "NIR", "Red") | Yes |
| `sensor_gain` | float | Normalized sensor gain | Yes |
| `exposure_time_us` | float | Exposure time in microseconds | Yes |
| `black_level` | float | Dark current / black level value | Yes |
| `sensor_gain_adjustment` | float | Additional gain factor | Optional |
| `irradiance` | float | Sun irradiance value | For reflectance |
| `bit_depth` | int | Image bit depth (8, 12, 16) | Yes |
| `vignetting_center_x/y` | float | Vignetting center offset | For vignetting |
| `vignetting_coefficients` | list[float] | Polynomial coefficients | For vignetting |
| `dewarp_params` | list[float] | Lens distortion parameters | For distortion |
| `homography_matrix` | list[float] | 3x3 alignment matrix | For alignment |
| `focal_length` | float | Camera focal length (mm) | Optional |
| `image_width/height` | int | Image dimensions | Yes |
| `raw_metadata` | dict | Full raw metadata dict | Recommended |
