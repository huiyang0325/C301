import sqlite3
db_path = 'projects/.arcreel.db'
conn = sqlite3.connect(db_path, timeout=5)
cursor = conn.cursor()
cursor.execute("SELECT task_id, status, task_type FROM tasks WHERE task_type='long_video' ORDER BY queued_at DESC LIMIT 5")
for r in cursor.fetchall():
    print(r)
conn.close()