"""Unit tests for SFM services: ColmapService, OpenSFMService, ServiceFactory, entities."""
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

sys.modules.setdefault("pycolmap", MagicMock())
sys.modules.setdefault("psygnal", MagicMock())

from services.sfm.app.core.services.service_factory import ServiceFactory
from services.sfm.app.core.services.colmap_service import ColmapSettings
from services.sfm.app.core.services.opensfm_service import OpenSfMSettings, OpenSFMService


class TestServiceFactory(unittest.TestCase):
    """Tests for ServiceFactory."""

    def test_available_services(self):
        self.assertIn("opensfm", ServiceFactory.services)
        self.assertIn("colmap", ServiceFactory.services)

    def test_create_colmap(self):
        mock_cls = MagicMock()
        with patch.dict(ServiceFactory.services, {"colmap": mock_cls}):
            ServiceFactory.create_service("colmap", {})
        mock_cls.assert_called_once_with({})

    def test_create_opensfm(self):
        mock_cls = MagicMock()
        with patch.dict(ServiceFactory.services, {"opensfm": mock_cls}):
            ServiceFactory.create_service("opensfm", {})
        mock_cls.assert_called_once_with({})

    def test_create_unknown(self):
        with self.assertRaises(ValueError) as ctx:
            ServiceFactory.create_service("unknown_engine", {})
        self.assertIn("not found", str(ctx.exception))


class TestColmapSettings(unittest.TestCase):
    """Tests for ColmapSettings."""

    def test_defaults(self):
        s = ColmapSettings(_env_file=None)
        self.assertEqual(s.feature_type, "sift")
        self.assertEqual(s.matcher_type, "sequential")
        self.assertEqual(s.camera_model, "OPENCV")
        self.assertTrue(s.single_camera)
        self.assertEqual(s.sift_max_num_features, 16384)
        self.assertTrue(s.feature_extraction_use_gpu)

    def test_matching_defaults(self):
        s = ColmapSettings(_env_file=None)
        self.assertEqual(s.sequential_overlap, 25)
        self.assertTrue(s.matching_guided_matching)
        self.assertEqual(s.matching_max_ratio, 0.75)

    def test_mapper_defaults(self):
        s = ColmapSettings(_env_file=None)
        self.assertEqual(s.glomap_output_format, "bin")
        self.assertTrue(s.mapper_ba_refine_focal_length)
        self.assertFalse(s.mapper_multiple_models)

    def test_dense_defaults(self):
        s = ColmapSettings(_env_file=None)
        self.assertEqual(s.patch_match_window_radius, 5)
        self.assertTrue(s.patch_match_geom_consistency)
        self.assertEqual(s.fusion_input_type, "photometric")


class TestOpenSfMSettings(unittest.TestCase):
    """Tests for OpenSfMSettings."""

    def test_defaults(self):
        s = OpenSfMSettings(_env_file=None)
        self.assertEqual(s.dataset_mounting_path, Path("/data/"))
        self.assertEqual(s.docker_image_name, "opensfm:latest")


class TestOpenSFMService(unittest.TestCase):
    """Tests for OpenSFMService."""

    def test_init_no_settings(self):
        svc = OpenSFMService()
        self.assertIsNotNone(svc.settings)

    def test_init_custom_settings(self):
        svc = OpenSFMService({"docker_image_name": "opensfm:custom"})
        self.assertEqual(svc.settings.docker_image_name, "opensfm:custom")

    @patch("services.sfm.app.core.services.opensfm_service.OpenSFMService._run_command")
    def test_extract_metadata(self, mock_run):
        svc = OpenSFMService()
        svc.extract_metadata("test-container")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("extract_metadata", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.OpenSFMService._run_command")
    def test_extract_features(self, mock_run):
        svc = OpenSFMService()
        svc.extract_features("test-container")
        mock_run.assert_called_once()
        self.assertIn("detect_features", mock_run.call_args[0][0])

    @patch("services.sfm.app.core.services.opensfm_service.OpenSFMService._run_command")
    def test_match_features(self, mock_run):
        svc = OpenSFMService()
        svc.match_features("test-container")
        self.assertIn("match_features", mock_run.call_args[0][0])

    @patch("services.sfm.app.core.services.opensfm_service.OpenSFMService._run_command")
    def test_create_tracks(self, mock_run):
        svc = OpenSFMService()
        svc.create_tracks("test-container")
        self.assertIn("create_tracks", mock_run.call_args[0][0])

    @patch("services.sfm.app.core.services.opensfm_service.OpenSFMService._run_command")
    def test_create_rig(self, mock_run):
        svc = OpenSFMService()
        svc.create_rig("test-container")
        self.assertIn("create_rig", mock_run.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
