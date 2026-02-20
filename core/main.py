import os
import time
import queue
import threading
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from pyModbusTCP.client import ModbusClient
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Modbus config ──────────────────────────────────────────────────────────────
MODBUS_HOST = os.getenv("MODBUS_HOST", "host.docker.internal")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", 502))
MODBUS_UNIT_ID = int(os.getenv("MODBUS_UNIT_ID", 1))
MODBUS_START_ADDRESS = int(os.getenv("MODBUS_START_ADDRESS", 0))
MODBUS_REGISTER_COUNT = int(os.getenv("MODBUS_REGISTER_COUNT", 5))
POLL_INTERVAL_MS = int(os.getenv("POLL_INTERVAL_MS", 20))

# ── InfluxDB config ────────────────────────────────────────────────────────────
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN") or os.getenv("INFLUXDB_TOKEN_FILE")
if INFLUXDB_TOKEN and INFLUXDB_TOKEN.startswith("/"):
    # Read token from file
    with open(INFLUXDB_TOKEN, "r") as f:
        INFLUXDB_TOKEN = f.read().strip()
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iot-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "plc_data")

# ── Batch writer config ────────────────────────────────────────────────────────
BATCH_FLUSH_INTERVAL_SEC = float(os.getenv("BATCH_FLUSH_INTERVAL_SEC", 1.0))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 500))

# ── Shared queue between threads ───────────────────────────────────────────────
data_queue: queue.Queue = queue.Queue(maxsize=10000)


# ══════════════════════════════════════════════════════════════════════════════
# Thread 1 — Modbus Reader
# ══════════════════════════════════════════════════════════════════════════════
def modbus_reader():
    poll_interval_sec = POLL_INTERVAL_MS / 1000.0
    client = ModbusClient(
        host=MODBUS_HOST,
        port=MODBUS_PORT,
        unit_id=MODBUS_UNIT_ID,
        auto_open=True,
        auto_close=False,
        timeout=1.0,
    )

    log.info(
        "ModbusReader started — host=%s port=%d unit=%d "
        "start_addr=%d count=%d poll=%dms",
        MODBUS_HOST, MODBUS_PORT, MODBUS_UNIT_ID,
        MODBUS_START_ADDRESS, MODBUS_REGISTER_COUNT, POLL_INTERVAL_MS,
    )

    consecutive_errors = 0

    while True:
        loop_start = time.perf_counter()

        regs = client.read_holding_registers(MODBUS_START_ADDRESS, MODBUS_REGISTER_COUNT)

        if regs is None:
            consecutive_errors += 1
            if consecutive_errors % 10 == 1:
                log.warning(
                    "Modbus read failed (attempt %d) — host=%s port=%d",
                    consecutive_errors, MODBUS_HOST, MODBUS_PORT,
                )
            time.sleep(min(consecutive_errors * 0.1, 5.0))
            continue

        consecutive_errors = 0
        ts = datetime.now(timezone.utc)

        try:
            data_queue.put_nowait({"ts": ts, "registers": regs})
        except queue.Full:
            log.warning("Queue is full — dropping sample (queue_size=%d)", data_queue.qsize())

        elapsed = time.perf_counter() - loop_start
        sleep_time = poll_interval_sec - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)


# ══════════════════════════════════════════════════════════════════════════════
# Thread 2 — InfluxDB Batch Writer
# ══════════════════════════════════════════════════════════════════════════════
def influx_batch_writer():
    influx_client = InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
    )
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    log.info(
        "InfluxBatchWriter started — url=%s org=%s bucket=%s "
        "flush_interval=%.1fs batch_size=%d",
        INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET,
        BATCH_FLUSH_INTERVAL_SEC, BATCH_SIZE,
    )

    buffer = []
    last_flush = time.monotonic()
    total_written = 0

    while True:
        # Drain queue into buffer (non-blocking)
        try:
            while True:
                item = data_queue.get_nowait()
                buffer.append(item)
                data_queue.task_done()
        except queue.Empty:
            pass

        now = time.monotonic()
        should_flush = (
            len(buffer) >= BATCH_SIZE
            or (now - last_flush) >= BATCH_FLUSH_INTERVAL_SEC
        )

        if should_flush and buffer:
            points = []
            for item in buffer:
                ts = item["ts"]
                regs = item["registers"]
                p = Point("plc_registers") \
                    .time(ts, WritePrecision.NS)
                for i, val in enumerate(regs):
                    p = p.field(f"register_{MODBUS_START_ADDRESS + i}", val)
                points.append(p)

            try:
                write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=points)
                total_written += len(points)
                log.info(
                    "Flushed %d points to InfluxDB (total=%d, queue_size=%d)",
                    len(points), total_written, data_queue.qsize(),
                )
            except Exception as exc:
                log.error("InfluxDB write error: %s", exc)

            buffer.clear()
            last_flush = time.monotonic()

        time.sleep(0.01)


# ══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log.info("=== Modbus TCP Data Logger starting ===")

    reader_thread = threading.Thread(
        target=modbus_reader,
        name="ModbusReader",
        daemon=True,
    )
    writer_thread = threading.Thread(
        target=influx_batch_writer,
        name="InfluxBatchWriter",
        daemon=True,
    )

    reader_thread.start()
    writer_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutdown requested — exiting.")
