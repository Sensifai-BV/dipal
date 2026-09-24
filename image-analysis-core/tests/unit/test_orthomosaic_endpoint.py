"""Unit tests for orthomosaic_endpoint helper functions."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))


ORTHO_MOD = "services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint"


class TestRunOrthomosaicTaskCached(unittest.IsolatedAsyncioTestCase):
    """Tests for run_orthomosaic_task when results already exist."""

    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    async def test_cached_results_skips_processing(self, mock_temp_cls, mock_cb):
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()

            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)

            workspace = Path(tmpdir) / "jobs" / "orthomosaic" / "j1"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "orthomosaic_rgb.tif").write_text("fake")
            (workspace / "dsm.tif").write_text("fake")

            result = await run_orthomosaic_task("j1", "ds1", str(ds_path), {})
            self.assertTrue(result["skipped_processing"])
            self.assertEqual(result["status"], "completed")
            self.assertIn("workspace_path", result)
            mock_cb.assert_called_once()

    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_full_pipeline_fast_mode(self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_cb):
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()
            (ds_path / "dense").mkdir()

            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline = MagicMock()
            mock_pipeline_cls.return_value = mock_pipeline

            with patch("asyncio.to_thread") as mock_thread:
                mock_thread.return_value = {"multi_res_2x": "/path/2x.tif"}

                result = await run_orthomosaic_task(
                    "j1", "ds1", str(ds_path), {"generate_cog": True},
                )

                self.assertEqual(result["status"], "completed")
                self.assertIn("outputs", result)
                self.assertIn("workspace_path", result)
                mock_cb.assert_called_once()

    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_full_pipeline_full_mode_multispectral(self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_cb):
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()
            (ds_path / "dense").mkdir()

            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline = MagicMock()
            mock_pipeline_cls.return_value = mock_pipeline

            with patch("asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = [
                    None,
                    {"ndvi": "/path/ndvi.tif", "ndre": "/path/ndre.tif"},
                ]

                result = await run_orthomosaic_task(
                    "j1", "ds1", str(ds_path),
                    {
                        "analysis_mode": "full",
                        "is_multispectral": True,
                        "calibration_path": "/data/cal",
                        "band_manifest": {"green": {}},
                    },
                )

                self.assertIn("ndvi", result["outputs"])
                self.assertEqual(mock_thread.call_count, 2)

    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_full_mode_missing_data_warns(self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_cb):
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()
            (ds_path / "dense").mkdir()

            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline = MagicMock()
            mock_pipeline_cls.return_value = mock_pipeline

            with patch("asyncio.to_thread") as mock_thread:
                mock_thread.return_value = None

                result = await run_orthomosaic_task(
                    "j1", "ds1", str(ds_path),
                    {"analysis_mode": "full", "is_multispectral": False},
                )

                self.assertEqual(result["status"], "completed")
                self.assertEqual(mock_thread.call_count, 1)


class TestCollectOutputs(unittest.TestCase):
    """Tests for _collect_outputs helper."""

    def test_returns_expected_keys(self):
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            _collect_outputs,
        )
        workspace = Path("/data/jobs/orthomosaic/j1")
        outputs = _collect_outputs(workspace)

        self.assertIn("dsm", outputs)
        self.assertIn("dsm_filled", outputs)
        self.assertIn("dsm_filled_cog", outputs)
        self.assertIn("orthomosaic_rgb", outputs)
        self.assertIn("hillshade", outputs)
        self.assertIn("statistics", outputs)
        self.assertEqual(outputs["orthomosaic_rgb"], str(workspace / "orthomosaic_rgb.tif"))


class TestSymlinkCreation(unittest.IsolatedAsyncioTestCase):
    """Tests for dense/ symlink from SFM into orthomosaic workspace."""

    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_symlink_created_for_dense_dir(self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_cb):
        """Verify dense/ symlink is created pointing to SFM input."""
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()
            dense_dir = ds_path / "dense"
            dense_dir.mkdir()
            (dense_dir / "fused.ply").write_text("fake")

            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline = MagicMock()
            mock_pipeline_cls.return_value = mock_pipeline

            with patch("asyncio.to_thread") as mock_thread:
                mock_thread.return_value = None

                await run_orthomosaic_task("j1", "ds1", str(ds_path), {})

                workspace = Path(tmpdir) / "jobs" / "orthomosaic" / "j1"
                link = workspace / "dense"
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), dense_dir.resolve())

    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_no_symlink_when_dense_missing(self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_cb):
        """Verify no symlink when SFM dense/ dir does not exist."""
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()

            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline = MagicMock()
            mock_pipeline_cls.return_value = mock_pipeline

            with patch("asyncio.to_thread") as mock_thread:
                mock_thread.return_value = None

                await run_orthomosaic_task("j1", "ds1", str(ds_path), {})

                workspace = Path(tmpdir) / "jobs" / "orthomosaic" / "j1"
                link = workspace / "dense"
                self.assertFalse(link.exists())

    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_geo_reference_symlinked_into_workspace(self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_cb):
        """geo_reference.json from SFM run_1/ must be symlinked into the orthomosaic workspace."""
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()
            (ds_path / "dense").mkdir()
            geo_ref_source = ds_path / "geo_reference.json"
            geo_ref_source.write_text('{"utm_epsg": 32636}')

            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline_cls.return_value = MagicMock()

            with patch("asyncio.to_thread", return_value=None):
                await run_orthomosaic_task("j1", "ds1", str(ds_path), {})

            workspace = Path(tmpdir) / "jobs" / "orthomosaic" / "j1"
            link = workspace / "geo_reference.json"
            self.assertTrue(link.is_symlink(), "geo_reference.json should be a symlink in the orthomosaic workspace")
            self.assertEqual(link.resolve(), geo_ref_source.resolve())

    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_no_geo_reference_symlink_when_source_absent(self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_cb):
        """When geo_reference.json is absent (model_aligner failed), no symlink is created."""
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()
            (ds_path / "dense").mkdir()
            # intentionally no geo_reference.json

            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline_cls.return_value = MagicMock()

            with patch("asyncio.to_thread", return_value=None):
                await run_orthomosaic_task("j1", "ds1", str(ds_path), {})

            workspace = Path(tmpdir) / "jobs" / "orthomosaic" / "j1"
            link = workspace / "geo_reference.json"
            self.assertFalse(link.exists(), "geo_reference.json symlink should not exist when source is absent")

    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_workspace_path_in_result(self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_cb):
        """Verify workspace_path is included in result dict."""
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()
            (ds_path / "dense").mkdir()

            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline = MagicMock()
            mock_pipeline_cls.return_value = mock_pipeline

            with patch("asyncio.to_thread") as mock_thread:
                mock_thread.return_value = None

                result = await run_orthomosaic_task("j1", "ds1", str(ds_path), {})

                expected_workspace = str(
                    Path(tmpdir) / "jobs" / "orthomosaic" / "j1"
                )
                self.assertEqual(result["workspace_path"], expected_workspace)
                self.assertIn("outputs", result)
                self.assertIn("orthomosaic_rgb", result["outputs"])


class TestSendOrthomosaicCallback(unittest.IsolatedAsyncioTestCase):
    """Tests for _send_orthomosaic_callback."""

    async def test_success(self):
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            _send_orthomosaic_callback,
        )
        settings = MagicMock(callback_url="http://gw/cb", timeout_seconds=5)

        with patch(f"{ORTHO_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "ok"
            mock_client.post = AsyncMock(return_value=mock_resp)

            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_client)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = ctx

            await _send_orthomosaic_callback(settings, "j1", {"status": "completed"})
            mock_client.post.assert_called_once()

    async def test_non_200_status(self):
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            _send_orthomosaic_callback,
        )
        settings = MagicMock(callback_url="http://gw/cb", timeout_seconds=5)

        with patch(f"{ORTHO_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = "error"
            mock_client.post = AsyncMock(return_value=mock_resp)

            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_client)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = ctx

            await _send_orthomosaic_callback(settings, "j1", {"status": "completed"})

    async def test_timeout_error(self):
        import httpx
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            _send_orthomosaic_callback,
        )
        settings = MagicMock(callback_url="http://gw/cb", timeout_seconds=5)

        with patch(f"{ORTHO_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_client)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = ctx

            await _send_orthomosaic_callback(settings, "j1", {})

    async def test_connect_error(self):
        import httpx
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            _send_orthomosaic_callback,
        )
        settings = MagicMock(callback_url="http://gw/cb", timeout_seconds=5)

        with patch(f"{ORTHO_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_client)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = ctx

            await _send_orthomosaic_callback(settings, "j1", {})

    async def test_generic_error(self):
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            _send_orthomosaic_callback,
        )
        settings = MagicMock(callback_url="http://gw/cb", timeout_seconds=5)

        with patch(f"{ORTHO_MOD}.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=RuntimeError("unexpected"))

            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_client)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = ctx

            await _send_orthomosaic_callback(settings, "j1", {})


class TestRunOrthomosaicTaskFailure(unittest.IsolatedAsyncioTestCase):
    """Tests that failure callbacks are sent when the pipeline crashes."""

    @patch(f"{ORTHO_MOD}._send_orthomosaic_failure_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_run_pipeline_failure_sends_failure_callback(
        self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_success_cb, mock_fail_cb
    ):
        """run_pipeline exception triggers failure callback and re-raises."""
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()
            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline_cls.return_value = MagicMock()

            with patch("asyncio.to_thread", side_effect=RuntimeError("COLMAP crashed")):
                with self.assertRaises(RuntimeError):
                    await run_orthomosaic_task("j1", "ds1", str(ds_path), {})

            mock_fail_cb.assert_called_once()
            call_args = mock_fail_cb.call_args[0]
            self.assertEqual(call_args[1], "j1")
            self.assertIn("RuntimeError", call_args[2])
            mock_success_cb.assert_not_called()

    @patch(f"{ORTHO_MOD}._send_orthomosaic_failure_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_ms_analysis_failure_sends_failure_callback(
        self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_success_cb, mock_fail_cb
    ):
        """run_multispectral_analysis exception triggers failure callback and re-raises."""
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()
            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline_cls.return_value = MagicMock()

            # First call (run_pipeline) succeeds; second call (run_multispectral_analysis) fails
            with patch("asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = [
                    None,  # run_pipeline succeeds
                    RuntimeError("GPS composite failed: no images could be warped"),
                ]

                with self.assertRaises(RuntimeError):
                    await run_orthomosaic_task(
                        "j1", "ds1", str(ds_path),
                        {
                            "analysis_mode": "full",
                            "is_multispectral": True,
                            "calibration_path": "/data/cal",
                            "band_manifest": {"green": {}},
                        },
                    )

            # Failure callback must be sent with the job id and error message
            mock_fail_cb.assert_called_once()
            call_args = mock_fail_cb.call_args[0]
            self.assertEqual(call_args[1], "j1")
            self.assertIn("GPS composite failed", call_args[2])
            # Success callback must NOT be sent
            mock_success_cb.assert_not_called()

    @patch(f"{ORTHO_MOD}._send_orthomosaic_failure_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}._send_orthomosaic_callback", new_callable=AsyncMock)
    @patch(f"{ORTHO_MOD}.TempStorageSettings")
    @patch(f"{ORTHO_MOD}.OrthomosaicPipeline")
    @patch(f"{ORTHO_MOD}.OrthomosaicService")
    async def test_ms_analysis_failure_error_message_includes_exception_type(
        self, mock_svc, mock_pipeline_cls, mock_temp_cls, mock_success_cb, mock_fail_cb
    ):
        """Failure callback error_msg includes exception type prefix."""
        from services.orthomosaic_generation.app.api.v1.endpoints.orthomosaic_endpoint import (
            run_orthomosaic_task,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "run_1"
            ds_path.mkdir()
            mock_temp_cls.return_value = MagicMock(base_path=tmpdir)
            mock_pipeline_cls.return_value = MagicMock()

            with patch("asyncio.to_thread") as mock_thread:
                mock_thread.side_effect = [
                    None,
                    ValueError("Invalid SRS for -t_srs"),
                ]

                with self.assertRaises(ValueError):
                    await run_orthomosaic_task(
                        "j2", "ds2", str(ds_path),
                        {
                            "analysis_mode": "full",
                            "is_multispectral": True,
                            "calibration_path": "/data/cal",
                        },
                    )

            error_msg = mock_fail_cb.call_args[0][2]
            # Must be formatted as "ExcType: message"
            self.assertTrue(error_msg.startswith("ValueError:"), error_msg)


if __name__ == "__main__":
    unittest.main()
