"""Fetch cloud-filtered Sentinel-2 imagery from Google Earth Engine and display
it as an interactive split-panel temporal comparison map.

Setup:
    pip install -r requirements.txt
    earthengine authenticate
    export EE_PROJECT_ID="your-gee-project-id"
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import ee
import folium
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from branca.element import Element

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

load_dotenv()

_SCL_CLEAR = [4, 5, 6, 7]
_MAX_SCENE_CLOUD_PCT = 40
_CLOUD_PROB_THRESHOLD = 60
_GEOCODER_USER_AGENT = "geovision/1.0"

_CHANGE_TRANSITIONS = [
    (1, 6, "Forest -> Urban", "f44336"),
    (0, 6, "Water -> Urban", "1976d2"),
    (6, 0, "Urban -> Water", "00bcd4"),
    (1, 4, "Forest -> Agriculture", "a5d6a7"),
    (4, 6, "Agriculture -> Urban", "d32f2f"),
    (7, 6, "Bare -> Urban", "795548"),
    (6, 1, "Urban -> Forest", "009688"),
    (0, 1, "Water -> Forest", "1e88e5"),
    (4, 1, "Agriculture -> Forest", "388e3c"),
    (1, 7, "Forest -> Bare soil", "81c784"),
    (0, 4, "Water -> Agriculture", "4fc3f7"),
    (6, 4, "Urban -> Agriculture", "ff9800"),
]

_MAP_DIVIDER_STYLE = """
<style>
.leaflet-sbs {
    z-index: 1200 !important;
}

.leaflet-sbs-range {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 52px;
    margin: 0;
    padding: 0;
    background: rgba(0, 113, 227, 0.14) !important;
    cursor: ew-resize;
    pointer-events: auto;
    z-index: 1200 !important;
}

.leaflet-sbs-divider {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 12px;
    margin-left: -6px;
    background: linear-gradient(90deg,
        rgba(0,0,0,0.6) 0%,
        rgba(255,255,255,0.98) 30%,
        rgba(255,255,255,0.98) 70%,
        rgba(0,0,0,0.6) 100%
    ) !important;
    box-shadow: 0 0 8px rgba(0,0,0,0.5), 0 0 2px rgba(0,0,0,0.3) !important;
    z-index: 1201 !important;
}

.leaflet-sbs-divider::before {
    content: '⇆';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 44px;
    height: 44px;
    transform: translate(-50%, -50%);
    border-radius: 50%;
    background: #ffffff !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.45), 0 0 0 3px rgba(0,113,227,0.9) !important;
    color: #0066cc;
    font-size: 20px;
    font-weight: 800;
    line-height: 44px;
    text-align: center;
}

.leaflet-sbs-divider::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 6px;
    height: 48px;
    transform: translate(-50%, -50%);
    border-radius: 999px;
    background: rgba(0,113,227,0.95) !important;
    box-shadow: 0 0 8px rgba(0,0,0,0.4), 0 0 0 2px #fff !important;
}

.leaflet-sbs-range::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 42px;
    height: 42px;
    border: 3px solid rgba(0, 113, 227, 0.98);
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.28) !important;
    pointer-events: auto;
}

.leaflet-sbs-range::-moz-range-thumb {
    width: 42px;
    height: 42px;
    border: 3px solid rgba(0, 113, 227, 0.98);
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.28) !important;
    pointer-events: auto;
}

.leaflet-sbs-range::-ms-thumb {
    width: 42px;
    height: 42px;
    border: 3px solid rgba(0, 113, 227, 0.98);
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.28) !important;
    pointer-events: auto;
}
</style>
"""

# Divider styles loaded at end of body for highest priority
_MAP_DIVIDER_OVERRIDE = """
<style id="sbs-override">
/* Side-by-side divider overrides - loaded last for highest priority */
.leaflet-sbs-divider {
    position: absolute !important;
    top: 0 !important;
    bottom: 0 !important;
    width: 14px !important;
    margin-left: -7px !important;
    background: rgba(255,255,255,0.95) !important;
    border-left: 3px solid rgba(0,0,0,0.25) !important;
    border-right: 3px solid rgba(0,0,0,0.25) !important;
    box-shadow: -4px 0 12px rgba(0,0,0,0.35), 4px 0 12px rgba(0,0,0,0.35) !important;
    z-index: 10000 !important;
}

.leaflet-sbs-divider::before {
    content: '⇆' !important;
    position: absolute !important;
    top: 50% !important;
    left: 50% !important;
    width: 48px !important;
    height: 48px !important;
    transform: translate(-50%, -50%) !important;
    border-radius: 50% !important;
    background: #fff !important;
    border: 4px solid #0066cc !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4) !important;
    color: #0066cc !important;
    font-size: 22px !important;
    font-weight: 900 !important;
    line-height: 40px !important;
    text-align: center !important;
    z-index: 10001 !important;
}

.leaflet-sbs-divider::after {
    display: none !important;
}

.leaflet-sbs-range {
    z-index: 10000 !important;
}
</style>
"""


@dataclass
class Location:
    name: str
    lat: float
    lon: float


@dataclass
class DateRange:
    start: str
    end: str

    def __str__(self) -> str:
        return f"{self.start} -> {self.end}"


@dataclass
class Config:
    location: Location = field(default_factory=lambda: Location("Pune", 18.5936, 73.7301))
    buffer_m: int = 10_000
    timeline1: DateRange = field(default_factory=lambda: DateRange("2023-11-01", "2024-02-28"))
    timeline2: DateRange = field(default_factory=lambda: DateRange("2024-11-01", "2025-02-28"))
    project: Optional[str] = field(default_factory=lambda: os.getenv("EE_PROJECT_ID"))
    output: str = "map.html"


# ---------------------------------------------------------------------------
def init_ee(project: Optional[str]) -> None:
    kwargs = {"project": project} if project else {}
    try:
        ee.Initialize(**kwargs)
        log.info("EE initialised (project=%s)", project or "<default>")
    except ee.EEException:
        log.info("Launching EE auth in browser...")
        ee.Authenticate()
        ee.Initialize(**kwargs)


# ---------------------------------------------------------------------------
def _mask_scl(image: ee.Image) -> ee.Image:
    scl = image.select("SCL")
    mask = ee.Image(0)
    for cls in _SCL_CLEAR:
        mask = mask.Or(scl.eq(cls))
    return image.updateMask(mask).copyProperties(image, ["system:index"])


def _join_cloudless(sr_col, aoi, date_range):
    cloud_col = (
        ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY")
        .filterBounds(aoi).filterDate(date_range.start, date_range.end)
    )
    def _attach_prob(img):
        p = cloud_col.filter(ee.Filter.eq("system:index", img.get("system:index"))).first()
        return img.set("cloud_prob", p)
    def _mask_prob(img):
        return img.updateMask(ee.Image(img.get("cloud_prob")).select("probability").lt(_CLOUD_PROB_THRESHOLD))
    return sr_col.map(_attach_prob).map(_mask_prob)


def _build_composite(aoi, date_range, label) -> ee.Image:
    sr_col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi).filterDate(date_range.start, date_range.end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", _MAX_SCENE_CLOUD_PCT))
    )
    sr_col = _join_cloudless(sr_col, aoi, date_range).map(_mask_scl)
    count = sr_col.size().getInfo()
    if count == 0:
        raise RuntimeError(f"No Sentinel-2 scenes for '{label}'. Widen your date range.")
    log.info("[%s] %d scenes — median.", label, count)
    return sr_col.median().clip(aoi)


# ---------------------------------------------------------------------------
def resolve_location(query, lat, lon, name) -> Location:
    if query:
        log.info("Geocoding '%s'...", query)
        g = Nominatim(user_agent=_GEOCODER_USER_AGENT)
        r = g.geocode(query)
        if r is None:
            sys.exit(f"Could not geocode '{query}'.")
        log.info("Resolved: %s (%.4f, %.4f)", r.address, r.latitude, r.longitude)
        return Location(query, r.latitude, r.longitude)
    if not (-90 <= lat <= 90) and (-180 <= lon <= 180):
        lat, lon = lon, lat
    return Location(name, lat, lon)


# ---------------------------------------------------------------------------
# Dynamic World land cover
# ---------------------------------------------------------------------------

def _dw_image_for_year(year, aoi) -> ee.Image:
    col = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(aoi)
        .filterDate(f"{year}-01-01", f"{year}-12-31")
    )
    n = col.size().getInfo()
    if n == 0:
        log.warning("No Dynamic World for %d — blank.", year)
        return ee.Image(0).clip(aoi).rename("landcover")
    log.info("Dynamic World %d: %d scenes — mode.", year, n)
    return col.select("label").mode().clip(aoi)


def get_classified_image(year, aoi) -> ee.Image:
    return _dw_image_for_year(year, aoi).rename("landcover")


def detect_changes(classified_a, classified_b) -> ee.Image:
    change = classified_a.multiply(0).rename("change").toInt16()
    for code, (from_cls, to_cls, _label, _color) in enumerate(_CHANGE_TRANSITIONS, start=1):
        mask = classified_a.eq(from_cls).And(classified_b.eq(to_cls))
        change = change.where(mask, code)
    return change.updateMask(change.neq(0)).rename("change")


def get_change_vis_params() -> dict:
    palette = ",".join(color for _from_cls, _to_cls, _label, color in _CHANGE_TRANSITIONS)
    return {"bands": ["change"], "min": 1, "max": len(_CHANGE_TRANSITIONS), "palette": palette}


def build_change_legend() -> str:
    entries = [(color, label) for _from_cls, _to_cls, label, color in _CHANGE_TRANSITIONS]
    rows = "".join(
        '<div style="display:flex;align-items:center;gap:7px;margin:3px 0">'
        '<div style="width:14px;height:14px;background:#' + c + ';border-radius:2px;flex-shrink:0"></div>'
        '<span style="font-size:11px;font-family:sans-serif">' + lbl + '</span></div>'
        for c, lbl in entries
    )
    return (
        '<div style="padding:8px 12px">'
        '<div style="font-weight:700;font-size:12px;margin-bottom:6px;'
        'border-bottom:1px solid #ddd;padding-bottom:4px">Change Mask</div>'
        + rows + '</div>'
    )


# ---------------------------------------------------------------------------
# Map building
# ---------------------------------------------------------------------------

_VIS = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 5000}


def build_split_map(
    image1, image2, aoi, cfg,
    classified1=None, classified2=None,
) -> None:
    """Build a split-panel map using Folium.

    Writes a single HTML file. The leaflet-side-by-side plugin creates the
    split. We suppress OSM by not adding it, and only add GEE tile layers.
    """
    loc = cfg.location

    m = folium.Map(
        location=[loc.lat, loc.lon],
        zoom_start=13,
        max_zoom=24,
        zoom_control=True,
        prefer_canvas=False,
    )

    # Remove the auto-added OSM tile layer from m._children
    to_del = [
        k for k, v in m._children.items()
        if isinstance(v, folium.raster_layers.TileLayer)
        and getattr(v, "tiles", "") and "openstreetmap" in v.tiles
    ]
    for k in to_del:
        del m._children[k]

    m.get_root().header.add_child(Element(_MAP_DIVIDER_STYLE))
    m.get_root().html.add_child(Element(_MAP_DIVIDER_OVERRIDE))

    # Use Esri Satellite as the visual base
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Satellite",
        overlay=True,
        control=True,
        max_zoom=24,
    ).add_to(m)

    # GEE tile URL for before and after
    tile1 = image1.resample("bilinear").getMapId(_VIS)["tile_fetcher"].url_format
    tile2 = image2.resample("bilinear").getMapId(_VIS)["tile_fetcher"].url_format

    left_layer = folium.TileLayer(
        tiles=tile1,
        attr="Google Earth Engine",
        name=f"Before ({cfg.timeline1})",
        overlay=True,
        control=False,
        max_zoom=24,
    ).add_to(m)

    right_layer = folium.TileLayer(
        tiles=tile2,
        attr="Google Earth Engine",
        name=f"After ({cfg.timeline2})",
        overlay=True,
        control=False,
        max_zoom=24,
    ).add_to(m)

    m.get_root().header.add_child(Element(
        '<script src="https://cdn.jsdelivr.net/gh/digidem/leaflet-side-by-side@2.0.0/leaflet-side-by-side.min.js"></script>'
    ))
    m.get_root().script.add_child(Element(
        f"window.addEventListener('load', function() {{ L.control.sideBySide({left_layer.get_name()}, {right_layer.get_name()}, {{padding: 0}}).addTo({m.get_name()}); }});"
    ))

    # Change detection layer
    if classified1 is not None and classified2 is not None:
        try:
            change_img = detect_changes(classified1, classified2)
            change_map_id = change_img.getMapId(get_change_vis_params())
            folium.TileLayer(
                tiles=change_map_id["tile_fetcher"].url_format,
                attr="Google Earth Engine",
                name="Change Mask",
                overlay=True,
                control=True,
                max_zoom=24,
                opacity=0.75,
            ).add_to(m)

            legend_html = build_change_legend()
            folium.Marker(
                location=[loc.lat, loc.lon],
                icon=folium.DivIcon(
                    icon_size=(280, 330),
                    icon_anchor=(10, 330),
                    html=(
                        '<div style="position:fixed;bottom:20px;left:20px;'
                        'z-index:9999;background:#fff;padding:10px 14px;'
                        'border-radius:10px;box-shadow:0 2px 14px rgba(0,0,0,.18);'
                        'font-family:system-ui,sans-serif;pointer-events:none">'
                        + legend_html + '</div>'
                    ),
                ),
                clickable=False,
            ).add_to(m)
        except Exception as e:
            log.warning("Change layer skipped: %s", e)

    # AOI outline
    aoi_geojson = aoi.getInfo()
    folium.GeoJson(
        aoi_geojson,
        name=f"AOI -- {loc.name}",
        style_function=lambda x: {
            "color": "#0071e3", "weight": 3,
            "fillColor": "#0071e3", "fillOpacity": 0.15,
        },
        control=False,
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    m.save(cfg.output)
    log.info("Map saved: %s", cfg.output)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    defaults = Config()
    g = p.add_argument_group("location")
    g.add_argument("--query", metavar="PLACE", help="City / address to geocode")
    g.add_argument("--lat",  type=float, default=defaults.location.lat)
    g.add_argument("--lon",  type=float, default=defaults.location.lon)
    g.add_argument("--name", default=defaults.location.name)
    g.add_argument("--buffer", type=int, default=defaults.buffer_m, metavar="METERS")
    t1 = p.add_argument_group("timeline 1")
    t1.add_argument("--start1", default=defaults.timeline1.start, metavar="YYYY-MM-DD")
    t1.add_argument("--end1",   default=defaults.timeline1.end,   metavar="YYYY-MM-DD")
    t2 = p.add_argument_group("timeline 2")
    t2.add_argument("--start2", default=defaults.timeline2.start, metavar="YYYY-MM-DD")
    t2.add_argument("--end2",   default=defaults.timeline2.end,   metavar="YYYY-MM-DD")
    adv = p.add_argument_group("advanced")
    adv.add_argument("--project", default=defaults.project)
    adv.add_argument("--output", default=defaults.output, metavar="FILE.html")
    return p


def _args_to_config(args):
    return Config(
        location=resolve_location(args.query, args.lat, args.lon, args.name),
        buffer_m=args.buffer,
        timeline1=DateRange(args.start1, args.end1),
        timeline2=DateRange(args.start2, args.end2),
        project=args.project or os.getenv("EE_PROJECT_ID"),
        output=args.output,
    )


def main():
    args = _build_parser().parse_args()
    cfg = _args_to_config(args)
    loc = cfg.location

    log.info("GeoVision Temporal Comparison")
    log.info("Location : %s (%.4f, %.4f)", loc.name, loc.lat, loc.lon)
    log.info("Timeline1: %s", cfg.timeline1)
    log.info("Timeline2: %s", cfg.timeline2)
    log.info("Output   : %s", cfg.output)

    init_ee(cfg.project)
    aoi = ee.Geometry.Point([loc.lon, loc.lat]).buffer(cfg.buffer_m)

    log.info("Fetching Timeline 1...")
    image1 = _build_composite(aoi, cfg.timeline1, "Timeline 1")
    log.info("Fetching Timeline 2...")
    image2 = _build_composite(aoi, cfg.timeline2, "Timeline 2")
    log.info("Building split-panel map...")
    build_split_map(image1, image2, aoi, cfg)
    log.info("Done: %s", cfg.output)


if __name__ == "__main__":
    main()