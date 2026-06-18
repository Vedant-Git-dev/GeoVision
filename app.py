import os
import sys
import uuid
from flask import Flask, request, jsonify, send_from_directory

# Add tests directory to path so we can import fetch_satellite_image
sys.path.append(os.path.join(os.path.dirname(__file__), 'tests'))
try:
    import fetch_satellite_image as fetcher
    import ee
except ImportError:
    print("Warning: Missing required modules. Did you install requirements.txt?")
    fetcher = None
    ee = None

app = Flask(__name__, static_folder='public', static_url_path='')

@app.after_request
def add_header(response):
    # Prevent browser caching during development so UI updates appear immediately
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/generate', methods=['POST'])
def generate():
    if fetcher is None or ee is None:
        return jsonify({"success": False, "error": "Required python modules (ee, geemap) are not installed."})

    data = request.json
    try:
        from datetime import datetime, timedelta
        
        query = data.get('location', 'Pune, India')
        before_date = data.get('before_date', '2023-11-01')
        after_date = data.get('after_date', '2024-11-01')

        # Create a 180-day window from the selected dates to ensure cloud-free composites
        def get_window(date_str):
            start = datetime.strptime(date_str, "%Y-%m-%d")
            end = start + timedelta(days=180)
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

        start1, end1 = get_window(before_date)
        start2, end2 = get_window(after_date)

        # Generate a unique HTML file for each request in public/maps
        output_filename = f"map_{uuid.uuid4().hex[:8]}.html"
        output_path = os.path.join(os.path.dirname(__file__), 'public', 'maps', output_filename)

        cfg = fetcher.Config(
            location=fetcher.resolve_location(query, 18.5936, 73.7301, query),
            buffer_m=10000,
            timeline1=fetcher.DateRange(start1, end1),
            timeline2=fetcher.DateRange(start2, end2),
            project=os.getenv("EE_PROJECT_ID"),
            output=output_path
        )
        
        # Initialize Earth Engine
        fetcher.init_ee(cfg.project)
        
        loc = cfg.location
        aoi = ee.Geometry.Point([loc.lon, loc.lat]).buffer(cfg.buffer_m)
        
        image1 = fetcher._build_composite(aoi, cfg.timeline1, "Timeline 1")
        image2 = fetcher._build_composite(aoi, cfg.timeline2, "Timeline 2")
        
        m = fetcher.build_split_map(image1, image2, aoi, cfg)
        m.save(cfg.output)
        
        return jsonify({"success": True, "map_url": f"maps/{output_filename}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    print("=========================================")
    print(" GeoVision Local Server ")
    print(" Starting on http://127.0.0.1:5000 ")
    print("=========================================")
    app.run(debug=True, port=5000)
