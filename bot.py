import os
import discord
import sqlite3
from dotenv import load_dotenv
import shlex
from datetime import datetime, timezone, timedelta
import asyncio
import traceback
import shutil
from dateutil import parser
import pytz
from modules.partner import (
    handle_add_partner, handle_list_partners, handle_info_partner, 
    handle_set_timezone, handle_delete_partner, handle_update_discord_user
)
from modules.project import (
    handle_list_projects, handle_info_project, handle_delete_project
)
from modules.message import (
    handle_send, handle_list_messages, handle_message_status, 
    handle_reply_rules, handle_status_reply
)
from modules.project_update import handle_update_projects

# Tải biến môi trường từ file .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
print(f"Token loaded: {'Yes' if TOKEN else 'No'}")
if not TOKEN:
    raise ValueError("Không tìm thấy DISCORD_TOKEN trong file .env hoặc biến môi trường!\nHãy chắc chắn rằng bạn đã tạo file .env với dòng: DISCORD_TOKEN=token_cua_ban")

DATABASE = 'bot_database.db'

# Hàm lấy thời gian Việt Nam
def get_vietnam_time():
    utc_now = datetime.now(timezone.utc)
    vietnam_tz = timezone(timedelta(hours=7))
    return utc_now.astimezone(vietnam_tz)

# Hàm chuẩn hóa tên
def normalize_name(name):
    """Chuẩn hóa tên để tránh xung đột"""
    return name.strip().lower().replace(' ', '_')

def find_partner_by_name_or_username(conn, identifier):
    """Tìm partner theo tên hoặc discord username"""
    cur = conn.cursor()
    
    # Thử tìm theo partner_name
    cur.execute('''
        SELECT partner_id, partner_name, server_id, timezone, discord_username, tag_type
        FROM partners 
        WHERE partner_name = ?
    ''', (identifier,))
    partner = cur.fetchone()
    
    if partner:
        return partner
    
    # Nếu không tìm thấy, thử tìm theo discord_username
    cur.execute('''
        SELECT partner_id, partner_name, server_id, timezone, discord_username, tag_type
        FROM partners 
        WHERE discord_username = ?
    ''', (identifier,))
    partner = cur.fetchone()
    
    return partner

# Hàm format timezone thành UTC+/- format
def format_timezone_display(timezone_str):
    """Format timezone string thành UTC+/- format"""
    try:
        if not timezone_str:
            return "UTC+07:00"
        
        if timezone_str.startswith('+'):
            return f"UTC{timezone_str}"
        elif timezone_str.startswith('-'):
            return f"UTC{timezone_str}"
        else:
            return f"UTC{timezone_str}"
    except:
        return "UTC+07:00"

# Hàm lấy thời gian theo timezone của partner
def get_partner_time_with_timezone(timezone_str):
    """Lấy thời gian hiện tại theo timezone của partner"""
    try:
        if not timezone_str:
            timezone_str = '+07:00'
        
        # Parse timezone offset
        if timezone_str.startswith('+'):
            hours = int(timezone_str[1:3])
            minutes = int(timezone_str[4:6]) if len(timezone_str) > 5 else 0
            offset = timedelta(hours=hours, minutes=minutes)
        elif timezone_str.startswith('-'):
            hours = int(timezone_str[1:3])
            minutes = int(timezone_str[4:6]) if len(timezone_str) > 5 else 0
            offset = timedelta(hours=-hours, minutes=-minutes)
        else:
            offset = timedelta(hours=7)  # Default to Vietnam time
        
        utc_now = datetime.now(timezone.utc)
        partner_time = utc_now.astimezone(timezone(offset))
        return partner_time.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return get_vietnam_time().strftime("%Y-%m-%d %H:%M:%S")

# Hàm validation nội dung tin nhắn
def validate_message_content(content):
    """Kiểm tra nội dung tin nhắn có hợp lệ không"""
    if not content or len(content.strip()) == 0:
        return False, "Nội dung tin nhắn không được để trống"
    
    if len(content) > 2000:
        return False, "Nội dung tin nhắn quá dài (tối đa 2000 ký tự)"
    
    return True, ""

# Hàm tạo tag message
def create_tag_message(partner_info):
    """Tạo tag message dựa trên cấu hình partner"""
    # sqlite3.Row objects use bracket notation, not .get() method
    discord_username = partner_info['discord_username'] if 'discord_username' in partner_info.keys() else None
    
    # Nếu có discord_username thì tag trực tiếp, nếu không thì dùng @everyone
    if discord_username:
        # Xử lý cả user ID mention và username thường
        if discord_username.startswith('<@') and discord_username.endswith('>'):
            # Đây là user ID mention, giữ nguyên để Discord tự động resolve
            return discord_username
        else:
            # Đây là username thường, thêm @ nếu chưa có
            clean_username = discord_username.replace('@', '')
            return f"@{clean_username}"
    else:
        return "@everyone"

# Hàm logging
def log_action(action, details=""):
    timestamp = get_vietnam_time().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {action}: {details}"
    print(log_entry)
    
    # Lưu vào file log
    try:
        with open('bot_log.txt', 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    except:
        pass

# Kết nối tới database và tạo bảng
def get_db_connection():
    """Tạo kết nối database với migration tự động"""
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row  # Cho phép truy cập bằng tên cột
    cur = conn.cursor()
    
    # Tạo bảng partners
    cur.execute('''
        CREATE TABLE IF NOT EXISTS partners (
            partner_id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_name TEXT NOT NULL,
            server_id TEXT NOT NULL,
            discord_username TEXT,
            timezone TEXT DEFAULT '+07:00',
            tag_type TEXT DEFAULT 'everyone',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(partner_name, server_id)
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
    return conn

# Cấu hình Intents
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Bot đã đăng nhập với tên {client.user}')
    print('Bot đang sử dụng cấu trúc modular mới!')

@client.event
async def on_message(message):
    # Bỏ qua tin nhắn từ chính bot
    if message.author == client.user:
        return

    try:
        # Xử lý reply vào tin nhắn của bot để update status
        if message.reference and message.reference.resolved:
            await handle_status_reply(message)
            return
        
        # Xử lý các lệnh partner
        if message.content.startswith('!add_partner'):
            await handle_add_partner(message)
        elif message.content.startswith('!list_partners') or message.content.startswith('!list_partner'):
            await handle_list_partners(message)
        elif message.content.startswith('!info_partner'):
            await handle_info_partner(message)
        elif message.content.startswith('!set_timezone'):
            await handle_set_timezone(message)
        elif message.content.startswith('!delete_partner'):
            await handle_delete_partner(message)
        elif message.content.startswith('!update_discord_user'):
            await handle_update_discord_user(message)
        
        # Xử lý các lệnh project
        elif message.content.startswith('!list_projects'):
            await handle_list_projects(message)
        elif message.content.startswith('!info_project'):
            await handle_info_project(message)
        elif message.content.startswith('!delete_project'):
            await handle_delete_project(message)
        elif message.content.startswith('!update_projects'):
            await handle_update_projects(message)
        
        # Xử lý các lệnh message
        elif message.content.startswith('!send'):
            await handle_send(message)
        elif message.content.startswith('!list'):
            await handle_list_messages(message)
        elif message.content.startswith('!message_status'):
            await handle_message_status(message)
        elif message.content.startswith('!reply_rules'):
            await handle_reply_rules(message)
        
        # Lệnh help
        elif message.content.startswith('!help'):
            await handle_help(message)
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"Error in on_message: {e}")
        traceback.print_exc()
        await message.channel.send(error_msg)

# Hàm xử lý lệnh !help
async def handle_help(message):
    """Handle !help command (English)"""
    help_text = """**🤖 Discord Bot Partner Management System**

**👥 Partner Commands:**
• `!add_partner <name> <server_id> <@user1> <@user2> [timezone]` - Add a partner
• `!list_partners` - List all partners
• `!info_partner <name>` - Partner details
• `!set_timezone <partner> <timezone>` - Update timezone
• `!update_discord_user -p <partner> <@old_user> <@new_user>` - Update Discord user
• `!delete_partner <name>` - Delete partner

**📁 Project Commands:**
• `!list_projects [-p partner] [-all]` - List projects
• `!info_project <code>` - Project details
• `!delete_project <name>` - Delete project
• `!update_projects -p <partner>` - Sync projects from Discord channels

**💬 Message Commands:**
• `!send -p <partner> | <content>` - Send message to ALL projects of partner
• `!send -p <partner> -c <channel1> -c <channel2> | <content>` - Send message to specific projects
• `!list [-p partner] [-c project] [-all]` - Track messages
• `!message_status <partner> <project> <status>` - Update status
• `!reply_rules` - Partner reply instructions

**📊 Status Types:**
• `request` → `order received` → `build sent` → `test pass` → `release app`

**🔧 Advanced Features:**

**Multi-Partner Sending:**
• `!send -p "partner1" -c -all -p "partner2" -c "channel" | <content>`

**Send to All Projects:**
• `!send -p "partner" -c -all | <content>`

**Project Synchronization:**
• `!update_projects -p "partner"` - Sync Discord channels with database

**💡 Examples:**
• `!add_partner "Client A" 123456789012345678 @john_doe +05:30`
• `!send -p "Client A" | Important announcement` - Send to ALL projects
• `!send -p "hoàng_thượng" -c "abp999" | Test message` - Send to specific project
• `!list -p "Client A" -all`
• `!message_status "Client A" general "test pass"`
• `!update_projects -p "huy"`
• `!update_discord_user -p "huy" @old_manager @new_manager`
• `!reply_rules`

**📝 Reply Tracking:**
Partners can reply to bot messages to automatically update status through the workflow.
"""
    await message.channel.send(help_text)

if __name__ == "__main__":
    client.run(TOKEN) 