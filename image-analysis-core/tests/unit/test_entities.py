"""Tests for job entities, enums, and Pydantic models."""
import unittest

from api_gateway.app.entities.jobs import (
    JobStatus,
    ProcessingStage,
    JobInitializationInput,
    JobRunRequest,
    JobInitializationOutput,
    JobStatusResponse,
    JobCancelResponse,
    JobSyncInput,
    JobSyncOutput,
    S3StorageConfig,
)


class TestJobStatus(unittest.TestCase):
    """Tests for JobStatus enum."""

    def test_all_statuses(self):
        """Test all expected status values exist."""
        expected = {"pending", "running", "completed", "failed", "cancelled", "not_found"}
        actual = {s.value for s in JobStatus}
        self.assertEqual(actual, expected)

    def test_string_comparison(self):
        """Test JobStatus can be compared as string."""
        self.assertEqual(JobStatus.PENDING, "pending")
        self.assertEqual(JobStatus.COMPLETED, "completed")


class TestProcessingStage(unittest.TestCase):
    """Tests for ProcessingStage enum."""

    def test_all_stages(self):
        """Test all expected processing stages exist."""
        expected = {
            "pending", "queued", "radiometric_calibration", "sfm",
            "orthomosaic", "uploading", "publishing", "completed",
            "failed", "cancelled",
        }
        actual = {s.value for s in ProcessingStage}
        self.assertEqual(actual, expected)


class TestJobRunRequest(unittest.TestCase):
    """Tests for JobRunRequest model."""

    def test_minimal_request(self):
        """Test creating request with minimal fields."""
        req = JobRunRequest(dataset_id="ds-1", download_url="https://example.com/data.zip")
        self.assertEqual(req.dataset_id, "ds-1")
        self.assertIsNone(req.job_id)
        self.assertIsNone(req.parameters)
        self.assertIsNone(req.starting_stage)

    def test_full_request(self):
        """Test creating request with all fields."""
        req = JobRunRequest(
            job_id="j-1",
            dataset_id="ds-1",
            download_url="https://example.com/data.zip",
            parameters={"gsd": 2.5},
            starting_stage="sfm",
        )
        self.assertEqual(req.job_id, "j-1")
        self.assertEqual(req.parameters, {"gsd": 2.5})
        self.assertEqual(req.starting_stage, "sfm")

    def test_list_download_url(self):
        """Test request with list of image URLs."""
        req = JobRunRequest(
            dataset_id="ds-1",
            download_url=[{"url": "https://example.com/img1.jpg", "filename": "img1.jpg"}],
        )
        self.assertIsInstance(req.download_url, list)


class TestJobStatusResponse(unittest.TestCase):
    """Tests for JobStatusResponse model."""

    def test_completed_response(self):
        """Test completed job status response."""
        resp = JobStatusResponse(
            job_id="j-1",
            status=JobStatus.COMPLETED,
            progress=100.0,
            current_stage=ProcessingStage.COMPLETED,
            result={"output": "s3://bucket/result"},
        )
        self.assertEqual(resp.status, JobStatus.COMPLETED)
        self.assertAlmostEqual(resp.progress, 100.0)

    def test_failed_response(self):
        """Test failed job status response."""
        resp = JobStatusResponse(
            job_id="j-2",
            status=JobStatus.FAILED,
            error="Processing failed",
        )
        self.assertEqual(resp.error, "Processing failed")

    def test_running_response(self):
        """Test running job status response."""
        resp = JobStatusResponse(
            job_id="j-3",
            status=JobStatus.RUNNING,
            progress=45.0,
            current_stage=ProcessingStage.SFM,
        )
        self.assertEqual(resp.current_stage, ProcessingStage.SFM)


class TestJobCancelResponse(unittest.TestCase):
    """Tests for JobCancelResponse model."""

    def test_cancel_response(self):
        """Test cancel response."""
        resp = JobCancelResponse(
            job_id="j-1", cancelled=True, message="Job cancelled"
        )
        self.assertTrue(resp.cancelled)


class TestJobInitializationModels(unittest.TestCase):
    """Tests for job initialization input/output."""

    def test_initialization_input(self):
        """Test JobInitializationInput."""
        inp = JobInitializationInput(
            job_id="j-1",
            dataset_id="ds-1",
            download_url="https://example.com/data.zip",
        )
        self.assertEqual(inp.job_id, "j-1")

    def test_initialization_output(self):
        """Test JobInitializationOutput."""
        out = JobInitializationOutput(
            job_id="j-1",
            dataset_id="ds-1",
            status="running",
            message="Job started",
        )
        self.assertEqual(out.status, "running")


class TestJobSyncModels(unittest.TestCase):
    """Tests for job sync models."""

    def test_sync_input(self):
        """Test JobSyncInput."""
        inp = JobSyncInput(job_id="j-1")
        self.assertEqual(inp.job_id, "j-1")

    def test_sync_output(self):
        """Test JobSyncOutput."""
        out = JobSyncOutput(job_id="j-1", status="running", progress=50.0)
        self.assertEqual(out.status, "running")
        self.assertAlmostEqual(out.progress, 50.0)


class TestS3StorageConfig(unittest.TestCase):
    """Tests for S3StorageConfig model."""

    def test_config(self):
        """Test S3StorageConfig."""
        cfg = S3StorageConfig(
            bucket_name="my-bucket",
            access_key="AKID",
            secret_key="SECRET",
            region="us-west-2",
            prefix="photogear",
        )
        self.assertEqual(cfg.bucket_name, "my-bucket")
        self.assertEqual(cfg.region, "us-west-2")


if __name__ == "__main__":
    unittest.main()
