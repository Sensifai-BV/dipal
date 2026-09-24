"""Unit tests for OpenSFMService."""
import sys
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))
sys.modules.setdefault("psygnal", MagicMock())

from services.sfm.app.core.services.opensfm_service import OpenSFMService, OpenSfMSettings


class TestOpenSfMSettings(unittest.TestCase):
    """Tests for OpenSfMSettings."""

    def test_defaults(self):
        s = OpenSfMSettings(_env_file=None)
        self.assertEqual(s.dataset_mounting_path, Path("/data/"))
        self.assertEqual(s.docker_image_name, "opensfm:latest")


class TestOpenSFMServiceInit(unittest.TestCase):
    """Tests for OpenSFMService initialization."""

    def test_default_init(self):
        svc = OpenSFMService({"_env_file": None})
        self.assertIsNotNone(svc)
        self.assertEqual(svc.settings.dataset_mounting_path, Path("/data/"))

    def test_custom_settings(self):
        svc = OpenSFMService({"_env_file": None, "docker_image_name": "custom:v1"})
        self.assertEqual(svc.settings.docker_image_name, "custom:v1")


class TestOpenSFMServiceCommands(unittest.TestCase):
    """Tests for OpenSFMService docker exec commands."""

    def setUp(self):
        self.svc = OpenSFMService({"_env_file": None})
        self.container = "test_container_abc"

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_extract_metadata(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.extract_metadata(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("extract_metadata", cmd)
        self.assertIn("docker", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_extract_features(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.extract_features(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("detect_features", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_match_features(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.match_features(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("match_features", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_create_tracks(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.create_tracks(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("create_tracks", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_create_rig(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.create_rig(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("create_rig", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_compute_reconstruct(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.compute_reconstruct(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("reconstruct", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_reconstruct_from_prior(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.reconstruct_from_prior(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("reconstruct_from_prior", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_bundle_reconstruction(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.bundle_reconstruction(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("bundle", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_mesh(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.mesh(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("mesh", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_undistort(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.undistort(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("undistort", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_compute_depthmaps(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.compute_depthmaps(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("compute_depthmaps", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_compute_statistics(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.compute_statistics(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("compute_statistics", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_export_report(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.export_report(self.container)
        cmd = mock_run.call_args[0][0]
        self.assertIn("export_report", cmd)


class TestOpenSFMServiceRunCommand(unittest.TestCase):
    """Tests for _run_command."""

    def setUp(self):
        self.svc = OpenSFMService({"_env_file": None})

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="output", stderr="", returncode=0)
        result = self.svc._run_command(["echo", "hello"], cwd=Path("/tmp"))
        self.assertEqual(result, "output")

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_called_process_error(self, mock_run):
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "docker", stderr="fail")
        with self.assertRaises(RuntimeError):
            self.svc._run_command(["docker", "exec"], cwd=Path("/tmp"))

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_docker_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        with self.assertRaises(RuntimeError):
            self.svc._run_command(["docker", "exec"], cwd=Path("/tmp"))


class TestOpenSFMServiceLifecycle(unittest.TestCase):
    """Tests for start, stop, clean."""

    def setUp(self):
        self.svc = OpenSFMService({"_env_file": None})
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_start_returns_container_name(self, mock_run):
        mock_run.return_value = MagicMock(stdout="containerid", stderr="", returncode=0)
        name = self.svc.start(self.tmpdir)
        self.assertIn("OpenSFMService", name)

    def test_start_relative_path_raises(self):
        with self.assertRaises(ValueError):
            self.svc.start(Path("relative/path"))

    def test_start_nonexistent_path_raises(self):
        with self.assertRaises(ValueError):
            self.svc.start(Path("/tmp/nonexistent_xyz_12345"))

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_stop(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.stop("test_container")
        cmd = mock_run.call_args[0][0]
        self.assertIn("stop", cmd)

    @patch("services.sfm.app.core.services.opensfm_service.subprocess.run")
    def test_clean(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        self.svc.clean("test_container")
        cmd = mock_run.call_args[0][0]
        self.assertIn("rm", cmd)


if __name__ == "__main__":
    unittest.main()
