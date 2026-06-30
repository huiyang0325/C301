import sqlite3
db_path = 'projects/.arcreel.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('DELETE FROM worker_lease')
cursor.execute("DELETE FROM tasks WHERE task_type='long_video' AND status='failed'")
conn.commit()
print(f'Cleared leases and failed tasks')
cursor.execute('SELECT COUNT(*) FROM tasks WHERE task_type="long_video"')
print(f'Remaining long_video tasks: {cursor.fetchone()[0]}')
conn.close()