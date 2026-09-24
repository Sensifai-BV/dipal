"""Unit tests for JobStateManager and job state models."""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC
import json

import sys
from pathlib import Path
root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))


class TestProcessingStage(unittest.TestCase):
    """Test ProcessingStage enum."""

    def test_stage_values(self):
        """Test all stage values exist."""
        from infrastructure.state.models import ProcessingStage

        self.assertEqual(ProcessingStage.PENDING.value, "pending")
        self.assertEqual(ProcessingStage.QUEUED.value, "queued")
        self.assertEqual(ProcessingStage.RADIOMETRIC_CALIBRATION.value, "radiometric_calibration")
        self.assertEqual(ProcessingStage.SFM.value, "sfm")
        self.assertEqual(ProcessingStage.ORTHOMOSAIC.value, "orthomosaic")
        self.assertEqual(ProcessingStage.UPLOADING.value, "uploading")
        self.assertEqual(ProcessingStage.PUBLISHING.value, "publishing")
        self.assertEqual(ProcessingStage.COMPLETED.value, "completed")

    def test_get_next_stage(self):
        """Test getting next stage in pipeline."""
        from infrastructure.state.models import ProcessingStage

        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.PENDING), ProcessingStage.QUEUED)
        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.QUEUED), ProcessingStage.RADIOMETRIC_CALIBRATION)
        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.RADIOMETRIC_CALIBRATION), ProcessingStage.SFM)
        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.SFM), ProcessingStage.ORTHOMOSAIC)
        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.ORTHOMOSAIC), ProcessingStage.UPLOADING)
        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.UPLOADING), ProcessingStage.PUBLISHING)
        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.PUBLISHING), ProcessingStage.COMPLETED)
        self.assertIsNone(ProcessingStage.get_next_stage(ProcessingStage.COMPLETED))

    def test_get_stage_progress(self):
        """Test progress percentages for stages."""
        from infrastructure.state.models import ProcessingStage

        self.assertEqual(ProcessingStage.get_stage_progress(ProcessingStage.PENDING), 0.0)
        self.assertEqual(ProcessingStage.get_stage_progress(ProcessingStage.RADIOMETRIC_CALIBRATION), 5.0)
        self.assertEqual(ProcessingStage.get_stage_progress(ProcessingStage.SFM), 15.0)
        self.assertEqual(ProcessingStage.get_stage_progress(ProcessingStage.ORTHOMOSAIC), 60.0)
        self.assertEqual(ProcessingStage.get_stage_progress(ProcessingStage.COMPLETED), 100.0)


class TestStageStatus(unittest.TestCase):
    """Test StageStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        from infrastructure.state.models import StageStatus

        self.assertEqual(StageStatus.PENDING.value, "pending")
        self.assertEqual(StageStatus.RUNNING.value, "running")
        self.assertEqual(StageStatus.COMPLETED.value, "completed")
        self.assertEqual(StageStatus.FAILED.value, "failed")
        self.assertEqual(StageStatus.SKIPPED.value, "skipped")


class TestJobState(unittest.TestCase):
    """Test JobState model."""

    def test_job_state_creation(self):
        """Test creating a JobState."""
        from infrastructure.state.models import JobState, ProcessingStage

        job = JobState(
            job_id="test-123",
            backend_job_id="backend-456",
            dataset_id="dataset-789",
            download_url="https://example.com/images.zip",
            parameters={"gsd": 5.0},
            current_stage=ProcessingStage.PENDING,
            status="pending",
            progress=0.0,
        )

        self.assertEqual(job.job_id, "test-123")
        self.assertEqual(job.backend_job_id, "backend-456")
        self.assertEqual(job.dataset_id, "dataset-789")
        self.assertEqual(job.current_stage, ProcessingStage.PENDING)
        self.assertEqual(job.progress, 0.0)

    def test_job_state_to_dict(self):
        """Test serializing JobState to dict."""
        from infrastructure.state.models import JobState, ProcessingStage

        job = JobState(
            job_id="test-123",
            backend_job_id="backend-456",
            dataset_id="dataset-789",
            download_url=["url1", "url2"],
            parameters={"key": "value"},
            current_stage=ProcessingStage.SFM,
            status="running",
            progress=30.0,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T01:00:00Z",
        )

        data = job.to_dict()

        self.assertEqual(data["job_id"], "test-123")
        self.assertEqual(data["current_stage"], "sfm")
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["progress"], 30.0)
        self.assertEqual(data["download_url"], ["url1", "url2"])

    def test_job_state_from_dict(self):
        """Test deserializing JobState from dict."""
        from infrastructure.state.models import JobState, ProcessingStage

        data = {
            "job_id": "test-123",
            "backend_job_id": "backend-456",
            "dataset_id": "dataset-789",
            "download_url": "https://example.com/images.zip",
            "parameters": {"gsd": 10.0},
            "current_stage": "orthomosaic",
            "status": "running",
            "progress": 70.0,
            "stage_statuses": {},
            "stage_results": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T02:00:00Z",
        }

        job = JobState.from_dict(data)

        self.assertEqual(job.job_id, "test-123")
        self.assertEqual(job.current_stage, ProcessingStage.ORTHOMOSAIC)
        self.assertEqual(job.progress, 70.0)


class TestJobStateManager(unittest.TestCase):
    """Test JobStateManager."""

    def setUp(self):
        """Create mock Redis client and JobStateManager."""
        self.mock_redis_client = MagicMock()
        self.mock_redis_client.set = MagicMock()
        self.mock_redis_client.get = MagicMock(return_value=None)
        self.mock_redis_client.delete = MagicMock(return_value=True)
        self.mock_redis_client.exists = MagicMock(return_value=False)

        from infrastructure.state.job_state_manager import JobStateManager, JobStateSettings
        settings = JobStateSettings()
        self.manager = JobStateManager(self.mock_redis_client, settings)

    def test_create_job(self):
        """Test creating a new job."""
        job = self.manager.create_job(
            job_id="test-123",
            backend_job_id="backend-456",
            dataset_id="dataset-789",
            download_url="https://example.com/images.zip",
            parameters={"gsd": 5.0},
        )

        self.assertEqual(job.job_id, "test-123")
        self.assertEqual(job.backend_job_id, "backend-456")
        self.assertEqual(job.status, "pending")
        self.mock_redis_client.set.assert_called_once()

    def test_create_job_with_starting_stage(self):
        """Test creating a job that resumes from a specific stage."""
        from infrastructure.state.models import ProcessingStage, StageStatus

        job = self.manager.create_job(
            job_id="test-123",
            backend_job_id="backend-456",
            dataset_id="dataset-789",
            download_url="https://example.com/images.zip",
            starting_stage="sfm",
        )

        self.assertEqual(job.current_stage, ProcessingStage.SFM)
        self.assertEqual(
            job.stage_statuses[ProcessingStage.RADIOMETRIC_CALIBRATION.value],
            StageStatus.SKIPPED.value,
        )

    def test_get_job_found(self):
        """Test getting an existing job."""
        from infrastructure.state.models import ProcessingStage

        job_data = {
            "job_id": "test-123",
            "backend_job_id": "backend-456",
            "dataset_id": "dataset-789",
            "download_url": "https://example.com/images.zip",
            "parameters": {},
            "current_stage": "sfm",
            "status": "running",
            "progress": 30.0,
            "stage_statuses": {},
            "stage_results": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
        }
        self.mock_redis_client.get.return_value = job_data

        job = self.manager.get_job("test-123")

        self.assertIsNotNone(job)
        self.assertEqual(job.job_id, "test-123")
        self.assertEqual(job.current_stage, ProcessingStage.SFM)

    def test_get_job_not_found(self):
        """Test getting a non-existent job."""
        self.mock_redis_client.get.return_value = None

        job = self.manager.get_job("nonexistent")

        self.assertIsNone(job)

    def test_start_stage(self):
        """Test starting a stage."""
        from infrastructure.state.models import ProcessingStage, StageStatus

        job_data = {
            "job_id": "test-123",
            "backend_job_id": "backend-456",
            "dataset_id": "dataset-789",
            "download_url": "https://example.com/images.zip",
            "parameters": {},
            "current_stage": "pending",
            "status": "pending",
            "progress": 0.0,
            "stage_statuses": {
                ProcessingStage.RADIOMETRIC_CALIBRATION.value: StageStatus.PENDING.value,
                ProcessingStage.SFM.value: StageStatus.PENDING.value,
            },
            "stage_results": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
        }
        self.mock_redis_client.get.return_value = job_data

        job = self.manager.start_stage("test-123", ProcessingStage.RADIOMETRIC_CALIBRATION)

        self.assertEqual(job.status, "running")
        self.assertEqual(
            job.stage_statuses[ProcessingStage.RADIOMETRIC_CALIBRATION.value],
            StageStatus.RUNNING.value,
        )

    def test_complete_stage(self):
        """Test completing a stage and getting next stage."""
        from infrastructure.state.models import ProcessingStage, StageStatus

        job_data = {
            "job_id": "test-123",
            "backend_job_id": "backend-456",
            "dataset_id": "dataset-789",
            "download_url": "https://example.com/images.zip",
            "parameters": {},
            "current_stage": "sfm",
            "status": "running",
            "progress": 30.0,
            "stage_statuses": {
                ProcessingStage.RADIOMETRIC_CALIBRATION.value: StageStatus.COMPLETED.value,
                ProcessingStage.SFM.value: StageStatus.RUNNING.value,
                ProcessingStage.ORTHOMOSAIC.value: StageStatus.PENDING.value,
            },
            "stage_results": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
        }
        self.mock_redis_client.get.return_value = job_data

        result = {"output": "sfm_results"}
        job, next_stage = self.manager.complete_stage("test-123", ProcessingStage.SFM, result)

        self.assertEqual(job.stage_statuses[ProcessingStage.SFM.value], StageStatus.COMPLETED.value)
        self.assertEqual(job.stage_results.get("sfm"), result)
        self.assertEqual(next_stage, ProcessingStage.ORTHOMOSAIC)

    def test_fail_stage(self):
        """Test failing a stage."""
        from infrastructure.state.models import ProcessingStage, StageStatus

        job_data = {
            "job_id": "test-123",
            "backend_job_id": "backend-456",
            "dataset_id": "dataset-789",
            "download_url": "https://example.com/images.zip",
            "parameters": {},
            "current_stage": "sfm",
            "status": "running",
            "progress": 30.0,
            "stage_statuses": {
                ProcessingStage.SFM.value: StageStatus.RUNNING.value,
            },
            "stage_results": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
        }
        self.mock_redis_client.get.return_value = job_data

        job = self.manager.fail_stage("test-123", ProcessingStage.SFM, "SFM processing failed")

        self.assertEqual(job.status, "failed")
        self.assertEqual(job.stage_statuses[ProcessingStage.SFM.value], StageStatus.FAILED.value)
        self.assertEqual(job.error, "SFM processing failed")


class TestCallbackSettings(unittest.TestCase):
    """Test CallbackSettings for SFM and Orthomosaic services."""

    def test_callback_settings_defaults(self):
        """Test default callback settings."""
        with patch.dict('os.environ', {
            "API_GATEWAY_URL": "http://api_gateway:8080",
        }, clear=True):
            from services.sfm.app.core.settings import CallbackSettings
            settings = CallbackSettings()

            self.assertEqual(settings.url, "http://api_gateway:8080")
            self.assertEqual(settings.callback_endpoint, "/jobs/subservice-callback")
            self.assertEqual(settings.timeout_seconds, 30.0)

    def test_callback_url_property(self):
        """Test callback URL is properly constructed."""
        with patch.dict('os.environ', {
            "API_GATEWAY_URL": "http://custom-gateway:9000",
            "API_GATEWAY_CALLBACK_ENDPOINT": "/api/v2/callback",
        }, clear=True):
            from services.sfm.app.core.settings import CallbackSettings
            settings = CallbackSettings()

            self.assertEqual(settings.callback_url, "http://custom-gateway:9000/api/v2/callback")


if __name__ == "__main__":
    unittest.main()
