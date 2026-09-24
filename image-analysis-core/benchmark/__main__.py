"""
PhotoGear Benchmark CLI.

Usage:
    python -m benchmark --dataset-path /path/to/images
    python -m benchmark --dataset-path /data/images --gpu-count 2 --num-runs 3
    python -m benchmark --dataset-path /data/images --stages sfm,orthomosaic
    python -m benchmark --dataset-path /data/images --ground-truth /data/gcps --validate
    python -m benchmark --dataset zenodo-eastkazakhstan --dataset-path /data/zenodo_7749239
    python -m benchmark --detect-layout /data/zenodo_7749239
"""

import argparse
import json
import sys
from pathlib import Path

from benchmark.datasets import detect_dataset_layout, get_preset, list_presets
from benchmark.report import ReportGenerator
from benchmark.runners.pipeline import PipelineRunner
from benchmark.settings import BenchmarkSettings
from benchmark.validators.checkpoint import CheckpointValidator
from benchmark.validators.performance import PerformanceCollector, capture_memory_snapshot
from benchmark.validators.radiometric import RadiometricValidator
from benchmark.validators.spatial import SpatialValidator
from benchmark.validators.vegetation import VegetationIndexValidator
from benchmark.validators.visual import VisualQAValidator


def build_parser() -> argparse.ArgumentParser:
    """
    Build the CLI argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="PhotoGear AI Pipeline Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m benchmark --dataset-path ./data/images
  python -m benchmark --dataset-path ./data/images --gpu-count 2 --num-runs 3
  python -m benchmark --dataset-path ./data/images --stages sfm,orthomosaic
  python -m benchmark --dataset-path ./data/images --validate --ground-truth ./data/gcps
  python -m benchmark --dataset-path ./data/images --target-gsd 2.5 --timeout 7200
  python -m benchmark --dataset zenodo-eastkazakhstan --dataset-path /data/zenodo_7749239
  python -m benchmark --list-datasets
  python -m benchmark --detect-layout /data/zenodo_7749239
        """,
    )

    parser.add_argument(
        "--dataset-path",
        type=Path,
        required=False,
        default=None,
        help="Path to the dataset directory containing images/",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("benchmark_results"),
        help="Path to store benchmark results (default: benchmark_results/)",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help="Path to ground truth data (GCPs, reference reflectance)",
    )

    parser.add_argument(
        "--gpu-count",
        type=int,
        default=1,
        help="Number of GPUs to use (default: 1, set 0 for CPU only)",
    )
    parser.add_argument(
        "--num-runs",
        type=int,
        default=1,
        help="Number of runs for reproducibility testing (default: 1)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Timeout per stage in seconds (default: 3600)",
    )

    parser.add_argument(
        "--gateway-url",
        type=str,
        default="http://localhost:8080",
        help="API gateway base URL (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--file-server-url",
        type=str,
        default=None,
        help="HTTP file server URL for Docker-accessible image URLs (e.g. http://172.18.0.1:9000/dataset)",
    )
    parser.add_argument(
        "--stages",
        type=str,
        default="all",
        help="Comma-separated stages: all, calibration, sfm, orthomosaic (default: all)",
    )

    parser.add_argument(
        "--target-gsd",
        type=float,
        default=None,
        help="Target GSD in cm/px (optional)",
    )
    parser.add_argument(
        "--max-image-size",
        type=int,
        default=None,
        help="Max image dimension in pixels (optional)",
    )

    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Dataset preset name (zenodo-eastkazakhstan, wur-dataverse). Auto-configures stages and GSD.",
    )
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        help="List all available dataset presets and exit",
    )
    parser.add_argument(
        "--detect-layout",
        type=Path,
        default=None,
        metavar="PATH",
        help="Scan a dataset directory and print its detected layout, then exit",
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run accuracy validation after benchmarking",
    )

    parser.add_argument(
        "--checkpoint-rmse-h",
        type=float,
        default=0.10,
        help="Max horizontal RMSE threshold in meters (default: 0.10)",
    )
    parser.add_argument(
        "--checkpoint-rmse-v",
        type=float,
        default=0.15,
        help="Max vertical RMSE threshold in meters (default: 0.15)",
    )
    parser.add_argument(
        "--radiometric-r2",
        type=float,
        default=0.85,
        help="Min radiometric R² threshold (default: 0.85)",
    )
    parser.add_argument(
        "--reproducibility",
        type=float,
        default=0.99,
        help="Min reproducibility correlation threshold (default: 0.99)",
    )
    parser.add_argument(
        "--gsd-accuracy",
        type=float,
        default=0.05,
        help="Max GSD deviation fraction (default: 0.05 = 5%%)",
    )
    parser.add_argument(
        "--vegetation-r2",
        type=float,
        default=0.80,
        help="Min vegetation index R² threshold (default: 0.80)",
    )

    return parser


def args_to_settings(args: argparse.Namespace) -> BenchmarkSettings:
    """
    Convert parsed CLI arguments to BenchmarkSettings, bypassing .env.

    Args:
        args: Parsed argument namespace

    Returns:
        BenchmarkSettings configured from CLI args
    """
    return BenchmarkSettings(
        dataset_path=args.dataset_path,
        output_path=args.output_path,
        ground_truth_path=args.ground_truth,
        gpu_count=args.gpu_count,
        num_runs=args.num_runs,
        timeout_seconds=args.timeout,
        gateway_url=args.gateway_url,
        file_server_url=args.file_server_url,
        run_stages=args.stages,
        target_gsd=args.target_gsd,
        max_image_size=args.max_image_size,
        checkpoint_rmse_h_threshold=args.checkpoint_rmse_h,
        checkpoint_rmse_v_threshold=args.checkpoint_rmse_v,
        radiometric_r2_threshold=args.radiometric_r2,
        reproducibility_threshold=args.reproducibility,
        gsd_accuracy_threshold=args.gsd_accuracy,
        vegetation_r2_threshold=args.vegetation_r2,
    )


def run_validation(
    settings: BenchmarkSettings,
    run_results: dict,
) -> dict:
    """
    Run all applicable validators against benchmark results.

    Args:
        settings: Benchmark configuration
        run_results: Dict mapping stage to list of RunResult

    Returns:
        Dict mapping validator name to result dataclass
    """
    validation_results: dict = {}

    if settings.ground_truth_path and "calibration" in run_results:
        cal_runs = run_results["calibration"]
        if cal_runs and cal_runs[0].success and cal_runs[0].output_path:
            try:
                validator = CheckpointValidator(settings)
                validation_results["checkpoint"] = validator.validate(
                    cal_runs[0].output_path
                )
            except FileNotFoundError as e:
                print(f"  Checkpoint validation skipped: {e}")

    if settings.ground_truth_path and "calibration" in run_results:
        cal_runs = run_results["calibration"]
        if cal_runs and cal_runs[0].success and cal_runs[0].output_path:
            try:
                validator = RadiometricValidator(settings)
                validation_results["radiometric"] = validator.validate(
                    cal_runs[0].output_path
                )
            except FileNotFoundError as e:
                print(f"  Radiometric validation skipped: {e}")

    if "orthomosaic" in run_results:
        ortho_runs = run_results["orthomosaic"]
        successful = [r for r in ortho_runs if r.success and r.output_path]
        if successful:
            run_dicts = [
                {"output_path": str(r.output_path)} for r in successful
            ]
            spatial_validator = SpatialValidator(settings)
            validation_results["spatial"] = spatial_validator.validate(run_dicts)

            visual_validator = VisualQAValidator()
            validation_results["visual_qa"] = visual_validator.validate(
                successful[0].output_path
            )

            if settings.ground_truth_path:
                try:
                    veg_validator = VegetationIndexValidator(settings)
                    validation_results["vegetation"] = veg_validator.validate(
                        successful[0].output_path
                    )
                except FileNotFoundError as e:
                    print(f"  Vegetation index validation skipped: {e}")

    return validation_results


def apply_preset(args: argparse.Namespace) -> argparse.Namespace:
    """
    Apply dataset preset defaults to CLI args (without overriding explicit values).

    Args:
        args: Parsed argument namespace

    Returns:
        Updated namespace with preset defaults applied
    """
    if not args.dataset:
        return args

    preset = get_preset(args.dataset)
    if preset is None:
        print(f"Error: Unknown dataset preset '{args.dataset}'")
        print("Available presets:")
        for p in list_presets():
            print(f"  {p.name}: {p.description[:80]}...")
        sys.exit(1)

    if args.stages == "all":
        args.stages = ",".join(preset.stages)

    if args.target_gsd is None and preset.expected_gsd_cm is not None:
        args.target_gsd = preset.expected_gsd_cm

    return args


def main() -> None:
    """Entry point for the benchmark CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.list_datasets:
        print("\nAvailable dataset presets:\n")
        for p in list_presets():
            print(f"  {p.name}")
            print(f"    {p.description}")
            print(f"    Source:  {p.source_url}")
            print(f"    Sensor:  {p.sensor_type}")
            print(f"    Stages:  {', '.join(p.stages)}")
            if p.expected_gsd_cm:
                print(f"    GSD:     {p.expected_gsd_cm} cm/px")
            print()
        sys.exit(0)

    if args.detect_layout:
        path = args.detect_layout
        if not path.exists():
            print(f"Error: Path does not exist: {path}")
            sys.exit(1)
        print(f"\nScanning dataset: {path}\n")
        layout = detect_dataset_layout(path)
        print(json.dumps(layout, indent=2))
        sys.exit(0)

    if not args.dataset_path:
        parser.error("--dataset-path is required")

    if not args.dataset_path.exists():
        print(f"Error: Dataset path does not exist: {args.dataset_path}")
        sys.exit(1)

    args = apply_preset(args)
    settings = args_to_settings(args)

    preset_label = f" (preset: {args.dataset})" if args.dataset else ""
    print(f"\nPhotoGear Benchmark Suite")
    print(f"{'='*60}")
    print(f"  Dataset:    {settings.dataset_path}{preset_label}")
    print(f"  Output:     {settings.output_path}")
    print(f"  Stages:     {', '.join(settings.get_stages())}")
    print(f"  GPU count:  {settings.gpu_count}")
    print(f"  Runs:       {settings.num_runs}")
    print(f"  Gateway:    {settings.gateway_url}")
    if settings.file_server_url:
        print(f"  File srv:   {settings.file_server_url}")
    if settings.target_gsd:
        print(f"  Target GSD: {settings.target_gsd} cm/px")
    print(f"{'='*60}")

    memory_before = capture_memory_snapshot()
    pipeline = PipelineRunner(settings)
    run_results = pipeline.run_all()

    validation_results = None
    if args.validate:
        print(f"\n{'='*60}")
        print("  RUNNING VALIDATION")
        print(f"{'='*60}")
        validation_results = run_validation(settings, run_results)

    perf_collector = PerformanceCollector(settings)
    perf_result = perf_collector.collect(run_results, memory_before)
    if validation_results is None:
        validation_results = {}
    validation_results["performance"] = perf_result

    report_gen = ReportGenerator(settings)
    report_path = report_gen.generate(run_results, validation_results)
    print(f"\n  Report saved to: {report_path}")


if __name__ == "__main__":
    main()
