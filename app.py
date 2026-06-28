"""GeoVision — Flask web server for satellite change detection."""

import logging
import os

import ee
from flask import Flask, request, jsonify, send_from_directory

from geovision import run_pipeline
from geovision.config import EE_PROJECT_ID
from geovision import explain
from geovision import chat

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


@app.route('/chat')
def chat_page():
    return send_from_directory('public', 'chat.html')


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
        location_query = data.get('location')
        before_date = data.get('before_date')
        after_date = data.get('after_date')
        question = data.get('question', '').strip()

        config = run_pipeline(
            location_query=location_query,
            before_date=before_date,
            after_date=after_date,
            project_id=EE_PROJECT_ID,
        )

        result = {
            "success": True,
            "map_url": "maps/default_map.html",
            "config": config,
        }

        if question:
            explanation = explain.generate_explanation(
                location_query=location_query,
                before_date=before_date,
                after_date=after_date,
                config=config,
                question=question,
            )
            result["explanation"] = explanation

        return jsonify(result)
    except Exception as e:
        log.error("Error: %s", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json
    message = data.get('message', '').strip()
    history = data.get('history', [])

    if not message:
        return jsonify({"success": False, "error": "No message provided."})

    try:
        result = chat.process_chat_message(message, history)
        return jsonify(result)
    except Exception as e:
        log.error("Chat error: %s", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


if __name__ == '__main__':
    print("=========================================")
    print(" GeoVision - Starting on http://127.0.0.1:5000")
    print("  Classic UI: http://127.0.0.1:5000/")
    print("  AI Chat:    http://127.0.0.1:5000/chat")
    print("=========================================")
    app.run(debug=True, port=5000)