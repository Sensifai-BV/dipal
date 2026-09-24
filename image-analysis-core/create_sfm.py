from __future__ import annotations

from pathlib import Path

from services.sfm.app.core.algorithms.algorithm_factory import AlgorithmFactory
from services.sfm.app.core.services.colmap_service import ColmapSettings
from services.sfm.app.core.services.service_factory import ServiceFactory

if __name__ == "__main__":
    print(ColmapSettings().model_dump_json(indent=4))

    # Create and run the SFM pipeline
    algorithm = AlgorithmFactory.create_sfm_pipeline(
        ServiceFactory.create_service("colmap", {}),
    )
    algorithm.run_pipeline(
        Path(
            "/media/omidsa/Data/PhotoGearData/Processed/1b80b3b0-2e94-427b-a8a9-3b17127b9a0c",
        ),
    )
