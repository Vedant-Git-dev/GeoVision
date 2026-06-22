import logging
log = logging.getLogger(__name__)

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

import ee
from flask import Flask, request, jsonify, send_from_directory

# Load .env file
load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), 'tests'))
try:
    import fetch_satellite_image as fetcher
except ImportError:
    print("Warning: fetch_satellite_image not found.")
    fetcher = None

app = Flask(__name__, static_folder='public', static_url_path='')

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/check-ee')
def check_ee():
    try:
        project = os.getenv("EE_PROJECT_ID")
        log.info("EE_PROJECT_ID: %s", project)
        ee.Initialize(project=project)
        return jsonify({"status": "ok", "project": project})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "project": os.getenv("EE_PROJECT_ID")})

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    try:
        location_query = data.get('location', 'Pune, India')
        before_date = data.get('before_date', '2023-11-01')
        after_date = data.get('after_date', '2024-11-01')

        if fetcher is None:
            return jsonify({"success": False, "error": "GEE modules not installed"})

        def get_window(date_str):
            start = datetime.strptime(date_str, "%Y-%m-%d")
            # Use a decent seasonal window so median composites are stable
            end = start + timedelta(days=90)
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

        start1, end1 = get_window(before_date)
        start2, end2 = get_window(after_date)

        fetcher.init_ee(os.getenv("EE_PROJECT_ID"))

        loc = fetcher.resolve_location(location_query, 18.5936, 73.7301, location_query)
        aoi = ee.Geometry.Point([loc.lon, loc.lat]).buffer(10000)

        log.info("Building composite 1 (%s -> %s)...", start1, end1)
        image1 = fetcher._build_composite(aoi, fetcher.DateRange(start1, end1), "Timeline 1")

        log.info("Building composite 2 (%s -> %s)...", start2, end2)
        image2 = fetcher._build_composite(aoi, fetcher.DateRange(start2, end2), "Timeline 2")

        vis_params = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}
        map_id1 = image1.getMapId(vis_params)
        map_id2 = image2.getMapId(vis_params)
        tile1_url = map_id1["tile_fetcher"].url_format
        tile2_url = map_id2["tile_fetcher"].url_format

        log.info("Detecting changes via neighborhood signatures...")
        change_img = fetcher.detect_changes(image1, image2)
        change_vis = fetcher.get_change_vis_params()
        change_map_id = change_img.getMapId(change_vis)
        change_mask_url = change_map_id["tile_fetcher"].url_format

        log.info("Generated map config for: %s", location_query)

        return jsonify({
            "success": True,
            "map_url": "maps/default_map.html",
            "config": {
                "center": [loc.lat, loc.lon],
                "before_tiles": tile1_url,
                "after_tiles": tile2_url,
                "change_mask_tiles": change_mask_url,
                "before_label": before_date,
                "after_label": after_date,
                "aoi": aoi.getInfo()
            }
        })
    except Exception as e:
        log.error("Error: %s", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    print("=========================================")
    print(" GeoVision - Starting on http://127.0.0.1:5000")
    print("=========================================")
    app.run(debug=True, port=5000)