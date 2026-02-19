import os
import logging
from flask import Flask, render_template, request, jsonify, send_file
from control import (
    SENSOR_LABELS,
    get_latest_sensor_values,
    get_sensor_history,
    start_recording,
    stop_recording,
    get_recording_status,
    list_recordings,
    get_recording_filepath,
    delete_recording,
    rename_recording,
    preview_recording,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)


# ── Pages ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", sensors=SENSOR_LABELS)


# ── Sensor data API ──────────────────────────────────────────────────────────
@app.route("/api/sensors", methods=["GET"])
def api_sensors():
    try:
        values = get_latest_sensor_values()
        return jsonify({"ok": True, "sensors": SENSOR_LABELS, "values": values})
    except Exception as e:
        log.exception("sensor fetch error")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/history", methods=["GET"])
def api_history():
    try:
        minutes = int(request.args.get("minutes", 5))
        series = get_sensor_history(minutes)
        return jsonify({"ok": True, "series": series})
    except Exception as e:
        log.exception("history fetch error")
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Recording API ────────────────────────────────────────────────────────────
@app.route("/api/recording/status", methods=["GET"])
def api_recording_status():
    return jsonify({"ok": True, **get_recording_status()})


@app.route("/api/recording/start", methods=["POST"])
def api_recording_start():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Recording name is required"}), 400
    try:
        start_recording(name)
        return jsonify({"ok": True, "message": f"Recording '{name}' started"})
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 409


@app.route("/api/recording/stop", methods=["POST"])
def api_recording_stop():
    try:
        info = stop_recording()
        return jsonify({"ok": True, "message": "Recording stopped and saved", **info})
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 409


# ── File management API ──────────────────────────────────────────────────────
@app.route("/api/files", methods=["GET"])
def api_files():
    return jsonify({"ok": True, "files": list_recordings()})


@app.route("/api/files/<filename>/download", methods=["GET"])
def api_file_download(filename):
    try:
        path = get_recording_filepath(filename)
        return send_file(path, as_attachment=True, download_name=filename)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "File not found"}), 404


@app.route("/api/files/<filename>/preview", methods=["GET"])
def api_file_preview(filename):
    try:
        data = preview_recording(filename)
        return jsonify({"ok": True, **data})
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "File not found"}), 404


@app.route("/api/files/<filename>/delete", methods=["DELETE"])
def api_file_delete(filename):
    try:
        delete_recording(filename)
        return jsonify({"ok": True, "message": f"Deleted {filename}"})
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "File not found"}), 404


@app.route("/api/files/<filename>/rename", methods=["POST"])
def api_file_rename(filename):
    data = request.get_json(silent=True) or {}
    new_name = (data.get("new_name") or "").strip()
    if not new_name:
        return jsonify({"ok": False, "error": "New name is required"}), 400
    try:
        actual = rename_recording(filename, new_name)
        return jsonify({"ok": True, "new_name": actual})
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "File not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
