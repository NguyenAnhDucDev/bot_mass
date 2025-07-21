#!/usr/bin/env python3
"""
Script setup để kiểm tra và khởi tạo database cho Bot Discord
"""

import sqlite3
import os
from datetime import datetime

def setup_database():
    """Khởi tạo database và tạo các bảng cần thiết"""
    print("🔧 Đang khởi tạo database...")
    
    # Kết nối database
    conn = sqlite3.connect('bot_database.db')
    cur = conn.cursor()
    
    # Tạo bảng partners
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
    print("✅ Bảng partners đã được tạo")
    
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
    print("✅ Bảng partner_discord_users đã được tạo")
    
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
    print("✅ Bảng projects đã được tạo")
    
    # Tạo bảng messages
    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            discord_message_id TEXT,
            status TEXT DEFAULT 'request',
            reply_timestamp TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (partner_id) REFERENCES partners (partner_id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects (project_id) ON DELETE CASCADE
        )
    ''')
    print("✅ Bảng messages đã được tạo")
    
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
    print("✅ Bảng schedules đã được tạo")
    
    # Tạo bảng templates
    cur.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL UNIQUE,
            template_content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ Bảng templates đã được tạo")
    
    # Commit và đóng kết nối
    conn.commit()
    conn.close()
    
    print("✅ Database đã được khởi tạo thành công!")

def check_environment():
    """Kiểm tra môi trường và cấu hình"""
    print("🔍 Đang kiểm tra môi trường...")
    
    # Kiểm tra file .env
    if not os.path.exists('.env'):
        print("⚠️  File .env không tồn tại!")
        print("📝 Vui lòng tạo file .env với nội dung:")
        print("DISCORD_TOKEN=YOUR_BOT_TOKEN")
        return False
    
    # Kiểm tra dependencies
    try:
        import discord
        print("✅ discord.py đã được cài đặt")
    except ImportError:
        print("❌ discord.py chưa được cài đặt")
        print("💡 Chạy: pip install -r requirements.txt")
        return False
    
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv đã được cài đặt")
    except ImportError:
        print("❌ python-dotenv chưa được cài đặt")
        print("💡 Chạy: pip install -r requirements.txt")
        return False
    
    # Kiểm tra token
    load_dotenv()
    token = os.getenv('DISCORD_TOKEN')
    if not token or token == 'YOUR_BOT_TOKEN':
        print("⚠️  DISCORD_TOKEN chưa được cấu hình đúng!")
        print("💡 Vui lòng cập nhật file .env với token thực")
        return False
    
    print("✅ Môi trường đã được cấu hình đúng!")
    return True

def main():
    """Hàm chính"""
    print("🤖 Bot Discord Setup")
    print("=" * 50)
    
    # Kiểm tra môi trường
    if not check_environment():
        print("\n❌ Setup không thành công!")
        return
    
    # Khởi tạo database
    setup_database()
    
    print("\n🎉 Setup hoàn tất!")
    print("💡 Bây giờ bạn có thể chạy: python bot.py")

if __name__ == "__main__":
    main() 