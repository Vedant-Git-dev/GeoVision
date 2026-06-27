"""Centralized configuration and constants for GeoVision."""

from __future__ import annotations

from dotenv import load_dotenv
import os

# Load .env on import
load_dotenv()

# ---------------------------------------------------------------------------
# Land cover class definitions (shared by stats, vis params, and frontend)
# ---------------------------------------------------------------------------

LAND_COVER_CLASSES = {
    0: {"name": "Water",       "color": "1565c0"},
    1: {"name": "Forest",      "color": "2e7d32"},
    3: {"name": "Bare Land",   "color": "a1887f"},
    4: {"name": "Agriculture", "color": "f9a825"},
    6: {"name": "Urban",       "color": "c62828"},
}

# ---------------------------------------------------------------------------
# Sentinel-2 cloud masking
# ---------------------------------------------------------------------------

SCL_CLEAR = [4, 5, 6, 7]
MAX_SCENE_CLOUD_PCT = 20
CLOUD_PROB_THRESHOLD = 50

# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

GEOCODER_USER_AGENT = "geovision/1.0"

# ---------------------------------------------------------------------------
# Change detection — approved LULC transitions
# ---------------------------------------------------------------------------

CHANGE_TRANSITIONS = [
    (1, 6, "Forest → Urban", "f44336"),
    (0, 6, "Water → Urban", "1976d2"),
    (1, 0, "Forest → Water", "81c784"),
    (6, 1, "Urban → Forest", "009688"),
    (6, 0, "Urban → Water", "00bcd4"),
    (0, 1, "Water → Forest", "1e88e5"),
]

# Per-class proportion band (used to gate transitions)
CLASS_PROP_BAND = {
    0: "water_prop",
    1: "forest_prop",
    3: "bare_prop",
    4: "agri_prop",
    6: "urban_prop",
}

# Minimum class proportion for a label to be trusted as a real transition
MIN_CLASS_CONF = 0.45

# Minimum raw DW probability for a class to be assigned as dominant in the
# base signature. Lower than MIN_CLASS_CONF because 9-class probability mass
# means a clearly dominant class often only reaches 0.25–0.40.  The margin
# check (MIN_DOMINANCE_MARGIN) already ensures dominance; this floor only
# rejects "tallest dwarf" pixels (e.g. ocean where trees=0.15 leads).
MIN_SIGNATURE_CONF = 0.25

# Minimum margin a class must lead over the runner-up to be assigned as dominant
MIN_DOMINANCE_MARGIN = 0.05

# ---------------------------------------------------------------------------
# Spectral cross-validation thresholds (NDVI / NDWI from Sentinel-2)
# ---------------------------------------------------------------------------

MIN_NDVI_FOR_FOREST = 0.0
MIN_NDWI_FOR_WATER = 0.0

# ---------------------------------------------------------------------------
# Surge gate
# ---------------------------------------------------------------------------

# Minimum probability increase in the target class between T1 and T2
MIN_PROB_SURGE = 0.25

# Maps class label to raw DW band name for surge checking
DW_BAND_FOR_CLASS = {
    0: "water",
    1: "trees",
    4: "crops",
    6: "built",
}

# ---------------------------------------------------------------------------
# FAO GAUL administrative boundaries
# ---------------------------------------------------------------------------

GAUL_LEVEL2 = "FAO/GAUL/2015/level2"

# ---------------------------------------------------------------------------
# Settlement discovery (OSMnx)
# ---------------------------------------------------------------------------

SETTLEMENT_PLACE_TAGS = ["city", "town"]

# ---------------------------------------------------------------------------
# Default parameters (used by app.py and pipeline.py)
# ---------------------------------------------------------------------------

DEFAULT_LOCATION = "Pune, India"
DEFAULT_LAT = 18.5936
DEFAULT_LON = 73.7301
DEFAULT_BUFFER_M = 10000
DEFAULT_BEFORE_DATE = "2023-11-01"
DEFAULT_AFTER_DATE = "2024-11-01"
DATE_WINDOW_DAYS = 90

# Sentinel-2 RGB visualization parameters
S2_VIS_PARAMS = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}

# Environment
EE_PROJECT_ID = os.getenv("EE_PROJECT_ID")
