"""Location resolution via Nominatim geocoding."""

from __future__ import annotations

import logging
import sys

from geopy.geocoders import Nominatim

from .types import Location
from . import config

log = logging.getLogger(__name__)


def resolve_location(query, lat, lon, name) -> Location:
    """Resolve a place name or coordinates to a Location.

    If *query* is provided, geocode via Nominatim.  Otherwise use the
    given lat/lon directly (with a swap correction if they appear
    inverted).
    """
    if query:
        log.info("Geocoding '%s'...", query)
        g = Nominatim(user_agent=config.GEOCODER_USER_AGENT)
        r = g.geocode(query)
        if r is None:
            sys.exit(f"Could not geocode '{query}'.")
        log.info("Resolved: %s (%.4f, %.4f)", r.address, r.latitude, r.longitude)
        return Location(query, r.latitude, r.longitude)
    if not (-90 <= lat <= 90) and (-180 <= lon <= 180):
        lat, lon = lon, lat
    return Location(name, lat, lon)
