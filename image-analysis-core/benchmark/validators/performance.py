import resource
from dataclasses import dataclass, field
from pathlib import Path

from benchmark.runners.base import RunResult
from benchmark.settings import BenchmarkSettings


@dataclass
class GpuInfo:
    """GPU device information snapshot."""

    name: str
    index: int
    memory_total_mb: float
    memory_used_mb: float
    memory_free_mb: float
    utilization_percent: float | None
    temperature_celsius: float | None


@dataclass
class PerformanceResult:
    """Result of performance metrics collection."""

    throughput_images_per_min: dict[str, float]
    memory_peak_mb: float | None
    gpu_devices: list[GpuInfo]
    gpu_memory_peak_mb: float | None
    storage_output_mb: float
    storage_throughput_mbps: float | None
    queue_latency_seconds: dict[str, float | None]
    scaling_efficiency: float | None
    passed: bool
    details: dict = field(default_factory=dict)


class PerformanceCollector:
    """
    Collect derived performance metrics from benchmark run results.

    Computes throughput, memory footprint, storage I/O, queue latency,
    and GPU scaling efficiency from completed runs.
    """

    def __init__(self, settings: BenchmarkSettings):
        self.settings = settings

    def collect(
        self,
        run_results: dict[str, list[RunResult]],
        memory_before_mb: float | None = None,
    ) -> PerformanceResult:
        """
        Collect all performance metrics from completed runs.

        Args:
            run_results: Dict mapping stage name to list of RunResult
            memory_before_mb: Peak RSS in MB captured before the benchmark

        Returns:
            PerformanceResult with all computed metrics
        """
        throughput = self._compute_throughput(run_results)
        memory_peak = self._measure_memory_peak()
        gpu_devices = self._query_gpu_devices()
        gpu_memory_peak = self._get_gpu_memory_peak(gpu_devices)
        output_mb = self._measure_output_size(self.settings.output_path)

        total_time = sum(
            r.elapsed_seconds
            for results in run_results.values()
            for r in results
            if r.success and r.elapsed_seconds > 0
        )
        storage_mbps = output_mb / total_time if total_time > 0 else None

        latency = self._estimate_queue_latency(run_results)
        scaling = self._compute_scaling_efficiency(run_results)

        return PerformanceResult(
            throughput_images_per_min=throughput,
            memory_peak_mb=memory_peak,
            gpu_devices=gpu_devices,
            gpu_memory_peak_mb=gpu_memory_peak,
            storage_output_mb=output_mb,
            storage_throughput_mbps=storage_mbps,
            queue_latency_seconds=latency,
            scaling_efficiency=scaling,
            passed=True,
            details={
                "gpu_count": self.settings.gpu_count,
                "num_runs": self.settings.num_runs,
                "memory_before_mb": memory_before_mb,
                "gpu_names": [g.name for g in gpu_devices],
            },
        )

    @staticmethod
    def _compute_throughput(
        run_results: dict[str, list[RunResult]],
    ) -> dict[str, float]:
        """
        Compute images processed per minute for each stage.

        Args:
            run_results: Dict mapping stage name to list of RunResult

        Returns:
            Dict mapping stage name to images/min
        """
        throughput: dict[str, float] = {}

        for stage, results in run_results.items():
            successful = [r for r in results if r.success]
            if not successful:
                continue

            total_images = 0
            total_seconds = 0.0

            for r in successful:
                image_count = r.metrics.get("image_count", 0)
                total_images += image_count
                total_seconds += r.elapsed_seconds

            if total_seconds > 0 and total_images > 0:
                throughput[stage] = (total_images / total_seconds) * 60.0

        return throughput

    @staticmethod
    def _measure_memory_peak() -> float | None:
        """
        Get peak resident set size of the current process.

        Returns:
            Peak RSS in MB, or None if unavailable
        """
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            peak_kb = usage.ru_maxrss
            return peak_kb / 1024.0
        except (AttributeError, ValueError):
            return None

    @staticmethod
    def _query_gpu_devices() -> list[GpuInfo]:
        """
        Query all visible NVIDIA GPUs via pynvml.

        Returns:
            List of GpuInfo for each detected GPU, empty if unavailable
        """
        try:
            import pynvml
        except ImportError:
            return []

        try:
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            devices: list[GpuInfo] = []

            for i in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")

                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_util = float(util.gpu)
                except pynvml.NVMLError:
                    gpu_util = None

                try:
                    temp = float(
                        pynvml.nvmlDeviceGetTemperature(
                            handle, pynvml.NVML_TEMPERATURE_GPU
                        )
                    )
                except pynvml.NVMLError:
                    temp = None

                devices.append(
                    GpuInfo(
                        name=name,
                        index=i,
                        memory_total_mb=mem_info.total / (1024 * 1024),
                        memory_used_mb=mem_info.used / (1024 * 1024),
                        memory_free_mb=mem_info.free / (1024 * 1024),
                        utilization_percent=gpu_util,
                        temperature_celsius=temp,
                    )
                )

            pynvml.nvmlShutdown()
            return devices
        except pynvml.NVMLError:
            return []

    @staticmethod
    def _get_gpu_memory_peak(devices: list[GpuInfo]) -> float | None:
        """
        Get peak GPU memory usage across all devices.

        Args:
            devices: List of GpuInfo snapshots

        Returns:
            Maximum memory_used_mb across devices, or None
        """
        if not devices:
            return None
        return max(d.memory_used_mb for d in devices)

    @staticmethod
    def _measure_output_size(output_path: Path) -> float:
        """
        Measure total output directory size in MB.

        Args:
            output_path: Path to benchmark output directory

        Returns:
            Total size in MB
        """
        if not output_path.exists():
            return 0.0

        total_bytes = sum(
            f.stat().st_size for f in output_path.rglob("*") if f.is_file()
        )
        return total_bytes / (1024.0 * 1024.0)

    @staticmethod
    def _estimate_queue_latency(
        run_results: dict[str, list[RunResult]],
    ) -> dict[str, float | None]:
        """
        Estimate queue latency from run metrics.

        Queue latency is the time from job submission to processing start.
        Runners may record 'submit_time' and 'start_time' in metrics.

        Args:
            run_results: Dict mapping stage name to list of RunResult

        Returns:
            Dict mapping stage name to average latency in seconds
        """
        latency: dict[str, float | None] = {}

        for stage, results in run_results.items():
            latencies = []
            for r in results:
                submit_ts = r.metrics.get("submit_time")
                start_ts = r.metrics.get("start_time")
                if submit_ts is not None and start_ts is not None:
                    latencies.append(float(start_ts) - float(submit_ts))

            if latencies:
                latency[stage] = sum(latencies) / len(latencies)
            else:
                latency[stage] = None

        return latency

    @staticmethod
    def _compute_scaling_efficiency(
        run_results: dict[str, list[RunResult]],
    ) -> float | None:
        """
        Compute GPU scaling efficiency from multi-run results.

        Scaling efficiency = (T_1 / T_n) / n, where T_1 is single-GPU time,
        T_n is n-GPU time, and n is the GPU count. A value of 1.0 means
        perfect linear scaling. Requires 'gpu_count' in run metrics.

        Args:
            run_results: Dict mapping stage name to list of RunResult

        Returns:
            Scaling efficiency ratio (0.0 to 1.0), or None if not enough data
        """
        single_gpu_times: list[float] = []
        multi_gpu_times: list[float] = []
        gpu_count: int | None = None

        for results in run_results.values():
            for r in results:
                if not r.success:
                    continue
                gc = r.metrics.get("gpu_count")
                if gc is None:
                    continue
                if gc == 1:
                    single_gpu_times.append(r.elapsed_seconds)
                elif gc > 1:
                    multi_gpu_times.append(r.elapsed_seconds)
                    gpu_count = gc

        if not single_gpu_times or not multi_gpu_times or gpu_count is None:
            return None

        t1 = sum(single_gpu_times) / len(single_gpu_times)
        tn = sum(multi_gpu_times) / len(multi_gpu_times)

        if tn <= 0:
            return None

        return (t1 / tn) / gpu_count


def capture_memory_snapshot() -> float | None:
    """
    Capture current peak RSS for before/after comparison.

    Returns:
        Peak RSS in MB, or None if unavailable
    """
    return PerformanceCollector._measure_memory_peak()
