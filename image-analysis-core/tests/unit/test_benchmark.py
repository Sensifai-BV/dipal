import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from benchmark.report import ReportGenerator
from benchmark.runners.base import BaseRunner, RunResult
from benchmark.settings import BenchmarkSettings
from benchmark.validators.checkpoint import CheckpointValidator
from benchmark.validators.radiometric import RadiometricValidator


def _make_settings(**overrides) -> BenchmarkSettings:
    """Create BenchmarkSettings with test defaults."""
    defaults = {
        "dataset_path": Path("/tmp/test_dataset"),
        "output_path": Path("/tmp/test_output"),
        "gpu_count": 0,
        "num_runs": 1,
        "timeout_seconds": 60,
        "gateway_url": "http://localhost:8080",
        "run_stages": "all",
    }
    defaults.update(overrides)
    return BenchmarkSettings(**defaults)


class TestBenchmarkSettings(unittest.TestCase):
    """Tests for BenchmarkSettings."""

    def test_get_stages_all(self):
        """Test that 'all' returns all three stages."""
        settings = _make_settings(run_stages="all")
        self.assertEqual(settings.get_stages(), ["calibration", "sfm", "orthomosaic"])

    def test_get_stages_specific(self):
        """Test parsing comma-separated stage list."""
        settings = _make_settings(run_stages="sfm, orthomosaic")
        self.assertEqual(settings.get_stages(), ["sfm", "orthomosaic"])

    def test_get_stages_single(self):
        """Test single stage parsing."""
        settings = _make_settings(run_stages="sfm")
        self.assertEqual(settings.get_stages(), ["sfm"])

    def test_default_thresholds(self):
        """Test default validation thresholds."""
        settings = _make_settings()
        self.assertAlmostEqual(settings.checkpoint_rmse_h_threshold, 0.10)
        self.assertAlmostEqual(settings.checkpoint_rmse_v_threshold, 0.15)
        self.assertAlmostEqual(settings.radiometric_r2_threshold, 0.85)
        self.assertAlmostEqual(settings.reproducibility_threshold, 0.99)
        self.assertAlmostEqual(settings.gsd_accuracy_threshold, 0.05)


class TestBaseRunner(unittest.TestCase):
    """Tests for BaseRunner timing and error handling."""

    def test_run_wraps_with_timing(self):
        """Test that run() populates elapsed_seconds."""

        class DummyRunner(BaseRunner):
            @property
            def stage_name(self):
                return "dummy"

            def _execute(self, run_index):
                return RunResult(
                    stage="dummy",
                    run_index=run_index,
                    success=True,
                    elapsed_seconds=0.0,
                )

        runner = DummyRunner(_make_settings())
        result = runner.run(run_index=0)
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.elapsed_seconds, 0.0)

    def test_run_catches_exception(self):
        """Test that run() catches exceptions and returns failure."""

        class FailRunner(BaseRunner):
            @property
            def stage_name(self):
                return "fail"

            def _execute(self, run_index):
                raise RuntimeError("test error")

        runner = FailRunner(_make_settings())
        result = runner.run(run_index=0)
        self.assertFalse(result.success)
        self.assertEqual(result.error, "test error")
        self.assertGreaterEqual(result.elapsed_seconds, 0.0)

    def test_run_multiple(self):
        """Test run_multiple runs the configured number of times."""

        class CountRunner(BaseRunner):
            @property
            def stage_name(self):
                return "count"

            def _execute(self, run_index):
                return RunResult(
                    stage="count",
                    run_index=run_index,
                    success=True,
                    elapsed_seconds=0.0,
                )

        runner = CountRunner(_make_settings(num_runs=3))
        results = runner.run_multiple()
        self.assertEqual(len(results), 3)
        self.assertEqual([r.run_index for r in results], [0, 1, 2])


class TestCheckpointValidator(unittest.TestCase):
    """Tests for CheckpointValidator RMSE computation."""

    def test_compute_rmse(self):
        """Test RMSE computation."""
        errors = [3.0, 4.0]
        rmse = CheckpointValidator._compute_rmse(errors)
        expected = math.sqrt((9 + 16) / 2)
        self.assertAlmostEqual(rmse, expected, places=6)

    def test_compute_rmse_empty(self):
        """Test RMSE with empty list returns 0."""
        self.assertEqual(CheckpointValidator._compute_rmse([]), 0.0)

    def test_validate_with_matched_points(self):
        """Test full validation flow with matching GCP files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gt_path = Path(tmpdir) / "ground_truth"
            gt_path.mkdir()

            gcp_csv = gt_path / "gcps.csv"
            gcp_csv.write_text("id,x,y,z\nP1,100.0,200.0,50.0\nP2,300.0,400.0,60.0\n")

            output_path = Path(tmpdir) / "output"
            output_path.mkdir()
            est_csv = output_path / "estimated_coords.csv"
            est_csv.write_text("id,x,y,z\nP1,100.05,200.03,50.02\nP2,300.1,400.08,60.05\n")

            settings = _make_settings(
                ground_truth_path=gt_path,
                checkpoint_rmse_h_threshold=1.0,
                checkpoint_rmse_v_threshold=1.0,
            )
            validator = CheckpointValidator(settings)
            result = validator.validate(output_path)

            self.assertEqual(result.num_checkpoints, 2)
            self.assertTrue(result.passed_horizontal)
            self.assertTrue(result.passed_vertical)
            self.assertGreater(result.horizontal_rmse, 0)
            self.assertLess(result.horizontal_rmse, 0.2)

    def test_validate_no_ground_truth(self):
        """Test that missing ground truth raises FileNotFoundError."""
        settings = _make_settings(ground_truth_path=None)
        validator = CheckpointValidator(settings)
        with self.assertRaises(FileNotFoundError):
            validator.validate(Path("/tmp/nonexistent"))


class TestRadiometricValidator(unittest.TestCase):
    """Tests for RadiometricValidator R² computation."""

    def test_compute_r_squared_perfect(self):
        """Test R² = 1.0 for perfect fit."""
        import numpy as np

        observed = np.array([1.0, 2.0, 3.0, 4.0])
        predicted = np.array([1.0, 2.0, 3.0, 4.0])
        r2 = RadiometricValidator._compute_r_squared(observed, predicted)
        self.assertAlmostEqual(r2, 1.0, places=6)

    def test_compute_r_squared_poor(self):
        """Test R² < 1.0 for poor fit."""
        import numpy as np

        observed = np.array([1.0, 2.0, 3.0, 4.0])
        predicted = np.array([4.0, 3.0, 2.0, 1.0])
        r2 = RadiometricValidator._compute_r_squared(observed, predicted)
        self.assertLess(r2, 0.0)

    def test_compute_r_squared_single_sample(self):
        """Test R² = 0.0 with insufficient samples."""
        import numpy as np

        r2 = RadiometricValidator._compute_r_squared(
            np.array([1.0]), np.array([1.0])
        )
        self.assertEqual(r2, 0.0)

    def test_parse_reflectance_csv(self):
        """Test parsing a reflectance CSV file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.csv"
            path.write_text("id,red,green,nir\n1,0.1,0.2,0.3\n2,0.4,0.5,0.6\n")
            result = RadiometricValidator._parse_reflectance_csv(path)
            self.assertIn("red", result)
            self.assertEqual(result["red"], [0.1, 0.4])
            self.assertEqual(result["green"], [0.2, 0.5])
            self.assertEqual(result["nir"], [0.3, 0.6])


class TestReportGenerator(unittest.TestCase):
    """Tests for ReportGenerator."""

    def test_generate_creates_json(self):
        """Test report generation produces valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = _make_settings(output_path=Path(tmpdir))
            gen = ReportGenerator(settings)

            run_results = {
                "sfm": [
                    RunResult(
                        stage="sfm",
                        run_index=0,
                        success=True,
                        elapsed_seconds=10.5,
                    ),
                    RunResult(
                        stage="sfm",
                        run_index=1,
                        success=True,
                        elapsed_seconds=11.2,
                    ),
                ],
            }

            report_path = gen.generate(run_results)
            self.assertTrue(report_path.exists())

            report = json.loads(report_path.read_text())
            self.assertIn("metadata", report)
            self.assertIn("stages", report)
            self.assertIn("overall", report)
            self.assertEqual(report["overall"]["verdict"], "PASS")
            self.assertEqual(report["overall"]["total_runs"], 2)
            self.assertEqual(report["overall"]["total_passed"], 2)

    def test_summarize_stage_with_failures(self):
        """Test stage summary includes failure count."""
        results = [
            RunResult(stage="sfm", run_index=0, success=True, elapsed_seconds=5.0),
            RunResult(stage="sfm", run_index=1, success=False, elapsed_seconds=2.0, error="timeout"),
        ]
        summary = ReportGenerator._summarize_stage(results)
        self.assertEqual(summary["total_runs"], 2)
        self.assertEqual(summary["successful_runs"], 1)
        self.assertEqual(summary["failed_runs"], 1)
        self.assertAlmostEqual(summary["success_rate"], 0.5)

    def test_overall_verdict_fail_on_run_failure(self):
        """Test overall verdict is FAIL when any run fails."""
        run_results = {
            "sfm": [
                RunResult(stage="sfm", run_index=0, success=False, elapsed_seconds=1.0),
            ],
        }
        overall = ReportGenerator._compute_overall(run_results, None)
        self.assertEqual(overall["verdict"], "FAIL")

    def test_overall_verdict_fail_on_validation(self):
        """Test overall verdict is FAIL when validation fails."""
        run_results = {
            "sfm": [
                RunResult(stage="sfm", run_index=0, success=True, elapsed_seconds=1.0),
            ],
        }
        mock_validation = MagicMock()
        mock_validation.passed = False
        validation = {"checkpoint": mock_validation}
        overall = ReportGenerator._compute_overall(run_results, validation)
        self.assertEqual(overall["verdict"], "FAIL")


class TestCLIParser(unittest.TestCase):
    """Tests for the CLI argument parser."""

    def test_build_parser_no_required_args_accepts_empty(self):
        """Test parser accepts empty args (validation happens in main)."""
        from benchmark.__main__ import build_parser

        parser = build_parser()
        args = parser.parse_args([])
        self.assertIsNone(args.dataset_path)

    def test_build_parser_defaults(self):
        """Test parser default values."""
        from benchmark.__main__ import build_parser

        parser = build_parser()
        args = parser.parse_args(["--dataset-path", "/data/images"])
        self.assertEqual(args.dataset_path, Path("/data/images"))
        self.assertEqual(args.gpu_count, 1)
        self.assertEqual(args.num_runs, 1)
        self.assertEqual(args.stages, "all")
        self.assertFalse(args.validate)

    def test_build_parser_all_args(self):
        """Test parser with all arguments."""
        from benchmark.__main__ import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--dataset-path", "/data/images",
            "--output-path", "/results",
            "--ground-truth", "/data/gcps",
            "--gpu-count", "4",
            "--num-runs", "5",
            "--timeout", "7200",
            "--stages", "sfm,orthomosaic",
            "--target-gsd", "2.5",
            "--max-image-size", "3000",
            "--validate",
            "--checkpoint-rmse-h", "0.05",
            "--radiometric-r2", "0.90",
        ])
        self.assertEqual(args.gpu_count, 4)
        self.assertEqual(args.num_runs, 5)
        self.assertEqual(args.stages, "sfm,orthomosaic")
        self.assertAlmostEqual(args.target_gsd, 2.5)
        self.assertTrue(args.validate)

    def test_args_to_settings(self):
        """Test conversion from argparse Namespace to BenchmarkSettings."""
        from benchmark.__main__ import args_to_settings, build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--dataset-path", "/data/images",
            "--gpu-count", "2",
            "--stages", "sfm",
        ])
        settings = args_to_settings(args)
        self.assertEqual(settings.dataset_path, Path("/data/images"))
        self.assertEqual(settings.gpu_count, 2)
        self.assertEqual(settings.get_stages(), ["sfm"])

    def test_dataset_preset_flag(self):
        """Test --dataset flag with preset name."""
        from benchmark.__main__ import apply_preset, build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--dataset-path", "/data/zenodo",
            "--dataset", "zenodo-eastkazakhstan",
        ])
        args = apply_preset(args)
        self.assertEqual(args.stages, "calibration,sfm,orthomosaic")
        self.assertAlmostEqual(args.target_gsd, 3.0)

    def test_dataset_preset_no_override_explicit(self):
        """Test --dataset does not override explicit --stages."""
        from benchmark.__main__ import apply_preset, build_parser

        parser = build_parser()
        args = parser.parse_args([
            "--dataset-path", "/data/zenodo",
            "--dataset", "zenodo-eastkazakhstan",
            "--stages", "sfm",
        ])
        args = apply_preset(args)
        self.assertEqual(args.stages, "sfm")

    def test_detect_layout_flag(self):
        """Test --detect-layout flag is parsed."""
        from benchmark.__main__ import build_parser

        parser = build_parser()
        args = parser.parse_args(["--detect-layout", "/data/zenodo"])
        self.assertEqual(args.detect_layout, Path("/data/zenodo"))


class TestDatasetPresets(unittest.TestCase):
    """Tests for the dataset presets module."""

    def test_get_preset_known(self):
        """Test retrieving a known preset."""
        from benchmark.datasets import get_preset

        preset = get_preset("zenodo-eastkazakhstan")
        self.assertIsNotNone(preset)
        self.assertEqual(preset.name, "zenodo-eastkazakhstan")
        self.assertEqual(preset.sensor_type, "multispectral")
        self.assertAlmostEqual(preset.expected_gsd_cm, 3.0)

    def test_get_preset_wur(self):
        """Test retrieving WUR preset."""
        from benchmark.datasets import get_preset

        preset = get_preset("wur-dataverse")
        self.assertIsNotNone(preset)
        self.assertEqual(preset.stages, ["calibration"])

    def test_get_preset_unknown(self):
        """Test unknown preset returns None."""
        from benchmark.datasets import get_preset

        self.assertIsNone(get_preset("nonexistent-dataset"))

    def test_list_presets(self):
        """Test listing all presets."""
        from benchmark.datasets import list_presets

        presets = list_presets()
        self.assertGreaterEqual(len(presets), 2)
        names = [p.name for p in presets]
        self.assertIn("zenodo-eastkazakhstan", names)
        self.assertIn("wur-dataverse", names)

    def test_detect_layout(self):
        """Test dataset layout detection."""
        from benchmark.datasets import detect_dataset_layout

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            img_dir = root / "images"
            img_dir.mkdir()
            (img_dir / "IMG_001.jpg").write_bytes(b"fake")
            (img_dir / "IMG_002.tif").write_bytes(b"fake")
            (root / "gcps.csv").write_text("id,x,y,z\n")

            layout = detect_dataset_layout(root)
            self.assertEqual(layout["image_count"], 2)
            self.assertIn("images", layout["image_dirs"])
            self.assertTrue(any("gcps.csv" in f for f in layout["ground_truth_files"]))


class TestVegetationIndexValidator(unittest.TestCase):
    """Tests for VegetationIndexValidator."""

    def test_compute_ndvi(self):
        """Test NDVI computation from NIR and Red arrays."""
        import numpy as np
        from benchmark.validators.vegetation import VegetationIndexValidator

        nir = np.array([0.8, 0.6, 0.4])
        red = np.array([0.2, 0.3, 0.4])
        ndvi = VegetationIndexValidator.compute_ndvi(nir, red)
        self.assertAlmostEqual(ndvi[0], 0.6, places=5)
        self.assertAlmostEqual(ndvi[1], 1 / 3, places=5)
        self.assertAlmostEqual(ndvi[2], 0.0, places=5)

    def test_compute_ndre(self):
        """Test NDRE computation from NIR and RedEdge arrays."""
        import numpy as np
        from benchmark.validators.vegetation import VegetationIndexValidator

        nir = np.array([0.8, 0.6])
        rededge = np.array([0.4, 0.3])
        ndre = VegetationIndexValidator.compute_ndre(nir, rededge)
        expected_0 = (0.8 - 0.4) / (0.8 + 0.4)
        expected_1 = (0.6 - 0.3) / (0.6 + 0.3)
        self.assertAlmostEqual(ndre[0], expected_0, places=5)
        self.assertAlmostEqual(ndre[1], expected_1, places=5)

    def test_compute_ndvi_zero_denominator(self):
        """Test NDVI handles zero denominator gracefully."""
        import numpy as np
        from benchmark.validators.vegetation import VegetationIndexValidator

        nir = np.array([0.0, 0.5])
        red = np.array([0.0, 0.1])
        ndvi = VegetationIndexValidator.compute_ndvi(nir, red)
        self.assertTrue(np.isnan(ndvi[0]))
        self.assertAlmostEqual(ndvi[1], (0.5 - 0.1) / (0.5 + 0.1), places=5)

    def test_r_squared_perfect(self):
        """Test R² = 1.0 for perfect vegetation index match."""
        import numpy as np
        from benchmark.validators.vegetation import VegetationIndexValidator

        obs = np.array([0.1, 0.3, 0.5, 0.7])
        pred = np.array([0.1, 0.3, 0.5, 0.7])
        self.assertAlmostEqual(
            VegetationIndexValidator._compute_r_squared(obs, pred), 1.0, places=6
        )

    def test_r_squared_single_sample(self):
        """Test R² = 0.0 with insufficient samples."""
        import numpy as np
        from benchmark.validators.vegetation import VegetationIndexValidator

        self.assertEqual(
            VegetationIndexValidator._compute_r_squared(
                np.array([0.5]), np.array([0.5])
            ),
            0.0,
        )

    def test_parse_index_csv(self):
        """Test parsing vegetation index CSV file."""
        from benchmark.validators.vegetation import VegetationIndexValidator

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "indices.csv"
            path.write_text("id,ndvi,ndre\n1,0.45,0.30\n2,0.60,0.40\n")
            result = VegetationIndexValidator._parse_index_csv(path)
            self.assertIn("ndvi", result)
            self.assertEqual(result["ndvi"], [0.45, 0.60])
            self.assertEqual(result["ndre"], [0.30, 0.40])
            self.assertNotIn("id", result)

    def test_validate_with_csv_data(self):
        """Test full validation flow with CSV reference and computed data."""
        from benchmark.validators.vegetation import VegetationIndexValidator

        with tempfile.TemporaryDirectory() as tmpdir:
            gt_path = Path(tmpdir) / "ground_truth"
            gt_path.mkdir()
            (gt_path / "reference_ndvi.csv").write_text(
                "plot_id,ndvi\n1,0.45\n2,0.60\n3,0.72\n4,0.80\n"
            )

            output_path = Path(tmpdir) / "output"
            output_path.mkdir()
            (output_path / "vegetation_indices.csv").write_text(
                "plot_id,ndvi\n1,0.44\n2,0.61\n3,0.71\n4,0.79\n"
            )

            settings = _make_settings(
                ground_truth_path=gt_path,
                vegetation_r2_threshold=0.90,
            )
            validator = VegetationIndexValidator(settings)
            result = validator.validate(output_path)

            self.assertIsNotNone(result.ndvi_r_squared)
            self.assertGreater(result.ndvi_r_squared, 0.90)
            self.assertTrue(result.passed)
            self.assertEqual(result.num_samples, 4)

    def test_validate_no_ground_truth(self):
        """Test missing ground truth raises FileNotFoundError."""
        from benchmark.validators.vegetation import VegetationIndexValidator

        settings = _make_settings(ground_truth_path=None)
        validator = VegetationIndexValidator(settings)
        with self.assertRaises(FileNotFoundError):
            validator.validate(Path("/tmp/nonexistent"))


class TestPerformanceCollector(unittest.TestCase):
    """Tests for PerformanceCollector."""

    def test_compute_throughput(self):
        """Test images/min computation from run results."""
        from benchmark.validators.performance import PerformanceCollector

        run_results = {
            "sfm": [
                RunResult(
                    stage="sfm", run_index=0, success=True,
                    elapsed_seconds=120.0,
                    metrics={"image_count": 60},
                ),
            ],
            "calibration": [
                RunResult(
                    stage="calibration", run_index=0, success=True,
                    elapsed_seconds=60.0,
                    metrics={"image_count": 60},
                ),
            ],
        }
        throughput = PerformanceCollector._compute_throughput(run_results)
        self.assertAlmostEqual(throughput["sfm"], 30.0)
        self.assertAlmostEqual(throughput["calibration"], 60.0)

    def test_compute_throughput_no_images(self):
        """Test throughput with zero images returns empty dict."""
        from benchmark.validators.performance import PerformanceCollector

        run_results = {
            "sfm": [
                RunResult(
                    stage="sfm", run_index=0, success=True,
                    elapsed_seconds=10.0, metrics={},
                ),
            ],
        }
        throughput = PerformanceCollector._compute_throughput(run_results)
        self.assertNotIn("sfm", throughput)

    def test_compute_throughput_failed_runs(self):
        """Test throughput ignores failed runs."""
        from benchmark.validators.performance import PerformanceCollector

        run_results = {
            "sfm": [
                RunResult(
                    stage="sfm", run_index=0, success=False,
                    elapsed_seconds=10.0, metrics={"image_count": 50},
                ),
            ],
        }
        throughput = PerformanceCollector._compute_throughput(run_results)
        self.assertEqual(throughput, {})

    def test_measure_memory_peak(self):
        """Test peak memory measurement returns positive value."""
        from benchmark.validators.performance import PerformanceCollector

        mem = PerformanceCollector._measure_memory_peak()
        self.assertIsNotNone(mem)
        self.assertGreater(mem, 0.0)

    def test_measure_output_size(self):
        """Test output directory size measurement."""
        from benchmark.validators.performance import PerformanceCollector

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            (path / "file1.json").write_text("x" * 1024)
            (path / "file2.json").write_text("x" * 2048)
            size_mb = PerformanceCollector._measure_output_size(path)
            self.assertGreater(size_mb, 0.0)
            self.assertAlmostEqual(size_mb, (1024 + 2048) / (1024 * 1024), places=4)

    def test_measure_output_size_missing_dir(self):
        """Test output size returns 0 for missing directory."""
        from benchmark.validators.performance import PerformanceCollector

        self.assertEqual(
            PerformanceCollector._measure_output_size(Path("/nonexistent")), 0.0
        )

    def test_estimate_queue_latency_with_timestamps(self):
        """Test queue latency estimation from submit/start timestamps."""
        from benchmark.validators.performance import PerformanceCollector

        run_results = {
            "sfm": [
                RunResult(
                    stage="sfm", run_index=0, success=True,
                    elapsed_seconds=10.0,
                    metrics={"submit_time": 1000.0, "start_time": 1002.5},
                ),
                RunResult(
                    stage="sfm", run_index=1, success=True,
                    elapsed_seconds=11.0,
                    metrics={"submit_time": 1020.0, "start_time": 1021.5},
                ),
            ],
        }
        latency = PerformanceCollector._estimate_queue_latency(run_results)
        self.assertAlmostEqual(latency["sfm"], 2.0)

    def test_estimate_queue_latency_no_timestamps(self):
        """Test queue latency returns None when timestamps are absent."""
        from benchmark.validators.performance import PerformanceCollector

        run_results = {
            "sfm": [
                RunResult(
                    stage="sfm", run_index=0, success=True,
                    elapsed_seconds=10.0, metrics={},
                ),
            ],
        }
        latency = PerformanceCollector._estimate_queue_latency(run_results)
        self.assertIsNone(latency["sfm"])

    def test_scaling_efficiency_perfect(self):
        """Test scaling efficiency = 1.0 for perfect linear scaling."""
        from benchmark.validators.performance import PerformanceCollector

        run_results = {
            "sfm": [
                RunResult(
                    stage="sfm", run_index=0, success=True,
                    elapsed_seconds=100.0,
                    metrics={"gpu_count": 1},
                ),
                RunResult(
                    stage="sfm", run_index=1, success=True,
                    elapsed_seconds=50.0,
                    metrics={"gpu_count": 2},
                ),
            ],
        }
        eff = PerformanceCollector._compute_scaling_efficiency(run_results)
        self.assertIsNotNone(eff)
        self.assertAlmostEqual(eff, 1.0)

    def test_scaling_efficiency_no_data(self):
        """Test scaling efficiency returns None without multi-GPU data."""
        from benchmark.validators.performance import PerformanceCollector

        run_results = {
            "sfm": [
                RunResult(
                    stage="sfm", run_index=0, success=True,
                    elapsed_seconds=100.0, metrics={},
                ),
            ],
        }
        self.assertIsNone(
            PerformanceCollector._compute_scaling_efficiency(run_results)
        )

    def test_collect_full(self):
        """Test full performance collection workflow."""
        from benchmark.validators.performance import PerformanceCollector

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)
            (output_path / "result.json").write_text("{}")

            settings = _make_settings(output_path=output_path)
            collector = PerformanceCollector(settings)

            run_results = {
                "sfm": [
                    RunResult(
                        stage="sfm", run_index=0, success=True,
                        elapsed_seconds=60.0,
                        metrics={"image_count": 30},
                    ),
                ],
            }
            result = collector.collect(run_results)
            self.assertIn("sfm", result.throughput_images_per_min)
            self.assertAlmostEqual(result.throughput_images_per_min["sfm"], 30.0)
            self.assertIsNotNone(result.memory_peak_mb)
            self.assertIsInstance(result.gpu_devices, list)
            self.assertGreater(result.storage_output_mb, 0.0)
            self.assertTrue(result.passed)
            self.assertIn("gpu_names", result.details)

    def test_capture_memory_snapshot(self):
        """Test memory snapshot helper function."""
        from benchmark.validators.performance import capture_memory_snapshot

        mem = capture_memory_snapshot()
        self.assertIsNotNone(mem)
        self.assertGreater(mem, 0.0)

    def test_query_gpu_devices_returns_list(self):
        """Test GPU query returns a list (empty if no GPU/pynvml)."""
        from benchmark.validators.performance import PerformanceCollector

        devices = PerformanceCollector._query_gpu_devices()
        self.assertIsInstance(devices, list)

    def test_get_gpu_memory_peak_empty(self):
        """Test GPU memory peak returns None for empty device list."""
        from benchmark.validators.performance import PerformanceCollector

        self.assertIsNone(PerformanceCollector._get_gpu_memory_peak([]))

    def test_get_gpu_memory_peak_with_devices(self):
        """Test GPU memory peak returns max used across devices."""
        from benchmark.validators.performance import GpuInfo, PerformanceCollector

        devices = [
            GpuInfo(
                name="GPU-0", index=0,
                memory_total_mb=8192, memory_used_mb=3000,
                memory_free_mb=5192, utilization_percent=60.0,
                temperature_celsius=65.0,
            ),
            GpuInfo(
                name="GPU-1", index=1,
                memory_total_mb=8192, memory_used_mb=5000,
                memory_free_mb=3192, utilization_percent=80.0,
                temperature_celsius=72.0,
            ),
        ]
        peak = PerformanceCollector._get_gpu_memory_peak(devices)
        self.assertAlmostEqual(peak, 5000.0)

    def test_gpu_info_dataclass(self):
        """Test GpuInfo dataclass fields."""
        from benchmark.validators.performance import GpuInfo

        gpu = GpuInfo(
            name="NVIDIA RTX 4090",
            index=0,
            memory_total_mb=24576.0,
            memory_used_mb=4096.0,
            memory_free_mb=20480.0,
            utilization_percent=45.0,
            temperature_celsius=68.0,
        )
        self.assertEqual(gpu.name, "NVIDIA RTX 4090")
        self.assertEqual(gpu.index, 0)
        self.assertAlmostEqual(gpu.memory_total_mb, 24576.0)
        self.assertAlmostEqual(gpu.utilization_percent, 45.0)

    def test_query_gpu_no_pynvml(self):
        """Test GPU query gracefully handles missing pynvml."""
        from benchmark.validators.performance import PerformanceCollector

        with patch.dict("sys.modules", {"pynvml": None}):
            devices = PerformanceCollector._query_gpu_devices()
            self.assertEqual(devices, [])


class TestDatasetPresetsExtended(unittest.TestCase):
    """Tests for Aukerman and DroneMapper dataset presets."""

    def test_get_preset_aukerman(self):
        """Test retrieving ODM Aukerman preset."""
        from benchmark.datasets import get_preset

        preset = get_preset("odm-aukerman")
        self.assertIsNotNone(preset)
        self.assertEqual(preset.sensor_type, "rgb")
        self.assertAlmostEqual(preset.expected_gsd_cm, 2.5)
        self.assertEqual(preset.stages, ["sfm", "orthomosaic"])
        self.assertIn("github.com", preset.source_url)

    def test_get_preset_dronemapper(self):
        """Test retrieving DroneMapper sample preset."""
        from benchmark.datasets import get_preset

        preset = get_preset("dronemapper-sample")
        self.assertIsNotNone(preset)
        self.assertEqual(preset.sensor_type, "rgb")
        self.assertEqual(preset.stages, ["sfm", "orthomosaic"])
        self.assertIn("orthomosaic", preset.reference_products)
        self.assertIn("dsm", preset.reference_products)

    def test_list_presets_includes_new(self):
        """Test listing presets includes all four datasets."""
        from benchmark.datasets import list_presets

        presets = list_presets()
        names = [p.name for p in presets]
        self.assertIn("odm-aukerman", names)
        self.assertIn("dronemapper-sample", names)
        self.assertEqual(len(presets), 4)


if __name__ == "__main__":
    unittest.main()
