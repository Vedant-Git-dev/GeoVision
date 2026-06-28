"""GeoVision — Flask web server for satellite change detection."""

import json
import logging
import os
import queue
import threading

import ee
from flask import Flask, request, jsonify, send_from_directory, Response

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
    return send_from_directory('public', 'chat.html')


@app.route('/classic')
def classicview():
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


@app.route('/generate/stream', methods=['POST'])
def generate_stream():
    """Stream pipeline progress as SSE events, returning the result at the end."""
    data = request.json
    location_query = data.get('location')
    before_date = data.get('before_date')
    after_date = data.get('after_date')
    question = data.get('question', '').strip()
    city = data.get('city')

    event_queue = queue.Queue()

    def on_progress(info):
        event_queue.put(('progress', json.dumps(info)))

    def run():
        try:
            config = run_pipeline(
                location_query=location_query,
                before_date=before_date,
                after_date=after_date,
                project_id=EE_PROJECT_ID,
                city=city,
                on_progress=on_progress,
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

            event_queue.put(('result', json.dumps(result)))
        except Exception as e:
            log.error("Stream error: %s", str(e))
            import traceback
            traceback.print_exc()
            event_queue.put(('error', json.dumps({"success": False, "error": str(e)})))
        finally:
            event_queue.put(None)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    def stream():
        while True:
            item = event_queue.get()
            if item is None:
                break
            event_type, payload = item
            yield f"event: {event_type}\ndata: {payload}\n\n"

    return Response(
        stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


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


@app.route('/api/chat/stream', methods=['POST'])
def api_chat_stream():
    """Stream chat response with pipeline progress as SSE events."""
    data = request.json
    message = data.get('message', '').strip()
    history = data.get('history', [])

    if not message:
        def error_stream():
            yield f"event: error\ndata: {json.dumps({'success': False, 'error': 'No message provided.'})}\n\n"
        return Response(error_stream(), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    event_queue = queue.Queue()

    def on_progress(info):
        event_queue.put(('progress', json.dumps(info)))

    def run():
        try:
            result = chat.process_chat_message(message, history, on_progress=on_progress)
            event_queue.put(('result', json.dumps(result)))
        except Exception as e:
            log.error("Chat stream error: %s", str(e))
            import traceback
            traceback.print_exc()
            event_queue.put(('error', json.dumps({"success": False, "error": str(e)})))
        finally:
            event_queue.put(None)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    def stream():
        while True:
            item = event_queue.get()
            if item is None:
                break
            event_type, payload = item
            yield f"event: {event_type}\ndata: {payload}\n\n"

    return Response(
        stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


if __name__ == '__main__':
    print("=========================================")
    print(" GeoVision - Starting on http://127.0.0.1:5000")
    print("  AI Chat:    http://127.0.0.1:5000/")
    print("  Classic UI: http://127.0.0.1:5000/classic")
    print("=========================================")
    app.run(debug=True, port=5000)