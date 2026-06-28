"""FAO GAUL district boundary lookup via Google Earth Engine."""

from __future__ import annotations

import logging

import ee
import osmnx as ox
from shapely.geometry import mapping, Polygon, MultiPolygon

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


def get_city_aoi(city_query: str, lat: float, lon: float) -> tuple[ee.Geometry, str]:
    """Look up a city/town boundary via OpenStreetMap using already-geocoded coords.

    Strategy:
      1. Search for Polygon/MultiPolygon features near the point.
      2. Try to match by name (e.g. "Kalyani Nagar" polygon for "Kalyani Nagar").
      3. If no name match, find the smallest admin polygon that contains the point
         (e.g. a Ward boundary containing Viman Nagar).
      4. Fall back to a buffer if nothing works.

    Args:
        city_query: City name, e.g. "Viman Nagar, Pune". Used for name matching.
        lat: Already-geocoded latitude.
        lon: Already-geocoded longitude.

    Returns:
        Tuple of (city geometry as ee.Geometry, city name string).
    """
    primary_name = city_query.split(",")[0].strip()

    try:
        gdf = ox.features_from_point(
            (lat, lon),
            tags={"boundary": "administrative", "place": True},
            dist=15000,
        )

        if gdf.empty:
            raise ValueError("No features found near point")

        # Only keep Polygon/MultiPolygon — settlements.py requires a polygon AOI
        gdf = gdf[gdf.geometry.notna()]
        gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
        if gdf.empty:
            raise ValueError("No polygon features near point")

        # Compute areas for sorting (smallest = most specific)
        gdf_proj = gdf.to_crs(epsg=3857)
        gdf["area"] = gdf_proj.geometry.area
        gdf = gdf.sort_values("area")

        # Strategy 1: name match
        if "name" in gdf.columns:
            mask = gdf["name"].fillna("").str.lower().str.contains(
                primary_name.lower(), regex=False
            )
            matches = gdf[mask]
            if not matches.empty:
                row = matches.iloc[0]
                city_name = str(row.get("name", primary_name))
                geom = row.geometry
                geojson = mapping(geom)
                aoi = ee.Geometry(geojson)
                log.info("City boundary (name match): %s", city_name)
                return aoi, city_name

        # Strategy 2: smallest polygon that contains the geocoded point
        from shapely.geometry import Point as ShapelyPoint
        pt = ShapelyPoint(lon, lat)
        containing = gdf[gdf.geometry.contains(pt)]
        if not containing.empty:
            row = containing.iloc[0]  # smallest (already sorted)
            city_name = str(row.get("name", primary_name))
            geom = row.geometry
            geojson = mapping(geom)
            aoi = ee.Geometry(geojson)
            log.info("City boundary (containing polygon): %s", city_name)
            return aoi, city_name

        # Nothing valid found
        raise ValueError("No matching or containing polygon")

    except Exception as e:
        log.warning("City boundary lookup failed for '%s' (%s) — falling back to %dm buffer",
                     city_query, e, config.DEFAULT_BUFFER_M)
        point = ee.Geometry.Point([lon, lat])
        return point.buffer(config.DEFAULT_BUFFER_M), primary_name
