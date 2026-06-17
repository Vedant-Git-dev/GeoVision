"""Fetch a cloud-filtered Sentinel-2 image from Google Earth Engine
for a given location and display it as an interactive map.

Setup (one-time):
    pip install -r requirements.txt
    earthengine authenticate
    export EE_PROJECT_ID="your-gee-project-id"

Usage:
    python fetch_satellite_image.py
    python fetch_satellite_image.py --output pune.html
    python fetch_satellite_image.py --lat 19.076 --lon 72.8777 --name Mumbai --output mumbai.html
"""

import argparse
import os
import sys

import ee
import geemap

DEFAULT_PROJECT = "geovision-499614"
DEFAULT_LOCATION = {"name": "Pune", "lat": 18.593617, "lon": 73.730133}
DEFAULT_BUFFER_M = 10_000
DEFAULT_START = "2024-11-01"
DEFAULT_END = "2025-02-28"  # post-monsoon window: low cloud cover in India

# Cloud masking thresholds
CLOUD_PROB_THRESHOLD = 60
SCL_KEEP = [4, 5, 6, 7]  # vegetation, bare/soil, water, low-prob cloud


def init_ee(project: str) -> None:
    """Authenticate and initialize the Earth Engine API."""
    try:
        ee.Initialize(project=project)
    except ee.EEException:
        print("First run: authenticating with Google Earth Engine...")
        ee.Authenticate()
        ee.Initialize(project=project)


def mask_s2_sr(image):
    """Mask clouds and shadows using the SCL (Scene Classification) band."""
    scl = image.select("SCL")
    mask = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(7))
    return image.updateMask(mask).copyProperties(image, ["system:index"])


def add_cloud_bands(image):
    """Add cloud probability band from s2cloudless collection."""
    cloud_prob = ee.Image(image.get("cloud_prob")).select("probability")
    is_cloud = cloud_prob.gt(CLOUD_PROB_THRESHOLD)
    return image.addBands(ee.Image(cloud_prob).rename("cloud_prob")).addBands(
        is_cloud.rename("clouds")
    )


def mask_clouds(image):
    """Mask pixels where s2cloudless probability > threshold."""
    clouds = image.select("clouds")
    return image.updateMask(clouds.Not())


def apply_s2cloudless(collection, aoi, start, end):
    """Join a Sentinel-2 SR collection with its s2cloudless counterpart and mask clouds."""
    s2_cloudless = (
        ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY")
        .filterBounds(aoi)
        .filterDate(start, end)
    )

    # Join by system:index
    def add_cloud_band(img):
        cloud_img = s2_cloudless.filter(ee.Filter.eq("system:index", img.get("system:index"))).first()
        return img.set("cloud_prob", cloud_img)

    joined = collection.map(add_cloud_band)
    return joined.map(add_cloud_bands).map(mask_clouds)


def fetch_image(lat: float, lon: float, start: str, end: str, buffer_m: int):
    """Return (aoi, composite_image) for a point and date range."""
    aoi = ee.Geometry.Point([lon, lat]).buffer(buffer_m)

    # Build the SR collection
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15))
    )

    # Apply s2cloudless masking
    collection = apply_s2cloudless(collection, aoi, start, end)

    # Apply SCL masking
    collection = collection.map(mask_s2_sr)

    count = collection.size().getInfo()
    if count == 0:
        sys.exit(
            f"No Sentinel-2 scenes with <15% cloud in {start} -> {end}. "
            "Widen the date range or raise the cloud threshold."
        )
    print(f"Found {count} scene(s); using median composite.")

    image = collection.median().clip(aoi)
    return aoi, image


def add_indices(image):
    """Add NDVI, NDBI, and NDWI bands to an image."""
    # NDVI = (NIR - Red) / (NIR + Red)
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

    # NDWI = (Green - NIR) / (Green + NIR)
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")

    # NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)
    ndbi = image.normalizedDifference(["B11", "B8"]).rename("NDBI")

    return image.addBands([ndvi, ndwi, ndbi])


def build_map(image, aoi, name: str) -> geemap.Map:
    """Build a folium-backed map centered on the AOI with the RGB composite."""
    m = geemap.Map()
    m.centerObject(aoi, 11)

    # Add RGB composite
    m.addLayer(
        image,
        {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000},
        f"Sentinel-2 RGB ({name})",
    )

    # Add Indices
    ndvi = image.select("NDVI")
    ndwi = image.select("NDWI")
    ndbi = image.select("NDBI")

    m.addLayer(ndvi, {"min": -0.2, "max": 0.8, "palette": ["blue", "white", "green"]}, "NDVI")
    m.addLayer(ndwi, {"min": -0.5, "max": 0.5, "palette": ["brown", "white", "blue"]}, "NDWI")
    m.addLayer(ndbi, {"min": -0.5, "max": 0.5, "palette": ["blue", "white", "red"]}, "NDBI")

    return m


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lat", type=float, default=DEFAULT_LOCATION["lat"])
    parser.add_argument("--lon", type=float, default=DEFAULT_LOCATION["lon"])
    parser.add_argument("--name", default=DEFAULT_LOCATION["name"])
    parser.add_argument("--buffer", type=int, default=DEFAULT_BUFFER_M,
                        help="AOI buffer around the point in meters")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--output", default="map.html",
                        help="Output HTML path (default: map.html)")
    args = parser.parse_args()

    init_ee(args.project)
    aoi, image = fetch_image(args.lat, args.lon, args.start, args.end, args.buffer)
    image = add_indices(image)
    m = build_map(image, aoi, args.name)
    m.to_html(args.output)
    print(f"Saved map to {args.output} (open it in a browser).")


if __name__ == "__main__":
    main()
