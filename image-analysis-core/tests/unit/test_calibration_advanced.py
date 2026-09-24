"""Unit tests for base_calibrator advanced methods and vendor-specific calibrators."""
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

import numpy as np

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from services.radiometric_calibration.app.core.services.base_calibrator import (
    BaseDroneCalibrator,
)
from services.radiometric_calibration.app.core.services.interfaces import (
    CalibrationMetadata,
)
from services.radiometric_calibration.app.core.services.mavic_m3m_calibration import (
    Mavic3MImageProcessor,
    _safe_float as dji_safe_float,
    DJI_MULTISPECTRAL_BANDS,
)
from services.radiometric_calibration.app.core.services.micasense_calibration import (
    MicaSenseImageProcessor,
    _safe_float as ms_safe_float,
    _normalise_micasense_band,
    _parse_float_list,
    MICASENSE_BANDS,
)


class DummyCalibrator(BaseDroneCalibrator):
    """Concrete subclass for testing base methods."""

    def get_supported_bands(self):
        return ["NIR", "Red", "Green", "RedEdge"]

    def extract_calibration_metadata(self, image_path):
        return CalibrationMetadata(band_name="Test")


class TestHomographyAlignment(unittest.TestCase):
    """Tests for homography_alignment."""

    def test_no_homography(self):
        cal = DummyCalibrator()
        img = np.ones((10, 10), dtype=np.float64)
        meta = CalibrationMetadata(band_name="Test", homography_matrix=[])
        result = cal.homography_alignment(img, meta)
        np.testing.assert_array_equal(result, img)

    @patch("services.radiometric_calibration.app.core.services.base_calibrator.cv2")
    def test_with_homography(self, mock_cv2):
        cal = DummyCalibrator()
        img = np.ones((10, 10), dtype=np.float64)
        mock_cv2.warpPerspective.return_value = img * 2
        meta = CalibrationMetadata(
            band_name="Test", homography_matrix=[1, 0, 0, 0, 1, 0, 0, 0, 1]
        )
        result = cal.homography_alignment(img, meta)
        mock_cv2.warpPerspective.assert_called_once()


class TestExposureAlignment(unittest.TestCase):
    """Tests for exposure_alignment."""

    @patch("services.radiometric_calibration.app.core.services.base_calibrator.cv2")
    def test_success(self, mock_cv2):
        cal = DummyCalibrator()
        ref = np.ones((10, 10), dtype=np.float64) * 100
        tgt = np.ones((10, 10), dtype=np.float64) * 80

        mock_cv2.normalize.return_value = np.ones((10, 10), dtype=np.uint8)
        mock_cv2.GaussianBlur.return_value = np.ones((10, 10), dtype=np.uint8)
        mock_cv2.MOTION_AFFINE = 2
        mock_cv2.TERM_CRITERIA_EPS = 1
        mock_cv2.TERM_CRITERIA_COUNT = 2
        mock_cv2.NORM_MINMAX = 32
        mock_cv2.INTER_LINEAR = 1
        mock_cv2.WARP_INVERSE_MAP = 16
        mock_cv2.findTransformECC.return_value = (0.9, np.eye(2, 3, dtype=np.float32))
        mock_cv2.warpAffine.return_value = tgt

        r, a = cal.exposure_alignment(ref, tgt)
        np.testing.assert_array_equal(r, ref)

    @patch("services.radiometric_calibration.app.core.services.base_calibrator.cv2")
    def test_ecc_failure_returns_original(self, mock_cv2):
        import cv2 as real_cv2

        cal = DummyCalibrator()
        ref = np.ones((10, 10), dtype=np.float64)
        tgt = np.ones((10, 10), dtype=np.float64) * 2

        mock_cv2.normalize.return_value = np.ones((10, 10), dtype=np.uint8)
        mock_cv2.GaussianBlur.return_value = np.ones((10, 10), dtype=np.uint8)
        mock_cv2.MOTION_AFFINE = 2
        mock_cv2.TERM_CRITERIA_EPS = 1
        mock_cv2.TERM_CRITERIA_COUNT = 2
        mock_cv2.NORM_MINMAX = 32
        mock_cv2.error = real_cv2.error
        mock_cv2.findTransformECC.side_effect = real_cv2.error("ECC failed")

        r, a = cal.exposure_alignment(ref, tgt)
        np.testing.assert_array_equal(a, tgt)


class TestCalculateCameraSignal(unittest.TestCase):
    """Tests for calculate_camera_signal."""

    def test_basic(self):
        cal = DummyCalibrator()
        img = np.ones((5, 5), dtype=np.float64) * 32768
        meta = CalibrationMetadata(
            band_name="NIR", bit_depth=16, black_level=3200, sensor_gain=1.0,
            exposure_time_us=1000.0,
        )
        signal = cal.calculate_camera_signal(img, meta)
        self.assertEqual(signal.shape, (5, 5))
        self.assertTrue(np.all(signal > 0))


class TestCalculateReflectanceFromSignal(unittest.TestCase):
    """Tests for calculate_reflectance_from_signal."""

    def test_basic(self):
        cal = DummyCalibrator()
        signal = np.ones((5, 5), dtype=np.float64) * 0.5
        meta = CalibrationMetadata(band_name="NIR", sensor_gain_adjustment=1.0, irradiance=1.0)
        ref = cal.calculate_reflectance_from_signal(signal, meta)
        self.assertTrue(np.all(ref >= 0))
        self.assertTrue(np.all(ref <= 1))


class TestProcessAllSteps(unittest.TestCase):
    """Tests for process_all_steps."""

    def test_band_not_loaded(self):
        cal = DummyCalibrator()
        with self.assertRaises(ValueError):
            cal.process_all_steps("missing")

    @patch("services.radiometric_calibration.app.core.services.base_calibrator.cv2")
    def test_with_loaded_band(self, mock_cv2):
        mock_cv2.undistort.side_effect = lambda img, *a, **k: img

        cal = DummyCalibrator()
        img = np.ones((10, 10), dtype=np.float64) * 100
        meta = CalibrationMetadata(
            band_name="Test",
            vignetting_coefficients=[0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
            vignetting_center_x=5, vignetting_center_y=5,
        )
        cal.band_data["test"] = {
            "image": img, "metadata": meta, "corrected_image": None, "image_path": "test.tif",
        }
        result = cal.process_all_steps("test")
        self.assertEqual(result.shape, (10, 10))
        self.assertIsNotNone(cal.band_data["test"]["corrected_image"])


class TestCalculateReflectance(unittest.TestCase):
    """Tests for calculate_reflectance."""

    def test_band_not_loaded(self):
        cal = DummyCalibrator()
        with self.assertRaises(ValueError):
            cal.calculate_reflectance("missing")

    @patch("services.radiometric_calibration.app.core.services.base_calibrator.cv2")
    def test_auto_process(self, mock_cv2):
        mock_cv2.undistort.side_effect = lambda img, *a, **k: img

        cal = DummyCalibrator()
        img = np.ones((5, 5), dtype=np.float64) * 30000
        meta = CalibrationMetadata(
            band_name="NIR", bit_depth=16, black_level=3200, sensor_gain=1.0,
            exposure_time_us=1000.0, sensor_gain_adjustment=1.0,
            irradiance=10.0,
        )
        cal.band_data["NIR"] = {
            "image": img, "metadata": meta, "corrected_image": None, "image_path": "nir.tif",
        }
        ref = cal.calculate_reflectance("NIR")
        self.assertTrue(np.all(ref >= 0))
        self.assertTrue(np.all(ref <= 1))


class TestVegetationIndices(unittest.TestCase):
    """Tests for vegetation index calculations."""

    @patch("services.radiometric_calibration.app.core.services.base_calibrator.cv2")
    def _setup_bands(self, cal, mock_cv2):
        mock_cv2.undistort.side_effect = lambda img, *a, **k: img
        mock_cv2.normalize.return_value = np.ones((5, 5), dtype=np.uint8)
        mock_cv2.GaussianBlur.return_value = np.ones((5, 5), dtype=np.uint8)
        mock_cv2.MOTION_AFFINE = 2
        mock_cv2.TERM_CRITERIA_EPS = 1
        mock_cv2.TERM_CRITERIA_COUNT = 2
        mock_cv2.NORM_MINMAX = 32
        mock_cv2.INTER_LINEAR = 1
        mock_cv2.WARP_INVERSE_MAP = 16
        mock_cv2.findTransformECC.return_value = (0.9, np.eye(2, 3, dtype=np.float32))
        mock_cv2.warpAffine.side_effect = lambda img, *a, **k: img

        for band_name, val in [("NIR", 40000), ("Red", 20000), ("Green", 25000), ("RedEdge", 22000)]:
            img = np.ones((5, 5), dtype=np.float64) * val
            meta = CalibrationMetadata(
                band_name=band_name, bit_depth=16, black_level=3200, sensor_gain=1.0,
                exposure_time_us=1000.0, sensor_gain_adjustment=1.0,
                irradiance=10.0,
            )
            cal.band_data[band_name] = {
                "image": img, "metadata": meta, "corrected_image": None, "image_path": f"{band_name}.tif",
            }

    def test_ensure_reflectance_missing_band(self):
        cal = DummyCalibrator()
        with self.assertRaises(ValueError):
            cal._ensure_reflectance("missing")

    def test_calculate_vegetation_indices_empty(self):
        cal = DummyCalibrator()
        indices = cal.calculate_vegetation_indices()
        self.assertEqual(indices, {})

    @patch("services.radiometric_calibration.app.core.services.base_calibrator.cv2")
    def test_calculate_vegetation_indices_all(self, mock_cv2):
        mock_cv2.undistort.side_effect = lambda img, *a, **k: img
        mock_cv2.normalize.return_value = np.ones((5, 5), dtype=np.uint8)
        mock_cv2.GaussianBlur.return_value = np.ones((5, 5), dtype=np.uint8)
        mock_cv2.MOTION_AFFINE = 2
        mock_cv2.TERM_CRITERIA_EPS = 1
        mock_cv2.TERM_CRITERIA_COUNT = 2
        mock_cv2.NORM_MINMAX = 32
        mock_cv2.INTER_LINEAR = 1
        mock_cv2.WARP_INVERSE_MAP = 16
        mock_cv2.findTransformECC.return_value = (0.9, np.eye(2, 3, dtype=np.float32))
        mock_cv2.warpAffine.side_effect = lambda img, *a, **k: img

        cal = DummyCalibrator()
        for band_name, val in [("NIR", 40000), ("Red", 20000), ("Green", 25000), ("RedEdge", 22000)]:
            img = np.ones((5, 5), dtype=np.float64) * val
            meta = CalibrationMetadata(
                band_name=band_name, bit_depth=16, black_level=3200, sensor_gain=1.0,
                exposure_time_us=1000.0, sensor_gain_adjustment=1.0,
                irradiance=10.0,
            )
            cal.band_data[band_name] = {
                "image": img, "metadata": meta, "corrected_image": None, "image_path": f"{band_name}.tif",
            }

        indices = cal.calculate_vegetation_indices()
        self.assertIn("ndvi", indices)
        self.assertIn("ndre", indices)
        self.assertIn("gndvi", indices)
        for name, arr in indices.items():
            self.assertTrue(np.all(arr >= -1))
            self.assertTrue(np.all(arr <= 1))


class TestMavic3MProcessor(unittest.TestCase):
    """Tests for Mavic3MImageProcessor."""

    def test_supported_bands(self):
        proc = Mavic3MImageProcessor()
        bands = proc.get_supported_bands()
        self.assertEqual(bands, DJI_MULTISPECTRAL_BANDS)

    @patch("services.radiometric_calibration.app.core.services.mavic_m3m_calibration.extract_all_metadata")
    @patch("services.radiometric_calibration.app.core.services.mavic_m3m_calibration.Image")
    def test_extract_calibration_metadata(self, mock_pil, mock_meta):
        mock_meta.return_value = {
            "BandName": "NIR",
            "VignettingData": "0.1,0.2,0.3,0.4,0.5,0.6",
            "DewarpData": "header;1.0,2.0,3.0,4.0,5.0",
            "CalibratedHMatrix": "1,0,0,0,1,0,0,0,1",
            "SensorGain": "2.0",
            "ExposureTime": "500.0",
            "BlackLevel": "4096",
            "SensorGainAdjustment": "1.1",
            "Irradiance": "5.0",
            "BitsPerSample": "12",
            "CalibratedOpticalCenterX": "320",
            "CalibratedOpticalCenterY": "240",
            "CalibratedFocalLength": "4.5",
        }
        mock_img = MagicMock()
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        mock_img.size = (640, 480)
        mock_pil.open.return_value = mock_img

        proc = Mavic3MImageProcessor()
        meta = proc.extract_calibration_metadata(Path("/fake/img.tif"))

        self.assertEqual(meta.band_name, "NIR")
        self.assertAlmostEqual(meta.sensor_gain, 2.0)
        self.assertEqual(len(meta.vignetting_coefficients), 6)
        self.assertEqual(len(meta.dewarp_params), 5)
        self.assertEqual(len(meta.homography_matrix), 9)

    @patch("services.radiometric_calibration.app.core.services.mavic_m3m_calibration.extract_all_metadata")
    @patch("services.radiometric_calibration.app.core.services.mavic_m3m_calibration.Image")
    def test_extract_metadata_empty_data(self, mock_pil, mock_meta):
        mock_meta.return_value = {}
        mock_img = MagicMock()
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        mock_img.size = (100, 100)
        mock_pil.open.return_value = mock_img

        proc = Mavic3MImageProcessor()
        meta = proc.extract_calibration_metadata(Path("/fake/img.tif"))
        self.assertEqual(meta.band_name, "Unknown")
        self.assertEqual(meta.vignetting_coefficients, [])

    def test_dji_safe_float(self):
        self.assertAlmostEqual(dji_safe_float("3.14"), 3.14)
        self.assertIsNone(dji_safe_float(None))
        self.assertIsNone(dji_safe_float("not_a_number"))


class TestMicaSenseProcessor(unittest.TestCase):
    """Tests for MicaSenseImageProcessor."""

    def test_supported_bands(self):
        proc = MicaSenseImageProcessor()
        self.assertEqual(proc.get_supported_bands(), MICASENSE_BANDS)

    @patch("services.radiometric_calibration.app.core.services.micasense_calibration.extract_all_metadata")
    @patch("services.radiometric_calibration.app.core.services.micasense_calibration.Image")
    def test_extract_calibration_metadata(self, mock_pil, mock_meta):
        mock_meta.return_value = {
            "BandName": "red edge",
            "VignettingPolynomial": "0.1,0.2,0.3,0.4,0.5,0.6",
            "VignettingCenter": "320,240",
            "BlackLevel": "4096",
            "ISOSpeed": "800",
            "ExposureTime": "0.001",
            "Irradiance": "5.0",
            "BandSensitivity": "0.9",
            "CentralWavelength": "717",
            "BitsPerSample": "12",
        }
        mock_img = MagicMock()
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        mock_img.size = (1280, 960)
        mock_pil.open.return_value = mock_img

        proc = MicaSenseImageProcessor()
        meta = proc.extract_calibration_metadata(Path("/fake/img.tif"))

        self.assertEqual(meta.band_name, "RedEdge")
        self.assertEqual(len(meta.vignetting_coefficients), 6)
        self.assertAlmostEqual(meta.vignetting_center_x, 320.0)
        self.assertAlmostEqual(meta.vignetting_center_y, 240.0)

    @patch("services.radiometric_calibration.app.core.services.micasense_calibration.extract_all_metadata")
    @patch("services.radiometric_calibration.app.core.services.micasense_calibration.Image")
    def test_extract_metadata_fallback_sensor_gain(self, mock_pil, mock_meta):
        mock_meta.return_value = {"SensorGain": "2.0"}
        mock_img = MagicMock()
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        mock_img.size = (100, 100)
        mock_pil.open.return_value = mock_img

        proc = MicaSenseImageProcessor()
        meta = proc.extract_calibration_metadata(Path("/fake/img.tif"))
        self.assertAlmostEqual(meta.sensor_gain, 2.0)


class TestMicaSenseHelpers(unittest.TestCase):
    """Tests for MicaSense helper functions."""

    def test_normalise_micasense_band(self):
        self.assertEqual(_normalise_micasense_band("blue"), "Blue")
        self.assertEqual(_normalise_micasense_band("green"), "Green")
        self.assertEqual(_normalise_micasense_band("red"), "Red")
        self.assertEqual(_normalise_micasense_band("red edge"), "RedEdge")
        self.assertEqual(_normalise_micasense_band("rededge"), "RedEdge")
        self.assertEqual(_normalise_micasense_band("nir"), "NIR")
        self.assertEqual(_normalise_micasense_band("near-ir"), "NIR")
        self.assertEqual(_normalise_micasense_band("lwir"), "Thermal")
        self.assertEqual(_normalise_micasense_band("Unknown"), "Unknown")

    def test_parse_float_list(self):
        self.assertEqual(_parse_float_list("1.0,2.0,3.0"), [1.0, 2.0, 3.0])
        self.assertEqual(_parse_float_list("1.0 2.0 3.0"), [1.0, 2.0, 3.0])
        self.assertEqual(_parse_float_list(""), [])
        self.assertEqual(_parse_float_list("not,numbers"), [])

    def test_ms_safe_float(self):
        self.assertAlmostEqual(ms_safe_float("3.14"), 3.14)
        self.assertIsNone(ms_safe_float(None))
        self.assertIsNone(ms_safe_float("text"))


if __name__ == "__main__":
    unittest.main()
