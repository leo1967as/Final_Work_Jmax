# High-Speed Modbus TCP Data Logger & Web Dashboard

อ่านค่า Holding Registers จาก PLC ผ่าน Modbus TCP ด้วยความเร็วสูง (20ms/cycle) บันทึกลง InfluxDB v2 และแสดงผลบน **Flask Web UI** พร้อม Live Chart และ Grafana Dashboard

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
  ┌─────────────────────────────────────────────────────────────────────┐
  │                     Web Services                                    │
  │  Flask Web UI :8080  ←→  Grafana :3000  ←→  InfluxDB :8086          │
  └─────────────────────────────────────────────────────────────────────┘
```

## Quick Start (Windows)

```powershell
# 1. รัน Modbus Simulator บน Windows (ModRSsim2, port 502)

# 2. รัน Docker Compose
docker compose up -d

# 3. เปิด Web UI
# http://localhost:8080  (Live Sensor Dashboard)

# 4. Grafana (optional)
# http://localhost:3000  (admin / admin)
```

## 🚀 Deploy บน Ubuntu 20.04 (SSH เท่านั้น)

### 1️⃣ ติดตั้ง Docker + Compose
```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repo
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
```

### 2️⃣ ให้ user ใช้ docker ได้โดยไม่ต้อง sudo
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### 3️⃣ Clone และรัน
```bash
git clone https://github.com/<username>/<repo>.git
cd <repo>
cp .env.example .env && nano .env
docker compose up -d --build
```

### 4️⃣ เช็คสถานะ
```bash
docker ps
docker logs web-ui --tail 10
```

### 5️⃣ เข้าใช้งานจากเครื่องอื่น
เปิด browser ที่เครื่องอื่น:
```
http://<IP-ของ-Ubuntu>:8080
```

---

## 📁 File Structure

```
Final_Work/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env                          ← แก้ค่า IP / Token ที่นี่
├── .gitignore
├── core/
│   ├── main.py                    ← Modbus Logger (2 Threads)
│   ├── control.py                 ← Recording & File Management
│   ├── web_ui.py                  ← Flask App + API
│   └── templates/
│       └── index.html            ← Web UI (Live Chart + File Manager)
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

## ⚙️ Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `MODBUS_HOST` | `host.docker.internal` | IP ของ PLC หรือ Simulator |
| `MODBUS_PORT` | `502` | Modbus TCP Port |
| `MODBUS_START_ADDRESS` | `210` | Starting Holding Register Address |
| `MODBUS_REGISTER_COUNT` | `5` | จำนวน Register ที่อ่านต่อรอบ |
| `POLL_INTERVAL_MS` | `20` | ความเร็วในการอ่าน (มิลลิวินาที) |
| `BATCH_SIZE` | `500` | จำนวน records ต่อ batch write |
| `BATCH_FLUSH_INTERVAL_SEC` | `1` | Flush ทุกกี่วินาที |
| `RECORDINGS_DIR` | `/app/recordings` | Path สำหรับบันทึก CSV |

## 🌐 Ports

| Service | Port | URL |
|---------|------|-----|
| Flask Web UI | 8080 | http://<IP>:8080 |
| Grafana | 3000 | http://<IP>:3000 |
| InfluxDB | 8086 | http://<IP>:8086 |

## 🎯 Web UI Features

- **Monitor Tab**: 5 Sensor cards, live telemetry chart (1m/5m/15m)
- **Recording Controls**: Start/Stop with custom naming, CSV export
- **File Management**: List, preview, rename, delete, download recordings
- **Click Sensor Card**: Opens individual sensor graph modal (1m/5m/15m/1h)

## 📱 Deploy บน Raspberry Pi 4

```bash
scp -r ./Final_Work pi@<PI_IP>:/home/pi/
ssh pi@<PI_IP>
cd /home/pi/Final_Work
# แก้ MODBUS_HOST ใน .env ให้เป็น IP จริงของ PLC
docker compose up -d
```

## 📚 คู่มือเพิ่มเติม

ดู [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) สำหรับ:
- วิธีติดตั้ง Modbus Simulator
- วิธีตั้งค่า Grafana
- วิธี Export CSV
- Troubleshooting
