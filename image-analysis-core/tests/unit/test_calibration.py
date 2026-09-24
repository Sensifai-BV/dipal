"""Unit tests for calibration factory, interfaces, and base calibrator."""
import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

import numpy as np

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from services.radiometric_calibration.app.core.services.interfaces import (
    CalibrationMetadata,
    CalibrationResult,
    DatasetCalibrationResult,
)
from services.radiometric_calibration.app.core.services.factory import (
    DroneType,
    DroneImageProcessorFactory,
    _MODEL_NAME_MAP,
    _REGISTRY,
)


class TestCalibrationMetadata(unittest.TestCase):
    """Tests for CalibrationMetadata dataclass."""

    def test_defaults(self):
        meta = CalibrationMetadata(band_name="red")
        self.assertEqual(meta.band_name, "red")
        self.assertEqual(meta.sensor_gain, 1.0)
        self.assertEqual(meta.exposure_time_us, 1000.0)
        self.assertEqual(meta.black_level, 3200.0)
        self.assertEqual(meta.bit_depth, 16)
        self.assertIsNone(meta.vignetting_center_x)
        self.assertEqual(meta.vignetting_coefficients, [])
        self.assertEqual(meta.dewarp_params, [])

    def test_custom_values(self):
        meta = CalibrationMetadata(
            band_name="nir",
            sensor_gain=2.5,
            exposure_time_us=5000.0,
            irradiance=1.2,
            vignetting_coefficients=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        )
        self.assertEqual(meta.sensor_gain, 2.5)
        self.assertEqual(len(meta.vignetting_coefficients), 6)


class TestCalibrationResult(unittest.TestCase):
    """Tests for CalibrationResult dataclass."""

    def test_success(self):
        result = CalibrationResult(
            band_name="red",
            input_path=Path("/in/img.tif"),
            output_path=Path("/out/img.tif"),
            success=True,
        )
        self.assertTrue(result.success)
        self.assertIsNone(result.error)

    def test_failure(self):
        result = CalibrationResult(
            band_name="nir",
            input_path=Path("/in/img.tif"),
            output_path=Path("/out/img.tif"),
            success=False,
            error="Missing metadata",
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Missing metadata")


class TestDatasetCalibrationResult(unittest.TestCase):
    """Tests for DatasetCalibrationResult dataclass."""

    def test_empty_success(self):
        result = DatasetCalibrationResult(
            dataset_id="ds1", job_id="j1", total_processed=5, total_failed=0
        )
        self.assertTrue(result.success)
        self.assertTrue(result.partial_success)

    def test_partial(self):
        result = DatasetCalibrationResult(
            dataset_id="ds1", job_id="j1", total_processed=3, total_failed=2
        )
        self.assertFalse(result.success)
        self.assertTrue(result.partial_success)

    def test_total_failure(self):
        result = DatasetCalibrationResult(
            dataset_id="ds1", job_id="j1", total_processed=0, total_failed=5
        )
        self.assertFalse(result.success)
        self.assertFalse(result.partial_success)

    def test_band_results(self):
        r = CalibrationResult(
            band_name="red",
            input_path=Path("/in/r.tif"),
            output_path=Path("/out/r.tif"),
        )
        result = DatasetCalibrationResult(
            dataset_id="ds1",
            job_id="j1",
            band_results={"red": [r]},
            total_processed=1,
        )
        self.assertIn("red", result.band_results)
        self.assertEqual(len(result.band_results["red"]), 1)


class TestDroneType(unittest.TestCase):
    """Tests for DroneType enum."""

    def test_values(self):
        self.assertEqual(DroneType.DJI_MAVIC_3M.value, "dji_mavic_3_m")
        self.assertEqual(DroneType.MICASENSE_REDEDGE.value, "micasense_rededge")
        self.assertEqual(DroneType.MICASENSE_ALTUM.value, "micasense_altum")

    def test_all_types_in_registry(self):
        for dt in DroneType:
            self.assertIn(dt, _REGISTRY)


class TestDroneImageProcessorFactory(unittest.TestCase):
    """Tests for DroneImageProcessorFactory."""

    @patch("services.radiometric_calibration.app.core.services.factory._REGISTRY")
    def test_create_known_type(self, mock_registry):
        mock_cls = MagicMock()
        mock_registry.get.return_value = mock_cls
        processor = DroneImageProcessorFactory.create(DroneType.DJI_MAVIC_3M)
        mock_cls.assert_called_once()

    def test_create_unknown_type(self):
        with patch(
            "services.radiometric_calibration.app.core.services.factory._REGISTRY",
            {},
        ):
            with self.assertRaises(ValueError):
                DroneImageProcessorFactory.create(DroneType.DJI_MAVIC_3M)

    @patch(
        "services.radiometric_calibration.app.core.services.factory.DroneImageProcessorFactory.create"
    )
    def test_create_from_model_name_dji(self, mock_create):
        DroneImageProcessorFactory.create_from_model_name("Mavic 3M")
        mock_create.assert_called_once_with(DroneType.DJI_MAVIC_3M)

    @patch(
        "services.radiometric_calibration.app.core.services.factory.DroneImageProcessorFactory.create"
    )
    def test_create_from_model_name_micasense(self, mock_create):
        DroneImageProcessorFactory.create_from_model_name("RedEdge-MX")
        mock_create.assert_called_once_with(DroneType.MICASENSE_REDEDGE)

    def test_create_from_model_name_unknown(self):
        with self.assertRaises(ValueError) as ctx:
            DroneImageProcessorFactory.create_from_model_name("Unknown Drone XYZ")
        self.assertIn("Cannot determine", str(ctx.exception))

    @patch(
        "services.radiometric_calibration.app.core.services.factory.DroneImageProcessorFactory.create"
    )
    def test_create_from_manufacturer_dji(self, mock_create):
        DroneImageProcessorFactory.create_from_manufacturer("dji")
        mock_create.assert_called_once_with(DroneType.DJI_MAVIC_3M)

    @patch(
        "services.radiometric_calibration.app.core.services.factory.DroneImageProcessorFactory.create"
    )
    def test_create_from_manufacturer_micasense(self, mock_create):
        DroneImageProcessorFactory.create_from_manufacturer("micasense")
        mock_create.assert_called_once_with(DroneType.MICASENSE_REDEDGE)

    @patch.object(DroneImageProcessorFactory, "create")
    def test_create_from_manufacturer_parrot(self, mock_create):
        DroneImageProcessorFactory.create_from_manufacturer("parrot")
        mock_create.assert_called_once_with(DroneType.DJI_MAVIC_3M)

    def test_create_from_manufacturer_unknown(self):
        with self.assertRaises(ValueError):
            DroneImageProcessorFactory.create_from_manufacturer("unknown_brand")

    def test_model_name_map_coverage(self):
        for name, dt in _MODEL_NAME_MAP.items():
            self.assertIsInstance(dt, DroneType)


class TestBaseCalibratorCorrections(unittest.TestCase):
    """Tests for base calibrator vignetting and distortion correction math."""

    def test_vignetting_no_coefficients(self):
        from services.radiometric_calibration.app.core.services.base_calibrator import (
            BaseDroneCalibrator,
        )

        class DummyCalibrator(BaseDroneCalibrator):
            def extract_calibration_metadata(self, image_path):
                return CalibrationMetadata(band_name="test")

            def get_supported_bands(self):
                return ["red"]

            def process_band(self, band_name):
                pass

            def process_all_bands(self):
                pass

        cal = DummyCalibrator()
        img = np.ones((10, 10), dtype=np.float64) * 100.0
        meta = CalibrationMetadata(band_name="test", vignetting_coefficients=[])
        result = cal.vignetting_correction(img, meta)
        np.testing.assert_array_equal(result, img)

    def test_vignetting_with_coefficients(self):
        from services.radiometric_calibration.app.core.services.base_calibrator import (
            BaseDroneCalibrator,
        )

        class DummyCalibrator(BaseDroneCalibrator):
            def extract_calibration_metadata(self, image_path):
                return CalibrationMetadata(band_name="test")

            def get_supported_bands(self):
                return ["red"]

            def process_band(self, band_name):
                pass

            def process_all_bands(self):
                pass

        cal = DummyCalibrator()
        img = np.ones((10, 10), dtype=np.float64) * 100.0
        meta = CalibrationMetadata(
            band_name="test",
            vignetting_coefficients=[0.0, 0.0, 0.0, 0.0, 0.0, 0.001],
            vignetting_center_x=5.0,
            vignetting_center_y=5.0,
        )
        result = cal.vignetting_correction(img, meta)
        self.assertEqual(result.shape, (10, 10))
        self.assertEqual(result[5, 5], 100.0)

    def test_distortion_no_params(self):
        from services.radiometric_calibration.app.core.services.base_calibrator import (
            BaseDroneCalibrator,
        )

        class DummyCalibrator(BaseDroneCalibrator):
            def extract_calibration_metadata(self, image_path):
                return CalibrationMetadata(band_name="test")

            def get_supported_bands(self):
                return ["red"]

            def process_band(self, band_name):
                pass

            def process_all_bands(self):
                pass

        cal = DummyCalibrator()
        img = np.ones((10, 10, 3), dtype=np.uint8) * 128
        meta = CalibrationMetadata(band_name="test", dewarp_params=[])
        result = cal.distortion_correction(img, meta)
        np.testing.assert_array_equal(result, img)

    def test_get_corrected_image_none(self):
        from services.radiometric_calibration.app.core.services.base_calibrator import (
            BaseDroneCalibrator,
        )

        class DummyCalibrator(BaseDroneCalibrator):
            def extract_calibration_metadata(self, image_path):
                return CalibrationMetadata(band_name="test")

            def get_supported_bands(self):
                return ["red"]

            def process_band(self, band_name):
                pass

            def process_all_bands(self):
                pass

        cal = DummyCalibrator()
        self.assertIsNone(cal.get_corrected_image("nonexistent"))

    def test_get_corrected_image_exists(self):
        from services.radiometric_calibration.app.core.services.base_calibrator import (
            BaseDroneCalibrator,
        )

        class DummyCalibrator(BaseDroneCalibrator):
            def extract_calibration_metadata(self, image_path):
                return CalibrationMetadata(band_name="test")

            def get_supported_bands(self):
                return ["red"]

            def process_band(self, band_name):
                pass

            def process_all_bands(self):
                pass

        cal = DummyCalibrator()
        cal.band_data["red"] = {"corrected_image": np.array([1, 2, 3])}
        result = cal.get_corrected_image("red")
        np.testing.assert_array_equal(result, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
