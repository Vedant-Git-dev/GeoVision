"""GeoVision — satellite change detection via Google Earth Engine."""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

from .pipeline import run_pipeline
from .types import Location, DateRange
from .ee_init import init_ee

__all__ = ["run_pipeline", "init_ee", "Location", "DateRange"]
