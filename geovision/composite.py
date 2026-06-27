"""Sentinel-2 cloud masking and median composite building."""

from __future__ import annotations

import logging

import ee

from .types import DateRange
from . import config

log = logging.getLogger(__name__)


def mask_scl(image: ee.Image) -> ee.Image:
    """Mask pixels using the Scene Classification Layer (SCL).

    Only keeps pixels where SCL is in ``config.SCL_CLEAR``.
    """
    scl = image.select("SCL")
    mask = ee.Image(0)
    for cls in config.SCL_CLEAR:
        mask = mask.Or(scl.eq(cls))
    return image.updateMask(mask).copyProperties(image, ["system:index"])


def join_cloudless(sr_col, aoi, date_range):
    """Attach per-pixel cloud probability to each S2 scene and mask cloudy pixels."""
    cloud_col = (
        ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY")
        .filterBounds(aoi).filterDate(date_range.start, date_range.end)
    )

    def _attach_prob(img):
        p = cloud_col.filter(ee.Filter.eq("system:index", img.get("system:index"))).first()
        return img.set("cloud_prob", p)

    def _mask_prob(img):
        return img.updateMask(
            ee.Image(img.get("cloud_prob")).select("probability").lt(config.CLOUD_PROB_THRESHOLD)
        )

    return sr_col.map(_attach_prob).map(_mask_prob)


def build_composite(aoi, date_range: DateRange, label: str) -> ee.Image:
    """Build a cloud-filtered Sentinel-2 median composite.

    1. Fetch S2_SR_HARMONIZED for the AOI / date range
    2. Filter out heavily cloudy scenes (CLOUDY_PIXEL_PERCENTAGE threshold)
    3. Attach per-pixel cloud probability and mask cloudy pixels
    4. Apply SCL masking
    5. Reduce via median
    """
    sr_col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi).filterDate(date_range.start, date_range.end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", config.MAX_SCENE_CLOUD_PCT))
    )
    sr_col = join_cloudless(sr_col, aoi, date_range).map(mask_scl)
    count = sr_col.size().getInfo()
    if count == 0:
        raise RuntimeError(f"No Sentinel-2 scenes for '{label}'. Widen your date range.")
    log.info("[%s] %d scenes — median.", label, count)
    return sr_col.median().clip(aoi)
