import os
import datetime
import math
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="GeoBadge Hub: Utility-First Backend")

# --- 🛰️ CORS CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 💾 DATABASE CONFIGURATION ---
# Using the AP-Southeast-1 (Singapore) IPv4 Pooler for maximum reliability in Dhaka
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.kqxhsmbbgucwzdxzkwfx:%2BQn4B8Vw%26Lf.6qE@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
)

# --- 📐 GEOFENCE CONSTANTS (Factory Entrance) ---
# Note: You can update these to your specific test coordinates
TARGET_LAT = 23.8103  
TARGET_LNG = 90.4125
GEOFENCE_RADIUS_METERS = 100 

# --- 🏗️ DATA MODELS ---
class CheckInPayload(BaseModel):
    employee_id: str
    device_id: str
    site_id: str        # From the scanned QR code
    latitude: float
    longitude: float
    timestamp: str

class LoginRequest(BaseModel):
    employee_id: str
    password: str

# --- 🛠️ DATABASE UTILITIES ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine formula to calculate distance in meters."""
    R = 6371000 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Clean Check-ins Table (Biometric Removed)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkins (
                id SERIAL PRIMARY KEY,
                employee_id TEXT NOT NULL,
                device_id TEXT,
                site_id TEXT,
                latitude REAL,
                longitude REAL,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Employees Table (For One-Time Onboarding)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY,
                password TEXT,
                name TEXT
            )
        """)

        # 3. Seed Root User
        cursor.execute("""
            INSERT INTO employees (employee_id, password, name)
            VALUES ('BRACU-2026', 'zarif123', 'Zarif Latif')
            ON CONFLICT (employee_id) DO NOTHING
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("🧠 Brain is successfully connected to the Cloud Vault!")
        print("✅ Database Initialized Successfully")
    except Exception as e:
        print(f"❌ DB Init Error: {e}")

init_db()

# --- 📡 ENDPOINTS ---

@app.get("/")
def root():
    return {"status": "online", "message": "GeoBadge Hub is Live"}

@app.post("/v1/login")
async def login(credentials: LoginRequest):
    """Handles the one-time onboarding for the Android Keystore setup."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT employee_id, name FROM employees WHERE employee_id = %s AND password = %s", 
            (credentials.employee_id, credentials.password)
        )
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
    """
    The Core 'Zero-Click' Endpoint.
    Validates GPS against Geofence before logging.
    """
    try:
        # 1. Geofence Validation
        distance = calculate_distance(data.latitude, data.longitude, TARGET_LAT, TARGET_LNG)
        
        if distance > GEOFENCE_RADIUS_METERS:
            # This triggers the "Double-Buzz" red error on the OnePlus 5
            raise HTTPException(
                status_code=403, 
                detail=f"Outside Geofence: {int(distance)}m from site."
            )

        # 2. Log Authorized Check-in
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO checkins (employee_id, device_id, site_id, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s)
        """, (data.employee_id, data.device_id, data.site_id, data.latitude, data.longitude))
        
        conn.commit()
        cursor.close()
        conn.close()

        # 3. Success Response
        # This triggers the "Satisfying Haptic" green checkmark on the phone
        return {
            "status": "success", 
            "message": "Check-in Verified",
            "distance_m": int(distance)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Check-in Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/v1/admin/stats")
async def get_admin_stats():
    """Feeds the Next.js Dashboard with real-time stats."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Count unique employees today
        cursor.execute("SELECT COUNT(DISTINCT employee_id) FROM checkins WHERE timestamp::date = CURRENT_DATE")
        total_today = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        
        return {
            "active_now": total_today,
            "anomalies": 0, # GPS filtering now happens at the endpoint
            "system_health": "Optimal",
            "last_sync": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))