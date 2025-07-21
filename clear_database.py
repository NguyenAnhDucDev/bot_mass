#!/usr/bin/env python3
"""
Script để xóa hết data cũ trong database
"""

import sqlite3
import os

def clear_database():
    """Xóa hết data trong database nhưng giữ lại cấu trúc bảng"""
    
    # Kiểm tra file database có tồn tại không
    if not os.path.exists('bot_database.db'):
        print("❌ Không tìm thấy file bot_database.db")
        return
    
    try:
        conn = sqlite3.connect('bot_database.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        print("🗑️ Đang xóa data cũ...")
        
        # Xóa data từ các bảng theo thứ tự để tránh lỗi foreign key
        tables_to_clear = [
            'messages',
            'schedules', 
            'templates',
            'projects',
            'partner_discord_users',
            'partners'
        ]
        
        for table in tables_to_clear:
            try:
                cur.execute(f'DELETE FROM {table}')
                deleted_count = cur.rowcount
                print(f"✅ Đã xóa {deleted_count} records từ bảng {table}")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Bảng {table} không tồn tại hoặc có lỗi: {e}")
        
        # Reset auto-increment counters
        cur.execute("DELETE FROM sqlite_sequence")
        
        conn.commit()
        conn.close()
        
        print("✅ Đã xóa hết data cũ thành công!")
        print("📊 Database hiện tại trống và sẵn sàng cho test mới")
        
    except Exception as e:
        print(f"❌ Lỗi khi xóa database: {e}")

if __name__ == "__main__":
    print("🧹 Script xóa database")
    print("=" * 40)
    
    confirm = input("⚠️ Bạn có chắc muốn xóa HẾT data? (y/N): ")
    if confirm.lower() == 'y':
        clear_database()
    else:
        print("❌ Đã hủy thao tác") 