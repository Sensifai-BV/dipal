"""Unit tests for OrthomosaicPipeline."""
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
import sys

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from services.orthomosaic_generation.app.core.algorithms.orthomosaic_pipeline import (
    OrthomosaicPipeline,
)


class TestOrthomosaicPipeline(unittest.TestCase):
    """Tests for OrthomosaicPipeline."""

    def _make_pipeline(self):
        mock_service = MagicMock()
        mock_service.start.return_value = "proj1"
        mock_service.generate_dsm_from_pointcloud.return_value = Path("/tmp/dsm.tif")
        mock_service.generate_rgb_orthomosaic.return_value = Path("/tmp/ortho.tif")
        mock_service.fill_dsm_holes.return_value = None
        mock_service.generate_hillshade.return_value = Path("/tmp/hillshade.tif")
        mock_service.convert_to_cog.return_value = None
        mock_service.generate_multi_resolution_outputs.return_value = {"full": "/tmp/full.tif"}
        mock_service.generate_statistics.return_value = {
            "outputs": {
                "dsm": {"exists": True, "path": "/tmp/dsm.tif", "size_mb": 1.0, "width": 100, "height": 100},
            }
        }
        return OrthomosaicPipeline(mock_service), mock_service

    def test_init(self):
        mock_service = MagicMock()
        pipeline = OrthomosaicPipeline(mock_service)
        self.assertEqual(pipeline.service, mock_service)

    def test_run_pipeline_success(self):
        pipeline, svc = self._make_pipeline()
        result = pipeline.run_pipeline(Path("/data"))
        svc.start.assert_called_once_with(Path("/data"))
        svc.generate_dsm_from_pointcloud.assert_called_once_with("proj1")
        svc.generate_rgb_orthomosaic.assert_called_once_with("proj1")
        svc.fill_dsm_holes.assert_called_once()
        svc.generate_hillshade.assert_called_once()
        svc.convert_to_cog.assert_called_once()
        svc.stop.assert_called_once()
        svc.clean.assert_called_once()

    def test_run_pipeline_skip_cog(self):
        pipeline, svc = self._make_pipeline()
        pipeline.run_pipeline(Path("/data"), generate_cog=False)
        svc.convert_to_cog.assert_not_called()

    def test_run_pipeline_rgb_failure_continues(self):
        pipeline, svc = self._make_pipeline()
        svc.generate_rgb_orthomosaic.side_effect = RuntimeError("no color")
        result = pipeline.run_pipeline(Path("/data"))
        svc.fill_dsm_holes.assert_called_once()

    def test_run_pipeline_hillshade_failure_continues(self):
        pipeline, svc = self._make_pipeline()
        svc.generate_hillshade.side_effect = RuntimeError("fail")
        pipeline.run_pipeline(Path("/data"))
        svc.convert_to_cog.assert_called_once()

    def test_run_pipeline_multi_resolution_failure_continues(self):
        pipeline, svc = self._make_pipeline()
        svc.generate_multi_resolution_outputs.side_effect = RuntimeError("fail")
        pipeline.run_pipeline(Path("/data"))
        svc.generate_statistics.assert_called_once()

    def test_run_pipeline_fatal_error(self):
        pipeline, svc = self._make_pipeline()
        svc.generate_dsm_from_pointcloud.side_effect = RuntimeError("fatal")
        with self.assertRaises(RuntimeError):
            pipeline.run_pipeline(Path("/data"))
        svc.stop.assert_called_once()
        svc.clean.assert_called_once()

    @patch("services.orthomosaic_generation.app.core.algorithms.orthomosaic_pipeline.orthorectify_bands")
    @patch("services.orthomosaic_generation.app.core.algorithms.orthomosaic_pipeline.stack_bands")
    @patch("services.orthomosaic_generation.app.core.algorithms.orthomosaic_pipeline.compute_vegetation_indices")
    @patch("services.orthomosaic_generation.app.core.algorithms.orthomosaic_pipeline.convert_index_to_cog")
    def test_run_multispectral_analysis(self, mock_cog, mock_vi, mock_stack, mock_ortho):
        import tempfile, shutil
        tmpdir = Path(tempfile.mkdtemp())
        try:
            dsm = tmpdir / "dsm_filled.tif"
            dsm.write_text("dsm")

            mock_ortho.return_value = {"NIR": "/tmp/nir.tif", "Red": "/tmp/red.tif"}
            mock_vi.return_value = {"ndvi": "/tmp/ndvi.tif"}
            mock_cog.return_value = "/tmp/ndvi_cog.tif"

            pipeline, svc = self._make_pipeline()
            result = pipeline.run_multispectral_analysis(
                tmpdir, "/cal", "/sfm", {"NIR": "nir.tif"}
            )
            self.assertIn("NIR_ortho", result)
            self.assertIn("Red_ortho", result)
            self.assertIn("multiband_reflectance", result)
            self.assertIn("ndvi", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_run_dsm_only(self):
        pipeline, svc = self._make_pipeline()
        pipeline.run_dsm_only(Path("/data"))
        svc.generate_dsm_from_pointcloud.assert_called_once()
        svc.stop.assert_called_once()
        svc.clean.assert_called_once()

    def test_run_from_existing_dsm(self):
        pipeline, svc = self._make_pipeline()
        pipeline.run_from_existing_dsm(Path("/data"))
        svc.fill_dsm_holes.assert_called_once()
        svc.convert_to_cog.assert_called_once()
        svc.generate_statistics.assert_called_once()
        svc.stop.assert_called_once()
        svc.clean.assert_called_once()


if __name__ == "__main__":
    unittest.main()
