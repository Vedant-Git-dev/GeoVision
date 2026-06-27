"""FAO GAUL district boundary lookup via Google Earth Engine."""

from __future__ import annotations

import logging

import ee

from . import config

log = logging.getLogger(__name__)


def get_district_aoi(lat: float, lon: float) -> tuple[ee.Geometry, str]:
    """Look up the FAO GAUL Level-2 (district) boundary containing a point.

    Args:
        lat: Latitude of the geocoded point.
        lon: Longitude of the geocoded point.

    Returns:
        Tuple of (district geometry as ee.Geometry, district name string).

    Falls back to a circular buffer around the point if no GAUL match.
    """
    point = ee.Geometry.Point([lon, lat])
    districts = ee.FeatureCollection(config.GAUL_LEVEL2).filterBounds(point)

    # Check server-side if any feature matched
    count = districts.size().getInfo()
    if count == 0:
        log.warning("No GAUL district found for (%.4f, %.4f) — falling back to %dm buffer",
                     lat, lon, config.DEFAULT_BUFFER_M)
        return point.buffer(config.DEFAULT_BUFFER_M), "Unknown"

    district = districts.first()
    district_name = district.get("ADM2_NAME").getInfo()
    geometry = district.geometry()

    log.info("GAUL district: %s", district_name)
    return geometry, str(district_name)
