"""Fetch a cloud-filtered Sentinel-2 image from Google Earth Engine
for a given location and display it as an interactive split-panel map.

Setup (one-time):
    pip install -r requirements.txt
    earthengine authenticate
    export EE_PROJECT_ID="your-gee-project-id"

Usage:
    # Run with default location (Pune) and compare default timelines
    python fetch_satellite_image.py

    # Run for a specific location comparing two specific timelines
    python fetch_satellite_image.py --lat 19.076 --lon 72.8777 --start1 2023-01-01 --end1 2023-05-01 --start2 2024-01-01 --end2 2024-05-01 --name Mumbai
"""

import argparse
import os
import sys
from dotenv import load_dotenv

import ee
import geemap
from geopy.geocoders import Nominatim

# Load environment variables
load_dotenv()

DEFAULT_PROJECT = os.getenv("EE_PROJECT_ID")
DEFAULT_LOCATION = {"name": "Pune", "lat": 18.593617, "lon": 73.730133}
DEFAULT_BUFFER_M = 10_000

# Default comparison is last year vs this year
DEFAULT_START1 = "2023-11-01"
DEFAULT_END1 = "2024-02-28"
DEFAULT_START2 = "2024-11-01"
DEFAULT_END2 = "2025-02-28"

# Cloud masking thresholds
CLOUD_PROB_THRESHOLD = 60
SCL_KEEP = [4, 5, 6, 7]


def init_ee(project: str) -> None:
    """Authenticate and initialize the Earth Engine API."""
    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
    except ee.EEException:
        print("First run: authenticating with Google Earth Engine...")
        ee.Authenticate()
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()


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


def resolve_location(query: str, lat: float, lon: float, default_name: str):
    """Resolve a city name/address to coordinates, or validate provided coordinates."""
    if query:
        print(f"🌍 Geocoding location: '{query}'...")
        try:
            geolocator = Nominatim(user_agent="geovision_satellite_fetcher")
            location = geolocator.geocode(query)
            if location:
                print(f"✅ Found: {location.address} (Lat: {location.latitude}, Lon: {location.longitude})")
                return location.latitude, location.longitude, query
            else:
                sys.exit(f"❌ ERROR: Could not find coordinates for '{query}'. Please provide --lat and --lon manually.")
        except Exception as e:
            sys.exit(f"❌ ERROR: Geocoding failed ({e}). Please provide --lat and --lon manually.")

    # Check if they were swapped accidentally
    if abs(lat) > 90 and abs(lon) <= 90:
        print(f"⚠️  WARNING: Latitude ({lat}) is out of bounds (-90 to 90).")
        print(f"🔄 Swapping latitude and longitude assuming they were entered backwards...")
        return lon, lat, default_name
        
    if not (-90 <= lat <= 90):
        sys.exit(f"❌ ERROR: Invalid latitude {lat}. Must be between -90 and 90.")
    if not (-180 <= lon <= 180):
        sys.exit(f"❌ ERROR: Invalid longitude {lon}. Must be between -180 and 180.")
        
    return lat, lon, default_name


def fetch_image(aoi, start: str, end: str, timeline_name: str):
    """Return composite_image for a given AOI and date range."""
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
            f"❌ No Sentinel-2 scenes found with <15% cloud cover for {timeline_name} ({start} to {end}).\n"
            "💡 Try widening the date range or adjusting the location."
        )
    print(f"✅ [{timeline_name}] Found {count} scene(s); generating median composite.")

    image = collection.median().clip(aoi)
    return image


def build_split_map(image1, image2, aoi, name, lat, lon):
    """Build the interactive split-panel geemap with AOI boundary."""
    # Initialize the map with explicit center
    m = geemap.Map(center=[lat, lon], zoom=12)

    # Add high-resolution Google Satellite basemap underneath
    m.add_basemap("SATELLITE")

    # Visualization parameters for Sentinel-2 true-color RGB
    vis_params = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}

    # Generate the split map. Left side = Timeline 1, Right side = Timeline 2
    # This allows smoothly sliding between the two images over the basemap
    try:
        left_layer = geemap.ee_tile_layer(image1, vis_params, "Timeline 1")
        right_layer = geemap.ee_tile_layer(image2, vis_params, "Timeline 2")
        m.split_map(left_layer, right_layer)
    except Exception as e:
        # Fallback if split_map API changes
        print("⚠️  Warning: split_map feature failed, falling back to overlapping layers. Error:", e)
        m.addLayer(image1, vis_params, "Timeline 1", shown=True)
        m.addLayer(image2, vis_params, "Timeline 2", shown=False)

    # --- Draw the precise Area of Interest (AOI) boundary ---
    # We paint the edge of the AOI so the user knows exactly what area is being compared
    aoi_boundary = ee.Image().byte().paint(
        featureCollection=ee.FeatureCollection([ee.Feature(aoi)]),
        color=1,
        width=3
    )
    m.addLayer(
        aoi_boundary, 
        {'palette': ['red']}, 
        f"AOI Boundary ({name})"
    )

    m.addLayerControl()
    return m


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch two cloud-filtered Sentinel-2 images from Google Earth Engine and compare them using a Split-Panel Map.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--query", type=str, help="Name of a city, address, or location to automatically lookup coordinates (e.g., 'Mumbai, India'). Overrides --lat and --lon.")
    parser.add_argument("--lat", type=float, default=DEFAULT_LOCATION["lat"], help="Latitude of the location")
    parser.add_argument("--lon", type=float, default=DEFAULT_LOCATION["lon"], help="Longitude of the location")
    parser.add_argument("--name", default=DEFAULT_LOCATION["name"], help="Name of the location (used for the map title)")
    parser.add_argument("--buffer", type=int, default=DEFAULT_BUFFER_M,
                        help="AOI radius buffer around the point in meters")
    
    # Timeline 1
    parser.add_argument("--start1", default=DEFAULT_START1, help="Timeline 1: Start date (YYYY-MM-DD)")
    parser.add_argument("--end1", default=DEFAULT_END1, help="Timeline 1: End date (YYYY-MM-DD)")
    
    # Timeline 2
    parser.add_argument("--start2", default=DEFAULT_START2, help="Timeline 2: Start date (YYYY-MM-DD)")
    parser.add_argument("--end2", default=DEFAULT_END2, help="Timeline 2: End date (YYYY-MM-DD)")
    
    parser.add_argument("--project", default=DEFAULT_PROJECT, help="Earth Engine Project ID")
    parser.add_argument("--output", default="map.html", help="Output HTML path")
    args = parser.parse_args()

    print("=" * 60)
    print("🛰️  Earth Engine - Temporal Comparison Fetcher")
    print("=" * 60)
    
    args.lat, args.lon, args.name = resolve_location(args.query, args.lat, args.lon, args.name)
    
    print(f"📍 Area of Interest : {args.name} (Lat: {args.lat}, Lon: {args.lon})")
    print(f"📏 AOI Buffer       : {args.buffer} meters radius")
    print(f"📅 Timeline 1       : {args.start1} to {args.end1}")
    print(f"📅 Timeline 2       : {args.start2} to {args.end2}")
    print(f"📁 Output File      : {args.output}")
    print("=" * 60)

    init_ee(args.project)
    
    # Create the Area of Interest
    aoi = ee.Geometry.Point([args.lon, args.lat]).buffer(args.buffer)
    
    print("⏳ Fetching imagery for Timeline 1...")
    image1 = fetch_image(aoi, args.start1, args.end1, "Timeline 1")
    
    print("⏳ Fetching imagery for Timeline 2...")
    image2 = fetch_image(aoi, args.start2, args.end2, "Timeline 2")
    
    print("🗺️  Building interactive split-panel map with AOI boundary...")
    m = build_split_map(image1, image2, aoi, args.name, args.lat, args.lon)
    m.to_html(args.output)
    
    print("=" * 60)
    print(f"✨ SUCCESS! Saved split-panel map to '{args.output}'.")
    print(f"🌐 Open '{args.output}' in your web browser to slide and compare the timelines!")
    print("=" * 60)


if __name__ == "__main__":
    main()
