from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BenchmarkSettings(BaseSettings):
    """
    Configuration for benchmark runs.

    Reads from environment variables with BENCHMARK_ prefix,
    but all values can be overridden via CLI arguments.
    """

    dataset_path: Path = Field(
        ..., description="Path to the dataset directory containing images"
    )
    output_path: Path = Field(
        Path("benchmark_results"),
        description="Path to store benchmark results and reports",
    )
    ground_truth_path: Path | None = Field(
        None, description="Path to ground truth data (GCPs, reference ortho, etc.)"
    )

    gpu_count: int = Field(1, description="Number of GPU cores to use", ge=0)
    num_runs: int = Field(1, description="Number of runs for reproducibility testing", ge=1)
    timeout_seconds: int = Field(3600, description="Timeout per stage in seconds", ge=60)

    gateway_url: str = Field(
        "http://localhost:8080", description="API gateway base URL"
    )
    file_server_url: str | None = Field(
        None,
        description="HTTP file server URL for Docker-accessible image URLs (e.g. http://172.18.0.1:9000/dataset)",
    )
    run_stages: str = Field(
        "all",
        description="Comma-separated stages to benchmark: all, calibration, sfm, orthomosaic",
    )

    target_gsd: float | None = Field(None, description="Target GSD in cm/px")
    max_image_size: int | None = Field(None, description="Max image dimension in pixels")

    checkpoint_rmse_h_threshold: float = Field(
        0.10, description="Max acceptable horizontal RMSE in meters"
    )
    checkpoint_rmse_v_threshold: float = Field(
        0.15, description="Max acceptable vertical RMSE in meters"
    )
    radiometric_r2_threshold: float = Field(
        0.85, description="Min acceptable radiometric R² value"
    )
    reproducibility_threshold: float = Field(
        0.99, description="Min acceptable correlation between runs"
    )
    gsd_accuracy_threshold: float = Field(
        0.05, description="Max acceptable GSD deviation (fraction)"
    )
    vegetation_r2_threshold: float = Field(
        0.80, description="Min acceptable vegetation index R² value"
    )

    model_config = SettingsConfigDict(
        env_prefix="BENCHMARK_",
        env_file=".env",
        extra="ignore",
    )

    def get_stages(self) -> list[str]:
        """Return list of stages to benchmark."""
        if self.run_stages == "all":
            return ["calibration", "sfm", "orthomosaic"]
        return [s.strip() for s in self.run_stages.split(",")]
