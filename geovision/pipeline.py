"""Full pipeline orchestration — geocode → composite → DW → detect → tile URLs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import ee

from .types import DateRange
from .ee_init import init_ee
from .geocode import resolve_location
from .boundary import get_district_aoi, get_city_aoi
from .settlements import get_settlements
from .composite import build_composite
from .dynamic_world import build_dw_composite
from .changes import detect_changes, get_change_vis_params
from .signature import dw_to_signature
from .stats import compute_land_cover_stats
from . import config

log = logging.getLogger(__name__)


def _get_window(date_str: str) -> tuple[str, str]:
    """Expand a date string into a window of DATE_WINDOW_DAYS days."""
    start = datetime.strptime(date_str, "%Y-%m-%d")
    end = start + timedelta(days=config.DATE_WINDOW_DAYS)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def run_pipeline(
    location_query: str = config.DEFAULT_LOCATION,
    before_date: str = config.DEFAULT_BEFORE_DATE,
    after_date: str = config.DEFAULT_AFTER_DATE,
    project_id: str | None = config.EE_PROJECT_ID,
    city: str | None = None,
) -> dict:
    """Run the full change-detection pipeline.

    Args:
        city: If provided, analyze only this city/town boundary instead
              of the full district.  e.g. "Kharadi, Pune, India".

    Returns:
        A config dict with center, tile URLs, labels, and AOI geometry —
        ready to be wrapped in a JSON response by the Flask route.
    """
    start1, end1 = _get_window(before_date)
    start2, end2 = _get_window(after_date)

    init_ee(project_id)

    loc = resolve_location(location_query, config.DEFAULT_LAT, config.DEFAULT_LON, location_query)

    if city:
        log.info("City-level analysis requested: %s", city)
        aoi, area_name = get_city_aoi(city, loc.lat, loc.lon)
    else:
        aoi, area_name = get_district_aoi(loc.lat, loc.lon)

    log.info("Fetching AOI geometry and discovering settlements in %s...", area_name)
    aoi_geojson = aoi.getInfo()
    settlements = get_settlements(aoi_geojson)

    log.info("Building composite 1 (%s -> %s)...", start1, end1)
    image1 = build_composite(aoi, DateRange(start1, end1), "Timeline 1")

    log.info("Building composite 2 (%s -> %s)...", start2, end2)
    image2 = build_composite(aoi, DateRange(start2, end2), "Timeline 2")

    map_id1 = image1.getMapId(config.S2_VIS_PARAMS)
    map_id2 = image2.getMapId(config.S2_VIS_PARAMS)
    tile1_url = map_id1["tile_fetcher"].url_format
    tile2_url = map_id2["tile_fetcher"].url_format

    log.info("Detecting changes via Dynamic World signatures...")
    dw1 = build_dw_composite(aoi, DateRange(start1, end1), "Timeline 1")
    dw2 = build_dw_composite(aoi, DateRange(start2, end2), "Timeline 2")
    change_img = detect_changes(dw1, dw2, s2_b=image2)
    change_vis = get_change_vis_params()
    change_map_id = change_img.getMapId(change_vis)
    change_mask_url = change_map_id["tile_fetcher"].url_format

    log.info("Building land cover classification tiles and statistics...")
    sig1 = dw_to_signature(dw1)
    sig2 = dw_to_signature(dw2)

    # Remap DW class codes (0,1,3,4,6) to sequential indices (0-4)
    # because GEE palette maps continuous integer ranges.
    class_codes = sorted(config.LAND_COVER_CLASSES)
    lc_palette = ",".join(
        config.LAND_COVER_CLASSES[c]["color"] for c in class_codes
    )
    lc_vis = {
        "bands": ["lc_class"],
        "min": 0,
        "max": len(class_codes) - 1,
        "palette": lc_palette,
    }
    lc1 = sig1.select("signature_label").remap(class_codes, list(range(len(class_codes)))).rename("lc_class")
    lc2 = sig2.select("signature_label").remap(class_codes, list(range(len(class_codes)))).rename("lc_class")
    lc1_url = lc1.getMapId(lc_vis)["tile_fetcher"].url_format
    lc2_url = lc2.getMapId(lc_vis)["tile_fetcher"].url_format

    lc_stats = compute_land_cover_stats(sig1, sig2, aoi)

    log.info("Generated map config for: %s", location_query)

    return {
        "center": [loc.lat, loc.lon],
        "before_tiles": tile1_url,
        "after_tiles": tile2_url,
        "change_mask_tiles": change_mask_url,
        "land_cover_before_tiles": lc1_url,
        "land_cover_after_tiles": lc2_url,
        "land_cover_stats": lc_stats,
        "before_label": before_date,
        "after_label": after_date,
        "aoi": aoi_geojson,
        "area_name": area_name,
        "is_city_analysis": city is not None,
        "settlements": settlements,
    }
