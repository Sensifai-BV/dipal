import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from benchmark.runners.base import RunResult
from benchmark.settings import BenchmarkSettings


class ReportGenerator:
    """Generate structured benchmark reports in JSON format."""

    def __init__(self, settings: BenchmarkSettings):
        self.settings = settings

    def generate(
        self,
        run_results: dict[str, list[RunResult]],
        validation_results: dict | None = None,
    ) -> Path:
        """
        Generate a comprehensive benchmark report.

        Args:
            run_results: Dict mapping stage to list of RunResult
            validation_results: Optional dict with validator outputs

        Returns:
            Path to the generated report JSON file
        """
        report = self._build_report(run_results, validation_results)

        output_dir = self.settings.output_path
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f"benchmark_report_{timestamp}.json"
        report_path.write_text(json.dumps(report, indent=2, default=str))

        self._print_summary(report)

        return report_path

    def _build_report(
        self,
        run_results: dict[str, list[RunResult]],
        validation_results: dict | None = None,
    ) -> dict:
        """
        Build the report data structure.

        Args:
            run_results: Dict mapping stage to list of RunResult
            validation_results: Optional validator outputs

        Returns:
            Complete report dict
        """
        stages = {}
        for stage_name, results in run_results.items():
            stage_data = {
                "runs": [self._serialize_run(r) for r in results],
                "summary": self._summarize_stage(results),
            }
            stages[stage_name] = stage_data

        report = {
            "metadata": {
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "dataset_path": str(self.settings.dataset_path),
                "stages": self.settings.get_stages(),
                "num_runs": self.settings.num_runs,
                "gpu_count": self.settings.gpu_count,
                "target_gsd": self.settings.target_gsd,
            },
            "stages": stages,
            "validation": self._serialize_validation(validation_results),
            "overall": self._compute_overall(run_results, validation_results),
        }
        return report

    @staticmethod
    def _serialize_run(result: RunResult) -> dict:
        """
        Serialize a RunResult to a dict.

        Args:
            result: RunResult to serialize

        Returns:
            Serialized dict
        """
        data = asdict(result)
        if data.get("output_path"):
            data["output_path"] = str(data["output_path"])
        return data

    @staticmethod
    def _summarize_stage(results: list[RunResult]) -> dict:
        """
        Compute summary statistics for a stage's runs.

        Args:
            results: List of RunResult for one stage

        Returns:
            Summary dict with timing and pass/fail stats
        """
        times = [r.elapsed_seconds for r in results if r.success]
        success_count = sum(1 for r in results if r.success)
        total = len(results)

        summary: dict = {
            "total_runs": total,
            "successful_runs": success_count,
            "failed_runs": total - success_count,
            "success_rate": success_count / total if total > 0 else 0.0,
        }

        if times:
            summary["min_time_seconds"] = min(times)
            summary["max_time_seconds"] = max(times)
            summary["mean_time_seconds"] = sum(times) / len(times)

        return summary

    @staticmethod
    def _serialize_validation(validation_results: dict | None) -> dict:
        """
        Serialize validation results for the report.

        Args:
            validation_results: Raw validator outputs

        Returns:
            Serialized validation dict
        """
        if not validation_results:
            return {"status": "skipped"}

        serialized = {}
        for key, val in validation_results.items():
            if hasattr(val, "__dataclass_fields__"):
                serialized[key] = asdict(val)
            else:
                serialized[key] = val
        return serialized

    @staticmethod
    def _compute_overall(
        run_results: dict[str, list[RunResult]],
        validation_results: dict | None,
    ) -> dict:
        """
        Compute overall benchmark verdict.

        Args:
            run_results: Stage run results
            validation_results: Validator outputs

        Returns:
            Overall summary dict
        """
        all_runs = [r for results in run_results.values() for r in results]
        total = len(all_runs)
        passed = sum(1 for r in all_runs if r.success)

        total_time = sum(r.elapsed_seconds for r in all_runs)

        validation_passed = True
        if validation_results:
            for val in validation_results.values():
                if hasattr(val, "passed") and not val.passed:
                    validation_passed = False
                    break

        return {
            "total_runs": total,
            "total_passed": passed,
            "total_failed": total - passed,
            "total_time_seconds": total_time,
            "all_stages_passed": passed == total,
            "validation_passed": validation_passed,
            "verdict": "PASS" if (passed == total and validation_passed) else "FAIL",
        }

    @staticmethod
    def _print_summary(report: dict) -> None:
        """
        Print a human-readable summary to stdout.

        Args:
            report: Complete report dict
        """
        print(f"\n{'='*60}")
        print("  BENCHMARK REPORT SUMMARY")
        print(f"{'='*60}")

        overall = report["overall"]
        print(f"  Verdict:    {overall['verdict']}")
        print(f"  Runs:       {overall['total_passed']}/{overall['total_runs']} passed")
        print(f"  Total time: {overall['total_time_seconds']:.2f}s")
        print(f"  Validation: {'PASS' if overall['validation_passed'] else 'FAIL'}")

        for stage_name, stage_data in report["stages"].items():
            s = stage_data["summary"]
            print(f"\n  {stage_name.upper()}:")
            print(f"    Runs: {s['successful_runs']}/{s['total_runs']} passed")
            if "mean_time_seconds" in s:
                print(f"    Mean time: {s['mean_time_seconds']:.2f}s")

        validation = report.get("validation", {})
        if validation.get("status") != "skipped":
            print("\n  VALIDATION:")
            for key, val in validation.items():
                if isinstance(val, dict) and "passed" in val:
                    status = "PASS" if val["passed"] else "FAIL"
                    print(f"    {key}: {status}")

        perf = validation.get("performance", {})
        if perf:
            print("\n  PERFORMANCE:")
            tput = perf.get("throughput_images_per_min", {})
            for stage, rate in tput.items():
                print(f"    {stage} throughput: {rate:.1f} images/min")
            mem = perf.get("memory_peak_mb")
            if mem is not None:
                print(f"    Peak CPU memory: {mem:.1f} MB")
            gpu_devs = perf.get("gpu_devices", [])
            for gpu in gpu_devs:
                name = gpu.get("name", "unknown")
                idx = gpu.get("index", 0)
                used = gpu.get("memory_used_mb", 0)
                total = gpu.get("memory_total_mb", 0)
                util = gpu.get("utilization_percent")
                util_str = f", util {util:.0f}%" if util is not None else ""
                print(f"    GPU {idx} ({name}): {used:.0f}/{total:.0f} MB{util_str}")
            gpu_peak = perf.get("gpu_memory_peak_mb")
            if gpu_peak is not None:
                print(f"    Peak GPU memory: {gpu_peak:.0f} MB")
            out_mb = perf.get("storage_output_mb", 0)
            if out_mb > 0:
                print(f"    Output size: {out_mb:.2f} MB")
            io_mbps = perf.get("storage_throughput_mbps")
            if io_mbps is not None:
                print(f"    Storage throughput: {io_mbps:.2f} MB/s")
            eff = perf.get("scaling_efficiency")
            if eff is not None:
                print(f"    Scaling efficiency: {eff:.2%}")
            latency = perf.get("queue_latency_seconds", {})
            for stage, lat in latency.items():
                if lat is not None:
                    print(f"    {stage} queue latency: {lat:.3f}s")

        print(f"\n{'='*60}")
