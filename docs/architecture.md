# GeoVision — System Architecture

GeoVision is a **land-use / land-cover (LULC) change detection** web application. It takes two dates and a location, fetches Sentinel-2 satellite imagery for both time periods via Google Earth Engine, combines it with Dynamic World land-cover probability data, detects land-cover transitions between them using a rule-based engine with confidence and surge gates, and renders the results as a dual-panel interactive map in the browser.

---

## 1. User Interface Layer (`public/index.html` + `style.css` + `script.js`)

**Structure**: A two-pane layout — sidebar + map area.

- **Sidebar** (`<aside class="sidebar">`):
  - **Location input** — free-text (e.g. "Pune, India")
  - **Before Date** / **After Date** — date pickers powered by [Flatpickr](https://flatpickr.js.org/) with `Y-m-d` format, displayed as "F j, Y" (human-readable)
  - **Change Legend** — 6 colored swatches mapping land-cover transitions (e.g. Forest → Urban = `#d73027`, Water → Urban = `#4575b9`)
  - **Generate Map button** — triggers the pipeline

- **Map Area** (`<main class="map-container">`):
  - An `<iframe>` that loads `maps/default_map.html` (the Leaflet map viewer)
  - A **loading overlay** (`map-overlay`) with a spinner that shows during processing and hides when the map loads

**Frontend Logic** (`script.js`):

1. On form submit, serializes `{location, before_date, after_date}` → `POST /generate`
2. Shows the loading overlay + spinner on the button
3. On success, stores the response config in `localStorage` under key `geovision_map_config`, adds a `_timestamp` field to ensure freshness, then resets the iframe to `about:blank` and re-navigates it to `maps/default_map.html`. This two-step (store → navigate) lets the iframe read fresh config from `localStorage`.
4. On error, shows an alert and removes the loading state

**Styling** (`style.css`): Apple-inspired design system with CSS variables, `-apple-system` font stack, backdrop blur (`backdrop-filter: blur(20px)`), subtle shadows, and smooth transitions. The `--primary: #0071e3` Apple blue is used throughout. Inputs get a focus ring (`0 0 0 3px rgba(0, 113, 227, 0.2)`) and buttons have a spin animation loader.

---

## 2. Flask Backend (`app.py`)

A lightweight Flask server on port 5000 with three routes:

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Serves `public/index.html` |
| `/check-ee` | GET | Verifies Earth Engine initialization (diagnostic) |
| `/generate` | POST | The main pipeline — accepts location + dates, returns tile URLs |

### `POST /generate` pipeline (the core flow)

1. **Parse input**: `location` (string), `before_date`, `after_date` (YYYY-MM-DD)
2. **Expand date windows**: Each date becomes a **90-day window** (`start → start + 90 days`) via the local `get_window()` helper. This ensures enough Sentinel-2 scenes for stable median composites.
3. **Initialize Earth Engine**: `fetcher.init_ee(EE_PROJECT_ID)` — authenticates and initializes the GEE session
4. **Geocode location**: `fetcher.resolve_location()` uses Nominatim (OpenStreetMap geocoder) to convert "Pune, India" → `(18.5936, 73.7301)`. Includes a swap correction if lat/lon appear inverted.
5. **Define AOI**: `ee.Geometry.Point([lon, lat]).buffer(10000)` — a 10km radius circle around the point
6. **Build Sentinel-2 composites**: `_build_composite()` called twice (before & after) — fetches Sentinel-2 imagery, applies cloud masking, computes median composite
7. **Generate S2 tile URLs**: `image.getMapId({bands:['B4','B3','B2'], max:3000})` creates GEE tile fetcher URLs for before and after layers
8. **Build Dynamic World composites**: `_build_dw_composite()` called twice (before & after) — fetches 9-band probability composites from Dynamic World
9. **Detect changes**: `fetcher.detect_changes(dw1, dw2)` — converts DW to 5-class signatures, then runs the rule engine with confidence and surge gates
10. **Generate change mask tile URL**: `getMapId()` on the change image
11. **Returns JSON**:

```json
{
  "success": true,
  "map_url": "maps/default_map.html",
  "config": {
    "center": [lat, lon],
    "before_tiles": "https://earthengine.googleapis.com/...",
    "after_tiles": "https://earthengine.googleapis.com/...",
    "change_mask_tiles": "https://earthengine.googleapis.com/...",
    "before_label": "Before: 2023-11-01 → 2024-01-30",
    "after_label": "After: 2024-11-01 → 2025-01-30",
    "aoi": { "type": "Polygon", "coordinates": ["..."] }
  }
}
```

All responses have `Cache-Control: no-store` headers (via `@app.after_request`) to prevent stale tile URLs from being cached by the browser.

---

## 3. The Core Engine — `tests/fetch_satellite_image.py`

This is the most complex part. It has **two entry points**: CLI (standalone) and imported by `app.py`. It implements a **Dynamic World probability + rule-based change detection** approach with two anti-noise gates.

### 3a. Data Types & Constants

```python
@dataclass Location: name, lat, lon
@dataclass DateRange: start, end
@dataclass Config: location, buffer_m, timeline1, timeline2, project, output
```

**Constants**:
- `_SCL_CLEAR = {4, 5, 6, 7, 11}` — SCL pixel classes considered clear (vegetation, bare, water, unclassified, snow/ice)
- `_MAX_SCENE_CLOUD_PCT = 20` — discard entire scenes where >20% of pixels are cloudy
- `_CLOUD_PROB_THRESHOLD = 50` — mask per-pixel cloud probability ≥ 50%
- `_MIN_CLASS_CONF = 0.45` — confidence gate: minimum class proportion at both T1 and T2
- `_MIN_PROB_SURGE = 0.25` — surge gate: minimum probability increase in the target class

### 3b. Step 1 — Cloud Filtering & Composite Building

`_build_composite(aoi, date_range, label)`:

1. Queries the **COPERNICUS/S2_SR_HARMONIZED** collection, filtered by AOI + date range
2. Filters scenes with `CLOUDY_PIXEL_PERCENTAGE < 20%` (scene-level gate)
3. Joins with **COPERNICUS/S2_CLOUD_PROBABILITY** collection — attaches per-pixel cloud probability to each scene via `ee.Join.saveFirst()`
4. Masks pixels where `cloud_probability >= 50` (pixel-level gate — cloud shadow/haze removal)
5. Applies **SCL (Scene Classification Layer) masking**: only keeps pixels where SCL ∈ `{4,5,6,7,11}` (vegetation, bare soil, water, unclassified, snow/ice — excludes cloud, shadow, cirrus, saturated)
6. Computes the **median** of all filtered scenes → stable, cloud-free composite
7. Raises `RuntimeError` if zero scenes found (prompts user to widen date range)

**Why median?** Median is robust against outliers — a single cloud-contaminated pixel that leaked through masking won't corrupt the composite. The 90-day window ensures enough scenes for a stable statistical estimate.

### 3c. Step 2 — Geocoding

`resolve_location(query, lat, lon, name)`:

1. If a text query is provided, uses **Nominatim** (OpenStreetMap's free geocoder) via `geopy` to resolve place name → lat/lon
2. If explicit lat/lon are given, uses those directly
3. Includes a **swap correction**: if lat > lon (which is impossible in valid coordinates — lat ∈ [-90, 90], lon ∈ [-180, 180]), it swaps them. This handles a common user error.

### 3d. Step 3 — Dynamic World Probability Compositing

**Dynamic World** is Google's near-real-time LULC dataset. Each pixel has 9 probability bands that sum to 1.0.

`_build_dw_composite(aoi, date_range, label)`:

1. Queries **GOOGLE/DYNAMICWORLD/V1**, filtered by AOI + date range
2. Selects the 9 probability bands: `water, trees, grass, flooded_vegetation, crops, shrub_and_scrub, built, bare, snow_and_ice`
3. Reduces via **median** across all images in the window → per-pixel probability distribution

### 3e. Step 4 — Signature Building (9 → 5 class mapping)

`_dw_to_signature(dw_image)` collapses the 9 Dynamic World bands into a **5-class signature schema**:

| Signature Class | DW Bands Aggregated | Proportion Band |
|---|---|---|
| Forest | trees + shrub_and_scrub | `forest_prop` |
| Urban | built | `urban_prop` |
| Water | water + flooded_vegetation | `water_prop` |
| Bare | bare | `bare_prop` |
| Agriculture | crops + grass | `agri_prop` |

Raw DW probabilities are used **without re-normalization** — this is intentional to avoid inflating marginal/mixed pixels where all classes have low probability.

The class with the **highest proportion** becomes the `signature_label` (argmax). Labels follow the convention: 0=Water, 1=Forest, 3=Bare, 4=Agriculture, 6=Urban.

### 3f. Step 5 — Rule-Based Change Detection

`detect_changes(dw_a, dw_b)` — the anti-noise core with **two gating thresholds**:

1. Convert both DW composites to signature images via `_dw_to_signature()`
2. For each of the **6 approved transitions**, compute a pixel-level mask requiring:
   - `signature_label_a == from_class` AND `signature_label_b == to_class` (label match)
   - `class_proportion >= 0.45` at **both** T1 and T2 (confidence gate)
   - Target class raw DW probability increased by ≥ 0.25 between T1 and T2 (surge gate)
3. Encode matching pixels with a transition code (1–6)
4. Mask out pixels matching no transition (transparent → no change)

**The 6 approved transitions**:

| Code | From → To | Color | Meaning |
|---|---|---|---|
| 1 | Forest → Urban | `#d73027` (red) | Deforestation / urbanization |
| 2 | Bare → Urban | `#fc8d59` (orange) | Land development |
| 3 | Water → Urban | `#4575b9` (blue) | Land reclamation |
| 4 | Water → Bare | `#91bfdb` (light blue) | Drying / drainage |
| 5 | Forest → Bare | `#fee08b` (yellow) | Deforestation / logging |
| 6 | Agriculture → Urban | `#d73027` (dark red) | Farmland urbanization |

**Why two gates?**

- **Confidence gate (0.45)**: Both the "from" class at T1 and the "to" class at T2 must have proportion ≥ 0.45. This prevents flagging transitions in ambiguous/mixed pixels (e.g., a forest edge where proportions are ~0.3 each). Without it, seasonal color differences or composite noise would cause massive spurious change.

- **Surge gate (0.25)**: The target class's raw DW probability must have increased by ≥ 25 percentage points between T1 and T2. This eliminates **seasonal flicker** — e.g., a forest area where the "crops" probability bounces 0.1→0.2 between seasons is not real change. Only sustained, large shifts are flagged.

**Key insight**: The rule engine asks not "Is this Urban?" but "Was this Forest? And is it now Urban? And were we confident both times? And did the urban probability actually surge?" — a much stricter question that dramatically reduces false positives.

### 3g. Visualization Helpers

- `get_change_vis_params()` — returns Earth Engine visualization parameters for the change mask (min=1, max=6, palette from transition colors)
- `build_change_legend()` — generates an HTML legend with colored swatches for each transition type

---

## 4. Map Rendering (`public/maps/default_map.html`)

A Leaflet.js map viewer loaded inside the iframe. Uses Leaflet 1.9.4 from unpkg CDN.

**Initial state**: Shows a centered Esri World Imagery basemap (Pune, India at zoom 11) with an instruction card ("Select a location and date range in the sidebar, then click **Generate Map**...").

**After generation** (`showMap(config)` is called when config is found in `localStorage`):

1. Removes the single default map and the instruction box
2. Creates a **dual-panel split layout** with two map `<div>`s separated by a blue divider (`4px`, `#0071e3`)
3. **Before map** (left panel):
   - Sentinel-2 tile layer (from `before_tiles` URL, full opacity — covers the Esri basemap)
   - Checkbox to toggle S2 layer visibility (`show-before-s2`)
   - Checkbox to toggle change mask overlay (`toggle-mask`)
   - AOI boundary (orange outline, `#ff6b00`, weight 4, no fill)
   - Label showing the before date range
4. **After map** (right panel):
   - Sentinel-2 tile layer (from `after_tiles` URL, full opacity)
   - AOI boundary (orange outline)
   - Change mask layer (when toggled on the left side — rendered at 70% opacity on both maps)
   - Label showing the after date range
5. **Synced navigation**: Moving/zooming one map automatically syncs the other via `map.on('move')` event listeners (`mapBefore.setView(...)` ↔ `mapAfter.setView(...)`)
6. **Fits bounds** to the AOI polygon with 50px padding on both maps

**Change mask overlay**: Created as `L.tileLayer` on both panels but initially not added to either map. Toggled via the "Change Mask" checkbox in the left panel, which adds/removes the mask layer from both maps simultaneously.

**Communication mechanism**: The parent page stores config in `localStorage`, then navigates the iframe to `default_map.html`. The iframe reads `localStorage.getItem('geovision_map_config')` on load, parses it, immediately removes it (`localStorage.removeItem`), and calls `showMap(config)`. This is a simple cross-frame communication pattern — `localStorage` is per-origin shared, so it works without CORS issues.

---

## 5. CLI Mode (standalone `fetch_satellite_image.py`)

The same engine also works as a command-line tool that generates a **single HTML file** using Folium:

```bash
python tests/fetch_satellite_image.py --query "Pune, India" \
  --start1 2023-11-01 --end1 2024-02-28 \
  --start2 2024-11-01 --end2 2025-02-28
```

CLI flags: `--query`, `--lat`, `--lon`, `--start1`, `--end1`, `--start2`, `--end2`, `--buffer`, `--project`, `--output`

This mode:

1. Builds the same composites and runs the same change detection as the web mode
2. Uses the `leaflet-side-by-side` plugin for a **slider comparison** (instead of the dual-map approach in the web UI)
3. Generates a self-contained HTML file (default: `map.html`) that can be opened directly in a browser
4. Includes the change detection overlay, AOI outline, and a floating legend panel
5. Uses Folium for map generation (including custom CSS for the divider handle and slider thumb)

---

## 6. Data Flow Summary

```
User Input (location, dates)
         │
         ▼
  POST /generate (Flask)
         │
         ├── resolve_location(query) → lat/lon (Nominatim)
         ├── AOI = Point(lat,lon).buffer(10km)
         │
         ├── _build_composite(AOI, before_window)
         │     ├── Fetch S2_SR_HARMONIZED
         │     ├── Cloud filter (scene < 20%, pixel < 50%)
         │     ├── SCL mask (keep 4,5,6,7,11)
         │     └── Median composite → tile URL
         │
         ├── _build_composite(AOI, after_window)  ← same pipeline → tile URL
         │
         ├── _build_dw_composite(AOI, before_window) → DW probabilities T1
         ├── _build_dw_composite(AOI, after_window)  → DW probabilities T2
         │
         ├── detect_changes(dw1, dw2)
         │     ├── _dw_to_signature(T1) → 5-class proportions + label
         │     ├── _dw_to_signature(T2) → 5-class proportions + label
         │     └── Rule engine (6 transitions × confidence ≥ 0.45 × surge ≥ 0.25)
         │         → change image → tile URL
         │
         └── Return JSON: {tile URLs, center, AOI, labels}
                 │
                 ▼
         localStorage.setItem(config)
         iframe → default_map.html
                 │
                 ▼
      Dual-panel Leaflet maps
      (synced pan/zoom, S2 toggle, change mask toggle)
```

---

## 7. Key Design Choices & Trade-offs

| Choice | Why | Trade-off |
|---|---|---|
| **Median composite** (not mean) | Robust against cloud shadows, outliers, and missing data | Loss of temporal detail within the 90-day window |
| **90-day window** | Ensures enough scenes for a stable median | Seasonal effects may appear as "change" — the confidence and surge gates help |
| **Dynamic World** (not hand-crafted indices) | Pre-trained ML dataset, 10m resolution, globally consistent | Depends on Google's classification accuracy; 9 classes may not match local land cover perfectly |
| **5-class signature** (not raw 9 DW classes) | Simplifies interpretation; groups similar DW classes (trees+shrub=forest, crops+grass=agriculture) | Loses granularity (flooded vegetation and water are merged) |
| **No re-normalization** of signature proportions | Avoids inflating mixed/marginal pixels where all raw probabilities are low | Proportions don't sum to exactly 1.0, but this is acceptable for the argmax and threshold logic |
| **Confidence gate (0.45)** | Kills false positives from seasonal/illumination differences and ambiguous pixels | May miss real but subtle changes on mixed pixels (e.g., peri-urban transitions) |
| **Surge gate (0.25)** | Eliminates seasonal flicker — only sustained probability shifts are flagged | May miss gradual change where probability increases slowly over time |
| **Rule-based detection** (not ML) | No training data needed, explainable, works globally | Less accurate than trained classifiers; only 6 transition types |
| **localStorage for iframe comms** | Simple, same-origin, no CORS issues | Fragile — if the iframe navigates away, config is lost; limited to same origin; config is consumed once (removed on read) |
| **Dual-map layout** (web UI) | Clean temporal comparison, independent controls per panel | More complex than a slider; no Esri basemap visible beneath S2 layers |
| **No server-side caching** | GEE tile URLs are ephemeral and per-request | Each `/generate` call recomputes everything (10–60 seconds) |
| **Flask debug server** | Simple, no production configuration needed | Not suitable for production deployment (single-threaded, no WSGI) |

---

## 8. Dependencies

### Python (backend)

| Package | Role |
|---|---|
| `earthengine-api` | Google Earth Engine Python API (data fetching, server-side computation, tile URL generation) |
| `geemap` | Earth Engine map visualization helpers (used in CLI mode) |
| `geopy` | Geocoding via Nominatim (place names → coordinates) |
| `flask` | Web server backend (3 routes, serves frontend) |
| `folium` | Map HTML generation (CLI mode — split-panel with side-by-side plugin) |
| `python-dotenv` | Loads `.env` for `EE_PROJECT_ID` |

### Frontend (CDN-loaded)

| Library | Role |
|---|---|
| **Leaflet.js** (1.9.4) | Interactive map rendering (dual-panel layout) |
| **Flatpickr** | Date picker UI component (sidebar) |
| **Esri World Imagery** | Basemap tiles (ArcGIS tile server) |

---

## 9. Environment & Configuration

- **`EE_PROJECT_ID`** — Google Earth Engine project ID (required, loaded via `.env` using `python-dotenv`). A template is provided in `tests/.env.example`.
- Earth Engine authentication is handled by `ee.Authenticate()` which opens a browser OAuth flow on first run. Subsequent runs use cached credentials.
- The Flask server runs on `http://127.0.0.1:5000` with debug mode enabled.
- The `tests/` directory is appended to `sys.path` in `app.py` to import `fetch_satellite_image` as `fetcher`. A graceful fallback prints a warning if the import fails.

---

## 10. Known Gaps & Limitations

- **No async processing** — `/generate` blocks for the full GEE computation (10–60 seconds). No WebSocket or polling-based progress updates.
- **No server-side caching** — each request recomputes composites, signatures, and change detection from scratch.
- **No user accounts / auth** — anyone with the URL can generate maps.
- **No database / result persistence** — no history, no saved comparisons.
- **No error recovery** — if GEE times out or returns no data (zero scenes), the user gets a generic error with no guidance on how to fix it (e.g., widening the date range).
- **`tests/` is misnamed** — `fetch_satellite_image.py` is the core module, not a test suite. There are no automated tests in the project.
- **Flask debug server** — single-threaded, no WSGI, not production-ready.
- **6 transitions only** — the change detection covers 6 specific from→to paths. Bidirectional (regrowth) transitions and agricultural changes (e.g., Agriculture → Bare) are not tracked.