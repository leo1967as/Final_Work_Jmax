# High-Speed Modbus TCP Data Logger & Local Web Dashboard

อ่านค่า Holding Registers จาก PLC ผ่าน Modbus TCP ด้วยความเร็วสูง (20ms/cycle) บันทึกลง InfluxDB v2 และแสดงผลบน Grafana Dashboard พร้อม Export CSV

## Architecture

```
[PLC / Modbus Simulator]
        │ 20ms polling
        ▼
  Thread 1: ModbusReader  ──→  queue.Queue  ──→  Thread 2: InfluxBatchWriter
                                                          │ batch 500 records / 1s
                                                          ▼
                                                    InfluxDB v2
                                                          │
                                                          ▼
                                                  Grafana :3000
```

## Quick Start

```powershell
# 1. รัน Modbus Simulator บน Windows (ModRSsim2, port 502)

# 2. รัน Docker Compose
docker compose up -d

# 3. เปิด Grafana
# http://localhost:3000  (admin / admin)
```

## File Structure

```
Final_Work/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env                          ← แก้ค่า IP / Token ที่นี่
├── .gitignore
├── core/
│   └── main.py                   ← Python Logger (2 Threads)
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── influxdb.yml      ← Auto-connect InfluxDB
│       └── dashboards/
│           ├── dashboard.yml
│           └── plc_dashboard.json ← Pre-built Dashboard
└── docs/
    └── SETUP_GUIDE.md            ← คู่มือครบถ้วน
```

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `MODBUS_HOST` | `host.docker.internal` | IP ของ PLC หรือ Simulator |
| `MODBUS_PORT` | `502` | Modbus TCP Port |
| `MODBUS_START_ADDRESS` | `0` | Starting Holding Register Address |
| `MODBUS_REGISTER_COUNT` | `5` | จำนวน Register ที่อ่านต่อรอบ |
| `POLL_INTERVAL_MS` | `20` | ความเร็วในการอ่าน (มิลลิวินาที) |
| `BATCH_SIZE` | `500` | จำนวน records ต่อ batch write |
| `BATCH_FLUSH_INTERVAL_SEC` | `1` | Flush ทุกกี่วินาที |

## Ports

| Service | Port | URL |
|---------|------|-----|
| Grafana | 3000 | http://localhost:3000 |
| InfluxDB | 8086 | http://localhost:8086 |

## Deploy บน Raspberry Pi 4

```bash
scp -r ./Final_Work pi@<PI_IP>:/home/pi/
ssh pi@<PI_IP>
cd /home/pi/Final_Work
# แก้ MODBUS_HOST ใน .env ให้เป็น IP จริงของ PLC
docker compose up -d
```

## คู่มือเพิ่มเติม

ดู [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) สำหรับ:
- วิธีติดตั้ง Modbus Simulator
- วิธีตั้งค่า Grafana
- วิธี Export CSV
- Troubleshooting
