from modules.db_utils import get_db_connection, log_action
from modules.utils import normalize_name, format_timezone_display, get_partner_time_with_timezone, format_time_with_timezones
import discord
import shlex

# Hàm tìm partner theo tên hoặc discord username
def find_partner_by_name_or_username(conn, identifier):
    """Tìm partner theo tên hoặc discord username"""
    cur = conn.cursor()
    
    # Thử tìm theo partner_name
    cur.execute('''
        SELECT partner_id, partner_name, server_id, timezone
        FROM partners 
        WHERE partner_name = ?
    ''', (identifier,))
    partner = cur.fetchone()
    
    if partner:
        # Lấy discord_username cho partner này từ partner_discord_users table
        cur.execute('''
            SELECT discord_username FROM partner_discord_users 
            WHERE partner_id = ?
        ''', (partner['partner_id'],))
        discord_users = cur.fetchall()
        discord_username = ', '.join([u['discord_username'] for u in discord_users]) if discord_users else None
        
        # Tạo partner dict với discord_username
        partner_dict = dict(partner)
        partner_dict['discord_username'] = discord_username
        return partner_dict
    
    # Nếu không tìm thấy, thử tìm theo discord_username
    cur.execute('''
        SELECT p.partner_id, p.partner_name, p.server_id, p.timezone
        FROM partners p
        JOIN partner_discord_users pdu ON p.partner_id = pdu.partner_id
        WHERE pdu.discord_username = ?
    ''', (identifier,))
    partner = cur.fetchone()
    
    if partner:
        # Lấy discord_username cho partner này
        cur.execute('''
            SELECT discord_username FROM partner_discord_users 
            WHERE partner_id = ?
        ''', (partner['partner_id'],))
        discord_users = cur.fetchall()
        discord_username = ', '.join([u['discord_username'] for u in discord_users]) if discord_users else None
        
        # Tạo partner dict với discord_username
        partner_dict = dict(partner)
        partner_dict['discord_username'] = discord_username
        return partner_dict
    
    return None

# Hàm xử lý lệnh !add_partner
async def handle_add_partner(message):
    """Handle !add_partner command (English)"""
    try:
        args = shlex.split(message.content)
        if len(args) < 4:
            await message.channel.send('❌ Invalid syntax! Use: !add_partner <partner_name> <server_id> <@discord_user1> <@discord_user2> ... [timezone]\n\n**Example:**\n• `!add_partner "Client A" 123456789012345678 @john_doe`\n• `!add_partner "Client B" 123456789012345678 @john_doe @jane_doe +05:30`')
            return
        
        partner_name = normalize_name(args[1])
        server_id = args[2].strip()
        partner_timezone = '+07:00'
        
        # Tìm timezone (thường ở cuối)
        timezone_index = -1
        for i, arg in enumerate(args[3:], 3):
            if arg.startswith(('+', '-')) and len(arg) >= 5:
                timezone_index = i
                partner_timezone = arg.strip()
                break
        
        # Lấy tất cả Discord usernames (bỏ qua timezone)
        discord_usernames = []
        for i in range(3, len(args)):
            if i != timezone_index:
                discord_usernames.append(args[i].strip())
        
        # Validation timezone
        try:
            if not partner_timezone.startswith(('+', '-')):
                await message.channel.send('❌ Timezone must start with + or - (e.g. +07:00, +05:30)')
                return
            
            # Test timezone parsing
            get_partner_time_with_timezone(partner_timezone)
        except:
            await message.channel.send('❌ Invalid timezone! Use format: +07:00, +05:30, -05:00')
            return
        
        # Kiểm tra xem có đang ở trong server không
        guild = message.guild
        if not guild:
            await message.channel.send('❌ This command only works in a Discord server.')
            return
        
        # Kiểm tra server ID có khớp không
        if str(guild.id) != server_id:
            await message.channel.send(f'❌ Server ID does not match!\n\n**Current Server:** {guild.name} (ID: {guild.id})\n**Server ID you entered:** {server_id}')
            return

        conn = get_db_connection()
        cur = conn.cursor()
        
        # Kiểm tra partner đã tồn tại chưa
        cur.execute('SELECT partner_id FROM partners WHERE partner_name = ? AND server_id = ?', (partner_name, server_id))
        existing_partner = cur.fetchone()
        
        if existing_partner:
            await message.channel.send(f'❌ Partner **{partner_name}** already exists in this server.')
            conn.close()
            return
        
        # Lấy tất cả text channels mà bot có thể truy cập
        accessible_channels = []
        for channel in guild.channels:
            try:
                if hasattr(channel, 'type') and str(channel.type) == 'text':
                    bot_permissions = channel.permissions_for(guild.me)
                    if bot_permissions.view_channel and bot_permissions.send_messages:
                        accessible_channels.append({
                            'name': channel.name,
                            'id': channel.id
                        })
            except:
                continue
        
        if not accessible_channels:
            await message.channel.send('❌ Bot does not have access to any channels in this server.')
            conn.close()
            return
        
        # Thêm partner
        cur.execute('''
            INSERT INTO partners (partner_name, server_id, timezone)
            VALUES (?, ?, ?)
        ''', (partner_name, server_id, partner_timezone))
        
        partner_id = cur.lastrowid
        
        # Thêm tất cả Discord users
        for discord_username in discord_usernames:
            # Xác định tag_type dựa trên discord_username
            if discord_username.startswith('<@') and discord_username.endswith('>'):
                tag_type = 'user_mention'
            else:
                tag_type = 'username'
            
            try:
                cur.execute('''
                    INSERT INTO partner_discord_users (partner_id, discord_username, tag_type)
                    VALUES (?, ?, ?)
                ''', (partner_id, discord_username, tag_type))
            except:
                # User đã tồn tại
                continue
        
        # Thêm tất cả channels làm projects
        projects_added = 0
        for channel in accessible_channels:
            try:
                cur.execute('''
                    INSERT INTO projects (project_name, partner_id, channel_id)
                    VALUES (?, ?, ?)
                ''', (channel['name'], partner_id, channel['id']))
                projects_added += 1
            except:
                # Project đã tồn tại
                continue
        
        conn.commit()
        conn.close()
        
        # Tạo danh sách Discord usernames để hiển thị
        discord_users_display = ', '.join(discord_usernames) if discord_usernames else 'None'
        
        log_action("ADD_PARTNER", f"User {message.author} added server as partner: {partner_name} with {projects_added} projects and {len(discord_usernames)} Discord users")
        await message.channel.send(f'✅ Partner **{partner_name}** added successfully!\n\n📊 **Information:**\n• **Server:** {guild.name}\n• **Discord Users:** {discord_users_display}\n• **Timezone:** {partner_timezone}\n• **Projects:** {projects_added} channels\n\n💡 **Next command:**\n• `!list_projects -p "{partner_name}"` - View project list\n• `!send -p "{partner_name}" -c "channel_name" | <content>` - Send message')
        
    except Exception as e:
        log_action("ERROR", f"Add partner error: {e}")
        await message.channel.send(f'❌ An error occurred: {e}')

# Hàm xử lý lệnh !list_partners
async def handle_list_partners(message):
    """Xử lý lệnh !list_partners"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Lấy thông tin partners đơn giản - chỉ thông tin cần thiết
        cur.execute('''
            SELECT pt.partner_id, pt.partner_name, pt.timezone,
                   GROUP_CONCAT(p.project_name, ', ') as projects,
                   COUNT(DISTINCT p.project_id) as project_count
            FROM partners pt
            LEFT JOIN projects p ON pt.partner_id = p.partner_id
            GROUP BY pt.partner_id, pt.partner_name, pt.timezone
            ORDER BY pt.partner_name
        ''')
        rows = cur.fetchall()
        
        if not rows:
            conn.close()
            await message.channel.send('❌ No partners found in the system.')
            return
        
        # Lấy tất cả Discord users cho tất cả partners và convert sang username
        partner_discord_users = {}
        for row in rows:
            cur.execute('''
                SELECT discord_username FROM partner_discord_users 
                WHERE partner_id = ?
            ''', (row['partner_id'],))
            discord_users = cur.fetchall()
            
            # Convert Discord User IDs sang usernames
            discord_usernames = []
            for user in discord_users:
                username = user['discord_username']
                if username.startswith('<@') and username.endswith('>'):
                    # User ID mention - convert sang username
                    user_id = username[2:-1]  # Bỏ <@ và >
                    discord_usernames.append(f"@{user_id}")
                else:
                    # Username thường - thêm @
                    clean_username = username.replace('@', '')
                    discord_usernames.append(f"@{clean_username}")
            
            partner_discord_users[row['partner_id']] = ', '.join(discord_usernames) if discord_usernames else "N/A"
        
        conn.close()
        
        # Tạo message đơn giản - không dùng bảng
        msg = '**👥 Partner List:**\n\n'
        
        for row in rows:
            # Lấy danh sách Discord users cho partner này
            discord_info = partner_discord_users.get(row['partner_id'], "N/A")
            
            # Format danh sách projects - loại bỏ trùng lặp
            projects_list = row["projects"] if row["projects"] else "N/A"
            if projects_list != "N/A":
                # Loại bỏ trùng lặp trong danh sách projects
                unique_projects = list(set([p.strip() for p in projects_list.split(',')]))
                projects_list = ', '.join(unique_projects)
            
            project_count = str(row["project_count"]) if row["project_count"] else "0"
            
            msg += f'**📋 {row["partner_name"]}**\n'
            msg += f'   • Discord: {discord_info}\n'
            msg += f'   • Timezone: {row["timezone"]}\n'
            msg += f'   • Projects: {project_count}\n'
            msg += f'   • Projects: {projects_list}\n\n'
        
        await message.channel.send(msg)
        
    except Exception as e:
        log_action("ERROR", f"List partners error: {e}")
        await message.channel.send(f'❌ An error occurred: {e}')

# Hàm xử lý lệnh !info_partner
async def handle_info_partner(message):
    """Handle !info_partner command (English)"""
    try:
        args = shlex.split(message.content)
        if len(args) < 2:
            await message.channel.send('❌ Invalid syntax! Dùng: !info_partner <tên_partner_hoặc_discord_username>')
            return
        
        partner_identifier = args[1].strip()
        
        conn = get_db_connection()
        partner = find_partner_by_name_or_username(conn, partner_identifier)
        
        if not partner:
            conn.close()
            await message.channel.send(f'❌ Không tìm thấy partner với tên hoặc username: **{partner_identifier}**')
            return
        
        # Lấy thông tin chi tiết về partner
        cur = conn.cursor()
        
        # Lấy danh sách projects
        cur.execute('''
            SELECT project_name, created_at
            FROM projects
            WHERE partner_id = ?
            ORDER BY project_name
        ''', (partner['partner_id'],))
        projects = cur.fetchall()
        
        # Lấy thống kê messages
        cur.execute('''
            SELECT 
                COUNT(*) as total_messages,
                SUM(CASE WHEN status = 'request' THEN 1 ELSE 0 END) as request_count,
                SUM(CASE WHEN status IN ('nhận order', 'order received') THEN 1 ELSE 0 END) as order_count,
                SUM(CASE WHEN status IN ('gửi lại bản build', 'build sent') THEN 1 ELSE 0 END) as build_count,
                SUM(CASE WHEN status = 'test pass' THEN 1 ELSE 0 END) as test_count,
                SUM(CASE WHEN status = 'release app' THEN 1 ELSE 0 END) as release_count
            FROM messages
            WHERE partner_id = ?
        ''', (partner['partner_id'],))
        stats = cur.fetchone()
        
        # Lấy tin nhắn gần đây
        cur.execute('''
            SELECT content, status, timestamp, reply_timestamp
            FROM messages
            WHERE partner_id = ?
            ORDER BY timestamp DESC
            LIMIT 5
        ''', (partner['partner_id'],))
        recent_messages = cur.fetchall()
        
        conn.close()
        
        # Format thông tin
        partner_timezone = partner.get('timezone', '+07:00')
        
        # Tạo message
        msg = f'**📊 Partner Information: {partner["partner_name"]}**\n\n'
        msg += f'**🔧 Basic Information:**\n'
        msg += f'• **Server ID:** {partner["server_id"]}\n'
        msg += f'• **Timezone:** {partner_timezone}\n'
        msg += f'• **Discord Users:** {partner.get("discord_username", "N/A")}\n\n'
        
        # Thống kê messages
        if stats and stats['total_messages'] > 0:
            total = stats['total_messages']
            msg += f'**📈 Message Statistics:**\n'
            msg += f'• **Total:** {total}\n'
            msg += f'• **Request:** {stats["request_count"]} ({stats["request_count"]/total*100:.1f}%)\n'
            msg += f'• **Order Received:** {stats["order_count"]} ({stats["order_count"]/total*100:.1f}%)\n'
            msg += f'• **Build Sent:** {stats["build_count"]} ({stats["build_count"]/total*100:.1f}%)\n'
            msg += f'• **Test Pass:** {stats["test_count"]} ({stats["test_count"]/total*100:.1f}%)\n'
            msg += f'• **Release App:** {stats["release_count"]} ({stats["release_count"]/total*100:.1f}%)\n\n'
        
        # Danh sách projects
        if projects:
            msg += f'**📁 Projects ({len(projects)}):**\n'
            for project in projects:
                msg += f'• {project["project_name"]}\n'
            msg += '\n'
        
        # Tin nhắn gần đây
        if recent_messages:
            msg += f'**💬 Recent messages:**\n'
            for msg_data in recent_messages:
                status = msg_data['status']
                content = msg_data['content']
                timestamp = msg_data['timestamp']
                reply_timestamp = msg_data['reply_timestamp'] if 'reply_timestamp' in msg_data.keys() else None
                # Thời gian cập nhật trạng thái (reply_timestamp nếu có, nếu không thì timestamp)
                update_time = reply_timestamp if reply_timestamp else timestamp
                # Định dạng thời gian cập nhật trạng thái (ngắn, +07:00)
                update_time_str = ''
                if update_time:
                    try:
                        update_time_str = str(update_time)[:19].replace('T', ' ') + ' (+07:00)'
                    except:
                        update_time_str = str(update_time) + ' (+07:00)'
                msg += f'• {status}  {update_time_str}\n{content}\n'
        
        await message.channel.send(msg)
        
    except Exception as e:
        log_action("ERROR", f"Info partner error: {e}")
        await message.channel.send(f'❌ Error: {e}')

# Hàm xử lý lệnh !set_timezone
async def handle_set_timezone(message):
    """Handle !set_timezone command (English)"""
    try:
        args = shlex.split(message.content)
        if len(args) < 3:
            await message.channel.send('❌ Invalid syntax! Use: !set_timezone <partner_name> <timezone>\n\n**Example:**\n• `!set_timezone "Client A" +05:30`\n• `!set_timezone "Client B" -05:00`')
            return
        partner_name = args[1].strip()
        new_timezone = args[2].strip()
        if not new_timezone.startswith(('+', '-')):
            await message.channel.send('❌ Timezone must start with + or - (e.g. +07:00, +05:30)')
            return
        try:
            get_partner_time_with_timezone(new_timezone)
        except:
            await message.channel.send('❌ Invalid timezone! Use format: +07:00, +05:30, -05:00')
            return
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT partner_id, partner_name FROM partners WHERE partner_name = ?', (partner_name,))
        partner = cur.fetchone()
        if not partner:
            conn.close()
            await message.channel.send(f'❌ Partner not found: **{partner_name}**')
            return
        cur.execute('UPDATE partners SET timezone = ? WHERE partner_id = ?', (new_timezone, partner['partner_id']))
        conn.commit()
        conn.close()
        log_action("SET_TIMEZONE", f"User {message.author} updated timezone for {partner_name}: {new_timezone}")
        await message.channel.send(f'✅ Timezone for **{partner_name}** updated to **{new_timezone}**')
    except Exception as e:
        log_action("ERROR", f"Set timezone error: {e}")
        await message.channel.send(f'❌ Error: {e}')

# Hàm xử lý lệnh !delete_partner
async def handle_delete_partner(message):
    """Xử lý lệnh !delete_partner"""
    try:
        args = shlex.split(message.content)
        if len(args) < 2:
            await message.channel.send('❌ Invalid syntax! Dùng: !delete_partner <tên_partner>')
            return
        
        partner_name = args[1].strip()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Tìm partner
        cur.execute('SELECT partner_id, partner_name FROM partners WHERE partner_name = ?', (partner_name,))
        partner = cur.fetchone()
        
        if not partner:
            conn.close()
            await message.channel.send(f'❌ Partner not found: **{partner_name}**')
            return
        
        # Xóa tất cả dữ liệu liên quan
        cur.execute('DELETE FROM messages WHERE partner_id = ?', (partner['partner_id'],))
        cur.execute('DELETE FROM projects WHERE partner_id = ?', (partner['partner_id'],))
        cur.execute('DELETE FROM partner_discord_users WHERE partner_id = ?', (partner['partner_id'],))
        cur.execute('DELETE FROM partners WHERE partner_id = ?', (partner['partner_id'],))
        
        conn.commit()
        conn.close()
        
        log_action("DELETE_PARTNER", f"User {message.author} deleted partner: {partner_name}")
        await message.channel.send(f'✅ Partner **{partner_name}** and all related data deleted')
        
    except Exception as e:
        log_action("ERROR", f"Delete partner error: {e}")
        await message.channel.send(f'❌ An error occurred: {e}') 

# Hàm xử lý lệnh !update_discord_user
async def handle_update_discord_user(message):
    """Handle !update_discord_user command (English)"""
    try:
        # Parse command: !update_discord_user -p <partner_name> <@old_user> <@new_user>
        content = message.content.strip()
        # Use shlex.split to correctly handle quoted arguments
        args = shlex.split(content)
        
        log_action("DEBUG", f"Update Discord user command: {content}")
        log_action("DEBUG", f"Parsed args: {args}")
        
        if len(args) < 5 or args[1] != '-p':
            await message.channel.send('❌ Invalid syntax! Use: `!update_discord_user -p <partner_name> <@old_user> <@new_user>`')
            return
        
        # shlex.split already handles stripping quotes, so no .strip() needed
        partner_name = args[2]
        old_discord_user = args[3]
        new_discord_user = args[4]
        
        log_action("DEBUG", f"Looking for partner: '{partner_name}'")
        
        # Validate Discord user format
        if not (old_discord_user.startswith('<@') and old_discord_user.endswith('>')):
            await message.channel.send('❌ Invalid old Discord user format! Use: @username or <@user_id>')
            return
        
        if not (new_discord_user.startswith('<@') and new_discord_user.endswith('>')):
            await message.channel.send('❌ Invalid new Discord user format! Use: @username or <@user_id>')
            return
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Debug: Kiểm tra tất cả partners
        cur.execute('SELECT partner_id, partner_name FROM partners')
        all_partners = cur.fetchall()
        log_action("DEBUG", f"All partners in DB: {all_partners}")
        
        # Find partner
        partner = find_partner_by_name_or_username(conn, partner_name)
        if not partner:
            conn.close()
            await message.channel.send(f'❌ Partner not found: **{partner_name}**')
            return
        
        log_action("DEBUG", f"Found partner: {partner['partner_name']} (ID: {partner['partner_id']})")
        
        # Get current Discord users
        current_discord_users = partner.get('discord_username', '')
        log_action("DEBUG", f"Current Discord users: '{current_discord_users}'")
        
        # Check if old user exists in current users
        if old_discord_user not in current_discord_users:
            conn.close()
            await message.channel.send(f'❌ Discord user **{old_discord_user}** not found for partner **{partner_name}**')
            return
        
        # Replace old user with new user
        updated_discord_users = current_discord_users.replace(old_discord_user, new_discord_user)
        log_action("DEBUG", f"Updated Discord users: '{updated_discord_users}'")
        
        # Update Discord users in partner_discord_users table
        # First, delete the old user
        cur.execute('''
            DELETE FROM partner_discord_users 
            WHERE partner_id = ? AND discord_username = ?
        ''', (partner['partner_id'], old_discord_user))
        
        # Then, add the new user
        cur.execute('''
            INSERT INTO partner_discord_users (partner_id, discord_username, tag_type)
            VALUES (?, ?, ?)
        ''', (partner['partner_id'], new_discord_user, 'user_mention'))
        
        conn.commit()
        conn.close()
        
        # Get updated Discord users for display
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT discord_username FROM partner_discord_users 
            WHERE partner_id = ?
        ''', (partner['partner_id'],))
        updated_users = cur.fetchall()
        updated_discord_users_display = ', '.join([u['discord_username'] for u in updated_users]) if updated_users else 'None'
        conn.close()
        
        # Log action
        log_action("UPDATE_DISCORD_USER", f"User {message.author} updated Discord user for {partner_name}: {old_discord_user} → {new_discord_user}")
        
        # Send confirmation
        report = f'**✅ Discord User Updated for {partner["partner_name"]}:**\n'
        report += f'• **Old:** {old_discord_user}\n'
        report += f'• **New:** {new_discord_user}\n'
        report += f'• **Updated by:** {message.author.display_name}\n'
        report += f'• **Current users:** {updated_discord_users_display}'
        
        await message.channel.send(report)
        
    except Exception as e:
        log_action("ERROR", f"Update Discord user error: {e}")
        await message.channel.send(f'❌ Error: {e}') 