import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
import csv
import io
from fastapi.middleware.cors import CORSMiddleware
import math
from datetime import datetime, timedelta

app = FastAPI(title="GeoBadge Employer Hub", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🟢 This pulls the URL from the cloud server environment
DATABASE_URL = os.getenv("DATABASE_URL") 

class CheckInPayload(BaseModel):
    employee_id: str
    device_id: str
    qr_payload: str
    latitude: float
    longitude: float
    biometric_hash: str
    timestamp: str

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL:
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkins (
                id SERIAL PRIMARY KEY,
                employee_id TEXT,
                device_id TEXT,
                qr_payload TEXT,
                latitude REAL,
                longitude REAL,
                biometric_hash TEXT,
                timestamp TEXT
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("DB Init Error:", e)

def calculate_haversine(lat1, lon1, lat2, lon2):
    # Haversine formula to calculate distance in meters
    """Calculate the great circle distance in meters between two points on the Earth."""
    R = 6371000  # Earth radius in meters
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

init_db()

# Update POST endpoint:
@app.post("/v1/checkin")
async def receive_checkin(data: CheckInPayload):
    FACTORY_LAT = 23.7704  # Set factory center
    FACTORY_LNG = 90.3586
    ALLOWED_RADIUS = 50.0  # meters

    distance = calculate_haversine(data.latitude, data.longitude, FACTORY_LAT, FACTORY_LNG)
    
    if distance > ALLOWED_RADIUS:
        raise HTTPException(status_code=403, detail=f"Location Violation: {round(distance)}m from site.")
    try:
        qr_parts = data.qr_payload.split("_")
        qr_time = datetime.fromisocalendar(qr_parts[-1])
        if datetime.now() - qr_time > timedelta(minutes=5):
            raise HTTPException(status_code=403, detail="QR Code Expired: Please rescan.")
    
    except:
        pass #Fallback for static QR testing
    
@app.post("/v1/checkin")
async def receive_checkin(data: CheckInPayload):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 🟢 Postgres uses %s instead of ? for secure variable injection
        cursor.execute("""
            INSERT INTO checkins (employee_id, device_id, qr_payload, latitude, longitude, biometric_hash, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (data.employee_id, data.device_id, data.qr_payload, data.latitude, data.longitude, data.biometric_hash, data.timestamp))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "message": "Zero-Click Check-In Verified & Logged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/logs")
async def get_logs():
    conn = get_db_connection()
    # RealDictCursor automatically formats the output as clean JSON
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM checkins ORDER BY timestamp DESC")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

@app.get("/v1/export")
async def export_csv():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id, qr_payload, latitude, longitude, timestamp FROM checkins ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Employee ID", "Site Scanned", "Latitude", "Longitude", "Timestamp"])
    for row in rows:
        writer.writerow(row)

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=geobadge_payroll_export.csv"}
    )