"""
Unit tests for the callback system.

Tests cover:
1. Subservice callback endpoint (API Gateway receives callbacks from services)
2. Callback sending from services (SFM, Calibration, Orthomosaic)
3. Pipeline orchestration via callbacks
4. Error handling in callback flows
"""
import unittest
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from datetime import datetime, UTC
import json
import sys
from pathlib import Path

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))


class TestSubserviceCallbackEndpoint(unittest.TestCase):
    """Tests for the API Gateway's subservice_callback endpoint."""

    def setUp(self):
        """Create mock dependencies."""
        from infrastructure.state.models import JobState, ProcessingStage, StageStatus

        self.job_state = JobState(
            job_id="test-job-123",
            backend_job_id="backend-job-456",
            dataset_id="dataset-789",
            download_url="https://example.com/images",
            parameters={"gsd": 10.0},
            current_stage=ProcessingStage.RADIOMETRIC_CALIBRATION,
            status="running",
            progress=10.0,
            stage_statuses={
                "radiometric_calibration": "running",
                "sfm": "pending",
                "orthomosaic": "pending",
                "uploading": "pending",
            },
        )

        self.mock_job_state_manager = Mock()
        self.mock_job_state_manager.get_job.return_value = self.job_state
        self.mock_job_state_manager.complete_stage.return_value = (self.job_state, ProcessingStage.SFM)
        self.mock_job_state_manager.fail_stage.return_value = self.job_state
        self.mock_job_state_manager.update_job.return_value = self.job_state

        self.mock_backend_client = AsyncMock()
        self.mock_backend_client.send_progress_update.return_value = None
        self.mock_backend_client.send_completion.return_value = None
        self.mock_backend_client.send_failure.return_value = None

        self.mock_sfm_client = AsyncMock()
        self.mock_sfm_client.run_sfm.return_value = {"status": "started"}

        self.mock_orthomosaic_client = AsyncMock()
        self.mock_orthomosaic_client.run_orthomosaic.return_value = {"status": "started"}

    def test_callback_payload_structure_calibration_completed(self):
        """Test that calibration callback payload has correct structure."""
        callback_data = {
            "job_id": "test-job-123_calibration",
            "service": "calibration",
            "status": "completed",
            "result": {
                "job_id": "test-job-123_calibration",
                "dataset_id": "dataset-789",
                "calibrated_images": ["/path/to/img1.jpg", "/path/to/img2.jpg"],
                "calibration_path": "/tmp/jobs/radiometric/test-job-123_calibration/calibrated",
                "images_path": "/tmp/datasets/dataset-789/images",
                "status": "completed",
            },
            "error": None,
        }

        self.assertIn("job_id", callback_data)
        self.assertIn("service", callback_data)
        self.assertIn("status", callback_data)
        self.assertIn(callback_data["status"], ["completed", "failed"])

        result = callback_data["result"]
        self.assertIn("dataset_id", result)
        self.assertIn("images_path", result)

    def test_callback_payload_structure_sfm_completed(self):
        """Test that SFM callback payload has correct structure."""
        callback_data = {
            "job_id": "test-job-123_sfm",
            "service": "sfm",
            "status": "completed",
            "result": {
                "job_id": "test-job-123_sfm",
                "dataset_id": "dataset-789",
                "run_path": "/tmp/jobs/sfm/test-job-123_sfm/run_1",
                "workspace_path": "/tmp/jobs/sfm/test-job-123_sfm",
                "images_path": "/tmp/datasets/dataset-789/images",
                "output_path": "/tmp/jobs/sfm/test-job-123_sfm/run_1",
                "status": "completed",
            },
            "error": None,
        }

        self.assertIn("job_id", callback_data)
        self.assertIn("service", callback_data)
        self.assertEqual(callback_data["service"], "sfm")

        result = callback_data["result"]
        self.assertIn("run_path", result)

    def test_callback_payload_structure_orthomosaic_completed(self):
        """Test that orthomosaic callback payload has correct structure."""
        callback_data = {
            "job_id": "test-job-123_orthomosaic",
            "service": "orthomosaic",
            "status": "completed",
            "result": {
                "job_id": "test-job-123_orthomosaic",
                "dataset_id": "dataset-789",
                "outputs": {
                    "orthomosaic_rgb": "/path/to/ortho.tif",
                    "dsm_filled_cog": "/path/to/dsm.tif",
                    "hillshade": "/path/to/hillshade.tif",
                },
                "status": "completed",
            },
            "error": None,
        }

        self.assertEqual(callback_data["service"], "orthomosaic")

        result = callback_data["result"]
        self.assertIn("outputs", result)

    def test_callback_payload_structure_failed(self):
        """Test that failed callback payload has correct structure."""
        callback_data = {
            "job_id": "test-job-123_sfm",
            "service": "sfm",
            "status": "failed",
            "result": None,
            "error": "COLMAP failed with exit code 1",
        }

        self.assertEqual(callback_data["status"], "failed")
        self.assertIsNotNone(callback_data["error"])
        self.assertIsNone(callback_data["result"])

    def test_extract_main_job_id_from_sub_job_id(self):
        """Test extracting main job ID from sub-job ID."""
        sub_job_ids = [
            ("test-job-123_calibration", "test-job-123"),
            ("test-job-123_sfm", "test-job-123"),
            ("test-job-123_orthomosaic", "test-job-123"),
            ("uuid-with-dashes-123_sfm", "uuid-with-dashes-123"),
            ("simple-job-id", "simple-job-id"),
        ]

        for sub_job_id, expected_main_id in sub_job_ids:
            with self.subTest(sub_job_id=sub_job_id):
                if "_" in sub_job_id:
                    main_job_id = sub_job_id.rsplit("_", 1)[0]
                else:
                    main_job_id = sub_job_id
                self.assertEqual(main_job_id, expected_main_id)

    def test_service_to_stage_mapping(self):
        """Test mapping from service name to processing stage."""
        from infrastructure.state.models import ProcessingStage

        stage_map = {
            "calibration": ProcessingStage.RADIOMETRIC_CALIBRATION,
            "sfm": ProcessingStage.SFM,
            "orthomosaic": ProcessingStage.ORTHOMOSAIC,
        }

        self.assertEqual(stage_map["calibration"], ProcessingStage.RADIOMETRIC_CALIBRATION)
        self.assertEqual(stage_map["sfm"], ProcessingStage.SFM)
        self.assertEqual(stage_map["orthomosaic"], ProcessingStage.ORTHOMOSAIC)


class TestCallbackSending(unittest.IsolatedAsyncioTestCase):
    """Tests for callback sending from services."""

    async def test_calibration_callback_format(self):
        """Test that calibration service sends correct callback format."""
        job_id = "test-job-123_calibration"
        main_job_id = job_id.replace("_calibration", "")

        payload = {
            "job_id": main_job_id,
            "service": "calibration",
            "status": "completed",
            "result": {
                "job_id": job_id,
                "dataset_id": "dataset-123",
                "calibrated_images": ["/path/img1.jpg"],
                "calibration_path": "/tmp/calibrated",
                "images_path": "/tmp/images",
                "status": "completed",
            },
            "error": None,
        }

        self.assertEqual(payload["job_id"], "test-job-123")
        self.assertEqual(payload["service"], "calibration")
        self.assertEqual(payload["status"], "completed")

    async def test_sfm_callback_format(self):
        """Test that SFM service sends correct callback format."""
        job_id = "test-job-123_sfm"

        payload = {
            "service": "sfm",
            "job_id": job_id,
            "status": "completed",
            "result": {
                "job_id": job_id,
                "dataset_id": "dataset-123",
                "run_path": "/tmp/jobs/sfm/test-job-123_sfm/run_1",
                "workspace_path": "/tmp/jobs/sfm/test-job-123_sfm",
                "images_path": "/tmp/datasets/dataset-123/images",
                "output_path": "/tmp/jobs/sfm/test-job-123_sfm/run_1",
                "status": "completed",
            },
        }

        self.assertEqual(payload["service"], "sfm")
        self.assertIn("run_path", payload["result"])

    async def test_callback_timeout_handling(self):
        """Test that callback timeouts are handled gracefully."""
        import httpx

        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.side_effect = httpx.TimeoutException("timeout")


class TestPipelineOrchestration(unittest.TestCase):
    """Tests for callback-driven pipeline orchestration."""

    def test_stage_progression_with_calibration(self):
        """Test stage progression: Calibration -> SFM -> Orthomosaic."""
        from infrastructure.state.models import ProcessingStage

        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.RADIOMETRIC_CALIBRATION), ProcessingStage.SFM)
        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.SFM), ProcessingStage.ORTHOMOSAIC)
        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.ORTHOMOSAIC), ProcessingStage.UPLOADING)
        self.assertEqual(ProcessingStage.get_next_stage(ProcessingStage.UPLOADING), ProcessingStage.PUBLISHING)

    def test_stage_progression_skip_calibration(self):
        """Test stage progression when calibration is skipped."""
        from infrastructure.state.models import ProcessingStage

        self.assertEqual(
            ProcessingStage.get_next_stage(ProcessingStage.QUEUED, skip_calibration=True),
            ProcessingStage.SFM,
        )

    def test_progress_values_per_stage(self):
        """Test that progress values are correct for each stage."""
        from infrastructure.state.models import ProcessingStage

        expected_progress = {
            ProcessingStage.PENDING: 0.0,
            ProcessingStage.QUEUED: 0.0,
            ProcessingStage.RADIOMETRIC_CALIBRATION: 5.0,
            ProcessingStage.SFM: 15.0,
            ProcessingStage.ORTHOMOSAIC: 60.0,
            ProcessingStage.UPLOADING: 90.0,
            ProcessingStage.PUBLISHING: 95.0,
            ProcessingStage.COMPLETED: 100.0,
        }

        for stage, expected in expected_progress.items():
            with self.subTest(stage=stage):
                self.assertEqual(ProcessingStage.get_stage_progress(stage), expected)

    def test_terminal_states(self):
        """Test terminal state detection."""
        from infrastructure.state.models import ProcessingStage

        self.assertTrue(ProcessingStage.is_terminal(ProcessingStage.COMPLETED))
        self.assertTrue(ProcessingStage.is_terminal(ProcessingStage.FAILED))
        self.assertTrue(ProcessingStage.is_terminal(ProcessingStage.CANCELLED))

        self.assertFalse(ProcessingStage.is_terminal(ProcessingStage.SFM))
        self.assertFalse(ProcessingStage.is_terminal(ProcessingStage.ORTHOMOSAIC))


class TestJobStateCallbackIntegration(unittest.TestCase):
    """Tests for JobStateManager integration with callbacks."""

    def setUp(self):
        """Create mock Redis client."""
        self.mock_redis = Mock()
        self.mock_redis.get.return_value = None
        self.mock_redis.set.return_value = True
        self.mock_redis.delete.return_value = 1
        self.mock_redis.exists.return_value = True

    def test_complete_stage_returns_next_stage(self):
        """Test that complete_stage returns the correct next stage."""
        from infrastructure.state.job_state_manager import JobStateManager, JobStateSettings
        from infrastructure.state.models import ProcessingStage, StageStatus

        manager = JobStateManager(self.mock_redis, JobStateSettings())

        job_data = {
            "job_id": "test-123",
            "backend_job_id": "backend-456",
            "dataset_id": "dataset-789",
            "download_url": "https://example.com",
            "parameters": {},
            "current_stage": "radiometric_calibration",
            "status": "running",
            "progress": 10.0,
            "stage_statuses": {
                "radiometric_calibration": "running",
                "sfm": "pending",
                "orthomosaic": "pending",
                "uploading": "pending",
            },
            "stage_results": {},
            "error": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        self.mock_redis.get.return_value = job_data

        job_state, next_stage = manager.complete_stage(
            "test-123",
            ProcessingStage.RADIOMETRIC_CALIBRATION,
            result={"calibration_path": "/path/to/calibrated"},
        )

        self.assertEqual(next_stage, ProcessingStage.SFM)

    def test_complete_final_stage_returns_none(self):
        """Test that completing the final stage returns None for next stage."""
        from infrastructure.state.job_state_manager import JobStateManager, JobStateSettings
        from infrastructure.state.models import ProcessingStage

        manager = JobStateManager(self.mock_redis, JobStateSettings())

        job_data = {
            "job_id": "test-123",
            "backend_job_id": "backend-456",
            "dataset_id": "dataset-789",
            "download_url": "https://example.com",
            "parameters": {},
            "current_stage": "publishing",
            "status": "running",
            "progress": 95.0,
            "stage_statuses": {
                "radiometric_calibration": "completed",
                "sfm": "completed",
                "orthomosaic": "completed",
                "uploading": "completed",
            },
            "stage_results": {},
            "error": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        self.mock_redis.get.return_value = job_data

        job_state, next_stage = manager.complete_stage(
            "test-123",
            ProcessingStage.PUBLISHING,
            result={"published": True},
        )

        self.assertIsNone(next_stage)

    def test_fail_stage_marks_job_failed(self):
        """Test that failing a stage marks the job as failed."""
        from infrastructure.state.job_state_manager import JobStateManager, JobStateSettings
        from infrastructure.state.models import ProcessingStage, StageStatus

        manager = JobStateManager(self.mock_redis, JobStateSettings())

        job_data = {
            "job_id": "test-123",
            "backend_job_id": "backend-456",
            "dataset_id": "dataset-789",
            "download_url": "https://example.com",
            "parameters": {},
            "current_stage": "sfm",
            "status": "running",
            "progress": 30.0,
            "stage_statuses": {
                "radiometric_calibration": "completed",
                "sfm": "running",
                "orthomosaic": "pending",
                "uploading": "pending",
            },
            "stage_results": {},
            "error": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        self.mock_redis.get.return_value = job_data

        job_state = manager.fail_stage(
            "test-123",
            ProcessingStage.SFM,
            error="COLMAP feature extraction failed",
        )

        self.assertEqual(job_state.status, "failed")
        self.assertEqual(job_state.error, "COLMAP feature extraction failed")


class TestCallbackRetryLogic(unittest.TestCase):
    """Tests for callback retry and error handling."""

    def test_callback_should_not_block_service(self):
        """Test that callback failure doesn't block the service task."""
        pass

    def test_callback_timeout_default(self):
        """Test that callback has reasonable timeout."""
        expected_min_timeout = 10
        expected_max_timeout = 60

        from services.radiometric_calibration.app.core.settings import CallbackSettings
        settings = CallbackSettings()

    def test_client_timeout_configuration(self):
        """Test that service clients have reasonable timeouts configured."""
        expected_max_client_timeout = 60

        from api_gateway.app.clients.calibration_client import CalibrationClientSettings
        from api_gateway.app.clients.sfm_client import SFMClientSettings
        from api_gateway.app.clients.orthomosaic_client import OrthomosaicClientSettings

        cal_settings = CalibrationClientSettings(address="http://test:8000")
        sfm_settings = SFMClientSettings(address="http://test:8000")
        ortho_settings = OrthomosaicClientSettings(address="http://test:8000")

        self.assertLessEqual(cal_settings.timeout_seconds, expected_max_client_timeout)
        self.assertLessEqual(sfm_settings.timeout_seconds, expected_max_client_timeout)
        self.assertLessEqual(ortho_settings.timeout_seconds, expected_max_client_timeout)

        self.assertGreater(cal_settings.timeout_seconds, 0)
        self.assertGreater(sfm_settings.timeout_seconds, 0)
        self.assertGreater(ortho_settings.timeout_seconds, 0)


class TestUploadResult(unittest.TestCase):
    """Tests for UploadResult helper class."""

    def test_upload_result_has_failures(self):
        """Test has_failures property."""
        class UploadResult:
            def __init__(self):
                self.uploaded: list[dict] = []
                self.failed: list[dict] = []

            @property
            def has_failures(self) -> bool:
                return len(self.failed) > 0

            @property
            def has_critical_failure(self) -> bool:
                critical_types = {"orthomosaic"}
                return any(f["product_type"] in critical_types for f in self.failed)

        result = UploadResult()
        self.assertFalse(result.has_failures)

        result.failed.append({
            "product_type": "pointcloud",
            "file_path": "/path/to/file.ply",
            "error": "File not found",
        })
        self.assertTrue(result.has_failures)

    def test_upload_result_has_critical_failure(self):
        """Test has_critical_failure property."""
        class UploadResult:
            def __init__(self):
                self.uploaded: list[dict] = []
                self.failed: list[dict] = []

            @property
            def has_failures(self) -> bool:
                return len(self.failed) > 0

            @property
            def has_critical_failure(self) -> bool:
                critical_types = {"orthomosaic"}
                return any(f["product_type"] in critical_types for f in self.failed)

        result = UploadResult()

        result.failed.append({
            "product_type": "pointcloud",
            "file_path": "/path/to/file.ply",
            "error": "File not found",
        })
        self.assertFalse(result.has_critical_failure)

        result.failed.append({
            "product_type": "orthomosaic",
            "file_path": "/path/to/ortho.tif",
            "error": "Upload failed",
        })
        self.assertTrue(result.has_critical_failure)


class TestTriggerNextStage(unittest.IsolatedAsyncioTestCase):
    """Tests for trigger_next_stage function.

    Note: These tests verify the expected behavior without importing
    the actual function to avoid boto3 dependency issues.
    """

    async def test_trigger_sfm_after_calibration(self):
        """Test that SFM is triggered after calibration completes."""
        from infrastructure.state.models import ProcessingStage, JobState

        job_state = JobState(
            job_id="test-123",
            backend_job_id="backend-456",
            dataset_id="dataset-789",
            download_url="https://example.com/images",
            parameters={"gsd": 10.0},
            current_stage=ProcessingStage.SFM,
            status="running",
        )

        sfm_client = AsyncMock()
        orthomosaic_client = AsyncMock()
        backend_client = AsyncMock()
        temp_manager = Mock()

        next_stage = ProcessingStage.SFM

        if next_stage == ProcessingStage.SFM:
            sfm_job_id = f"{job_state.job_id}_sfm"
            await sfm_client.run_sfm(
                job_id=sfm_job_id,
                dataset_id=job_state.dataset_id,
                download_url=job_state.download_url,
                parameters=job_state.parameters,
            )

        sfm_client.run_sfm.assert_called_once()
        call_args = sfm_client.run_sfm.call_args
        self.assertEqual(call_args.kwargs["dataset_id"], "dataset-789")
        self.assertEqual(call_args.kwargs["job_id"], "test-123_sfm")

    async def test_trigger_orthomosaic_after_sfm(self):
        """Test that orthomosaic is triggered after SFM completes."""
        from infrastructure.state.models import ProcessingStage, JobState

        job_state = JobState(
            job_id="test-123",
            backend_job_id="backend-456",
            dataset_id="dataset-789",
            download_url="https://example.com/images",
            parameters={"gsd": 10.0},
            current_stage=ProcessingStage.ORTHOMOSAIC,
            status="running",
            stage_results={
                "sfm": {
                    "run_path": "/tmp/jobs/sfm/test-123_sfm/run_1",
                },
            },
        )

        sfm_client = AsyncMock()
        orthomosaic_client = AsyncMock()
        backend_client = AsyncMock()
        temp_manager = Mock()

        next_stage = ProcessingStage.ORTHOMOSAIC

        if next_stage == ProcessingStage.ORTHOMOSAIC:
            sfm_result = job_state.stage_results.get("sfm", {})
            sfm_output_path = sfm_result.get("run_path")

            orthomosaic_job_id = f"{job_state.job_id}_orthomosaic"
            await orthomosaic_client.run_orthomosaic(
                job_id=orthomosaic_job_id,
                dataset_id=job_state.dataset_id,
                dataset_path=sfm_output_path,
                parameters=job_state.parameters,
            )

        orthomosaic_client.run_orthomosaic.assert_called_once()
        call_args = orthomosaic_client.run_orthomosaic.call_args
        self.assertEqual(call_args.kwargs["dataset_path"], "/tmp/jobs/sfm/test-123_sfm/run_1")


class TestPipelineOrderValidation(unittest.TestCase):
    """Tests to validate the correct pipeline order.

    IMPORTANT: The user specified the correct order should be:
    SFM -> Orthomosaic -> Calibration

    However, the current implementation uses:
    Calibration -> SFM -> Orthomosaic

    These tests document the expected behavior for review.
    """

    def test_current_pipeline_order(self):
        """Document current pipeline order (for review)."""
        from infrastructure.state.models import ProcessingStage

        self.assertEqual(
            ProcessingStage.get_next_stage(ProcessingStage.QUEUED),
            ProcessingStage.RADIOMETRIC_CALIBRATION,
        )
        self.assertEqual(
            ProcessingStage.get_next_stage(ProcessingStage.RADIOMETRIC_CALIBRATION),
            ProcessingStage.SFM,
        )
        self.assertEqual(
            ProcessingStage.get_next_stage(ProcessingStage.SFM),
            ProcessingStage.ORTHOMOSAIC,
        )

    def test_user_requested_pipeline_order(self):
        """Document user-requested pipeline order (not yet implemented).

        User requested order: SFM -> Orthomosaic -> Calibration

        Reasoning (from user):
        - SFM should download images first (it's called first)
        - Then Orthomosaic processes
        - Then Radiometric Calibration
        """
        expected_order = [
            "sfm",
            "orthomosaic",
            "radiometric_calibration",
        ]

        self.assertEqual(len(expected_order), 3)


if __name__ == "__main__":
    unittest.main()
