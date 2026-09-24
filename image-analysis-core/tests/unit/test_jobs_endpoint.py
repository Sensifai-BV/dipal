"""Unit tests for Jobs API endpoint and pipeline orchestration helpers."""
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from api_gateway.app.api.v1.endpoints.jobs import (
    UploadResult,
    _upload_stage_products_background,
    _extract_orthomosaic_metadata,
    process_callback_async,
    upload_stage_products,
    trigger_next_stage,
    run_pipeline_task,
)
from infrastructure.state import ProcessingStage as StateProcessingStage


class TestUploadResult(unittest.TestCase):
    """Tests for UploadResult helper class."""

    def test_empty_result(self):
        r = UploadResult()
        self.assertFalse(r.has_failures)
        self.assertFalse(r.has_critical_failure)
        self.assertEqual(len(r.uploaded), 0)
        self.assertEqual(len(r.failed), 0)

    def test_with_success(self):
        r = UploadResult()
        r.uploaded.append({"product_type": "dsm", "product_id": "p1"})
        self.assertFalse(r.has_failures)

    def test_with_non_critical_failure(self):
        r = UploadResult()
        r.failed.append({"product_type": "hillshade", "error": "fail"})
        self.assertTrue(r.has_failures)
        self.assertFalse(r.has_critical_failure)

    def test_with_critical_failure(self):
        r = UploadResult()
        r.failed.append({"product_type": "orthomosaic", "error": "fail"})
        self.assertTrue(r.has_failures)
        self.assertTrue(r.has_critical_failure)


class TestUploadStageProducts(unittest.IsolatedAsyncioTestCase):
    """Tests for upload_stage_products function."""

    def setUp(self):
        self.mock_upload_client = AsyncMock()

    async def test_calibration_with_manifest(self):
        result_data = {"band_manifest": {"green": {"path": "/tmp/g"}}}
        self.mock_upload_client.upload_product = AsyncMock(return_value={"product_id": "p1", "s3_uri": "s3://b/k"})
        result = await upload_stage_products(
            "calibration", "job1", result_data, self.mock_upload_client,
        )
        self.mock_upload_client.upload_product.assert_called_once()

    async def test_calibration_no_manifest(self):
        result = await upload_stage_products(
            "calibration", "job1", {}, self.mock_upload_client,
        )
        self.mock_upload_client.upload_product.assert_not_called()
        self.assertFalse(result.has_failures)

    async def test_sfm_with_run_path(self):
        tmpdir = Path(tempfile.mkdtemp())
        dense = tmpdir / "dense"
        dense.mkdir()
        fused = dense / "fused.ply"
        fused.write_text("fake")
        mesh = dense / "meshed-poisson.ply"
        mesh.write_text("fake")

        self.mock_upload_client.upload_product = AsyncMock(
            return_value={"product_id": "p1", "s3_uri": "s3://b/k"}
        )
        result = await upload_stage_products(
            "sfm", "job1", {"run_path": str(tmpdir)}, self.mock_upload_client,
        )
        self.assertEqual(self.mock_upload_client.upload_product.call_count, 2)

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    async def test_sfm_missing_run_path(self):
        result = await upload_stage_products(
            "sfm", "job1", {"run_path": "/tmp/nonexistent_xyz_11111"}, self.mock_upload_client,
        )
        self.mock_upload_client.upload_product.assert_not_called()

    async def test_orthomosaic_uploads(self):
        tmpdir = Path(tempfile.mkdtemp())
        ortho = tmpdir / "ortho.tif"
        ortho.write_text("fake")
        dsm = tmpdir / "dsm.tif"
        dsm.write_text("fake")

        outputs = {
            "orthomosaic_rgb": str(ortho),
            "dsm_filled_cog": str(dsm),
        }
        self.mock_upload_client.upload_product = AsyncMock(
            return_value={"product_id": "p1", "s3_uri": "s3://b/k"}
        )
        result = await upload_stage_products(
            "orthomosaic", "job1", {"outputs": outputs, "dataset_id": "d1"},
            self.mock_upload_client,
        )
        self.assertEqual(self.mock_upload_client.upload_product.call_count, 2)

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    async def test_orthomosaic_with_vi_and_multiband(self):
        tmpdir = Path(tempfile.mkdtemp())
        ndvi = tmpdir / "ndvi.tif"
        ndvi.write_text("fake")
        mb = tmpdir / "multiband.tif"
        mb.write_text("fake")

        outputs = {
            "ndvi": str(ndvi),
            "multiband_reflectance": str(mb),
        }
        self.mock_upload_client.upload_product = AsyncMock(
            return_value={"product_id": "p1", "s3_uri": "s3://b/k"}
        )
        result = await upload_stage_products(
            "orthomosaic", "job1", {"outputs": outputs, "dataset_id": "d1"},
            self.mock_upload_client,
        )
        self.assertEqual(self.mock_upload_client.upload_product.call_count, 2)

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    async def test_upload_failure_tracked(self):
        self.mock_upload_client.upload_product = AsyncMock(side_effect=Exception("upload fail"))

        tmpdir = Path(tempfile.mkdtemp())
        ortho = tmpdir / "ortho.tif"
        ortho.write_text("fake")

        mock_state = MagicMock()
        result = await upload_stage_products(
            "orthomosaic", "job1",
            {"outputs": {"orthomosaic_rgb": str(ortho)}, "dataset_id": "d1"},
            self.mock_upload_client,
            job_state_manager=mock_state,
            main_job_id="main_job",
        )
        self.assertTrue(result.has_failures)
        mock_state.update_job.assert_called_once()

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


class TestTriggerNextStage(unittest.IsolatedAsyncioTestCase):
    """Tests for trigger_next_stage function."""

    def _make_job_state(self, **overrides):
        state = MagicMock()
        state.job_id = "job1"
        state.backend_job_id = "backend_job1"
        state.dataset_id = "dataset1"
        state.download_url = "http://example.com/images.zip"
        state.parameters = {}
        state.stage_results = {}
        for k, v in overrides.items():
            setattr(state, k, v)
        return state

    @patch("infrastructure.storage.s3_settings.TempStorageSettings")
    async def test_trigger_sfm(self, mock_temp):
        job_state = self._make_job_state()
        mock_sfm = AsyncMock()
        mock_backend = AsyncMock()
        mock_ortho = AsyncMock()
        mock_state_mgr = MagicMock()
        mock_temp_mgr = MagicMock()

        await trigger_next_stage(
            StateProcessingStage.SFM, job_state, mock_state_mgr,
            mock_sfm, mock_ortho, mock_backend, mock_temp_mgr,
        )
        mock_sfm.run_sfm.assert_called_once()
        mock_backend.send_progress_update.assert_called_once()

    @patch("infrastructure.storage.s3_settings.TempStorageSettings")
    async def test_trigger_orthomosaic(self, mock_temp):
        mock_temp.return_value = MagicMock(base_path="/data/temp")
        job_state = self._make_job_state(
            stage_results={"sfm": {"run_path": "/data/sfm/run_1"}},
        )
        mock_sfm = AsyncMock()
        mock_backend = AsyncMock()
        mock_ortho = AsyncMock()
        mock_state_mgr = MagicMock()
        mock_temp_mgr = MagicMock()

        await trigger_next_stage(
            StateProcessingStage.ORTHOMOSAIC, job_state, mock_state_mgr,
            mock_sfm, mock_ortho, mock_backend, mock_temp_mgr,
        )
        mock_ortho.run_orthomosaic.assert_called_once()

    @patch("infrastructure.storage.s3_settings.TempStorageSettings")
    async def test_trigger_orthomosaic_with_calibration(self, mock_temp):
        mock_temp.return_value = MagicMock(base_path="/data/temp")
        job_state = self._make_job_state(
            stage_results={
                "sfm": {"run_path": "/data/sfm/run_1"},
                "radiometric_calibration": {
                    "is_multispectral": True,
                    "calibration_path": "/data/cal",
                    "band_manifest": {"green": {}},
                    "has_reflectance": True,
                },
            },
        )
        mock_sfm = AsyncMock()
        mock_backend = AsyncMock()
        mock_ortho = AsyncMock()
        mock_state_mgr = MagicMock()
        mock_temp_mgr = MagicMock()

        await trigger_next_stage(
            StateProcessingStage.ORTHOMOSAIC, job_state, mock_state_mgr,
            mock_sfm, mock_ortho, mock_backend, mock_temp_mgr,
        )
        call_kwargs = mock_ortho.run_orthomosaic.call_args
        params = call_kwargs[1]["parameters"] if "parameters" in call_kwargs[1] else call_kwargs[0][3]
        self.assertTrue(params.get("is_multispectral"))

    @patch("infrastructure.storage.s3_settings.TempStorageSettings")
    async def test_trigger_uploading_stage(self, mock_temp):
        job_state = self._make_job_state(stage_results={"sfm": {}, "orthomosaic": {}})
        mock_sfm = AsyncMock()
        mock_backend = AsyncMock()
        mock_ortho = AsyncMock()
        mock_state_mgr = MagicMock()
        mock_state_mgr.complete_stage.return_value = (job_state, None)
        mock_temp_mgr = MagicMock()

        await trigger_next_stage(
            StateProcessingStage.UPLOADING, job_state, mock_state_mgr,
            mock_sfm, mock_ortho, mock_backend, mock_temp_mgr,
        )
        mock_backend.send_completion.assert_called_once()


class TestProcessCallbackAsync(unittest.IsolatedAsyncioTestCase):
    """Tests for process_callback_async."""

    def _make_mocks(self):
        state_mgr = MagicMock()
        backend = AsyncMock()
        sfm = AsyncMock()
        ortho = AsyncMock()
        upload_client = AsyncMock()
        temp_mgr = MagicMock()
        return state_mgr, backend, sfm, ortho, upload_client, temp_mgr

    def _make_job_state(self, **overrides):
        state = MagicMock()
        state.job_id = "job1"
        state.backend_job_id = "backend_job1"
        state.dataset_id = "d1"
        state.download_url = "http://example.com"
        state.parameters = {}
        state.stage_results = {}
        state.progress = 50.0
        state.created_at = "2024-01-01T00:00:00+00:00"
        for k, v in overrides.items():
            setattr(state, k, v)
        return state

    @patch("api_gateway.app.api.v1.endpoints.jobs.upload_stage_products")
    @patch("api_gateway.app.api.v1.endpoints.jobs.trigger_next_stage")
    async def test_completed_callback_triggers_next(self, mock_trigger, mock_upload):
        state_mgr, backend, sfm, ortho, upload_client, temp_mgr = self._make_mocks()
        job_state = self._make_job_state()
        next_stage = StateProcessingStage.SFM

        state_mgr.get_job.return_value = job_state
        state_mgr.complete_stage.return_value = (job_state, next_stage)
        mock_upload.return_value = UploadResult()

        callback_data = {
            "service": "calibration",
            "job_id": "job1_calibration",
            "status": "completed",
            "result": {"calibration_path": "/data/cal"},
        }

        await process_callback_async(
            callback_data, state_mgr, backend, sfm, ortho, upload_client, temp_mgr,
        )

        state_mgr.complete_stage.assert_called_once()
        mock_trigger.assert_called_once()
        backend.send_progress_update.assert_called_once()

    @patch("api_gateway.app.api.v1.endpoints.jobs.upload_stage_products")
    @patch("api_gateway.app.api.v1.endpoints.jobs.record_job_completion")
    async def test_completed_final_stage(self, mock_record, mock_upload):
        state_mgr, backend, sfm, ortho, upload_client, temp_mgr = self._make_mocks()
        job_state = self._make_job_state()

        state_mgr.get_job.return_value = job_state
        state_mgr.complete_stage.return_value = (job_state, None)
        mock_upload.return_value = UploadResult()

        callback_data = {
            "service": "orthomosaic",
            "job_id": "job1_orthomosaic",
            "status": "completed",
            "result": {"outputs": {}},
        }

        await process_callback_async(
            callback_data, state_mgr, backend, sfm, ortho, upload_client, temp_mgr,
        )

        backend.send_completion.assert_called_once()
        mock_record.assert_called_once()

    @patch("api_gateway.app.api.v1.endpoints.jobs.record_job_failure")
    async def test_failed_callback(self, mock_record_fail):
        state_mgr, backend, sfm, ortho, upload_client, temp_mgr = self._make_mocks()
        job_state = self._make_job_state()

        state_mgr.get_job.return_value = job_state

        callback_data = {
            "service": "sfm",
            "job_id": "job1_sfm",
            "status": "failed",
            "error": "SFM processing failed",
        }

        await process_callback_async(
            callback_data, state_mgr, backend, sfm, ortho, upload_client, temp_mgr,
        )

        state_mgr.fail_stage.assert_called_once()
        backend.send_failure.assert_called_once()
        mock_record_fail.assert_called_once()

    async def test_job_not_found(self):
        state_mgr, backend, sfm, ortho, upload_client, temp_mgr = self._make_mocks()
        state_mgr.get_job.return_value = None

        callback_data = {
            "service": "sfm",
            "job_id": "missing_sfm",
            "status": "completed",
            "result": {},
        }

        await process_callback_async(
            callback_data, state_mgr, backend, sfm, ortho, upload_client, temp_mgr,
        )
        state_mgr.complete_stage.assert_not_called()

    @patch("api_gateway.app.api.v1.endpoints.jobs.upload_stage_products")
    @patch("api_gateway.app.api.v1.endpoints.jobs.trigger_next_stage")
    async def test_callback_error_notifies_backend(self, mock_trigger, mock_upload):
        state_mgr, backend, sfm, ortho, upload_client, temp_mgr = self._make_mocks()
        job_state = self._make_job_state()
        state_mgr.get_job.return_value = job_state
        state_mgr.complete_stage.side_effect = RuntimeError("state error")

        callback_data = {
            "service": "sfm",
            "job_id": "job1_sfm",
            "status": "completed",
            "result": {},
        }

        await process_callback_async(
            callback_data, state_mgr, backend, sfm, ortho, upload_client, temp_mgr,
        )
        backend.send_failure.assert_called_once()


class TestRunPipelineTask(unittest.IsolatedAsyncioTestCase):
    """Tests for run_pipeline_task."""

    def _make_job_state(self, current_stage=StateProcessingStage.PENDING, **overrides):
        state = MagicMock()
        state.job_id = "job1"
        state.backend_job_id = "backend_job1"
        state.dataset_id = "d1"
        state.download_url = "http://example.com"
        state.parameters = {}
        state.stage_results = {}
        state.current_stage = current_stage
        for k, v in overrides.items():
            setattr(state, k, v)
        return state

    async def test_start_from_pending_triggers_calibration(self):
        job_state = self._make_job_state(StateProcessingStage.PENDING)
        state_mgr = MagicMock()
        state_mgr.get_job.return_value = job_state
        cal = AsyncMock()
        sfm = AsyncMock()
        ortho = AsyncMock()
        backend = AsyncMock()
        temp = MagicMock()

        result = await run_pipeline_task("job1", state_mgr, cal, sfm, ortho, backend, temp_manager=temp)
        cal.run_calibration.assert_called_once()
        sfm.run_sfm.assert_not_called()

    async def test_start_from_sfm(self):
        job_state = self._make_job_state(StateProcessingStage.SFM)
        state_mgr = MagicMock()
        state_mgr.get_job.return_value = job_state
        cal = AsyncMock()
        sfm = AsyncMock()
        ortho = AsyncMock()
        backend = AsyncMock()
        temp = MagicMock()

        result = await run_pipeline_task("job1", state_mgr, cal, sfm, ortho, backend, temp_manager=temp)
        sfm.run_sfm.assert_called_once()
        cal.run_calibration.assert_not_called()

    @patch("infrastructure.storage.s3_settings.TempStorageSettings")
    async def test_start_from_orthomosaic(self, mock_temp):
        mock_temp.return_value = MagicMock(base_path="/data/temp")
        job_state = self._make_job_state(StateProcessingStage.ORTHOMOSAIC)
        state_mgr = MagicMock()
        state_mgr.get_job.return_value = job_state
        cal = AsyncMock()
        sfm = AsyncMock()
        ortho = AsyncMock()
        backend = AsyncMock()
        temp = MagicMock()

        result = await run_pipeline_task("job1", state_mgr, cal, sfm, ortho, backend, temp_manager=temp)
        ortho.run_orthomosaic.assert_called_once()

    async def test_job_not_found_raises(self):
        state_mgr = MagicMock()
        state_mgr.get_job.return_value = None
        cal = AsyncMock()
        sfm = AsyncMock()
        ortho = AsyncMock()
        backend = AsyncMock()
        temp = MagicMock()

        with self.assertRaises(ValueError):
            await run_pipeline_task("missing", state_mgr, cal, sfm, ortho, backend, temp_manager=temp)

    async def test_pipeline_error_updates_state(self):
        job_state = self._make_job_state(StateProcessingStage.PENDING)
        state_mgr = MagicMock()
        state_mgr.get_job.return_value = job_state
        cal = AsyncMock()
        cal.run_calibration.side_effect = RuntimeError("calibration failed")
        sfm = AsyncMock()
        ortho = AsyncMock()
        backend = AsyncMock()
        temp = MagicMock()

        with self.assertRaises(RuntimeError):
            await run_pipeline_task("job1", state_mgr, cal, sfm, ortho, backend, temp_manager=temp)

        state_mgr.update_job.assert_called_once()
        backend.send_failure.assert_called_once()


class TestUploadStageProductsBackground(unittest.IsolatedAsyncioTestCase):
    """Tests for _upload_stage_products_background fire-and-forget wrapper."""

    @patch("api_gateway.app.api.v1.endpoints.jobs.upload_stage_products")
    async def test_background_upload_success(self, mock_upload):
        """Test background wrapper calls upload_stage_products and returns cleanly."""
        mock_upload.return_value = UploadResult()
        mock_backend = AsyncMock()

        await _upload_stage_products_background(
            service_name="sfm",
            job_id="bj1",
            result={"run_path": "/data/run_1"},
            product_upload_client=AsyncMock(),
            backend_client=mock_backend,
            job_state_manager=MagicMock(),
            main_job_id="j1",
        )
        mock_upload.assert_awaited_once()
        mock_backend.send_upload_status.assert_awaited_once()

    @patch("api_gateway.app.api.v1.endpoints.jobs.upload_stage_products")
    async def test_background_upload_partial_failure_sends_status(self, mock_upload):
        """Test background wrapper sends upload status with failures to backend."""
        result = UploadResult()
        result.failed.append({"product_type": "mesh", "error": "timeout"})
        mock_upload.return_value = result
        mock_backend = AsyncMock()

        await _upload_stage_products_background(
            service_name="sfm",
            job_id="bj1",
            result={"run_path": "/data/run_1"},
            product_upload_client=AsyncMock(),
            backend_client=mock_backend,
            main_job_id="j1",
        )
        mock_upload.assert_awaited_once()
        mock_backend.send_upload_status.assert_awaited_once_with(
            job_id="bj1",
            uploaded=[],
            failed=[{"product_type": "mesh", "error": "timeout"}],
        )

    @patch("api_gateway.app.api.v1.endpoints.jobs.upload_stage_products")
    async def test_background_upload_exception_caught(self, mock_upload):
        """Test background wrapper catches exceptions instead of propagating."""
        mock_upload.side_effect = RuntimeError("connection refused")
        mock_backend = AsyncMock()

        await _upload_stage_products_background(
            service_name="sfm",
            job_id="bj1",
            result={},
            product_upload_client=AsyncMock(),
            backend_client=mock_backend,
            main_job_id="j1",
        )


class TestNonBlockingUploadPattern(unittest.IsolatedAsyncioTestCase):
    """Tests verifying uploads don't block the pipeline."""

    def _make_mocks(self):
        state_mgr = MagicMock()
        backend = AsyncMock()
        sfm = AsyncMock()
        ortho = AsyncMock()
        upload_client = AsyncMock()
        temp_mgr = MagicMock()
        return state_mgr, backend, sfm, ortho, upload_client, temp_mgr

    def _make_job_state(self, **overrides):
        state = MagicMock()
        state.job_id = "job1"
        state.backend_job_id = "backend_job1"
        state.dataset_id = "d1"
        state.download_url = "http://example.com"
        state.parameters = {}
        state.stage_results = {}
        state.progress = 50.0
        state.created_at = "2024-01-01T00:00:00+00:00"
        for k, v in overrides.items():
            setattr(state, k, v)
        return state

    @patch("api_gateway.app.api.v1.endpoints.jobs._upload_stage_products_background", new_callable=MagicMock)
    @patch("api_gateway.app.api.v1.endpoints.jobs.trigger_next_stage")
    async def test_upload_fires_via_create_task_after_trigger(self, mock_trigger, mock_bg_upload):
        """Test that trigger_next_stage is awaited directly and upload is fired via create_task."""
        state_mgr, backend, sfm, ortho, upload_client, temp_mgr = self._make_mocks()
        job_state = self._make_job_state()
        state_mgr.get_job.return_value = job_state
        state_mgr.complete_stage.return_value = (job_state, StateProcessingStage.SFM)

        call_order = []
        async def track_trigger(*a, **kw):
            call_order.append("trigger")
        mock_trigger.side_effect = track_trigger
        mock_bg_upload.return_value = None

        callback_data = {
            "service": "calibration",
            "job_id": "job1_calibration",
            "status": "completed",
            "result": {"band_manifest": {"green": {}}},
        }

        with patch("api_gateway.app.api.v1.endpoints.jobs.asyncio") as mock_asyncio:
            mock_asyncio.create_task = MagicMock()
            await process_callback_async(
                callback_data, state_mgr, backend, sfm, ortho, upload_client, temp_mgr,
            )

        mock_trigger.assert_awaited_once()
        mock_asyncio.create_task.assert_called_once()

    @patch("api_gateway.app.api.v1.endpoints.jobs._upload_stage_products_background", new_callable=MagicMock)
    @patch("api_gateway.app.api.v1.endpoints.jobs.trigger_next_stage")
    async def test_sfm_callback_upload_non_blocking(self, mock_trigger, mock_bg_upload):
        """Test SFM callback triggers orthomosaic before starting upload."""
        state_mgr, backend, sfm, ortho, upload_client, temp_mgr = self._make_mocks()
        job_state = self._make_job_state()
        state_mgr.get_job.return_value = job_state
        state_mgr.complete_stage.return_value = (job_state, StateProcessingStage.ORTHOMOSAIC)
        mock_bg_upload.return_value = None

        callback_data = {
            "service": "sfm",
            "job_id": "job1_sfm",
            "status": "completed",
            "result": {"run_path": "/data/run_1", "outputs": {}},
        }

        with patch("api_gateway.app.api.v1.endpoints.jobs.asyncio") as mock_asyncio:
            mock_asyncio.create_task = MagicMock()
            await process_callback_async(
                callback_data, state_mgr, backend, sfm, ortho, upload_client, temp_mgr,
            )

        mock_trigger.assert_awaited_once()
        mock_asyncio.create_task.assert_called_once()

    @patch("api_gateway.app.api.v1.endpoints.jobs._upload_stage_products_background", new_callable=MagicMock)
    @patch("api_gateway.app.api.v1.endpoints.jobs.record_job_completion")
    async def test_final_stage_upload_non_blocking(self, mock_record, mock_bg_upload):
        """Test final stage sends completion then fires background upload."""
        state_mgr, backend, sfm, ortho, upload_client, temp_mgr = self._make_mocks()
        job_state = self._make_job_state()
        state_mgr.get_job.return_value = job_state
        state_mgr.complete_stage.return_value = (job_state, None)
        mock_bg_upload.return_value = None

        callback_data = {
            "service": "orthomosaic",
            "job_id": "job1_orthomosaic",
            "status": "completed",
            "result": {"outputs": {"orthomosaic_rgb": "/data/ortho.tif"}},
        }

        with patch("api_gateway.app.api.v1.endpoints.jobs.asyncio") as mock_asyncio:
            mock_asyncio.create_task = MagicMock()
            await process_callback_async(
                callback_data, state_mgr, backend, sfm, ortho, upload_client, temp_mgr,
            )

        backend.send_completion.assert_called_once()
        mock_asyncio.create_task.assert_called_once()

    @patch("api_gateway.app.api.v1.endpoints.jobs._upload_stage_products_background", new_callable=MagicMock)
    @patch("api_gateway.app.api.v1.endpoints.jobs.trigger_next_stage")
    async def test_calibration_callback_upload_non_blocking(self, mock_trigger, mock_bg_upload):
        """Test calibration callback triggers SFM before starting upload."""
        state_mgr, backend, sfm, ortho, upload_client, temp_mgr = self._make_mocks()
        job_state = self._make_job_state()
        state_mgr.get_job.return_value = job_state
        state_mgr.complete_stage.return_value = (job_state, StateProcessingStage.SFM)
        mock_bg_upload.return_value = None

        callback_data = {
            "service": "calibration",
            "job_id": "job1_calibration",
            "status": "completed",
            "result": {"calibration_path": "/data/cal", "band_manifest": {}},
        }

        with patch("api_gateway.app.api.v1.endpoints.jobs.asyncio") as mock_asyncio:
            mock_asyncio.create_task = MagicMock()
            await process_callback_async(
                callback_data, state_mgr, backend, sfm, ortho, upload_client, temp_mgr,
            )

        mock_trigger.assert_awaited_once()
        mock_asyncio.create_task.assert_called_once()


class TestExtractOrthomosaicMetadata(unittest.TestCase):
    """Tests for _extract_orthomosaic_metadata helper."""

    def test_empty_outputs(self):
        """No statistics key returns empty dict."""
        result = _extract_orthomosaic_metadata({})
        self.assertEqual(result, {})

    def test_missing_statistics_file(self):
        """Non-existent statistics file returns empty dict."""
        result = _extract_orthomosaic_metadata({"statistics": "/nonexistent/path.json"})
        self.assertEqual(result, {})

    def test_valid_statistics_file(self):
        """Metadata is extracted from a valid statistics JSON file."""
        import json

        stats = {
            "outputs": {
                "orthomosaic_rgb.tif": {
                    "width": 5000,
                    "height": 4000,
                    "bands": 3,
                    "geotransform": [0.0, 0.05, 0.0, 0.0, 0.0, -0.05],
                    "crs": "EPSG:32637",
                    "size_mb": 150.5,
                },
                "dsm_filled_cog.tif": {
                    "width": 5000,
                    "height": 4000,
                    "bands": 1,
                    "geotransform": [0.0, 0.05, 0.0, 0.0, 0.0, -0.05],
                    "crs": "EPSG:32637",
                    "size_mb": 20.0,
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(stats, f)
            stats_path = f.name

        try:
            result = _extract_orthomosaic_metadata({"statistics": stats_path})
        finally:
            Path(stats_path).unlink()

        self.assertIn("orthomosaic", result)
        self.assertAlmostEqual(result["orthomosaic"]["resolution_cm"], 5.0, places=2)
        self.assertEqual(result["orthomosaic"]["bands"], ["band_1", "band_2", "band_3"])
        self.assertEqual(result["orthomosaic"]["stats"]["width"], 5000)

        self.assertIn("dsm", result)
        self.assertEqual(result["dsm"]["bands"], ["band_1"])

    def test_malformed_json(self):
        """Malformed JSON file returns empty dict."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not json {{{")
            stats_path = f.name

        try:
            result = _extract_orthomosaic_metadata({"statistics": stats_path})
        finally:
            Path(stats_path).unlink()

        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
