"""Extended unit tests for ColmapService — remaining pipeline methods."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

sys.modules.setdefault("pycolmap", MagicMock())
sys.modules.setdefault("psygnal", MagicMock())

from services.sfm.app.core.services.colmap_service import ColmapService


def _make_service():
    """Create ColmapService with a temp workspace."""
    tmpdir = Path(tempfile.mkdtemp())
    ws = tmpdir / "workspace"
    ws.mkdir()
    (ws / "colmap" / "sparse" / "0").mkdir(parents=True)
    (ws / "colmap" / "dense").mkdir(parents=True)
    svc = ColmapService({"_env_file": None})
    svc._projects["proj1"] = ws
    return svc, ws, tmpdir


class TestMatchFeaturesMatchers(unittest.TestCase):
    """Tests for match_features with different matcher types."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch.object(ColmapService, "_run_command")
    def test_spatial_matcher(self, mock_cmd):
        self.svc.settings.matcher_type = "spatial"
        self.svc.match_features("proj1")
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("spatial_matcher", cmd)

    @patch.object(ColmapService, "_run_command")
    def test_exhaustive_matcher(self, mock_cmd):
        self.svc.settings.matcher_type = "exhaustive"
        self.svc.match_features("proj1")
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("exhaustive_matcher", cmd)

    @patch.object(ColmapService, "_run_command")
    def test_vocab_tree_matcher(self, mock_cmd):
        self.svc.settings.matcher_type = "vocab_tree"
        self.svc.match_features("proj1")
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("vocab_tree_matcher", cmd)

    @patch.object(ColmapService, "_run_command")
    def test_unknown_matcher_defaults_sequential(self, mock_cmd):
        self.svc.settings.matcher_type = "unknown_type"
        self.svc.match_features("proj1")
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("sequential_matcher", cmd)

    @patch.object(ColmapService, "_run_command")
    def test_match_features_error(self, mock_cmd):
        mock_cmd.side_effect = RuntimeError("fail")
        with self.assertRaises(RuntimeError):
            self.svc.match_features("proj1")


class TestCreateTracksAndRig(unittest.TestCase):
    """Tests for create_tracks and create_rig (no-ops)."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_tracks(self):
        self.svc.create_tracks("proj1")

    def test_create_rig(self):
        self.svc.create_rig("proj1")


class TestComputeReconstruct(unittest.TestCase):
    """Tests for compute_reconstruct (glomap)."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch.object(ColmapService, "_run_command")
    def test_success(self, mock_cmd):
        self.svc.compute_reconstruct("proj1")
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("glomap", cmd)
        self.assertIn("mapper", cmd)

    @patch.object(ColmapService, "_run_command")
    def test_error(self, mock_cmd):
        mock_cmd.side_effect = RuntimeError("fail")
        with self.assertRaises(RuntimeError):
            self.svc.compute_reconstruct("proj1")


class TestReconstructFromPrior(unittest.TestCase):
    """Tests for reconstruct_from_prior (placeholder)."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_placeholder(self):
        self.svc.reconstruct_from_prior("proj1")


class TestBundleReconstruction(unittest.TestCase):
    """Tests for bundle_reconstruction."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch.object(ColmapService, "_run_command")
    def test_success(self, mock_cmd):
        self.svc.bundle_reconstruction("proj1")
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("bundle_adjuster", cmd)

    @patch.object(ColmapService, "_run_command")
    def test_error(self, mock_cmd):
        mock_cmd.side_effect = RuntimeError("bundle fail")
        with self.assertRaises(RuntimeError):
            self.svc.bundle_reconstruction("proj1")


class TestMesh(unittest.TestCase):
    """Tests for mesh generation."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service()
        self._write_fused_ply()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_fused_ply(self):
        """Create a fused.ply with enough vertices to pass the meshing guard."""
        dense = self.svc._get_dense_path("proj1")
        dense.mkdir(parents=True, exist_ok=True)
        n = max(self.svc.settings.mesh_min_points + 10, 20)
        header = (
            "ply\nformat ascii 1.0\n"
            f"element vertex {n}\n"
            "property float x\nproperty float y\nproperty float z\n"
            "end_header\n"
        )
        body = "".join(f"{i}.0 {i}.0 {i}.0\n" for i in range(n))
        (dense / "fused.ply").write_text(header + body)

    @patch.object(ColmapService, "_run_command")
    def test_success(self, mock_cmd):
        self.svc.mesh("proj1")
        # mesh() may run several commands (model_transformer, pdal, poisson_mesher);
        # assert poisson_mesher appears in at least one invocation.
        all_cmds = [c.args[0] for c in mock_cmd.call_args_list]
        self.assertTrue(
            any("poisson_mesher" in cmd for cmd in all_cmds),
            f"poisson_mesher not invoked; calls={all_cmds}",
        )

    @patch.object(ColmapService, "_run_command")
    def test_error(self, mock_cmd):
        mock_cmd.side_effect = RuntimeError("mesh fail")
        with self.assertRaises(RuntimeError):
            self.svc.mesh("proj1")


class TestUndistort(unittest.TestCase):
    """Tests for image undistortion."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch.object(ColmapService, "_run_command")
    def test_success(self, mock_cmd):
        self.svc.undistort("proj1")
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("image_undistorter", cmd)

    @patch.object(ColmapService, "_run_command")
    def test_error(self, mock_cmd):
        mock_cmd.side_effect = RuntimeError("undistort fail")
        with self.assertRaises(RuntimeError):
            self.svc.undistort("proj1")


class TestComputeDepthmaps(unittest.TestCase):
    """Tests for compute_depthmaps (patch_match + fusion)."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch.object(ColmapService, "_run_command")
    def test_success(self, mock_cmd):
        self.svc.compute_depthmaps("proj1")
        self.assertEqual(mock_cmd.call_count, 2)
        first_cmd = mock_cmd.call_args_list[0][0][0]
        second_cmd = mock_cmd.call_args_list[1][0][0]
        self.assertIn("patch_match_stereo", first_cmd)
        self.assertIn("stereo_fusion", second_cmd)

    @patch.object(ColmapService, "_run_command")
    def test_error(self, mock_cmd):
        mock_cmd.side_effect = RuntimeError("depthmap fail")
        with self.assertRaises(RuntimeError):
            self.svc.compute_depthmaps("proj1")


class TestComputeStatistics(unittest.TestCase):
    """Tests for compute_statistics."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.sfm.app.core.services.colmap_service.pycolmap")
    def test_success(self, mock_pycolmap):
        mock_recon = MagicMock()
        mock_recon.cameras = {1: "cam"}
        mock_recon.images = {1: "img", 2: "img2"}
        mock_recon.points3D = {1: "pt"}
        mock_recon.num_reg_images.return_value = 2
        mock_recon.compute_mean_track_length.return_value = 3.5
        mock_recon.compute_mean_observations_per_reg_image.return_value = 100.0
        mock_recon.compute_mean_reprojection_error.return_value = 0.5
        mock_pycolmap.Reconstruction.return_value = mock_recon

        self.svc.compute_statistics("proj1")
        stats_file = self.ws / "statistics.json"
        self.assertTrue(stats_file.exists())
        stats = json.loads(stats_file.read_text())
        self.assertEqual(stats["num_cameras"], 1)
        self.assertEqual(stats["num_points3D"], 1)

    @patch("services.sfm.app.core.services.colmap_service.pycolmap")
    def test_error(self, mock_pycolmap):
        mock_pycolmap.Reconstruction.side_effect = RuntimeError("load fail")
        with self.assertRaises(RuntimeError):
            self.svc.compute_statistics("proj1")


class TestExportReport(unittest.TestCase):
    """Tests for export_report."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.sfm.app.core.services.colmap_service.pycolmap")
    def test_success(self, mock_pycolmap):
        mock_recon = MagicMock()
        mock_cam_model = type("CameraModel", (), {"name": "SIMPLE_RADIAL"})()
        mock_recon.cameras = {1: MagicMock(model=mock_cam_model)}
        mock_recon.images = {1: "img"}
        mock_recon.points3D = {1: "pt"}
        mock_recon.num_reg_images.return_value = 1
        mock_pycolmap.Reconstruction.return_value = mock_recon

        self.svc.export_report("proj1")
        report_dir = self.ws / "report"
        self.assertTrue(report_dir.exists())
        self.assertTrue((report_dir / "summary.json").exists())

    @patch("services.sfm.app.core.services.colmap_service.pycolmap")
    def test_error(self, mock_pycolmap):
        mock_pycolmap.Reconstruction.side_effect = RuntimeError("load fail")
        with self.assertRaises(RuntimeError):
            self.svc.export_report("proj1")


class TestColmapLifecycle(unittest.TestCase):
    """Tests for start, stop, clean."""

    def setUp(self):
        self.svc = ColmapService({"_env_file": None})
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_start_success(self):
        pid = self.svc.start(self.tmpdir)
        self.assertIn("ColmapService", pid)
        self.assertIn(pid, self.svc._projects)

    def test_start_relative_raises(self):
        with self.assertRaises(ValueError):
            self.svc.start(Path("relative"))

    def test_start_nonexistent_raises(self):
        with self.assertRaises(ValueError):
            self.svc.start(Path("/tmp/nonexistent_xyz_98765"))

    def test_stop_noop(self):
        pid = self.svc.start(self.tmpdir)
        self.svc.stop(pid)
        self.assertIn(pid, self.svc._projects)

    def test_clean_removes_tracking(self):
        pid = self.svc.start(self.tmpdir)
        self.svc.clean(pid)
        self.assertNotIn(pid, self.svc._projects)

    def test_clean_unknown_project(self):
        self.svc.clean("nonexistent")


if __name__ == "__main__":
    unittest.main()
