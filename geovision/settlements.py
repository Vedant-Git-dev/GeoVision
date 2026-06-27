"""Settlement discovery within an AOI using OSMnx."""

from __future__ import annotations

import logging

import osmnx as ox
from shapely.geometry import shape

from . import config

log = logging.getLogger(__name__)


def get_settlements(geom_geojson: dict) -> list[dict]:
    """Find named settlements within a boundary polygon via OSMnx.

    Queries OpenStreetMap for features tagged with ``place=*`` (filtered
    to SETTLEMENT_PLACE_TAGS) that fall inside the given geometry.

    Args:
        geom_geojson: A GeoJSON geometry dict (as returned by
            ``ee.Geometry.getInfo()``) — must be a Polygon or MultiPolygon.

    Returns:
        List of dicts, each with ``name``, ``lat``, ``lon``, ``type``.
    """
    polygon = shape(geom_geojson)

    try:
        gdf = ox.features_from_polygon(polygon, tags={"place": True})
    except ox._errors.InsufficientResponseError:
        log.warning("OSMnx returned no features for this area")
        return []

    # Filter to the place values we care about
    mask = gdf["place"].isin(config.SETTLEMENT_PLACE_TAGS)
    gdf = gdf[mask]

    if gdf.empty:
        return []

    # Ensure every row has a name
    gdf = gdf[gdf["name"].notna()]

    settlements = []
    for _, row in gdf.iterrows():
        centroid = row.geometry.centroid
        settlements.append({
            "name": str(row["name"]),
            "lat": round(centroid.y, 5),
            "lon": round(centroid.x, 5),
            "type": str(row["place"]),
        })

    log.info("Found %d settlements", len(settlements))
    return settlements
