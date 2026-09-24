from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

from psygnal import Signal
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.sfm.logger import logger

from .interfaces import IService

ContainerName = str
StepName = str


class OpenSfMSettings(BaseSettings):
    dataset_mounting_path: Path = Path("/data/")
    docker_image_name: str = "opensfm:latest"

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_prefix="OPEN_SFM_",
    )


class OpenSFMService(IService):
    __service_name = "OpenSFMService"

    completion_steps_signal = Signal(ContainerName, StepName)

    def __init__(self, additional_settings: dict | None = None):
        if additional_settings is None:
            additional_settings = {}
        self.settings = OpenSfMSettings(**additional_settings)

    def create_processing_config(self): ...

    def extract_metadata(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "extract_metadata",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "extract_metadata")

    def extract_features(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "detect_features",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "extract_features")

    def match_features(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "match_features",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "match_features")

    def create_tracks(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "create_tracks",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "create_tracks")

    def create_rig(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "create_rig",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "create_rig")

    def compute_reconstruct(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "reconstruct",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "compute_reconstruct")

    def reconstruct_from_prior(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "reconstruct_from_prior",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "reconstruct_from_prior")

    def bundle_reconstruction(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "bundle",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "bundle_reconstruction")

    def mesh(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "mesh",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "mesh")

    def geo_register(self, container_name: str) -> None:
        """
        Geo-registration is handled natively by OpenSfM via GPS EXIF priors.

        This is a no-op for OpenSfM compatibility with the IService interface.

        Args:
            container_name: OpenSfM container identifier
        """
        logger.info(
            "OpenSfM handles geo-registration internally via GPS EXIF. "
            "No additional alignment step required."
        )
        self.completion_steps_signal.emit(container_name, "geo_register")

    def undistort(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "undistort",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "undistort")

    def compute_depthmaps(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "compute_depthmaps",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "compute_depthmaps")

    def compute_statistics(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "compute_statistics",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "compute_statistics")

    def export_report(self, container_name: str):
        command = [
            "docker",
            "exec",
            container_name,
            "./bin/opensfm",
            "export_report",
            str(self.settings.dataset_mounting_path),
        ]
        self._run_command(command, cwd=Path(".").cwd())
        self.completion_steps_signal.emit(container_name, "export_report")

    def _run_command(self, command: list[str], cwd: Path) -> str:
        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                cwd=cwd,
            )
            if process.stdout:
                logger.info(
                    f"Docker container started with ID: {process.stdout.strip()}",
                )
            if process.stderr:
                logger.warning(f"Docker command stderr: {process.stderr.strip()}")

            return process.stdout
        except subprocess.CalledProcessError as e:
            error_msg = f"Docker command failed with error: {e.stderr or e.stdout}"
            raise RuntimeError(error_msg)
        except FileNotFoundError:
            raise RuntimeError("Docker is not installed or not found in PATH.")

    def start(self, dataset_path: Path) -> str:
        if not dataset_path.is_absolute():
            raise ValueError("The dataset_path must be an absolute path.")

        if not dataset_path.exists():
            raise ValueError(f"The dataset_path '{dataset_path}' does not exist.")

        container_name = f"{self.__service_name}_{uuid.uuid4().hex[:8]}"
        user_id = os.getuid()
        group_id = os.getuid()

        command = [
            "docker",
            "run",
            "--name",
            container_name,
            "-v" f"{str(dataset_path)}:{str(self.settings.dataset_mounting_path)}",
            "--user",
            f"{user_id}:{group_id}",
            "-d",
            "-t",
            self.settings.docker_image_name,
            "sh",
        ]
        self._run_command(command, cwd=Path(".").cwd())
        return container_name

    def stop(self, container_name: str):
        command = [
            "docker",
            "stop",
            container_name,
        ]
        self._run_command(command, cwd=Path(".").cwd())

    def clean(self, container_name: str):
        command = [
            "docker",
            "rm",
            container_name,
        ]
        self._run_command(command, cwd=Path(".").cwd())
