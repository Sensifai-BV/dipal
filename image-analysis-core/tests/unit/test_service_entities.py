"""Unit tests for all service entities (SFM, Orthomosaic, Calibration)."""
import unittest
import sys
from pathlib import Path

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from services.sfm.app.entities import (
    ColmapPipelineInput,
    SFMJobRequest,
    SFMJobResponse,
    SFMJobStatusResponse,
)
from services.orthomosaic_generation.app.entities import (
    OrthomosaicJobRequest,
    OrthomosaicJobResponse,
    OrthomosaicJobStatusResponse,
)
from services.radiometric_calibration.app.entities import (
    NDVICalculationInput,
    NDVICalculationOutput,
    CalibrationJobRequest,
    CalibrationJobResponse,
    CalibrationJobStatusResponse,
)


class TestColmapPipelineInput(unittest.TestCase):
    """Tests for ColmapPipelineInput model."""

    def test_create_with_required_fields(self):
        inp = ColmapPipelineInput(
            job_id="j1", storage_base_path="/data", project_id="p1"
        )
        self.assertEqual(inp.job_id, "j1")
        self.assertEqual(inp.storage_base_path, "/data")
        self.assertEqual(inp.project_id, "p1")
        self.assertIsNone(inp.parameters)

    def test_create_with_parameters(self):
        inp = ColmapPipelineInput(
            job_id="j1",
            storage_base_path="/data",
            project_id="p1",
            parameters={"quality": "high"},
        )
        self.assertEqual(inp.parameters, {"quality": "high"})


class TestSFMJobRequest(unittest.TestCase):
    """Tests for SFMJobRequest model."""

    def test_minimal(self):
        req = SFMJobRequest(
            job_id="sfm-1", dataset_id="ds-1", download_url="https://example.com"
        )
        self.assertEqual(req.job_id, "sfm-1")
        self.assertIsNone(req.parameters)

    def test_with_list_download_url(self):
        urls = [{"url": "https://a.com/1.jpg", "filename": "1.jpg"}]
        req = SFMJobRequest(
            job_id="sfm-2", dataset_id="ds-2", download_url=urls
        )
        self.assertIsInstance(req.download_url, list)

    def test_with_parameters(self):
        req = SFMJobRequest(
            job_id="sfm-3",
            dataset_id="ds-3",
            download_url="https://x.com",
            parameters={"matcher": "sequential"},
        )
        self.assertEqual(req.parameters["matcher"], "sequential")


class TestSFMJobResponse(unittest.TestCase):
    """Tests for SFMJobResponse."""

    def test_create(self):
        resp = SFMJobResponse(job_id="j1", status="running", message="Started")
        self.assertEqual(resp.job_id, "j1")
        self.assertEqual(resp.status, "running")
        self.assertEqual(resp.message, "Started")

    def test_no_message(self):
        resp = SFMJobResponse(job_id="j1", status="completed")
        self.assertIsNone(resp.message)


class TestSFMJobStatusResponse(unittest.TestCase):
    """Tests for SFMJobStatusResponse."""

    def test_completed(self):
        resp = SFMJobStatusResponse(
            job_id="j1", status="completed", progress=100.0, result={"path": "/out"}
        )
        self.assertEqual(resp.progress, 100.0)
        self.assertIsNotNone(resp.result)
        self.assertIsNone(resp.error)

    def test_failed(self):
        resp = SFMJobStatusResponse(
            job_id="j1", status="failed", error="OOM"
        )
        self.assertEqual(resp.error, "OOM")
        self.assertIsNone(resp.progress)


class TestOrthomosaicJobRequest(unittest.TestCase):
    """Tests for OrthomosaicJobRequest."""

    def test_create(self):
        req = OrthomosaicJobRequest(
            job_id="o1", dataset_id="ds-1", dataset_path="/sfm/output"
        )
        self.assertEqual(req.dataset_path, "/sfm/output")
        self.assertIsNone(req.parameters)

    def test_with_params(self):
        req = OrthomosaicJobRequest(
            job_id="o2",
            dataset_id="ds-2",
            dataset_path="/p",
            parameters={"resolution": 0.05},
        )
        self.assertEqual(req.parameters["resolution"], 0.05)


class TestOrthomosaicJobResponse(unittest.TestCase):
    """Tests for OrthomosaicJobResponse."""

    def test_create(self):
        resp = OrthomosaicJobResponse(job_id="o1", status="running")
        self.assertEqual(resp.status, "running")
        self.assertIsNone(resp.message)


class TestOrthomosaicJobStatusResponse(unittest.TestCase):
    """Tests for OrthomosaicJobStatusResponse."""

    def test_running(self):
        resp = OrthomosaicJobStatusResponse(
            job_id="o1", status="running", progress=50.0
        )
        self.assertEqual(resp.progress, 50.0)

    def test_defaults(self):
        resp = OrthomosaicJobStatusResponse(job_id="o1", status="pending")
        self.assertIsNone(resp.progress)
        self.assertIsNone(resp.result)
        self.assertIsNone(resp.error)


class TestNDVICalculationInput(unittest.TestCase):
    """Tests for NDVICalculationInput."""

    def test_create(self):
        inp = NDVICalculationInput(
            job_id="c1", s3_url_get="https://get", s3_url_post="https://post"
        )
        self.assertEqual(inp.s3_url_get, "https://get")
        self.assertIsNone(inp.parameters)


class TestNDVICalculationOutput(unittest.TestCase):
    """Tests for NDVICalculationOutput."""

    def test_create(self):
        out = NDVICalculationOutput(
            job_id="c1", status="completed", message="Done"
        )
        self.assertEqual(out.status, "completed")


class TestCalibrationJobRequest(unittest.TestCase):
    """Tests for CalibrationJobRequest."""

    def test_string_url(self):
        req = CalibrationJobRequest(
            job_id="cal-1", dataset_id="ds-1", download_url="https://example.com"
        )
        self.assertIsInstance(req.download_url, str)

    def test_list_url(self):
        urls = [{"url": "https://a.com", "filename": "1.tif"}]
        req = CalibrationJobRequest(
            job_id="cal-2", dataset_id="ds-2", download_url=urls
        )
        self.assertIsInstance(req.download_url, list)


class TestCalibrationJobResponse(unittest.TestCase):
    """Tests for CalibrationJobResponse."""

    def test_create(self):
        resp = CalibrationJobResponse(job_id="c1", status="queued")
        self.assertEqual(resp.status, "queued")
        self.assertIsNone(resp.message)


class TestCalibrationJobStatusResponse(unittest.TestCase):
    """Tests for CalibrationJobStatusResponse."""

    def test_completed(self):
        resp = CalibrationJobStatusResponse(
            job_id="c1",
            status="completed",
            progress=100.0,
            result={"bands": ["nir", "red"]},
        )
        self.assertEqual(resp.result["bands"], ["nir", "red"])

    def test_failed(self):
        resp = CalibrationJobStatusResponse(
            job_id="c1", status="failed", error="No images found"
        )
        self.assertEqual(resp.error, "No images found")


if __name__ == "__main__":
    unittest.main()
