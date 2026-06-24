"""GeoVision — Flask web server for satellite change detection."""

import logging
import os

import ee
from flask import Flask, request, jsonify, send_from_directory

from geovision import run_pipeline
from geovision.config import EE_PROJECT_ID

log = logging.getLogger(__name__)

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
        log.info("EE_PROJECT_ID: %s", EE_PROJECT_ID)
        ee.Initialize(project=EE_PROJECT_ID)
        return jsonify({"status": "ok", "project": EE_PROJECT_ID})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "project": EE_PROJECT_ID})


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    try:
        config = run_pipeline(
            location_query=data.get('location'),
            before_date=data.get('before_date'),
            after_date=data.get('after_date'),
            project_id=EE_PROJECT_ID,
        )
        return jsonify({"success": True, "map_url": "maps/default_map.html", "config": config})
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
