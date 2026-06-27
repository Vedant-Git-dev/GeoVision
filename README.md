# GeoVision

GeoVision is a web application that classifies land cover from satellite imagery and identifies how it transitioned between two points in time. You pick a place and choose two dates, and it tells you what kind of land was there before, what kind of land is there now, and which specific transitions occurred between them. A forest that became buildings, a water body that dried out, or a city that got greener are all mapped and quantified. It runs on Google Earth Engine, so all computation happens server side and you never have to download terabytes of imagery yourself.

Instead of computing hand-crafted spectral indices to classify land cover, GeoVision uses Google Dynamic World, a globally consistent deep learning dataset that provides per-pixel class probabilities at 10 meter resolution. This means the classification is already trained and calibrated across the entire planet, so you get reliable labels without needing training data, model training, or threshold tweaking for each region.

The core idea is a temporal comparison. Take two snapshots in time, classify what kind of land cover each pixel represents using Google Dynamic World, then flag pixels where the cover actually shifted from one class to another. What makes GeoVision different from a naive pixel differencing approach is a three gate filter that kills false positives from seasonal variation, cloud shadows, and classification noise.

## How It Works

You enter a location and two dates in the sidebar. The backend does the rest.

1. Your place name gets geocoded into coordinates via OpenStreetMap
2. The official district boundary is fetched from FAO GAUL (UN-recognized administrative boundaries at Level 2) via Earth Engine — if no district is found, it falls back to a 10 km buffer
3. Major cities and towns within the district are discovered via OSMnx and displayed as labeled markers on the map
4. Each date is expanded into a 90 day window so there are enough satellite scenes for a stable composite
4. Sentinel 2 imagery is fetched for both windows, clouds are stripped out using scene level and pixel level filters plus the Scene Classification Layer, and a cloud free median composite is built for each timeline
5. Google Dynamic World probability bands are fetched for the same windows and reduced to median composites
6. The 9 class Dynamic World probabilities are mapped into a 5 class signature schema (water, forest, bare land, agriculture, urban) with raw proportions kept as is to avoid inflating ambiguous pixels
7. A rule engine runs over 6 approved transitions with three gates per pixel:

   * **Confidence gate**: the from class at T1 and the to class at T2 must both have proportion at or above 0.50
   * **Surge gate**: the raw probability of the target class must have increased by at least 0.25 between timelines
   * **Spectral gate**: transitions to forest are cross checked against NDVI and transitions to water are cross checked against NDWI from the Sentinel 2 composite, so shadow induced false water and seasonal greenup get rejected

8. Land cover statistics are computed as per class pixel counts converted to percentages, with delta between timelines
9. Everything comes back as tile URLs that a Leaflet map renders in a dual panel view

The result is a split screen map where the left panel shows the before image, the right shows the after image, and a color coded transition overlay can be toggled on. Panning and zooming stay synced between both panels.

## Tech Stack

**Backend**: Python, Flask, Google Earth Engine Python API, geopy (Nominatim geocoding), osmnx (settlement discovery), shapely (geometry conversion), python-dotenv

**Frontend**: Vanilla HTML/CSS/JS, Leaflet.js for maps, Flatpickr for date picking, Esri World Imagery basemap

**Data sources**: Copernicus Sentinel 2 SR Harmonized (optical imagery), Copernicus S2 Cloud Probability, Google Dynamic World V1 (land cover probabilities), FAO GAUL 2015 Level 2 (official district boundaries), OpenStreetMap (settlement names and locations)

## Project Structure

```
geovision/
  __init__.py         package entry, exposes run_pipeline
  config.py           all constants and thresholds in one place
  types.py            Location and DateRange dataclasses
  ee_init.py          Earth Engine authentication
  geocode.py          place name to coordinates
  boundary.py         FAO GAUL district boundary lookup
  settlements.py      OSMnx settlement discovery (cities and towns)
  composite.py        Sentinel 2 cloud masking and median compositing
  dynamic_world.py    Dynamic World probability compositing
  signature.py        9 band to 5 class mapping with dominance logic
  spectral.py         NDVI and NDWI from Sentinel 2
  changes.py          rule based transition detection engine
  stats.py            per class land cover area statistics
  pipeline.py         orchestrates the full pipeline

public/
  index.html          sidebar with controls, map iframe, legends
  style.css           Apple inspired design system
  script.js           form handling, API calls, iframe communication

app.py                Flask server, three routes
```

## Getting Started

You need a Google Earth Engine account with a cloud project enabled.

1. Clone the repository
2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file from the example and set your Earth Engine project ID:

```bash
cp .env.example .env
# edit .env and add EE_PROJECT_ID=your-project-id
```

4. Run the server:

```bash
python app.py
```

5. Open `http://127.0.0.1:5000` in your browser

On first run, Earth Engine will open a browser tab for OAuth authentication. After that, credentials are cached.

## The Six Transitions

The detection engine tracks these specific land cover shifts:

| Transition | Color | What It Catches |
|---|---|---|
| Forest to Urban | red | deforestation and urbanization |
| Water to Urban | blue | land reclamation from water bodies |
| Forest to Water | sage | flooding or reservoir expansion |
| Urban to Forest | teal | reforestation and greening |
| Urban to Water | cyan | inundation or subsidence |
| Water to Forest | steel blue | wetland establishment or drainage |

These are not all possible transitions. They are the ones most useful to track and most reliable to detect given the noise characteristics of satellite data. Adding more transitions is straightforward in `config.py` but each one needs careful threshold tuning.

## Architecture

The architecture follows a clear pipeline pattern. The Flask server is thin, just three routes. All logic lives in the `geovision` package where each module owns one step of the pipeline. Configuration is centralized so thresholds can be tuned without touching logic code. The frontend is deliberately simple with no build step and no framework, just a Leaflet map inside an iframe that reads tile URLs from localStorage.

Three gates make the transition detection reliable. The confidence gate says both endpoints must be decisive, we do not flag a transition if we were not sure about either class label. The surge gate says the target class must have actually grown, which eliminates seasonal flicker where probabilities bounce around without real change. The spectral gate cross checks Dynamic World labels against independent Sentinel 2 spectral indices, catching cases where the classifier mislabels shadows as water or dry grassland as urban.

## Roadmap

### Phase 1: Change Detection [Complete]

The baseline. Given two satellite images of the same place from different times, detect whether change happened. The output is a change mask highlighting modified regions and the percentage of area that shifted.

### Phase 2: Land Cover Classification [Current]

Understanding what actually changed. The system classifies land into five categories (water, forest, bare land, agriculture, urban) for both timelines, quantifies how each category shifted, and renders a color coded transition visualization. This phase introduced Dynamic World integration, the five class signature schema, the three gate detection engine, the spectral cross validation layer, and the land cover statistics panel.

### Phase 3: Geographic Change Analysis [Planned]

Where did it change the most. Break the region into sub areas and rank them by change intensity. The output will be a ranked list of neighborhoods and a heatmap showing which pockets experienced rapid development, deforestation, or other significant transformations.

### Phase 4: AI Satellite Intelligence Assistant [Planned]

An LLM powered analysis layer that converts raw satellite data into human readable reports. Ask a question like "How did Pune change between 2020 and 2026?" and get a detailed narrative with visual change maps, key statistics, areas of major transformation, and environmental and urban development insights.

## Known Limitations

Processing is synchronous. A `/generate` call blocks for 10 to 60 seconds while Earth Engine computes. There is no progress feedback beyond the spinner.

There is no server side caching. Every request recomputes everything from scratch.

The detection covers six transitions. Agricultural changes, bare land shifts, and bidirectional regrowth beyond the six tracked paths are not detected.

Flask runs in debug mode with a single thread. Not production ready.

Only one user at a time since there is no authentication or session management.

The 90 day window trades temporal precision for composite stability. Short events within a window are averaged out.
