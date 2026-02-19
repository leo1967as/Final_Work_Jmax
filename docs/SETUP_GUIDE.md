# Setup Guide — Modbus TCP Data Logger

## Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Docker Desktop | Latest | https://www.docker.com/products/docker-desktop/ |
| Modbus Simulator | Any | See Step 1 below |

---

## Step 1 — ติดตั้ง Modbus Simulator บน Windows

ใช้ **ModRSsim2** (ฟรี, ไม่ต้องติดตั้ง):

1. ดาวน์โหลด ModRSsim2 จาก: https://sourceforge.net/projects/modrssim2/
2. แตกไฟล์ และรัน `ModRSsim2.exe`
3. ตั้งค่า:
   - **Protocol:** MODBUS TCP/IP
   - **Port:** 502
   - **Unit ID:** 1
4. กดปุ่ม **Start** — Simulator จะฟังที่ `localhost:502`
5. ลองแก้ค่า Register 0–4 ในตาราง เพื่อดูว่าค่าเปลี่ยนบน Grafana

> **หมายเหตุ:** ค่า `MODBUS_HOST=host.docker.internal` ใน `.env` ทำให้ Docker container เชื่อมกลับมาที่ Windows host ได้อัตโนมัติ

---

## Step 2 — รัน Docker Compose

เปิด **PowerShell** หรือ **Command Prompt** แล้วไปที่โฟลเดอร์โปรเจกต์:

```powershell
cd d:\GoogleDriveSync\Work\2026\Jmax\Final_Work
docker compose up -d
```

รอประมาณ 1–2 นาทีครั้งแรก (Docker ต้อง pull images)

### ตรวจสอบสถานะ

```powershell
docker compose ps
```

ทุก service ควรแสดงสถานะ `running` หรือ `Up`:

```
NAME              STATUS
influxdb          Up (healthy)
grafana           Up
modbus-logger     Up
```

### ดู Log ของ Python Logger

```powershell
docker compose logs -f modbus-logger
```

ถ้าเชื่อมสำเร็จจะเห็น:
```
[ModbusReader] INFO — ModbusReader started — host=host.docker.internal ...
[InfluxBatchWriter] INFO — Flushed 50 points to InfluxDB (total=50, ...)
```

---

## Step 3 — เข้าใช้งาน Grafana

1. เปิด Browser ไปที่: **http://localhost:3000**
2. Login ด้วย:
   - **Username:** `admin`
   - **Password:** `admin`
3. ระบบจะ redirect ให้เปลี่ยน password (ข้ามได้ถ้าเป็นแค่ทดสอบ)

### Dashboard อัตโนมัติ

Dashboard **"PLC Modbus Dashboard"** จะถูกโหลดอัตโนมัติ (Grafana Provisioning):
- ไปที่ **Dashboards → Browse → PLC Modbus Dashboard**
- กราฟจะแสดงค่า Register 0–4 แบบ Real-time (refresh ทุก 5 วินาที)

---

## Step 4 — Export ข้อมูลเป็น CSV

### วิธีที่ 1: Export จาก Panel โดยตรง

1. Hover ที่ Panel กราฟ → คลิกเมนู **⋮ (3 จุด)** มุมขวาบน
2. เลือก **Inspect → Data**
3. คลิกปุ่ม **Download CSV**

### วิธีที่ 2: Export ผ่าน Explore

1. ไปที่ **Explore** (ไอคอน Compass ด้านซ้าย)
2. เลือก Data Source: **InfluxDB**
3. พิมพ์ Flux Query:

```flux
from(bucket: "plc_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "plc_registers")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
```

4. คลิก **Run Query** → คลิก **⋮ → Inspect → Data → Download CSV**

---

## Step 5 — หยุดและลบ Containers

```powershell
# หยุด (เก็บข้อมูลไว้)
docker compose stop

# หยุดและลบ containers (เก็บ volume/ข้อมูลไว้)
docker compose down

# หยุด + ลบทุกอย่างรวมถึง volume (ข้อมูลหาย!)
docker compose down -v
```

---

## Step 6 — Deploy บน Raspberry Pi 4

1. Copy โฟลเดอร์โปรเจกต์ไปยัง Pi:
```bash
scp -r ./Final_Work pi@<PI_IP>:/home/pi/
```

2. SSH เข้า Pi แล้วรัน:
```bash
cd /home/pi/Final_Work
docker compose up -d
```

3. แก้ไข `.env`:
```
MODBUS_HOST=<IP จริงของ PLC บน Network>
```

> Pi 4 รัน Docker ได้ปกติ เพราะ Image ที่ใช้ (`python:3.10-slim`, `influxdb:2.7`, `grafana`) รองรับ `linux/arm64`

---

## Troubleshooting

| ปัญหา | วิธีแก้ |
|-------|---------|
| `modbus-logger` ขึ้น `Restarting` | ตรวจสอบว่า Modbus Simulator รันอยู่และ Port 502 เปิดอยู่ |
| Grafana ไม่มี Dashboard | รัน `docker compose restart grafana` |
| InfluxDB token ผิด | แก้ `INFLUXDB_TOKEN` ใน `.env` ให้ตรงกัน แล้ว `docker compose up -d` |
| ข้อมูลไม่ขึ้นกราฟ | เช็ค Time Range ใน Grafana ให้เป็น "Last 5 minutes" |
| Port 3000 ถูกใช้งานอยู่ | แก้ `"3000:3000"` เป็น `"3001:3000"` ใน `docker-compose.yml` |
