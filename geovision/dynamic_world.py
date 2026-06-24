"""Dynamic World probability compositing."""

from __future__ import annotations

import logging

import ee

from .types import DateRange
from . import config

log = logging.getLogger(__name__)

# Dynamic World probability band names (per-pixel class confidence from DL model)
DW_PROB_BANDS = [
    "water", "trees", "grass", "flooded_vegetation",
    "crops", "shrub_and_scrub", "built", "bare", "snow_and_ice",
]


def build_dw_composite(aoi, date_range: DateRange, label: str) -> ee.Image:
    """Build a median composite of Dynamic World probability bands.

    Queries the GOOGLE/DYNAMICWORLD/V1 collection for the given AOI
    and date range, selects the 9 probability bands, and reduces via
    median to get a stable per-pixel probability distribution.
    """
    col = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(aoi)
        .filterDate(date_range.start, date_range.end)
        .select(DW_PROB_BANDS)
    )
    n = col.size().getInfo()
    if n == 0:
        raise RuntimeError(
            f"No Dynamic World scenes for '{label}'. "
            "Widen your date range or check the AOI."
        )
    log.info("[DW %s] %d scenes — median probability.", label, n)
    return col.median().clip(aoi)
