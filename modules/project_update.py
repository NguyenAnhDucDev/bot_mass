import sqlite3
import discord
from datetime import datetime
import shlex

def get_db_connection():
    """Tạo kết nối database"""
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row
    return conn

def log_action(action, details=""):
    """Log action"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {action}: {details}"
    print(log_entry)
    
    try:
        with open('bot_log.txt', 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    except:
        pass

def find_partner_by_name_or_username(conn, identifier):
    """Tìm partner theo tên hoặc discord username"""
    cur = conn.cursor()
    
    # Thử tìm theo partner_name - chỉ sử dụng các cột cơ bản
    cur.execute('''
        SELECT partner_id, partner_name, server_id, timezone
        FROM partners 
        WHERE LOWER(partner_name) = LOWER(?)
    ''', (identifier,))
    partner = cur.fetchone()
    
    if partner:
        return partner
    
    # Nếu không tìm thấy, thử tìm theo discord_username (nếu cột tồn tại)
    try:
        cur.execute('''
            SELECT partner_id, partner_name, server_id, timezone, discord_username
            FROM partners 
            WHERE LOWER(discord_username) = LOWER(?)
        ''', (identifier,))
        partner = cur.fetchone()
        return partner
    except sqlite3.OperationalError:
        # Cột discord_username không tồn tại, chỉ tìm theo partner_name
        return None

async def handle_update_projects(message):
    """Handle !update_projects command (English)"""
    conn = None
    try:
        content = message.content.strip()
        # Use shlex.split to correctly handle quoted arguments
        args = shlex.split(content) 
        
        if len(args) < 3 or args[1] != '-p':
            await message.channel.send('❌ Invalid syntax! Use: `!update_projects -p <partner_name>`')
            return
        
        partner_name = args[2] # shlex.split already handles stripping quotes
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        log_action("DEBUG", f"Looking for partner: '{partner_name}'")
        
        partner = find_partner_by_name_or_username(conn, partner_name)
        if not partner:
            conn.close()
            await message.channel.send(f'❌ Partner not found: **{partner_name}**')
            return
        
        log_action("DEBUG", f"Found partner: {partner['partner_name']} (ID: {partner['partner_id']})")
        
        # Get all text channels in the guild
        discord_text_channels = [c for c in message.guild.channels if isinstance(c, discord.TextChannel)]
        
        # Create a map of Discord channels by their ID
        discord_channels_map = {str(channel.id): channel for channel in discord_text_channels}
        
        # Get existing projects for this partner from DB
        cur.execute('SELECT project_id, project_name, channel_id FROM projects WHERE partner_id = ?', (partner['partner_id'],))
        db_projects = cur.fetchall()
        
        # Create a map of DB projects by their channel_id
        db_projects_map_by_channel_id = {p['channel_id']: p for p in db_projects}
        
        added_projects = []
        updated_projects = []
        removed_projects = []
        
        # Keep track of DB projects that are still present in Discord
        processed_db_project_ids = set()
        
        # Step 1: Add new projects and update existing ones
        for discord_channel_id, discord_channel in discord_channels_map.items():
            if discord_channel_id in db_projects_map_by_channel_id:
                # Project exists in DB, check for name change
                db_project = db_projects_map_by_channel_id[discord_channel_id]
                if db_project['project_name'] != discord_channel.name:
                    # Name changed, update it
                    cur.execute('UPDATE projects SET project_name = ? WHERE project_id = ?', 
                                (discord_channel.name, db_project['project_id']))
                    updated_projects.append(f"{db_project['project_name']} → {discord_channel.name}")
                processed_db_project_ids.add(db_project['project_id'])
            else:
                # New project, add it to DB
                try:
                    cur.execute('INSERT INTO projects (partner_id, project_name, channel_id) VALUES (?, ?, ?)',
                                (partner['partner_id'], discord_channel.name, discord_channel_id))
                    added_projects.append(discord_channel.name)
                except sqlite3.IntegrityError:
                    # Project already exists with same name, skip
                    log_action("DEBUG", f"Project {discord_channel.name} already exists for partner {partner['partner_name']}")
        
        # Step 2: Remove projects that no longer exist in Discord
        for db_project in db_projects:
            if db_project['project_id'] not in processed_db_project_ids:
                # This DB project's channel_id was not found in current Discord channels
                cur.execute('DELETE FROM projects WHERE project_id = ?', (db_project['project_id'],))
                removed_projects.append(db_project['project_name'])
        
        conn.commit()
        conn.close()
        
        # Generate report
        report = f"📋 Project Update Report for **{partner['partner_name']}**:\n"
        if added_projects:
            report += "✅ Added: " + ", ".join(added_projects) + "\n"
        if updated_projects:
            report += "🔄 Updated: " + ", ".join(updated_projects) + "\n"
        if removed_projects:
            report += "❌ Removed: " + ", ".join(removed_projects) + "\n"
        
        if not added_projects and not updated_projects and not removed_projects:
            report += "No changes detected."
            
        await message.channel.send(report)
        
    except Exception as e:
        log_action("ERROR", f"Error in handle_update_projects: {e}")
        await message.channel.send(f'❌ Error: {e}')
        if conn:
            conn.close() 