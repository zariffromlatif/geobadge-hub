import sqlite3

try:
    conn = sqlite3.connect('geobadge_hub.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"📦 Tables found in local file: {tables}")
    
    if not tables:
        print("💡 The local database is EMPTY. Your data is likely already in the cloud!")
except Exception as e:
    print(f"❌ Error: {e}")