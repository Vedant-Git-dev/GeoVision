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
_MAX_SCENE_CLOUD_PCT = 20
_CLOUD_PROB_THRESHOLD = 50
_GEOCODER_USER_AGENT = "geovision/1.0"

_CHANGE_TRANSITIONS = [
    (1, 6, "Forest -> Urban", "f44336"),
    (0, 6, "Water -> Urban", "1976d2"),
    (6, 0, "Urban -> Water", "00bcd4"),
    (1, 4, "Forest -> Agriculture", "a5d6a7"),
    (4, 6, "Agriculture -> Urban", "d32f2f"),
    (3, 6, "Bare -> Urban", "795548"),
    (6, 1, "Urban -> Forest", "009688"),
    (0, 1, "Water -> Forest", "1e88e5"),
    (4, 1, "Agriculture -> Forest", "388e3c"),
    (1, 3, "Forest -> Bare soil", "81c784"),
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


"""Detect land cover changes via DIRECT spectral comparison.

Instead of classifying each image and comparing labels (which is noisy),
compare the actual band values and spectral indices between two dates.
Real land-use change (urban expansion, deforestation, etc.) causes
a large, consistent shift in spectral bands, while sensor/noise differences
are much smaller and scattered.
"""

# Dynamic World class indices (from label band)
_DW_CLASSES = {
    "water": 0,
    "trees": 1,
    "grass": 2,
    "flooded_vegetation": 3,
    "crops": 4,
    "shrub_and_scrub": 5,
    "built": 6,
    "bare": 7,
    "snow_and_ice": 8,
}

_DW_LABEL_NAMES = [
    "water", "trees", "grass", "flooded_vegetation", "crops",
    "shrub_and_scrub", "built", "bare", "snow_and_ice"
]

_MAJORITY_THRESH = 0.30  # Require at least 30% of scenes agreed on majority class

def _dw_image_for_year(year, aoi, date_range) -> ee.Image:
    """Build majority-voted land cover from Jan-Mar of the given year.

    Returns an image with:
    - 'label': majority-voted class (mode) across all scenes
    - 'vote_pct': fraction of scenes that agreed on the majority class (0-1)
    """
    col = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(aoi)
        .filterDate(date_range.start, date_range.end)
        .select("label")
    )
    n = col.size().getInfo()
    if n == 0:
        log.warning("No Dynamic World for %s — blank.", date_range)
        return ee.Image.constant(0).rename(["label", "vote_pct"]).clip(aoi)

    log.info("Dynamic World %s: %d scenes — majority vote.", date_range, n)

    # Mode (majority vote) across all scenes
    mode_img = col.mode().clip(aoi)

    # Count votes: for each class c, create a 0/1 mask of scenes labeled c, then sum
    count_bands = []
    for c in range(9):
        # Binary mask: 1 where this scene had label c, else 0
        mask = col.map(lambda img: img.eq(c).copyProperties(img, ["system:time_start"]))
        count_bands.append(mask.sum())
    votes_img = ee.Image.cat(count_bands).rename(_DW_LABEL_NAMES)

    # Fraction of scenes that agreed on the majority class
    total_scenes = ee.Image(n).float()
    majority_pct = votes_img.reduce(ee.Reducer.max()).divide(total_scenes).rename("vote_pct")

    return mode_img.addBands(majority_pct)


def get_classified_image(year, aoi, date_range) -> ee.Image:
    """Fetch Dynamic World imagery for Jan-Mar of the given year to match seasonal window."""
    return _dw_image_for_year(year, aoi, date_range)


# ---------------------------------------------------------------------------
# Spectral indices (Step 2 of neighborhood approach)
# ---------------------------------------------------------------------------

def _spectral_indices(image: ee.Image) -> ee.Image:
    """Compute 4 spectral indices per Step 2 of the neighborhood approach.

    Required bands: B2(Blue), B3(Green), B4(Red), B8(NIR), B11(SWIR1), B12(SWIR2)

    Indices:
      NDVI = (NIR - Red) / (NIR + Red)              -> Vegetation
      NDWI = (Green - NIR) / (Green + NIR)          -> Water
      NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)          -> Built-up
      BSI  = (SWIR1 + SWIR2 - NIR - Red) / (SWIR1 + SWIR2 + NIR + Red)  -> Bare Soil
    """
    b2 = image.select("B2")
    b3 = image.select("B3")
    b4 = image.select("B4")
    b8 = image.select("B8")
    b11 = image.select("B11")
    b12 = image.select("B12")

    ndvi = b8.subtract(b4).divide(b8.add(b4)).rename("NDVI")
    ndwi = b3.subtract(b8).divide(b3.add(b8)).rename("NDWI")
    ndbi = b11.subtract(b8).divide(b11.add(b8)).rename("NDBI")
    # BSI: bare soil reflectance is high in SWIR, low in NIR and Red
    bsi = b11.add(b12).subtract(b8).subtract(b4).divide(
        b11.add(b12).add(b8).add(b4)).rename("BSI")

    return image.addBands([ndvi, ndwi, ndbi, bsi])


# ---------------------------------------------------------------------------
# Feature extraction (Steps 3-4 of neighborhood approach)
# ---------------------------------------------------------------------------

_RAW_BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
_INDEX_BANDS = ["NDVI", "NDWI", "NDBI", "BSI"]
_KERNEL: ee.Kernel | None = None  # lazy-initialized


def _neighborhood_kernel() -> ee.Kernel:
    global _KERNEL
    if _KERNEL is None:
        _KERNEL = ee.Kernel.circle(radius=1, units="pixels")
    return _KERNEL


def _neighborhood_stats(image: ee.Image) -> ee.Image:
    """Compute 3×3 focal mean + stddev for all bands and indices.

    No pixel is classified independently — every pixel uses neighborhood info.
    """
    all_bands = _RAW_BANDS + _INDEX_BANDS

    result = image.select(all_bands).reduceNeighborhood(
        ee.Reducer.mean(), _neighborhood_kernel())
    result = result.select(
        [f"{b}_mean" for b in all_bands]
    ).rename([f"{b}_mean" for b in all_bands])

    std = image.select(all_bands).reduceNeighborhood(
        ee.Reducer.stdDev(), _neighborhood_kernel())
    std = std.select(
        [f"{b}_stdDev" for b in all_bands]
    ).rename([f"{b}_std" for b in all_bands])

    return image.addBands(result).addBands(std)


def _texture_features(image: ee.Image) -> ee.Image:
    """Compute texture features per Step 4.

    Features: CoV (heterogeneity proxy), GLCM Contrast, GLCM Homogeneity.
    These describe surface structure across the 3x3 neighborhood.

    CoV (Coefficient of Variation) = std / |mean|
      - High CoV = heterogeneous (urban, mixed agriculture)
      - Low CoV = homogeneous (water, dense forest)
    GLCM metrics capture spatial texture patterns on the reflectance band.
    """
    all_bands = _RAW_BANDS + _INDEX_BANDS

    # Compute mean and stdDev separately (each preserves original band names)
    mean_img = image.select(all_bands).reduceNeighborhood(
        ee.Reducer.mean(), _neighborhood_kernel())
    std_img = image.select(all_bands).reduceNeighborhood(
        ee.Reducer.stdDev(), _neighborhood_kernel())

    # Coefficient of variation = std / |mean| (proxy for entropy/heterogeneity)
    _eps_img = ee.Image.constant(0.001)
    cov_img = std_img.divide(mean_img.abs().add(_eps_img)).rename(
        [f"{b}_var" for b in all_bands])

    # GLCM on B4 (Red): requires int16 input, captures spatial heterogeneity
    # (building density, crop rows, forest texture)
    glcm = image.select("B4").int16().glcmTexture(size=3)
    contrast = glcm.select("B4_contrast").rename("glcm_contrast")
    homogeneity = glcm.select("B4_idm").rename("glcm_homogeneity")  # idm = Inverse Difference Moment = homogeneity

    return image.addBands(cov_img).addBands(contrast).addBands(homogeneity)


def build_feature_stack(image: ee.Image) -> ee.Image:
    """Build the complete 24-feature image per Step 4.

    Feature vector (24 dimensions):
      - Raw Bands (12): B2-B12 × (mean, std)       [6 bands × 2 = 12]
      - Indices (8):   NDVI/NDWI/NDBI/BSI × (mean, std) [4 × 2 = 8]
      - Texture (4):   Variance, Entropy, GLCM Contrast, GLCM Homogeneity

    Total: 24 features per 3×3 window.
    Returns an image with all features as individual bands.
    """
    with_indices = _spectral_indices(image)
    with_stats = _neighborhood_stats(with_indices)
    return _texture_features(with_stats)


# ---------------------------------------------------------------------------
# Signature builder (Step 5 of neighborhood approach)
# ---------------------------------------------------------------------------

def _safe_div(a: ee.Image, b: ee.Image) -> ee.Image:
    """Divide with a tiny epsilon to avoid division by zero."""
    EPS = ee.Image.constant(0.001)
    return a.divide(b.add(EPS))


def compute_signature(features: ee.Image) -> ee.Image:
    """Build class signatures from 24-feature image per Step 5.

    Class labels (matching Dynamic World convention):
      0 = Water      — NDWI dominant, very smooth texture
      1 = Forest     — NDVI dominant, smooth texture
      3 = Bare        — BSI dominant, high BSI_mean
      4 = Agriculture — moderate NDVI, moderate BSI, heterogeneous texture
      6 = Urban       — NDBI dominant, high texture complexity

    Returns an image with class proportions + label.
    """
    # ---- Class intensity scores ----
    # Indices are signed: a class only scores where its index is POSITIVE.
    # Do NOT use .abs() — that makes water/forest (strongly negative NDBI)
    # look like built-up, causing bare→forest/water to flag as Forest→Urban.
    zero = ee.Image.constant(0)
    veg_score = features.select("NDVI_mean").max(zero)    # + only for vegetation
    built_score = features.select("NDBI_mean").max(zero)  # + only for built-up
    water_score = features.select("NDWI_mean").max(zero)  # + only for water
    bare_score = features.select("BSI_mean").max(zero)    # + only for bare soil
    # Agriculture: bare_score moderate + higher veg texture variance (crop rows)
    agri_score = bare_score.multiply(features.select("NDVI_var").add(0.01))

    # ---- Normalize to class proportions ----
    total = veg_score.add(built_score).add(water_score).add(bare_score).add(agri_score)
    forest_prop = _safe_div(veg_score, total)
    urban_prop = _safe_div(built_score, total)
    water_prop = _safe_div(water_score, total)
    bare_prop = _safe_div(bare_score, total)
    agri_prop = _safe_div(agri_score, total)

    # ---- Class label: dominant proportion ----
    is_water = water_prop.gte(forest_prop).And(
        water_prop.gte(urban_prop)).And(water_prop.gte(bare_prop)).And(
        water_prop.gte(agri_prop))
    is_agri = agri_prop.gte(forest_prop).And(
        agri_prop.gte(urban_prop)).And(agri_prop.gte(bare_prop)).And(
        agri_prop.gte(water_prop))
    is_forest = forest_prop.gte(urban_prop).And(
        forest_prop.gte(bare_prop)).And(forest_prop.gte(agri_prop)).And(
        forest_prop.gte(water_prop))
    is_bare = bare_prop.gte(urban_prop).And(
        bare_prop.gte(agri_prop)).And(bare_prop.gte(forest_prop)).And(
        bare_prop.gte(water_prop))
    is_urban = urban_prop.gte(forest_prop).And(
        urban_prop.gte(bare_prop)).And(urban_prop.gte(agri_prop)).And(
        urban_prop.gte(water_prop))

    label = (
        is_water.where(is_forest, 1)
                .where(is_bare, 3)
                .where(is_agri, 4)
                .where(is_urban, 6)
                .rename("signature_label")
    )

    return features.addBands([
        forest_prop.rename("forest_prop"),
        urban_prop.rename("urban_prop"),
        water_prop.rename("water_prop"),
        bare_prop.rename("bare_prop"),
        agri_prop.rename("agri_prop"),
        label,
    ])


# ---------------------------------------------------------------------------
# Rule engine (Step 6 of neighborhood approach)
# ---------------------------------------------------------------------------

# Approved class labels from signatures:
# 0=Water, 1=Forest, 3=Bare, 4=Agriculture, 6=Urban
_LABEL_NAMES = {
    0: "Water",
    1: "Forest",
    3: "Bare",
    4: "Agriculture",
    6: "Urban",
}

# Per-class proportion band produced by compute_signature.
# Used to gate transitions: a flip only counts if BOTH the old class (before)
# and the new class (after) are decisively dominant — marginal, noise-driven
# relabels are rejected so unchanged ground is not flagged.
_CLASS_PROP_BAND = {
    0: "water_prop",
    1: "forest_prop",
    3: "bare_prop",
    4: "agri_prop",
    6: "urban_prop",
}

# Minimum class proportion for a label to be trusted as a real transition
# endpoint. 0 = trust every label flip (noisy); higher = fewer false positives
# but more missed changes on mixed pixels. 0.35 = clear majority required.
_MIN_CLASS_CONF = 0.35


def detect_changes(image_a: ee.Image, image_b: ee.Image) -> ee.Image:
    """Detect land cover changes via neighborhood signatures + rule engine.

    Full pipeline:
      1. Build 24-feature stack for each image (3x3 neighborhood)
      2. Compute class signatures (forest/urban/water/bare/agriculture proportions)
      3. Get BEFORE label and AFTER label for every pixel
      4. Apply rule engine: only flag approved transitions

    The rule engine is the anti-noise core:
      - Does NOT ask "Is this Urban?" - that false-positives everywhere
      - Asks "Was Forest? Is now Urban?" -> Forest→Urban -> flag
      - Asks "Was Forest? Is now Bare?" -> ignored (not an approved transition)
    """
    log.info("Building feature stacks...")
    feat_a = build_feature_stack(image_a)
    feat_b = build_feature_stack(image_b)

    log.info("Computing signatures...")
    sig_a = compute_signature(feat_a)
    sig_b = compute_signature(feat_b)

    label_a = sig_a.select("signature_label")
    label_b = sig_b.select("signature_label")

    change = label_a.multiply(0).rename("change").toInt16()

    # Confidence gate: only flag a transition where the OLD class was
    # decisively present before AND the NEW class is decisively present after.
    # This kills false positives from marginal, noise-driven relabels on
    # unchanged ground (season/illumination/composite differences).
    for code, (from_cls, to_cls, label, color) in enumerate(_CHANGE_TRANSITIONS, start=1):
        conf_a = sig_a.select(_CLASS_PROP_BAND[from_cls])
        conf_b = sig_b.select(_CLASS_PROP_BAND[to_cls])
        mask = (
            label_a.eq(from_cls)
            .And(label_b.eq(to_cls))
            .And(conf_a.gte(_MIN_CLASS_CONF))
            .And(conf_b.gte(_MIN_CLASS_CONF))
        )
        change = change.where(mask, code)

    change = change.updateMask(change.neq(0))

    return change


def get_change_vis_params() -> dict:
    """Visualization for the change mask (multi-transition palette)."""
    palette = ",".join(color for _from, _to, _label, color in _CHANGE_TRANSITIONS)
    return {"bands": ["change"], "min": 1, "max": len(_CHANGE_TRANSITIONS), "palette": palette}


def build_change_legend() -> str:
    """Build HTML legend for all allowed transitions."""
    rows = "".join(
        f'<div style="display:flex;align-items:center;gap:7px;margin:3px 0">'
        f'<div style="width:14px;height:14px;background:#{c};border-radius:2px;flex-shrink:0"></div>'
        f'<span style="font-size:11px;font-family:sans-serif">{lbl}</span></div>'
        for _f, _t, lbl, c in _CHANGE_TRANSITIONS
    )
    return (
        f'<div style="padding:8px 12px">'
        f'<div style="font-weight:700;font-size:12px;margin-bottom:6px;'
        f'border-bottom:1px solid #ddd;padding-bottom:4px">Neighborhood Change</div>'
        f'{rows}'
        f'</div>'
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