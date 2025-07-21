import sqlite3
import os

def reset_database():
    """Xóa toàn bộ dữ liệu cũ và tạo lại database"""
    
    # Xóa file database cũ nếu tồn tại
    if os.path.exists('bot_database.db'):
        os.remove('bot_database.db')
        print("Đã xóa database cũ")
    
    # Tạo database mới
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Tạo bảng partners với cấu trúc mới
    cur.execute('''
        CREATE TABLE IF NOT EXISTS partners (
            partner_id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_name TEXT NOT NULL,
            server_id TEXT NOT NULL,
            timezone TEXT DEFAULT '+07:00',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(partner_name, server_id)
        )
    ''')
    
    # Tạo bảng partner_discord_users để lưu nhiều Discord users cho một partner
    cur.execute('''
        CREATE TABLE IF NOT EXISTS partner_discord_users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER NOT NULL,
            discord_username TEXT NOT NULL,
            tag_type TEXT DEFAULT 'username',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
            UNIQUE(partner_id, discord_username)
        )
    ''')
    
    # Tạo bảng projects
    cur.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            partner_id INTEGER NOT NULL,
            channel_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
            UNIQUE(project_name, partner_id)
        )
    ''')
    
    # Tạo bảng messages
    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            discord_message_id TEXT,
            status TEXT DEFAULT 'sent',
            reply_status TEXT DEFAULT 'pending',
            reply_timestamp TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects (project_id) ON DELETE CASCADE
        )
    ''')
    
    # Tạo bảng schedules
    cur.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            scheduled_for TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects (project_id) ON DELETE CASCADE
        )
    ''')
    
    # Tạo bảng templates
    cur.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL UNIQUE,
            template_content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    
    print("✅ Đã tạo lại database với cấu trúc mới!")
    print("📊 Cấu trúc mới:")
    print("• partners: Lưu thông tin partner")
    print("• partner_discord_users: Lưu nhiều Discord users cho một partner")
    print("• projects: Lưu thông tin projects")
    print("• messages: Lưu tin nhắn đã gửi")
    print("• schedules: Lưu tin nhắn đã lên lịch")
    print("• templates: Lưu templates tin nhắn")

if __name__ == "__main__":
    confirm = input("⚠️ Bạn có chắc chắn muốn xóa toàn bộ dữ liệu cũ? (y/N): ")
    if confirm.lower() == 'y':
        reset_database()
    else:
        print("❌ Hủy bỏ việc xóa database") 