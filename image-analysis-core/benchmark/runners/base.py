import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from benchmark.settings import BenchmarkSettings


@dataclass
class RunResult:
    """Result of a single benchmark run."""

    stage: str
    run_index: int
    success: bool
    elapsed_seconds: float
    output_path: Path | None = None
    error: str | None = None
    metrics: dict = field(default_factory=dict)


class BaseRunner(ABC):
    """Base class for benchmark stage runners."""

    def __init__(self, settings: BenchmarkSettings):
        self.settings = settings

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Return the name of this processing stage."""

    @abstractmethod
    def _execute(self, run_index: int) -> RunResult:
        """
        Execute the benchmark stage once.

        Args:
            run_index: Index of current run (0-based)

        Returns:
            RunResult with timing and output info
        """

    def run(self, run_index: int = 0) -> RunResult:
        """
        Run the stage with timing wrapper.

        Args:
            run_index: Index of current run (0-based)

        Returns:
            RunResult with elapsed time populated
        """
        submit_time = time.time()
        start = time.perf_counter()
        try:
            result = self._execute(run_index)
            result.elapsed_seconds = time.perf_counter() - start
            result.metrics["submit_time"] = submit_time
            result.metrics["start_time"] = submit_time
            result.metrics["gpu_count"] = self.settings.gpu_count
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            return RunResult(
                stage=self.stage_name,
                run_index=run_index,
                success=False,
                elapsed_seconds=elapsed,
                error=str(e),
                metrics={
                    "submit_time": submit_time,
                    "start_time": submit_time,
                    "gpu_count": self.settings.gpu_count,
                },
            )

    def run_multiple(self) -> list[RunResult]:
        """
        Run the stage settings.num_runs times for reproducibility testing.

        Returns:
            List of RunResult for each run
        """
        results = []
        for i in range(self.settings.num_runs):
            results.append(self.run(run_index=i))
        return results
