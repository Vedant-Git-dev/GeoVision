"""Fetch cloud-filtered Sentinel-2 imagery from Google Earth Engine
and display it as an interactive split-panel temporal comparison map.

Setup (one-time):
    pip install -r requirements.txt
    earthengine authenticate
    export EE_PROJECT_ID="your-gee-project-id"

Usage:
    # Default location (Pune), default date ranges
    python fetch_satellite_image.py

    # Named location lookup
    python fetch_satellite_image.py --query "Mumbai, India"

    # Explicit coordinates with custom date ranges
    python fetch_satellite_image.py \\
        --lat 19.076 --lon 72.877 --name Mumbai \\
        --start1 2023-01-01 --end1 2023-06-01 \\
        --start2 2024-01-01 --end2 2024-06-01
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import ee
import geemap
import folium
from folium import plugins
from dotenv import load_dotenv
from geopy.geocoders import Nominatim

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

# Scene Classification Layer classes considered "clear":
#   4=Vegetation, 5=Bare Soil, 6=Water, 7=Unclassified
_SCL_CLEAR = [4, 5, 6, 7]

# Reject scenes with more cloud cover than this (pre-filter, fast)
_MAX_SCENE_CLOUD_PCT = 40

# Reject individual pixels with s2cloudless probability above this (per-pixel, slow but accurate)
_CLOUD_PROB_THRESHOLD = 60

_GEOCODER_USER_AGENT = "geovision_satellite_fetcher/1.0"


@dataclass
class Location:
    name: str
    lat: float
    lon: float


@dataclass
class DateRange:
    start: str  # YYYY-MM-DD
    end: str    # YYYY-MM-DD

    def __str__(self) -> str:
        return f"{self.start} → {self.end}"


@dataclass
class Config:
    location: Location = field(default_factory=lambda: Location("Pune", 18.5936, 73.7301))
    buffer_m: int = 10_000
    timeline1: DateRange = field(default_factory=lambda: DateRange("2023-11-01", "2024-02-28"))
    timeline2: DateRange = field(default_factory=lambda: DateRange("2024-11-01", "2025-02-28"))
    project: Optional[str] = field(default_factory=lambda: os.getenv("EE_PROJECT_ID"))
    output: str = "map.html"


# ---------------------------------------------------------------------------
# Earth Engine initialisation
# ---------------------------------------------------------------------------

def init_ee(project: Optional[str]) -> None:
    """Initialise (and authenticate if needed) the Earth Engine API."""
    kwargs = {"project": project} if project else {}
    try:
        ee.Initialize(**kwargs)
        log.info("Earth Engine initialised (project=%s)", project or "<default>")
    except ee.EEException:
        log.info("No cached credentials found — launching browser authentication...")
        ee.Authenticate()
        ee.Initialize(**kwargs)


# ---------------------------------------------------------------------------
# Cloud masking
# ---------------------------------------------------------------------------

def _mask_scl(image: ee.Image) -> ee.Image:
    """Mask out non-clear pixels using the Scene Classification Layer."""
    scl = image.select("SCL")
    mask = ee.Image(0)
    for cls in _SCL_CLEAR:
        mask = mask.Or(scl.eq(cls))
    return image.updateMask(mask).copyProperties(image, ["system:index"])


def _join_cloudless(
    sr_col: ee.ImageCollection,
    aoi: ee.Geometry,
    date_range: DateRange,
) -> ee.ImageCollection:
    """Join the SR collection with s2cloudless and mask high-probability cloud pixels."""
    cloud_col = (
        ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY")
        .filterBounds(aoi)
        .filterDate(date_range.start, date_range.end)
    )

    # Attach cloud-probability image as a property so we can reference it per-image
    def _attach_prob(img: ee.Image) -> ee.Image:
        prob_img = cloud_col.filter(
            ee.Filter.eq("system:index", img.get("system:index"))
        ).first()
        return img.set("cloud_prob", prob_img)

    def _mask_prob(img: ee.Image) -> ee.Image:
        prob = ee.Image(img.get("cloud_prob")).select("probability")
        return img.updateMask(prob.lt(_CLOUD_PROB_THRESHOLD))

    return sr_col.map(_attach_prob).map(_mask_prob)


def _build_composite(aoi: ee.Geometry, date_range: DateRange, label: str) -> ee.Image:
    """Return a cloud-masked median composite clipped to *aoi* for *date_range*."""
    sr_col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(date_range.start, date_range.end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", _MAX_SCENE_CLOUD_PCT))
    )

    sr_col = _join_cloudless(sr_col, aoi, date_range)
    sr_col = sr_col.map(_mask_scl)

    count: int = sr_col.size().getInfo()
    if count == 0:
        raise RuntimeError(
            f"No usable Sentinel-2 scenes found for '{label}' ({date_range}).\n"
            "Try widening the date range, raising --max-cloud-pct, or choosing a different location."
        )

    log.info("[%s] %d scene(s) found — computing median composite.", label, count)
    return sr_col.median().clip(aoi)


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def resolve_location(
    query: Optional[str],
    lat: float,
    lon: float,
    name: str,
) -> Location:
    """Return a validated/geocoded Location.

    Priority: --query > explicit --lat/--lon > defaults.
    """
    if query:
        log.info("Geocoding '%s'...", query)
        geolocator = Nominatim(user_agent=_GEOCODER_USER_AGENT)
        result = geolocator.geocode(query)
        if result is None:
            sys.exit(
                f"Could not geocode '{query}'. "
                "Try a more specific query or supply --lat / --lon manually."
            )
        log.info("Resolved: %s (%.4f, %.4f)", result.address, result.latitude, result.longitude)
        return Location(query, result.latitude, result.longitude)

    # Detect silently swapped lat/lon
    if not (-90 <= lat <= 90) and (-90 <= lon <= 90):
        log.warning(
            "Latitude %.4f is out of range — looks like lat/lon were swapped. Correcting.", lat
        )
        lat, lon = lon, lat

    if not (-90 <= lat <= 90):
        sys.exit(f"Invalid latitude {lat}: must be between -90 and 90.")
    if not (-180 <= lon <= 180):
        sys.exit(f"Invalid longitude {lon}: must be between -180 and 180.")

    return Location(name, lat, lon)


# ---------------------------------------------------------------------------
# Map building
# ---------------------------------------------------------------------------

_VIS = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}
_AOI_PALETTE = ["#FF4444"]


def build_split_map(
    image1: ee.Image,
    image2: ee.Image,
    aoi: ee.Geometry,
    cfg: Config,
):
    """Compose an interactive split-panel map with an AOI boundary overlay using Folium."""
    loc = cfg.location
    m = folium.Map(location=[loc.lat, loc.lon], zoom_start=13, max_zoom=24)

    # Add Esri Satellite basemap
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        overlay=False,
        control=True,
        max_zoom=24
    ).add_to(m)

    # Apply bilinear resampling to smooth out the jagged 10m pixels when zoomed in
    vis_image1 = image1.resample('bilinear')
    vis_image2 = image2.resample('bilinear')

    # Get Earth Engine map IDs
    map_id1 = vis_image1.getMapId(_VIS)
    map_id2 = vis_image2.getMapId(_VIS)

    left_layer = folium.TileLayer(
        tiles=map_id1['tile_fetcher'].url_format,
        attr='Google Earth Engine',
        name=f"Timeline 1 ({cfg.timeline1})",
        overlay=True,
        control=False,
        max_zoom=24
    ).add_to(m)

    right_layer = folium.TileLayer(
        tiles=map_id2['tile_fetcher'].url_format,
        attr='Google Earth Engine',
        name=f"Timeline 2 ({cfg.timeline2})",
        overlay=True,
        control=False,
        max_zoom=24
    ).add_to(m)

    # Add Split Control
    sbs = plugins.SideBySideLayers(layer_left=left_layer, layer_right=right_layer)
    sbs.add_to(m)

    # Better AOI Outline (Apple Blue with translucent fill)
    aoi_geojson = aoi.getInfo()
    folium.GeoJson(
        aoi_geojson,
        name=f"AOI — {loc.name}",
        style_function=lambda x: {
            'color': '#0071e3',
            'weight': 3,
            'fillColor': '#0071e3',
            'fillOpacity': 0.15
        },
        control=False
    ).add_to(m)

    return m


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    defaults = Config()

    # Location
    loc_g = p.add_argument_group("location")
    loc_g.add_argument("--query", metavar="PLACE",
                       help="City / address to geocode (overrides --lat and --lon)")
    loc_g.add_argument("--lat",  type=float, default=defaults.location.lat)
    loc_g.add_argument("--lon",  type=float, default=defaults.location.lon)
    loc_g.add_argument("--name", default=defaults.location.name,
                       help="Label shown on the map")
    loc_g.add_argument("--buffer", type=int, default=defaults.buffer_m,
                       metavar="METERS", help="AOI radius around the point")

    # Timelines
    t1 = p.add_argument_group("timeline 1 (left panel)")
    t1.add_argument("--start1", default=defaults.timeline1.start, metavar="YYYY-MM-DD")
    t1.add_argument("--end1",   default=defaults.timeline1.end,   metavar="YYYY-MM-DD")

    t2 = p.add_argument_group("timeline 2 (right panel)")
    t2.add_argument("--start2", default=defaults.timeline2.start, metavar="YYYY-MM-DD")
    t2.add_argument("--end2",   default=defaults.timeline2.end,   metavar="YYYY-MM-DD")

    # Advanced / output
    adv = p.add_argument_group("advanced")
    adv.add_argument("--project",       default=defaults.project,
                     help="Earth Engine Cloud Project ID")
    adv.add_argument("--max-cloud-pct", type=int, default=_MAX_SCENE_CLOUD_PCT,
                     dest="max_cloud_pct",
                     help="Per-scene cloud-cover percentage ceiling")
    adv.add_argument("--output", default=defaults.output, metavar="FILE.html")

    return p


def _args_to_config(args: argparse.Namespace) -> Config:
    global _MAX_SCENE_CLOUD_PCT
    _MAX_SCENE_CLOUD_PCT = args.max_cloud_pct

    location = resolve_location(args.query, args.lat, args.lon, args.name)

    return Config(
        location=location,
        buffer_m=args.buffer,
        timeline1=DateRange(args.start1, args.end1),
        timeline2=DateRange(args.start2, args.end2),
        project=args.project,
        output=args.output,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = _build_parser().parse_args()
    cfg  = _args_to_config(args)
    loc  = cfg.location

    log.info("━" * 55)
    log.info("🛰  Earth Engine — Temporal Comparison Fetcher")
    log.info("━" * 55)
    log.info("Location   : %s  (%.4f, %.4f)", loc.name, loc.lat, loc.lon)
    log.info("AOI buffer : %d m", cfg.buffer_m)
    log.info("Timeline 1 : %s", cfg.timeline1)
    log.info("Timeline 2 : %s", cfg.timeline2)
    log.info("Output     : %s", cfg.output)
    log.info("━" * 55)

    init_ee(cfg.project)

    aoi = ee.Geometry.Point([loc.lon, loc.lat]).buffer(cfg.buffer_m)

    log.info("Fetching Timeline 1 imagery...")
    image1 = _build_composite(aoi, cfg.timeline1, "Timeline 1")

    log.info("Fetching Timeline 2 imagery...")
    image2 = _build_composite(aoi, cfg.timeline2, "Timeline 2")

    log.info("Building split-panel map...")
    m = build_split_map(image1, image2, aoi, cfg)
    m.save(cfg.output)

    log.info("━" * 55)
    log.info("✓ Saved to '%s'. Open it in a browser to compare the timelines.", cfg.output)
    log.info("━" * 55)


if __name__ == "__main__":
    main()