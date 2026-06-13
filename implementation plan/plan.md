# Phase 1: Change Detection MVP

## Objective

Detect where changes occurred between two timestamps.

## Input

* Location
* Start Year
* End Year

Example:

```text
Pune
2020
2026
```

## Architecture

```text
User Input
      ↓
Google Earth Engine
      ↓
Satellite Image Retrieval
      ↓
Preprocessing
      ↓
NDVI Difference
      ↓
Change Mask
      ↓
Visualization
```

## Technologies

### Data Source

* Google Earth Engine

### Processing

* Python
* NumPy
* OpenCV
* Rasterio

## Implementation

### Image Retrieval

Fetch cloud-filtered Sentinel-2 imagery.

Steps:

1. Select Area of Interest (AOI)
2. Select date range
3. Apply cloud filtering
4. Export imagery

### Preprocessing

* Cloud masking
* Image alignment
* Band selection
* Normalization

### Change Detection

Compute NDVI for both years.

NDVI Formula:

```text
NDVI = (NIR - Red) / (NIR + Red)
```

Generate:

```text
NDVI_2020
      -
NDVI_2026
      =
Difference Map
```

Apply thresholding:

```text
Difference Map
      ↓
Binary Mask
      ↓
Changed / Unchanged Pixels
```

## Output

* Before image
* After image
* Change mask
* Changed area percentage

---

# Phase 2: Land Cover Classification

## Objective

Determine what changed.

Instead of:

```text
Change Detected
```

Generate:

```text
Forest → Urban
Water → Urban
Forest → Agriculture
```

## Architecture

```text
Image
      ↓
Land Cover Classification
      ↓
Class Map
      ↓
Change Analysis
```

## Technologies

Dynamic World (I feel good as already pretrained on google's satellite data)

Classes:

* Water
* Trees
* Grass
* Crops
* Built Area
* Bare Ground

Outputs probabilities of each class, may take higher one

### Option 2

SegFormer

### Option 3

Custom CNN

---

# Phase 3: Area Identification

## Objective

Identify actual locations affected.

## Architecture

```text
Change Mask
      ↓
Polygon Extraction
      ↓
Coordinate Mapping
      ↓
Area Identification
```

## Technologies

* GeoPandas
* Shapely
* Folium

## Output

```text
Hinjawadi
Urban Growth: +8%

Wagholi
Urban Growth: +11%

Kharadi
Forest Loss: -3%
```

---

# Phase 4: Analytics Engine

## Objective

Convert raw data into meaningful insights.

## Processing

Calculate:

* Urban growth %
* Forest loss %
* Water body change %
* Total changed area %

## Example Output

```text
Urban area increased from 30% to 42%.

Forest cover decreased by 5%.

Major expansion observed around
Hinjawadi and Wagholi.
```

---

# Phase 5: Dashboard & Reporting

## Objective

Provide an interactive interface.

## Technologies

* Streamlit
* Plotly
* Folium
* Leafmap

## Dashboard Components

### Visualizations

* Before Image
* After Image
* Change Mask
* NDVI Difference Map

### Statistics

* Urban Growth
* Forest Loss
* Water Changes

### Reports

* PDF Export
* JSON Export
