import os
import csv
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv

load_dotenv()

# ── InfluxDB config ───────────────────────────────────────────────────────────
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN") or os.getenv("INFLUXDB_TOKEN_FILE")
if INFLUXDB_TOKEN and INFLUXDB_TOKEN.startswith("/"):
    # Read token from file
    with open(INFLUXDB_TOKEN, "r") as f:
        INFLUXDB_TOKEN = f.read().strip()
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iot-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "plc_data")

# ── Sensor labels — auto-built from Modbus address config ────────────────────
_MODBUS_START = int(os.getenv("MODBUS_START_ADDRESS", 0))
_MODBUS_COUNT = int(os.getenv("MODBUS_REGISTER_COUNT", 5))
_ICONS = ["sensors", "thermostat", "water_drop", "speed", "analytics"]

_default_labels = [
    {
        "id": f"register_{_MODBUS_START + i}",
        "name": f"Sensor {i + 1}",
        "unit": "",
        "icon": _ICONS[i % len(_ICONS)],
    }
    for i in range(_MODBUS_COUNT)
]
SENSOR_LABELS = json.loads(os.getenv("SENSOR_LABELS", json.dumps(_default_labels)))

# ── Recordings directory ──────────────────────────────────────────────────────
RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", "/app/recordings"))
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Recording state (thread-safe) ────────────────────────────────────────────
_lock = threading.Lock()
_recording_state = {
    "active": False,
    "name": None,
    "started_at": None,
}


# ═══════════════════════════════════════════════════════════════════════════════
#  InfluxDB helpers
# ═══════════════════════════════════════════════════════════════════════════════
def _get_influx_client():
    return InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)


def get_latest_sensor_values():
    """Return latest value for each register field."""
    client = _get_influx_client()
    query_api = client.query_api()
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -1m)
      |> filter(fn: (r) => r["_measurement"] == "plc_registers")
      |> last()
    '''
    try:
        tables = query_api.query(query)
        values = {}
        for table in tables:
            for record in table.records:
                values[record.get_field()] = {
                    "value": record.get_value(),
                    "time": record.get_time().isoformat(),
                }
        return values
    except Exception:
        return {}
    finally:
        client.close()


def get_sensor_history(minutes=5):
    """Return time-series data for the live chart."""
    client = _get_influx_client()
    query_api = client.query_api()
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r["_measurement"] == "plc_registers")
      |> aggregateWindow(every: 1s, fn: mean, createEmpty: false)
      |> sort(columns: ["_time"])
    '''
    try:
        tables = query_api.query(query)
        series = {}
        for table in tables:
            field = table.records[0].get_field() if table.records else None
            if field:
                series[field] = [
                    {"t": r.get_time().isoformat(), "v": r.get_value()}
                    for r in table.records
                ]
        return series
    except Exception:
        return {}
    finally:
        client.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  Recording control
# ═══════════════════════════════════════════════════════════════════════════════
def start_recording(name: str):
    with _lock:
        if _recording_state["active"]:
            raise RuntimeError("Recording already in progress")
        _recording_state["active"] = True
        _recording_state["name"] = name
        _recording_state["started_at"] = datetime.now(timezone.utc).isoformat()


def stop_recording():
    """Stop current recording and export the data range to CSV."""
    with _lock:
        if not _recording_state["active"]:
            raise RuntimeError("No active recording")
        name = _recording_state["name"]
        started_at = _recording_state["started_at"]
        _recording_state["active"] = False
        _recording_state["name"] = None
        _recording_state["started_at"] = None

    stopped_at = datetime.now(timezone.utc).isoformat()
    _export_range_to_csv(name, started_at, stopped_at)
    return {"name": name, "started_at": started_at, "stopped_at": stopped_at}


def get_recording_status():
    with _lock:
        return dict(_recording_state)


def _export_range_to_csv(name: str, start_iso: str, stop_iso: str):
    """Query InfluxDB for the given time range and save as CSV."""
    client = _get_influx_client()
    query_api = client.query_api()
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: {start_iso}, stop: {stop_iso})
      |> filter(fn: (r) => r["_measurement"] == "plc_registers")
      |> sort(columns: ["_time"])
    '''
    try:
        tables = query_api.query(query)
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{ts}.csv"
        filepath = RECORDINGS_DIR / filename

        rows = {}
        for table in tables:
            for record in table.records:
                t = record.get_time().isoformat()
                if t not in rows:
                    rows[t] = {"timestamp": t}
                rows[t][record.get_field()] = record.get_value()

        if rows:
            all_fields = set()
            for r in rows.values():
                all_fields.update(r.keys())
            all_fields.discard("timestamp")
            fieldnames = ["timestamp"] + sorted(all_fields)

            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in sorted(rows.values(), key=lambda x: x["timestamp"]):
                    writer.writerow(row)
    except Exception:
        pass
    finally:
        client.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  File management
# ═══════════════════════════════════════════════════════════════════════════════
def list_recordings():
    """List all CSV files in the recordings directory."""
    files = []
    for p in sorted(RECORDINGS_DIR.glob("*.csv"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = p.stat()
        size_kb = stat.st_size / 1024
        files.append({
            "name": p.name,
            "size": f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB",
            "size_bytes": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return files


def get_recording_filepath(filename: str) -> Path:
    """Return validated path for a recording file."""
    filepath = RECORDINGS_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        raise FileNotFoundError(f"File not found: {filename}")
    if filepath.parent.resolve() != RECORDINGS_DIR.resolve():
        raise ValueError("Invalid path")
    return filepath


def delete_recording(filename: str):
    filepath = get_recording_filepath(filename)
    filepath.unlink()


def rename_recording(old_name: str, new_name: str):
    filepath = get_recording_filepath(old_name)
    safe_new = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in new_name)
    if not safe_new.endswith(".csv"):
        safe_new += ".csv"
    new_path = RECORDINGS_DIR / safe_new
    filepath.rename(new_path)
    return safe_new


def preview_recording(filename: str, max_rows: int = 50):
    """Return first N rows of a CSV file as list of dicts."""
    filepath = get_recording_filepath(filename)
    rows = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(row)
    return {"headers": headers, "rows": rows}
