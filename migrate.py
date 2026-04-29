import sqlite3
import psycopg2

# 1. Source: Local SQLite
local_conn = sqlite3.connect('geobadge_hub.db')
local_cursor = local_conn.cursor()

# 2. Destination: Supabase Cloud (Replace with your URI)
CLOUD_DB_URL = "postgresql://postgres.kqxhsmbbgucwzdxzkwfx:+Qn4B8Vw&Lf.6qE@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"
cloud_conn = psycopg2.connect(CLOUD_DB_URL)
cloud_cursor = cloud_conn.cursor()

def migrate():
    print("🛰️ Migrating check-in logs to the cloud...")
    
    try:
        # We only migrate checkins since 'employees' wasn't found locally
        local_cursor.execute("SELECT * FROM checkins")
        logs = local_cursor.fetchall()
        
        for log in logs:
            # We skip the first column (local ID) and insert the rest
            cloud_cursor.execute(
                """INSERT INTO checkins 
                (employee_id, device_id, qr_payload, latitude, longitude, biometric_hash, timestamp) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (log[1], log[2], log[3], log[4], log[5], log[6], log[7])
            )
        
        cloud_conn.commit()
        print(f"✅ Successfully moved {len(logs)} logs to Supabase!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        local_conn.close()
        cloud_conn.close()

if __name__ == "__main__":
    migrate()