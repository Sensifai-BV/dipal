"""Extended tests for jobs.py — API handler coverage and upload_stage_products edge cases."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from api_gateway.app.api.v1.endpoints.jobs import (
    UploadResult,
    upload_stage_products,
    process_callback_async,
)


class TestUploadStageProductsSFM(unittest.IsolatedAsyncioTestCase):
    """Tests for upload_stage_products with SFM service."""

    async def test_sfm_nonexistent_run_path(self):
        client = AsyncMock()
        result = {"run_path": "/tmp/nonexistent_xyz_98765", "dataset_id": "ds1"}
        upload = await upload_stage_products("sfm", "j1", result, client)
        self.assertEqual(len(upload.uploaded), 0)

    async def test_sfm_uploads_pointcloud_and_mesh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_path = Path(tmpdir) / "run_1"
            dense = run_path / "dense"
            dense.mkdir(parents=True)
            (dense / "fused.ply").write_bytes(b"\x00" * 100)
            (dense / "meshed-poisson.ply").write_bytes(b"\x00" * 100)

            client = AsyncMock()
            client.upload_product = AsyncMock(return_value={"product_id": "p1", "s3_uri": "s3://b/k"})

            result = {"run_path": str(run_path), "dataset_id": "ds1", "outputs": {}}
            upload = await upload_stage_products("sfm", "j1", result, client)
            self.assertEqual(len(upload.uploaded), 2)
            self.assertFalse(upload.has_failures)


class TestUploadStageProductsOrthomosaic(unittest.IsolatedAsyncioTestCase):
    """Tests for upload_stage_products with orthomosaic service."""

    async def test_orthomosaic_with_vi_and_multiband(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ("orthomosaic_rgb.tif", "dsm_filled_cog.tif", "hillshade.tif",
                         "ndvi.tif", "ndre.tif", "multiband_reflectance.tif",
                         "orthomosaic_rgb_2x.tif"):
                (Path(tmpdir) / name).write_bytes(b"\x00" * 50)

            outputs = {
                "orthomosaic_rgb": str(Path(tmpdir) / "orthomosaic_rgb.tif"),
                "dsm_filled_cog": str(Path(tmpdir) / "dsm_filled_cog.tif"),
                "hillshade": str(Path(tmpdir) / "hillshade.tif"),
                "ndvi": str(Path(tmpdir) / "ndvi.tif"),
                "ndre": str(Path(tmpdir) / "ndre.tif"),
                "multiband_reflectance": str(Path(tmpdir) / "multiband_reflectance.tif"),
                "orthomosaic_rgb_2x": str(Path(tmpdir) / "orthomosaic_rgb_2x.tif"),
            }

            client = AsyncMock()
            client.upload_product = AsyncMock(return_value={"product_id": "p1", "s3_uri": "s3://b/k"})

            result = {"outputs": outputs, "dataset_id": "ds1"}
            upload = await upload_stage_products("orthomosaic", "j1", result, client)
            self.assertEqual(len(upload.uploaded), 7)

    async def test_orthomosaic_file_not_found(self):
        outputs = {
            "orthomosaic_rgb": "/tmp/nonexistent_xyz_ortho.tif",
        }
        client = AsyncMock()
        result = {"outputs": outputs, "dataset_id": "ds1"}
        upload = await upload_stage_products("orthomosaic", "j1", result, client)
        self.assertEqual(len(upload.failed), 1)
        self.assertTrue(upload.has_critical_failure)

    async def test_orthomosaic_upload_exception_tracked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "orthomosaic_rgb.tif").write_bytes(b"\x00" * 50)

            client = AsyncMock()
            client.upload_product = AsyncMock(side_effect=RuntimeError("upload fail"))

            outputs = {"orthomosaic_rgb": str(Path(tmpdir) / "orthomosaic_rgb.tif")}
            result = {"outputs": outputs, "dataset_id": "ds1"}

            state_mgr = MagicMock()
            upload = await upload_stage_products(
                "orthomosaic", "j1", result, client,
                job_state_manager=state_mgr, main_job_id="main1",
            )
            self.assertEqual(len(upload.failed), 1)
            state_mgr.update_job.assert_called_once()

    async def test_orthomosaic_multi_resolution_all_scales(self):
        """Test all multi-resolution output scales (2x, 4x, 8x) are uploaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ("ortho_2x.tif", "ortho_4x.tif", "ortho_8x.tif"):
                (Path(tmpdir) / name).write_bytes(b"\x00" * 50)

            outputs = {
                "orthomosaic_rgb_2x": str(Path(tmpdir) / "ortho_2x.tif"),
                "orthomosaic_rgb_4x": str(Path(tmpdir) / "ortho_4x.tif"),
                "orthomosaic_rgb_8x": str(Path(tmpdir) / "ortho_8x.tif"),
            }

            client = AsyncMock()
            client.upload_product = AsyncMock(return_value={"product_id": "p1", "s3_uri": "s3://b/k"})

            result = {"outputs": outputs, "dataset_id": "ds1"}
            upload = await upload_stage_products("orthomosaic", "j1", result, client)
            self.assertEqual(len(upload.uploaded), 3)

            uploaded_types = {c[1]["product_type"] for c in client.upload_product.call_args_list}
            self.assertEqual(uploaded_types, {"orthomosaic_2x", "orthomosaic_4x", "orthomosaic_8x"})

    async def test_orthomosaic_all_vegetation_indices(self):
        """Test NDVI, NDRE, and GNDVI vegetation index outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ("ndvi.tif", "ndre.tif", "gndvi.tif"):
                (Path(tmpdir) / name).write_bytes(b"\x00" * 50)

            outputs = {
                "ndvi": str(Path(tmpdir) / "ndvi.tif"),
                "ndre": str(Path(tmpdir) / "ndre.tif"),
                "gndvi": str(Path(tmpdir) / "gndvi.tif"),
            }

            client = AsyncMock()
            client.upload_product = AsyncMock(return_value={"product_id": "p1", "s3_uri": "s3://b/k"})

            result = {"outputs": outputs, "dataset_id": "ds1"}
            upload = await upload_stage_products("orthomosaic", "j1", result, client)
            self.assertEqual(len(upload.uploaded), 3)

            uploaded_types = {c[1]["product_type"] for c in client.upload_product.call_args_list}
            self.assertEqual(uploaded_types, {"ndvi", "ndre", "gndvi"})

    async def test_orthomosaic_full_multispectral_pipeline(self):
        """Test complete multispectral orthomosaic output with all product types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "orthomosaic_rgb": "ortho_rgb.tif",
                "dsm_filled_cog": "dsm.tif",
                "hillshade": "hillshade.tif",
                "ndvi": "ndvi.tif",
                "ndre": "ndre.tif",
                "gndvi": "gndvi.tif",
                "multiband_reflectance": "multiband.tif",
                "orthomosaic_rgb_2x": "ortho_2x.tif",
                "orthomosaic_rgb_4x": "ortho_4x.tif",
                "orthomosaic_rgb_8x": "ortho_8x.tif",
            }
            outputs = {}
            for key, fname in files.items():
                path = Path(tmpdir) / fname
                path.write_bytes(b"\x00" * 50)
                outputs[key] = str(path)

            client = AsyncMock()
            client.upload_product = AsyncMock(return_value={"product_id": "p1", "s3_uri": "s3://b/k"})

            result = {"outputs": outputs, "dataset_id": "ds1"}
            upload = await upload_stage_products("orthomosaic", "j1", result, client)
            self.assertEqual(len(upload.uploaded), 10)
            self.assertFalse(upload.has_failures)


class TestUploadStageProductsCalibration(unittest.IsolatedAsyncioTestCase):
    """Tests for upload_stage_products with calibration service."""

    async def test_calibration_with_manifest(self):
        client = AsyncMock()
        client.upload_product = AsyncMock(return_value={"product_id": "p1", "s3_uri": "s3://b/k"})

        result = {
            "band_manifest": {"bands": {"green": {}}},
            "dataset_id": "ds1",
            "outputs": {},
        }
        upload = await upload_stage_products("calibration", "j1", result, client)
        self.assertEqual(len(upload.uploaded), 1)
        call_args = client.upload_product.call_args
        self.assertEqual(call_args[1]["product_type"], "band_manifest")


class TestProcessCallbackAsyncFailure(unittest.IsolatedAsyncioTestCase):
    """Tests for process_callback_async failure path."""

    async def test_failed_callback_records_metrics(self):
        state_mgr = MagicMock()
        job_state = MagicMock()
        job_state.backend_job_id = "bj1"
        job_state.dataset_id = "ds1"
        job_state.created_at = None
        state_mgr.get_job.return_value = job_state
        state_mgr.fail_stage.return_value = job_state

        backend = AsyncMock()

        callback_data = {
            "service": "sfm",
            "job_id": "j1_sfm",
            "status": "failed",
            "error": "SFM failed",
        }

        with patch("api_gateway.app.api.v1.endpoints.jobs.record_job_failure"):
            await process_callback_async(
                callback_data=callback_data,
                job_state_manager=state_mgr,
                backend_client=backend,
                sfm_client=AsyncMock(),
                orthomosaic_client=AsyncMock(),
                product_upload_client=AsyncMock(),
                temp_manager=MagicMock(),
            )
            backend.send_failure.assert_called_once()
            state_mgr.fail_stage.assert_called_once()


class TestProcessCallbackAsyncCompleted(unittest.IsolatedAsyncioTestCase):
    """Tests for process_callback_async completed path with upload."""

    async def test_completed_sfm_triggers_next_stage(self):
        state_mgr = MagicMock()
        job_state = MagicMock()
        job_state.backend_job_id = "bj1"
        job_state.dataset_id = "ds1"
        job_state.progress = 50.0
        job_state.created_at = None
        state_mgr.get_job.return_value = job_state
        state_mgr.complete_stage.return_value = (job_state, MagicMock(value="orthomosaic"))

        backend = AsyncMock()
        sfm = AsyncMock()
        ortho = AsyncMock()
        product_client = AsyncMock()

        callback_data = {
            "service": "sfm",
            "job_id": "j1_sfm",
            "status": "completed",
            "result": {"run_path": "/data/run_1", "dataset_id": "ds1", "outputs": {}},
        }

        with patch("api_gateway.app.api.v1.endpoints.jobs.upload_stage_products", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = MagicMock(has_failures=False, failed=[])
            with patch("api_gateway.app.api.v1.endpoints.jobs.trigger_next_stage", new_callable=AsyncMock):
                await process_callback_async(
                    callback_data=callback_data,
                    job_state_manager=state_mgr,
                    backend_client=backend,
                    sfm_client=sfm,
                    orthomosaic_client=ortho,
                    product_upload_client=product_client,
                    temp_manager=MagicMock(),
                )
                backend.send_progress_update.assert_called_once()
                state_mgr.complete_stage.assert_called_once()


class TestUploadBandZips(unittest.IsolatedAsyncioTestCase):
    """Tests for upload_stage_products — raw band zip products."""

    async def test_band_zips_uploaded_with_correct_product_types(self):
        """All five band_*_zip keys are uploaded as band_* product types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outputs = {}
            for band in ("green", "red", "red_edge", "nir", "blue"):
                zip_path = Path(tmpdir) / f"{band}_band.zip"
                zip_path.write_bytes(b"\x50\x4b\x05\x06" + b"\x00" * 18)
                outputs[f"band_{band}_zip"] = str(zip_path)

            client = AsyncMock()
            client.upload_product = AsyncMock(
                return_value={"product_id": "p1", "s3_uri": "s3://b/k"}
            )

            result = {"outputs": outputs, "dataset_id": "ds1"}
            upload = await upload_stage_products("orthomosaic", "j1", result, client)

            self.assertEqual(len(upload.uploaded), 5)
            uploaded_types = {
                c[1]["product_type"] for c in client.upload_product.call_args_list
            }
            expected = {"band_green", "band_red", "band_red_edge", "band_nir", "band_blue"}
            self.assertEqual(uploaded_types, expected)

    async def test_band_zip_missing_file_tracked_as_failure(self):
        """A missing band zip file is recorded as a failed product."""
        outputs = {
            "band_green_zip": "/tmp/nonexistent_xyz_green_band.zip",
        }
        client = AsyncMock()
        result = {"outputs": outputs, "dataset_id": "ds1"}
        upload = await upload_stage_products("orthomosaic", "j1", result, client)
        self.assertEqual(len(upload.failed), 1)
        self.assertEqual(upload.failed[0]["product_type"], "band_green")
        client.upload_product.assert_not_called()

    async def test_band_zips_alongside_other_products(self):
        """Band zips are uploaded in addition to (not instead of) other products."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "orthomosaic_rgb": "ortho.tif",
                "dsm_filled_cog": "dsm.tif",
                "ndvi": "ndvi.tif",
                "band_green_zip": "green_band.zip",
                "band_nir_zip": "nir_band.zip",
            }
            outputs = {}
            for key, fname in files.items():
                p = Path(tmpdir) / fname
                p.write_bytes(b"\x00" * 32)
                outputs[key] = str(p)

            client = AsyncMock()
            client.upload_product = AsyncMock(
                return_value={"product_id": "p1", "s3_uri": "s3://b/k"}
            )

            result = {"outputs": outputs, "dataset_id": "ds1"}
            upload = await upload_stage_products("orthomosaic", "j1", result, client)

            self.assertEqual(len(upload.uploaded), 5)
            uploaded_types = {
                c[1]["product_type"] for c in client.upload_product.call_args_list
            }
            self.assertIn("band_green", uploaded_types)
            self.assertIn("band_nir", uploaded_types)
            self.assertIn("orthomosaic", uploaded_types)
            self.assertIn("ndvi", uploaded_types)

    async def test_partial_bands_only_present_uploaded(self):
        """Only bands present in outputs are uploaded; absent bands are not failed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "red_band.zip"
            zip_path.write_bytes(b"\x00" * 32)
            outputs = {"band_red_zip": str(zip_path)}

            client = AsyncMock()
            client.upload_product = AsyncMock(
                return_value={"product_id": "p1", "s3_uri": "s3://b/k"}
            )

            result = {"outputs": outputs, "dataset_id": "ds1"}
            upload = await upload_stage_products("orthomosaic", "j1", result, client)

            self.assertEqual(len(upload.uploaded), 1)
            self.assertFalse(upload.has_failures)
            call_args = client.upload_product.call_args
            self.assertEqual(call_args[1]["product_type"], "band_red")


if __name__ == "__main__":
    unittest.main()
