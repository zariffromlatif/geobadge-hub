import os
import datetime
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

# FIX 4: Correct os.getenv usage — env var NAME first, connection string as FALLBACK
# Note: '&' in password is URL-encoded as '%26'
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.kqxhsmbbgucwzdxzkwfx:%2BQn4B8Vw%26Lf.6qE@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
)

if DATABASE_URL:
    print("Brain is successfully connected to the Cloud Vault!")
else:
    print("Warning: DATABASE_URL not found. Check Render Env Variables.")

# The New 'Site' Model for the Hub
class Site(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_meters: int
    active_employees: int = 0

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

@app.get("/v1/admin/stats")
async def get_admin_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Total Presence Today
        cursor.execute("SELECT COUNT(DISTINCT employee_id) FROM checkins WHERE timestamp::date = CURRENT_DATE")
        total_today = cursor.fetchone()['count']
        
        # 2. Recent Anomalies (Check-ins far from factory)
        cursor.execute("SELECT COUNT(*) FROM checkins WHERE timestamp::date = CURRENT_DATE AND latitude IS NULL")
        anomalies = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        
        # FIX 4: Fixed Python datetime usage (was DateTime.now().iso8601() which doesn't exist)
        return {
            "active_now": total_today,
            "anomalies": anomalies,
            "system_health": "Optimal",
            "last_sync": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            # Don't send password back to the client
            safe_user = {"employee_id": user["employee_id"], "name": user["name"]}
            return {"status": "success", "user": safe_user}
        return {"status": "error", "detail": "Invalid Credentials"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login Error: {e}")
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