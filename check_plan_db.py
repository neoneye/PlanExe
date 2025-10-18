import sqlite3
from pathlib import Path

db_path = Path("planexe.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get the latest plan
cursor.execute("""
    SELECT plan_id, status, progress_percentage, progress_message, error_message
    FROM plans
    ORDER BY created_at DESC
    LIMIT 1
""")

row = cursor.fetchone()
if row:
    print(f"Plan ID: {row[0]}")
    print(f"Status: {row[1]}")
    print(f"Progress: {row[2]}%")
    print(f"Message: {row[3]}")
    print(f"Error: {row[4]}")
else:
    print("No plans found")

conn.close()
