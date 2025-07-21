import sqlite3
from datetime import datetime, timezone

def get_db_connection():
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Hàm logging
def log_action(action, details=""):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {action}: {details}"
    print(log_entry)
    try:
        with open('bot_log.txt', 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    except:
        pass 