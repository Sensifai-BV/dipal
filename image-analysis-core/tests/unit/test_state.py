"""Unit tests for infrastructure/state (JobStateManager, JobState, ProcessingStage)."""
import unittest
from unittest.mock import MagicMock
import sys
from pathlib import Path

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from infrastructure.state.models import (
    ProcessingStage,
    StageStatus,
    JobState,
)
from infrastructure.state.job_state_manager import (
    JobStateManager,
    JobStateSettings,
)


class TestProcessingStage(unittest.TestCase):
    """Tests for ProcessingStage enum."""

    def test_values(self):
        self.assertEqual(ProcessingStage.PENDING.value, "pending")
        self.assertEqual(ProcessingStage.SFM.value, "sfm")
        self.assertEqual(ProcessingStage.ORTHOMOSAIC.value, "orthomosaic")
        self.assertEqual(ProcessingStage.UPLOADING.value, "uploading")
        self.assertEqual(ProcessingStage.COMPLETED.value, "completed")

    def test_get_next_stage_normal(self):
        nxt = ProcessingStage.get_next_stage(ProcessingStage.SFM)
        self.assertEqual(nxt, ProcessingStage.ORTHOMOSAIC)

    def test_get_next_stage_completed(self):
        nxt = ProcessingStage.get_next_stage(ProcessingStage.COMPLETED)
        self.assertIsNone(nxt)

    def test_get_next_stage_skip_calibration(self):
        nxt = ProcessingStage.get_next_stage(
            ProcessingStage.QUEUED, skip_calibration=True
        )
        self.assertEqual(nxt, ProcessingStage.SFM)

    def test_get_stage_progress(self):
        self.assertEqual(ProcessingStage.get_stage_progress(ProcessingStage.PENDING), 0.0)
        self.assertEqual(ProcessingStage.get_stage_progress(ProcessingStage.SFM), 15.0)
        self.assertEqual(ProcessingStage.get_stage_progress(ProcessingStage.COMPLETED), 100.0)

    def test_is_terminal(self):
        self.assertTrue(ProcessingStage.is_terminal(ProcessingStage.COMPLETED))
        self.assertTrue(ProcessingStage.is_terminal(ProcessingStage.FAILED))
        self.assertTrue(ProcessingStage.is_terminal(ProcessingStage.CANCELLED))
        self.assertFalse(ProcessingStage.is_terminal(ProcessingStage.SFM))

    def test_get_next_stage_invalid(self):
        nxt = ProcessingStage.get_next_stage(ProcessingStage.FAILED)
        self.assertIsNone(nxt)


class TestStageStatus(unittest.TestCase):
    """Tests for StageStatus enum."""

    def test_values(self):
        self.assertEqual(StageStatus.PENDING.value, "pending")
        self.assertEqual(StageStatus.RUNNING.value, "running")
        self.assertEqual(StageStatus.COMPLETED.value, "completed")
        self.assertEqual(StageStatus.FAILED.value, "failed")
        self.assertEqual(StageStatus.SKIPPED.value, "skipped")


class TestJobState(unittest.TestCase):
    """Tests for JobState class."""

    def test_defaults(self):
        state = JobState(job_id="j1")
        self.assertEqual(state.job_id, "j1")
        self.assertEqual(state.backend_job_id, "j1")
        self.assertEqual(state.current_stage, ProcessingStage.PENDING)
        self.assertEqual(state.status, "pending")
        self.assertEqual(state.progress, 0.0)
        self.assertIn("sfm", state.stage_statuses)

    def test_to_dict(self):
        state = JobState(
            job_id="j1",
            backend_job_id="bj1",
            dataset_id="ds1",
            status="running",
            current_stage=ProcessingStage.SFM,
            progress=15.0,
        )
        d = state.to_dict()
        self.assertEqual(d["job_id"], "j1")
        self.assertEqual(d["current_stage"], "sfm")
        self.assertEqual(d["progress"], 15.0)

    def test_from_dict(self):
        d = {
            "job_id": "j2",
            "backend_job_id": "bj2",
            "dataset_id": "ds2",
            "current_stage": "orthomosaic",
            "status": "running",
            "progress": 60.0,
        }
        state = JobState.from_dict(d)
        self.assertEqual(state.job_id, "j2")
        self.assertEqual(state.current_stage, ProcessingStage.ORTHOMOSAIC)

    def test_from_dict_invalid_stage(self):
        d = {"job_id": "j3", "current_stage": "invalid_stage"}
        state = JobState.from_dict(d)
        self.assertEqual(state.current_stage, ProcessingStage.PENDING)

    def test_roundtrip(self):
        state = JobState(
            job_id="j4",
            dataset_id="ds4",
            parameters={"quality": "high"},
            current_stage=ProcessingStage.UPLOADING,
            progress=90.0,
        )
        d = state.to_dict()
        restored = JobState.from_dict(d)
        self.assertEqual(restored.job_id, "j4")
        self.assertEqual(restored.current_stage, ProcessingStage.UPLOADING)
        self.assertEqual(restored.parameters, {"quality": "high"})


class TestJobStateSettings(unittest.TestCase):
    """Tests for JobStateSettings."""

    def test_defaults(self):
        s = JobStateSettings()
        self.assertEqual(s.key_prefix, "photogear:job:")
        self.assertEqual(s.ttl_hours, 72)


class TestJobStateManager(unittest.TestCase):
    """Tests for JobStateManager."""

    def setUp(self):
        self.mock_redis = MagicMock()
        self.manager = JobStateManager(redis_client=self.mock_redis)

    def test_create_job(self):
        result = self.manager.create_job(
            job_id="j1", backend_job_id="bj1", dataset_id="ds1"
        )
        self.assertEqual(result.job_id, "j1")
        self.assertEqual(result.backend_job_id, "bj1")
        self.mock_redis.set.assert_called_once()

    def test_create_job_with_starting_stage(self):
        result = self.manager.create_job(
            job_id="j2", starting_stage="sfm"
        )
        self.assertEqual(result.current_stage, ProcessingStage.SFM)
        statuses = result.stage_statuses
        self.assertEqual(statuses["radiometric_calibration"], "skipped")
        self.assertEqual(statuses["sfm"], "pending")

    def test_create_job_invalid_starting_stage(self):
        result = self.manager.create_job(
            job_id="j3", starting_stage="invalid"
        )
        self.assertEqual(result.current_stage, ProcessingStage.PENDING)

    def test_get_job_exists(self):
        state = JobState(job_id="j1", status="running")
        self.mock_redis.get.return_value = state.to_dict()
        result = self.manager.get_job("j1")
        self.assertIsNotNone(result)
        self.assertEqual(result.job_id, "j1")

    def test_get_job_not_exists(self):
        self.mock_redis.get.return_value = None
        result = self.manager.get_job("missing")
        self.assertIsNone(result)

    def test_update_job(self):
        state = JobState(job_id="j1")
        self.mock_redis.get.return_value = state.to_dict()
        result = self.manager.update_job(
            "j1", status="running", progress=50.0
        )
        self.assertEqual(result.status, "running")
        self.assertEqual(result.progress, 50.0)

    def test_update_job_not_found(self):
        self.mock_redis.get.return_value = None
        result = self.manager.update_job("missing", status="running")
        self.assertIsNone(result)

    def test_update_job_with_stage_string(self):
        state = JobState(job_id="j1")
        self.mock_redis.get.return_value = state.to_dict()
        result = self.manager.update_job("j1", current_stage="sfm")
        self.assertEqual(result.current_stage, ProcessingStage.SFM)

    def test_start_stage(self):
        state = JobState(job_id="j1")
        self.mock_redis.get.return_value = state.to_dict()
        result = self.manager.start_stage("j1", ProcessingStage.SFM)
        self.assertEqual(result.status, "running")
        self.assertEqual(result.stage_statuses["sfm"], "running")

    def test_start_stage_not_found(self):
        self.mock_redis.get.return_value = None
        result = self.manager.start_stage("missing", ProcessingStage.SFM)
        self.assertIsNone(result)

    def test_complete_stage_with_next(self):
        state = JobState(job_id="j1")
        self.mock_redis.get.return_value = state.to_dict()
        job, nxt = self.manager.complete_stage(
            "j1", ProcessingStage.SFM, result={"path": "/out"}
        )
        self.assertIsNotNone(job)
        self.assertEqual(job.stage_statuses["sfm"], "completed")
        self.assertEqual(nxt, ProcessingStage.ORTHOMOSAIC)

    def test_complete_stage_pipeline_done(self):
        state = JobState(job_id="j1")
        self.mock_redis.get.return_value = state.to_dict()
        job, nxt = self.manager.complete_stage("j1", ProcessingStage.PUBLISHING)
        self.assertIsNone(nxt)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.progress, 100.0)

    def test_complete_stage_not_found(self):
        self.mock_redis.get.return_value = None
        job, nxt = self.manager.complete_stage("missing", ProcessingStage.SFM)
        self.assertIsNone(job)
        self.assertIsNone(nxt)

    def test_fail_stage(self):
        state = JobState(job_id="j1")
        self.mock_redis.get.return_value = state.to_dict()
        result = self.manager.fail_stage("j1", ProcessingStage.SFM, "OOM")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error, "OOM")
        self.assertEqual(result.stage_statuses["sfm"], "failed")

    def test_fail_stage_not_found(self):
        self.mock_redis.get.return_value = None
        result = self.manager.fail_stage("missing", "sfm", "err")
        self.assertIsNone(result)

    def test_get_stage_result(self):
        state = JobState(job_id="j1", stage_results={"sfm": {"path": "/out"}})
        self.mock_redis.get.return_value = state.to_dict()
        result = self.manager.get_stage_result("j1", ProcessingStage.SFM)
        self.assertEqual(result, {"path": "/out"})

    def test_get_stage_result_not_found(self):
        self.mock_redis.get.return_value = None
        result = self.manager.get_stage_result("missing", "sfm")
        self.assertIsNone(result)

    def test_delete_job(self):
        self.mock_redis.delete.return_value = 1
        self.assertTrue(self.manager.delete_job("j1"))

    def test_delete_job_not_found(self):
        self.mock_redis.delete.return_value = 0
        self.assertFalse(self.manager.delete_job("missing"))

    def test_job_exists(self):
        self.mock_redis.exists.return_value = True
        self.assertTrue(self.manager.job_exists("j1"))

    def test_job_not_exists(self):
        self.mock_redis.exists.return_value = False
        self.assertFalse(self.manager.job_exists("missing"))

    def test_complete_stage_skips_skipped(self):
        state = JobState(
            job_id="j1",
            stage_statuses={
                "radiometric_calibration": "skipped",
                "sfm": "pending",
                "orthomosaic": "skipped",
                "uploading": "pending",
            },
        )
        self.mock_redis.get.return_value = state.to_dict()
        job, nxt = self.manager.complete_stage("j1", ProcessingStage.SFM)
        self.assertEqual(nxt, ProcessingStage.UPLOADING)


if __name__ == "__main__":
    unittest.main()
