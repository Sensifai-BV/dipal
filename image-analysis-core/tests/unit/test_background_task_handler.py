"""Tests for BackgroundTaskHandler, job lifecycle and storage."""
import unittest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, UTC, timedelta

from infrastructure.message_queue.background_task import (
    BackgroundTaskHandler,
    BackgroundTaskSettings,
    JobStatus,
)


class TestBackgroundTaskHandlerInMemory(unittest.TestCase):
    """Test BackgroundTaskHandler with in-memory storage."""

    def setUp(self):
        self.settings = BackgroundTaskSettings(use_redis=False, cleanup_hours=1)
        self.handler = BackgroundTaskHandler(settings=self.settings)

    def test_create_job(self):
        """Test creating a new job."""
        self.handler.create_job("job-1", metadata={"key": "val"})
        status = self.handler.get_task_status("job-1")
        self.assertEqual(status["status"], "pending")
        self.assertEqual(status["metadata"], {"key": "val"})
        self.assertAlmostEqual(status["progress"], 0.0)

    def test_update_job_status(self):
        """Test updating job status with progress."""
        self.handler.create_job("job-2")
        self.handler.update_job_status("job-2", JobStatus.RUNNING, progress=30.0)
        status = self.handler.get_task_status("job-2")
        self.assertEqual(status["status"], "running")
        self.assertAlmostEqual(status["progress"], 30.0)

    def test_update_job_completed(self):
        """Test completing a job."""
        self.handler.create_job("job-3")
        self.handler.update_job_status(
            "job-3", JobStatus.COMPLETED, result={"out": "data"}, progress=100.0
        )
        status = self.handler.get_task_status("job-3")
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["result"], {"out": "data"})

    def test_update_job_failed(self):
        """Test failing a job."""
        self.handler.create_job("job-4")
        self.handler.update_job_status("job-4", JobStatus.FAILED, error="boom")
        status = self.handler.get_task_status("job-4")
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error"], "boom")

    def test_get_nonexistent_job(self):
        """Test getting status of nonexistent job."""
        status = self.handler.get_task_status("nonexistent")
        self.assertEqual(status["status"], "not_found")

    def test_update_job_metadata(self):
        """Test updating job metadata."""
        self.handler.create_job("job-5", metadata={"a": 1})
        self.handler.update_job_metadata("job-5", {"b": 2})
        status = self.handler.get_task_status("job-5")
        self.assertEqual(status["metadata"], {"a": 1, "b": 2})

    def test_store_task_result_legacy(self):
        """Test legacy store_task_result method."""
        self.handler.store_task_result("task-1", "completed", result={"x": 1})
        status = self.handler.get_task_status("task-1")
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["result"], {"x": 1})
        self.assertAlmostEqual(status["progress"], 100.0)

    def test_cancel_pending_job(self):
        """Test cancelling a pending job."""
        self.handler.create_job("job-6")
        result = self.handler.cancel_job("job-6")
        self.assertTrue(result)
        status = self.handler.get_task_status("job-6")
        self.assertEqual(status["status"], "cancelled")

    def test_cancel_nonexistent_job(self):
        """Test cancelling a nonexistent job returns False."""
        result = self.handler.cancel_job("nonexistent")
        self.assertFalse(result)

    def test_store_file(self):
        """Test storing a file."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            self.handler.assets_file_path = Path(tmpdir)
            file_path = self.handler.store_file(b"hello world", "test.txt")
            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.read_bytes(), b"hello world")

    def test_cleanup_old_tasks(self):
        """Test cleaning up old tasks."""
        self.handler.create_job("old-job")
        old_time = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
        self.handler._task_storage["old-job"]["updated_at"] = old_time
        self.handler.cleanup_old_tasks(max_age_hours=1)
        status = self.handler.get_task_status("old-job")
        self.assertEqual(status["status"], "not_found")

    def test_cleanup_preserves_recent_tasks(self):
        """Test that cleanup keeps recent tasks."""
        self.handler.create_job("new-job")
        self.handler.cleanup_old_tasks(max_age_hours=1)
        status = self.handler.get_task_status("new-job")
        self.assertEqual(status["status"], "pending")

    def test_delete_storage(self):
        """Test deleting from storage."""
        self.handler.create_job("del-job")
        self.handler._delete_storage("del-job")
        status = self.handler.get_task_status("del-job")
        self.assertEqual(status["status"], "not_found")


class TestBackgroundTaskHandlerRedis(unittest.TestCase):
    """Test BackgroundTaskHandler with Redis storage."""

    def setUp(self):
        self.settings = BackgroundTaskSettings(use_redis=True, cleanup_hours=1)
        self.redis = MagicMock()
        self.handler = BackgroundTaskHandler(
            redis_client=self.redis, settings=self.settings
        )

    def test_set_storage_uses_redis(self):
        """Test that set_storage delegates to Redis."""
        self.handler._set_storage("j1", {"status": "pending"})
        self.redis.set.assert_called_once()
        key = self.redis.set.call_args[0][0]
        self.assertIn("j1", key)

    def test_get_storage_uses_redis(self):
        """Test that get_storage delegates to Redis."""
        self.redis.get.return_value = {"status": "running"}
        result = self.handler._get_storage("j2")
        self.redis.get.assert_called_once()
        self.assertEqual(result["status"], "running")

    def test_delete_storage_uses_redis(self):
        """Test that delete_storage delegates to Redis."""
        self.handler._delete_storage("j3")
        self.redis.delete.assert_called_once()


class TestBackgroundTaskHandlerAsync(unittest.IsolatedAsyncioTestCase):
    """Test async background task execution."""

    def setUp(self):
        self.settings = BackgroundTaskSettings(use_redis=False)
        self.handler = BackgroundTaskHandler(settings=self.settings)

    async def test_run_background_task_success(self):
        """Test successful background task execution."""
        async def dummy_task():
            return {"result": "ok"}

        self.handler.create_job("aj-1")
        await self.handler.run_background_task("aj-1", dummy_task)
        status = self.handler.get_task_status("aj-1")
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["result"], {"result": "ok"})

    async def test_run_background_task_failure(self):
        """Test background task that raises an exception."""
        async def failing_task():
            raise ValueError("something broke")

        self.handler.create_job("aj-2")
        await self.handler.run_background_task("aj-2", failing_task)
        status = self.handler.get_task_status("aj-2")
        self.assertEqual(status["status"], "failed")
        self.assertIn("ValueError", status["error"])

    async def test_start_background_task(self):
        """Test starting a background task and tracking it."""
        completed = asyncio.Event()

        async def tracked_task():
            completed.set()
            return "done"

        self.handler.create_job("aj-3")
        self.handler.start_background_task("aj-3", tracked_task)
        self.assertIn("aj-3", self.handler._running_tasks)
        await asyncio.wait_for(completed.wait(), timeout=5.0)
        await asyncio.sleep(0.1)
        status = self.handler.get_task_status("aj-3")
        self.assertEqual(status["status"], "completed")

    async def test_cancel_running_task(self):
        """Test cancelling a running async task."""
        started = asyncio.Event()

        async def long_task():
            started.set()
            await asyncio.sleep(60)

        self.handler.create_job("aj-4")
        self.handler.start_background_task("aj-4", long_task)
        await asyncio.wait_for(started.wait(), timeout=5.0)
        result = self.handler.cancel_job("aj-4")
        self.assertTrue(result)
        await asyncio.sleep(0.2)
        status = self.handler.get_task_status("aj-4")
        self.assertEqual(status["status"], "cancelled")


class TestPipelineConcurrencyControl(unittest.IsolatedAsyncioTestCase):
    """Test pipeline slot management for concurrency control."""

    def setUp(self):
        self.settings = BackgroundTaskSettings(
            use_redis=False, max_concurrent_pipelines=1,
        )
        self.handler = BackgroundTaskHandler(settings=self.settings)

    async def test_acquire_and_release_slot(self):
        """Test basic acquire and release of a pipeline slot."""
        await self.handler.acquire_pipeline_slot("job-1")
        self.assertIn("job-1", self.handler._pipeline_events)
        self.handler.release_pipeline_slot("job-1")
        self.assertNotIn("job-1", self.handler._pipeline_events)

    async def test_signal_unblocks_wait(self):
        """Test that signaling completion unblocks wait_for_pipeline."""
        await self.handler.acquire_pipeline_slot("job-1")

        async def signal_after_delay():
            await asyncio.sleep(0.1)
            self.handler.signal_pipeline_complete("job-1")

        asyncio.create_task(signal_after_delay())
        await asyncio.wait_for(
            self.handler.wait_for_pipeline("job-1"), timeout=2.0,
        )
        self.handler.release_pipeline_slot("job-1")

    async def test_second_job_waits_for_first(self):
        """Test that a second job blocks until the first releases its slot."""
        order = []

        async def pipeline(job_id: str, delay: float):
            await self.handler.acquire_pipeline_slot(job_id)
            try:
                order.append(f"{job_id}_start")
                await asyncio.sleep(delay)
                order.append(f"{job_id}_end")
            finally:
                self.handler.release_pipeline_slot(job_id)

        task1 = asyncio.create_task(pipeline("job-1", 0.2))
        await asyncio.sleep(0.05)
        task2 = asyncio.create_task(pipeline("job-2", 0.1))

        await asyncio.gather(task1, task2)

        self.assertEqual(order, [
            "job-1_start", "job-1_end",
            "job-2_start", "job-2_end",
        ])

    async def test_concurrent_slots_with_higher_limit(self):
        """Test that multiple jobs run concurrently when limit allows."""
        settings = BackgroundTaskSettings(
            use_redis=False, max_concurrent_pipelines=2,
        )
        handler = BackgroundTaskHandler(settings=settings)

        order = []
        barrier = asyncio.Event()

        async def pipeline(job_id: str):
            await handler.acquire_pipeline_slot(job_id)
            try:
                order.append(f"{job_id}_start")
                barrier.set()
                await asyncio.sleep(0.1)
                order.append(f"{job_id}_end")
            finally:
                handler.release_pipeline_slot(job_id)

        task1 = asyncio.create_task(pipeline("job-1"))
        task2 = asyncio.create_task(pipeline("job-2"))

        await asyncio.gather(task1, task2)

        self.assertIn("job-1_start", order[:2])
        self.assertIn("job-2_start", order[:2])

    async def test_cancellation_releases_slot(self):
        """Test that cancelling a waiting task releases the slot."""
        await self.handler.acquire_pipeline_slot("job-1")

        async def blocked_pipeline():
            await self.handler.acquire_pipeline_slot("job-2")
            self.handler.release_pipeline_slot("job-2")

        task = asyncio.create_task(blocked_pipeline())
        await asyncio.sleep(0.05)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.handler.release_pipeline_slot("job-1")

        await asyncio.wait_for(
            self.handler.acquire_pipeline_slot("job-3"), timeout=1.0,
        )
        self.handler.release_pipeline_slot("job-3")

    async def test_signal_nonexistent_job_is_noop(self):
        """Test that signaling a non-existent job does nothing."""
        self.handler.signal_pipeline_complete("nonexistent")

    async def test_release_already_released_slot(self):
        """Test that releasing an already-released slot logs warning."""
        await self.handler.acquire_pipeline_slot("job-1")
        self.handler.release_pipeline_slot("job-1")
        self.handler.release_pipeline_slot("job-1")

    async def test_event_based_pipeline_flow(self):
        """Test the full event-based flow: acquire → wait → signal → release."""
        order = []

        async def run_pipeline(job_id: str):
            """Simulates run_pipeline_task with concurrency control."""
            await self.handler.acquire_pipeline_slot(job_id)
            try:
                order.append(f"{job_id}_acquired")
                await self.handler.wait_for_pipeline(job_id)
                order.append(f"{job_id}_done")
            finally:
                self.handler.release_pipeline_slot(job_id)

        async def simulate_callback(job_id: str, delay: float):
            """Simulates process_callback_async signaling completion."""
            await asyncio.sleep(delay)
            self.handler.signal_pipeline_complete(job_id)

        task1 = asyncio.create_task(run_pipeline("job-1"))
        await asyncio.sleep(0.05)
        task2 = asyncio.create_task(run_pipeline("job-2"))
        await asyncio.sleep(0.05)

        self.assertEqual(order, ["job-1_acquired"])

        asyncio.create_task(simulate_callback("job-1", 0.1))
        await asyncio.sleep(0.2)

        self.assertIn("job-1_done", order)
        self.assertIn("job-2_acquired", order)

        asyncio.create_task(simulate_callback("job-2", 0.1))
        await asyncio.gather(task1, task2)

        self.assertEqual(order, [
            "job-1_acquired", "job-1_done",
            "job-2_acquired", "job-2_done",
        ])


if __name__ == "__main__":
    unittest.main()
