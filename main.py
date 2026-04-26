import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="GeoBadge Employer Hub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🟢 Pulls from Render Environment Variables
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
        print("ERROR: DATABASE_URL not found!")
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Create Check-ins Table
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

        # 2. Create Employees Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY,
                password TEXT,
                name TEXT
            )
        """)

        # 3. Seed your account
        cursor.execute("""
            INSERT INTO employees (employee_id, password, name)
            VALUES ('BRACU-2026', 'zarif123', 'Zarif Latif')
            ON CONFLICT (employee_id) DO NOTHING
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database Initialized Successfully")
    except Exception as e:
        print(f"❌ DB Init Error: {e}")

init_db()

@app.get("/")
def root():
    return {"message": "GeoBadge Hub is Live"}

@app.post("/v1/login")
async def login(credentials: dict):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM employees WHERE employee_id = %s AND password = %s", 
                       (credentials.get('employee_id'), credentials.get('password')))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            return {"status": "success", "user": user}
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/checkin")
async def receive_checkin(data: CheckInPayload):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO checkins (employee_id, device_id, qr_payload, latitude, longitude, biometric_hash, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (data.employee_id, data.device_id, data.qr_payload, data.latitude, data.longitude, data.biometric_hash, data.timestamp))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))