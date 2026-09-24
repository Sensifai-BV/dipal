from __future__ import annotations

import logging
import sys

# Create logger
logger = logging.getLogger("orthomosaic_generation")
logger.setLevel(logging.DEBUG)

# Create console handler with formatting
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
handler.setFormatter(formatter)
logger.addHandler(handler)
