from modules.db_utils import get_db_connection, log_action
from modules.utils import format_time_with_timezones, validate_message_content, create_tag_message
from modules.partner import find_partner_by_name_or_username
from modules.project import find_project_by_code
import discord
import shlex
import asyncio
from datetime import datetime

# Hàm xử lý lệnh !send
async def handle_send(message):
    """Handle !send command (English)"""
    try:
        # Parse command: !send -p partner -c channel1 -c channel2 | content
        content = message.content
        
        # Split content after |
        if '|' not in content:
            await message.channel.send('❌ Invalid syntax! Use: !send -p <partner> -c <channel1> -c <channel2> | <content>')
            return
        
        command_part, message_content = content.split('|', 1)
        message_content = message_content.strip()
        
        # Validation content
        is_valid, error_msg = validate_message_content(message_content)
        if not is_valid:
            await message.channel.send(f'❌ {error_msg}')
            return
        
        # Parse arguments
        args = shlex.split(command_part)
        partners_config = []  # List of (partner_name, channels, send_all, send_specific) tuples
        current_partner = None
        current_channels = []
        current_send_all = False
        current_send_specific = False
        
        i = 1
        while i < len(args):
            if args[i] == '-p':
                # Save previous partner config if exists
                if current_partner:
                    partners_config.append((current_partner, current_channels, current_send_all, current_send_specific))
                
                # Start new partner
                if i + 1 < len(args):
                    current_partner = args[i + 1].strip()
                    current_channels = []
                    current_send_all = False
                    current_send_specific = False
                    i += 2
                else:
                    await message.channel.send('❌ Invalid syntax! -p must be followed by a partner name')
                    return
            elif args[i] == '-all':
                # Handle -all as a special partner
                if current_partner:
                    partners_config.append((current_partner, current_channels, current_send_all, current_send_specific))
                
                current_partner = '-all'
                current_channels = []
                current_send_all = False
                current_send_specific = False
                i += 1
            elif args[i] == '-c':
                if i + 1 < len(args):
                    if args[i + 1].strip() == '-all':
                        current_send_all = True
                        i += 2
                    else:
                        current_channels.append(args[i + 1].strip())
                        current_send_specific = True  # Đánh dấu là gửi cụ thể
                        i += 2
                else:
                    await message.channel.send('❌ Invalid syntax! -c must be followed by a channel name or -all')
                    return
            else:
                i += 1
        
        # Add last partner config
        if current_partner:
            partners_config.append((current_partner, current_channels, current_send_all, current_send_specific))
        
        if not partners_config:
            await message.channel.send('❌ Invalid syntax! You must specify at least one partner with -p')
            return
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        all_projects_to_send = []
        all_partners_info = []
        
        # Process each partner
        for partner_name, channels, send_all, send_specific in partners_config:
            # Debug log
            log_action("DEBUG", f"Processing partner: {partner_name}, channels: {channels}, send_all: {send_all}, send_specific: {send_specific}")
            
            # Handle -all special case
            if partner_name == '-all':
                # Get all partners from database
                cur.execute('SELECT partner_id, partner_name FROM partners ORDER BY partner_name')
                all_partners = cur.fetchall()
                log_action("DEBUG", f"Found {len(all_partners)} total partners for -all")
                
                for partner_row in all_partners:
                    partner = {'partner_id': partner_row[0], 'partner_name': partner_row[1]}
                    log_action("DEBUG", f"Processing -all partner: {partner['partner_name']}")
                    
                    # Luôn lấy toàn bộ projects của partner để tracking
                    cur.execute('SELECT project_id, project_name, channel_id FROM projects WHERE partner_id = ?', (partner['partner_id'],))
                    all_partner_projects = cur.fetchall()
                    log_action("DEBUG", f"Found {len(all_partner_projects)} total projects for {partner['partner_name']}")
                    
                    if not all_partner_projects:
                        log_action("DEBUG", f"No projects found for partner {partner['partner_name']}")
                        continue
                    
                    # Với -all, luôn gửi đến tất cả projects
                    projects_to_send = all_partner_projects
                    log_action("DEBUG", f"Sending to all {len(projects_to_send)} projects for {partner['partner_name']}")
                    
                    log_action("DEBUG", f"Total projects to send for {partner['partner_name']}: {len(projects_to_send)}")
                    if projects_to_send:
                        all_projects_to_send.extend(projects_to_send)
                        all_partners_info.append((partner, projects_to_send, all_partner_projects))
                
                continue  # Skip normal processing for -all
            
            # Find partner
            partner = find_partner_by_name_or_username(conn, partner_name)
            if not partner:
                await message.channel.send(f'❌ Partner not found: **{partner_name}**')
                continue
            
            # Luôn lấy toàn bộ projects của partner để tracking
            cur.execute('SELECT project_id, project_name, channel_id FROM projects WHERE partner_id = ?', (partner['partner_id'],))
            all_partner_projects = cur.fetchall()
            log_action("DEBUG", f"Found {len(all_partner_projects)} total projects for {partner_name}")
            
            if not all_partner_projects:
                await message.channel.send(f'❌ No projects found for partner **{partner_name}**')
                continue
            
            # Xác định projects cần gửi theo lệnh
            if send_specific and channels:
                # Nếu chỉ định channels cụ thể, chỉ gửi đến những project đó
                projects_to_send = []
                for channel_name in channels:
                    cur.execute('''
                        SELECT project_id, project_name, channel_id
                        FROM projects
                        WHERE partner_id = ? AND LOWER(SUBSTR(project_name, 1, 6)) = LOWER(?)
                    ''', (partner['partner_id'], channel_name[:6]))
                    found_projects = cur.fetchall()
                    log_action("DEBUG", f"Found {len(found_projects)} projects for {partner_name} with channel {channel_name}")
                    if not found_projects:
                        await message.channel.send(f'❌ Channel **{channel_name}** not found in partner **{partner_name}**')
                        continue
                    projects_to_send.extend(found_projects)
            else:
                # Nếu có -all hoặc không chỉ định channels, gửi đến tất cả projects
                projects_to_send = all_partner_projects
                log_action("DEBUG", f"Sending to all {len(projects_to_send)} projects for {partner_name}")
            
            log_action("DEBUG", f"Total projects to send for {partner_name}: {len(projects_to_send)}")
            if projects_to_send:
                all_projects_to_send.extend(projects_to_send)
                all_partners_info.append((partner, projects_to_send, all_partner_projects))  # Thêm all_partner_projects để tracking
        
        if not all_projects_to_send:
            conn.close()
            await message.channel.send('❌ No valid channels found to send the message')
            return
        
        # Send message to each channel
        sent_count = 0
        failed_channels = []
        
        log_action("DEBUG", f"Total projects to send: {len(all_projects_to_send)}")
        
        for project in all_projects_to_send:
            try:
                log_action("DEBUG", f"Processing project: {project['project_name']} with channel_id: {project['channel_id']}")
                
                channel_id = int(project['channel_id']) if not isinstance(project['channel_id'], int) else project['channel_id']
                
                # Tìm channel trong tất cả servers mà bot tham gia (cross-server)
                channel = None
                client = message._state._get_client()
                for guild in client.guilds:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        log_action("DEBUG", f"Found channel {channel.name} in server {guild.name}")
                        break
                
                if not channel:
                    log_action("DEBUG", f"Channel_id not found: {channel_id} for project {project['project_name']} in any server")
                    failed_channels.append(project['project_name'])
                    continue
                
                log_action("DEBUG", f"Found channel: {channel.name} for project {project['project_name']}")
                
                # Find partner for this project
                partner_for_project = None
                for partner_info, projects_to_send, all_partner_projects in all_partners_info:
                    if any(p['project_id'] == project['project_id'] for p in projects_to_send):
                        partner_for_project = partner_info
                        break
                
                log_action("DEBUG", f"Partner for project {project['project_name']}: {partner_for_project['partner_name']}")
                
                try:
                    tag_message = create_tag_message(conn, partner_for_project['partner_id'])
                    log_action("DEBUG", f"Tag message for {project['project_name']}: {tag_message}")
                    full_message = f"{tag_message}\n\n{message_content}"
                    log_action("DEBUG", f"Full message for {project['project_name']}: {full_message}")
                    discord_message = await channel.send(full_message)
                    cur.execute('''
                        INSERT INTO messages (partner_id, project_id, content, discord_message_id, status, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (partner_for_project['partner_id'], project['project_id'], message_content, discord_message.id, 'request', datetime.now().isoformat()))
                    sent_count += 1
                    log_action("DEBUG", f"Successfully sent to {project['project_name']}")
                except Exception as e:
                    log_action("ERROR", f"Failed to send message to {project['project_name']}: {e}")
                    failed_channels.append(project['project_name'])
            except Exception as e:
                log_action("ERROR", f"Failed to process project {project['project_name']}: {e}")
                failed_channels.append(project['project_name'])
        conn.commit()
        conn.close()
        # Tạo báo cáo cho tất cả partners trong hệ thống
        reports = []
        
        # Lấy tất cả partners từ database
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT partner_id, partner_name FROM partners ORDER BY partner_name')
        all_partners = cur.fetchall()
        conn.close()
        
        # Tạo mapping partner_id -> trạng thái gửi
        sent_partners = set([partner['partner_id'] for partner, _, _ in all_partners_info])
        
        for partner_data in all_partners:
            partner_id = partner_data['partner_id']
            partner_name = partner_data['partner_name']
            
            # Kiểm tra xem partner này có được gửi không
            if partner_id in sent_partners:
                # Partner này được gửi - tìm thông tin chi tiết
                partner_info = None
                projects_to_send = []
                all_partner_projects = []
                
                for p_info, p_projects, p_all_projects in all_partners_info:
                    if p_info['partner_id'] == partner_id:
                        partner_info = p_info
                        projects_to_send = p_projects
                        all_partner_projects = p_all_projects
                        break
                
                if partner_info:
                    # Tạo mapping project_name -> trạng thái gửi
                    sent_projects = set([p['project_name'] for p in projects_to_send if p['project_name'] not in failed_channels])
                    failed_projects = set([p['project_name'] for p in projects_to_send if p['project_name'] in failed_channels])
                    
                    # Báo cáo cho partner này - hiển thị tất cả projects
                    report = f'- {partner_name}:'
                    
                    # Hiển thị tất cả projects của partner này
                    for p in all_partner_projects:
                        if p['project_name'] in sent_projects:
                            report += f'\n    • {p["project_name"]}: The request has been sent to this project.'
                        elif p['project_name'] in failed_projects:
                            report += f'\n    • {p["project_name"]}: Failed to send the request.'
                        else:
                            report += f'\n    • {p["project_name"]}: This project didn\'t get the request.'
                else:
                    report = f'- {partner_name}: No projects were processed for this partner.'
            else:
                # Partner này không được gửi
                report = f'- {partner_name}: This partner was not included in the send request.'
            
            reports.append(report)
        
        # Gửi Send Report một lần duy nhất
        log_action("DEBUG", f"Final sent_count: {sent_count}")
        log_action("DEBUG", f"Failed channels: {failed_channels}")
        
        if sent_count > 0:
            await message.channel.send(f'**Send Report:**\n' + '\n'.join(reports))
        else:
            await message.channel.send('❌ Failed to send message to any channel')
    except Exception as e:
        log_action("ERROR", f"Send message error: {e}")
        await message.channel.send(f'❌ Error: {e}')

# Hàm xử lý lệnh !list (tracking messages)
async def handle_list_messages(message):
    """Handle !list command (English)"""
    try:
        args = shlex.split(message.content)
        
        # Parse arguments
        partners = []
        projects = []
        show_all = False
        
        i = 1
        while i < len(args):
            if args[i] == '-p':
                if i + 1 < len(args):
                    partners.append(args[i + 1].strip())
                    i += 2
                else:
                    await message.channel.send('❌ Invalid syntax! -p must be followed by a partner name')
                    return
            elif args[i] == '-c':
                if i + 1 < len(args):
                    projects.append(args[i + 1].strip())
                    i += 2
                else:
                    await message.channel.send('❌ Invalid syntax! -c must be followed by a project name')
                    return
            elif args[i] == '-all':
                show_all = True
                i += 1
            else:
                i += 1
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        if show_all:
            # Hiển thị tất cả messages
            cur.execute('''
                SELECT m.content, m.status, m.timestamp, pt.partner_name, p.project_name, pt.timezone
                FROM messages m
                JOIN partners pt ON m.partner_id = pt.partner_id
                JOIN projects p ON m.project_id = p.project_id
                ORDER BY m.timestamp DESC
                LIMIT 50
            ''')
            rows = cur.fetchall()
            
            if not rows:
                conn.close()
                await message.channel.send('❌ No messages found in the system.')
                return
            
            # Tạo message
            msg = '**📋 Recent messages (all):**\n\n'
            
            for row in rows:
                formatted_time = format_time_with_timezones(row['timestamp'], '+07:00', row['timezone'])
                content = row['content'][:100] + '...' if len(row['content']) > 100 else row['content']
                msg += f'**{row["status"]}** - {row["partner_name"]}/{row["project_name"]}\n'
                msg += f'• {content}\n'
                msg += f'• {formatted_time}\n\n'
            
            conn.close()
            await message.channel.send(msg)
            
        elif partners:
            # Hiển thị messages của các partners cụ thể
            all_messages = []
            
            for partner_name in partners:
                partner = find_partner_by_name_or_username(conn, partner_name)
                if not partner:
                    await message.channel.send(f'❌ Partner not found: **{partner_name}**')
                    continue
                
                # Build query based on projects filter
                if projects:
                    placeholders = ','.join(['?' for _ in projects])
                    cur.execute(f'''
                        SELECT m.content, m.status, m.timestamp, p.project_name, pt.timezone
                        FROM messages m
                        JOIN projects p ON m.project_id = p.project_id
                        JOIN partners pt ON m.partner_id = pt.partner_id
                        WHERE m.partner_id = ? AND p.project_name IN ({placeholders})
                        ORDER BY m.timestamp DESC
                        LIMIT 20
                    ''', [partner['partner_id']] + projects)
                else:
                    cur.execute('''
                        SELECT m.content, m.status, m.timestamp, p.project_name, pt.timezone
                        FROM messages m
                        JOIN projects p ON m.project_id = p.project_id
                        JOIN partners pt ON m.partner_id = pt.partner_id
                        WHERE m.partner_id = ?
                        ORDER BY m.timestamp DESC
                        LIMIT 20
                    ''', (partner['partner_id'],))
                
                messages = cur.fetchall()
                
                if messages:
                    all_messages.append({
                        'partner_name': partner['partner_name'],
                        'timezone': partner.get('timezone', '+07:00'),
                        'messages': messages
                    })
            
            conn.close()
            
            if not all_messages:
                await message.channel.send('❌ No messages found for the specified partners.')
                return
            
            # Tạo message
            msg = '**📋 Messages by Partners:**\n\n'
            
            for partner_data in all_messages:
                msg += f'**👥 {partner_data["partner_name"]}:**\n'
                for msg_data in partner_data['messages']:
                    formatted_time = format_time_with_timezones(msg_data['timestamp'], '+07:00', partner_data['timezone'])
                    content = msg_data['content'][:100] + '...' if len(msg_data['content']) > 100 else msg_data['content']
                    msg += f'• **{msg_data["status"]}** - {msg_data["project_name"]}\n'
                    msg += f'  {content}\n'
                    msg += f'  {formatted_time}\n\n'
            
            await message.channel.send(msg)
            
        else:
            # Hiển thị tất cả messages (mặc định)
            cur.execute('''
                SELECT m.content, m.status, m.timestamp, pt.partner_name, p.project_name, pt.timezone
                FROM messages m
                JOIN partners pt ON m.partner_id = pt.partner_id
                JOIN projects p ON m.project_id = p.project_id
                ORDER BY m.timestamp DESC
                LIMIT 30
            ''')
            rows = cur.fetchall()
            
            if not rows:
                conn.close()
                await message.channel.send('❌ No messages found in the system.')
                return
            
            # Tạo message
            msg = '**📋 Recent messages:**\n\n'
            
            for row in rows:
                formatted_time = format_time_with_timezones(row['timestamp'], '+07:00', row['timezone'])
                content = row['content'][:100] + '...' if len(row['content']) > 100 else row['content']
                msg += f'**{row["status"]}** - {row["partner_name"]}/{row["project_name"]}\n'
                msg += f'• {content}\n'
                msg += f'• {formatted_time}\n\n'
            
            conn.close()
            await message.channel.send(msg)
        
    except Exception as e:
        log_action("ERROR", f"List messages error: {e}")
        await message.channel.send(f'❌ Error: {e}')

# Hàm xử lý lệnh !message_status
async def handle_message_status(message):
    """Handle !message_status command (English)"""
    try:
        args = shlex.split(message.content)
        if len(args) < 3:
            await message.channel.send('❌ Invalid syntax! Use: !message_status <partner> <project> <status>')
            return
        
        partner_name = args[1].strip()
        project_name = args[2].strip()
        new_status = args[3].strip()
        
        # Validation status
        valid_statuses = ['request', 'order received', 'build sent', 'test pass', 'release app']
        if new_status not in valid_statuses:
            await message.channel.send(f'❌ Invalid status! Valid statuses: {", ".join(valid_statuses)}')
            return
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Find partner
        partner = find_partner_by_name_or_username(conn, partner_name)
        if not partner:
            conn.close()
            await message.channel.send(f'❌ Partner not found: **{partner_name}**')
            return
        
        # Find project
        cur.execute('''
            SELECT project_id, project_name
            FROM projects
            WHERE partner_id = ? AND project_name = ?
        ''', (partner['partner_id'], project_name))
        project = cur.fetchone()
        
        if not project:
            conn.close()
            await message.channel.send(f'❌ Project **{project_name}** not found in partner **{partner_name}**')
            return
        
        # Update status of the most recent message
        cur.execute('''
            UPDATE messages 
            SET status = ?, reply_timestamp = ?
            WHERE project_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (new_status, datetime.now().isoformat(), project['project_id']))
        
        if cur.rowcount == 0:
            conn.close()
            await message.channel.send(f'❌ No message found in project **{project_name}**')
            return
        
        conn.commit()
        conn.close()
        
        log_action("MESSAGE_STATUS", f"User {message.author} updated status for {partner_name}/{project_name}: {new_status}")
        await message.channel.send(f'✅ Successfully updated the status of the latest message in **{project_name}** to **{new_status}**')
        
    except Exception as e:
        log_action("ERROR", f"Message status error: {e}")
        await message.channel.send(f'❌ Error: {e}')

# Hàm xử lý lệnh !reply_rules (English)
async def handle_reply_rules(message):
    """Xử lý lệnh !reply_rules - Hướng dẫn partner reply tin nhắn để tracking tiến độ"""
    try:
        reply_rules_text = """**REPLY RULES FOR PARTNERS**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**How to Reply to Messages:**

When you receive a message from our bot, please reply with the following format to update the status:

**Request → Order Received:**
```
order_received | [Your response message]
```
**Example:**
```
order_received | Order received, we will start working on this project
```

**Order Received → Build Sent:**
```
resend_build | [Your response message]
```
**Example:**
```
resend_build | New build has been sent, please check and test
```

**Build Sent → Test Pass:**
```
pass_test | [Your response message]
```
**Example:**
```
pass_test | Testing completed successfully, all features working
```

**Test Pass → Release App:**
```
release_app | [Your response message]
```
**Example:**
```
release_app | App has been released to production
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Status Workflow:**
Request → Order Received → Build Sent → Test Pass → Release App

**Important Notes:**
• Status must follow the exact order above
• Use the exact keywords: `order_received`, `resend_build`, `pass_test`, `release_app`
• You can add any message after the `|` symbol
• If you reply with wrong format, status will not change
• Each status change will be logged and tracked
• Bot will show error messages in English if you reply incorrectly

**Tips:**
• Reply directly to the bot's message
• Make sure to use the exact keywords
• You can include additional information after the `|` symbol
• The bot will automatically update the status when you reply correctly
• Error messages will guide you to the correct format"""
        
        await message.channel.send(reply_rules_text)
        
    except Exception as e:
        log_action("ERROR", f"Reply rules error: {e}")
        await message.channel.send(f'❌ Error: {e}') 

# Hàm xử lý reply vào tin nhắn của bot để update status (English)
async def handle_status_reply(message):
    """Handle reply to bot message to update status (English)"""
    try:
        if not message.reference or not message.reference.resolved:
            return
        if message.reference.resolved.author.id != message.guild.me.id:
            return
        if '|' not in message.content:
            await message.channel.send("❌ **Wrong reply format!**\n\nPlease use: `<status_tag> | <your message>`\n\n**Valid status tags:**\n• `order_received` - Order received\n• `resend_build` - Build sent\n• `pass_test` - Test passed\n• `release_app` - App released\n\n**Example:** `order_received | Order received, starting work`")
            return
        parts = message.content.split('|', 1)
        if len(parts) != 2:
            await message.channel.send("❌ **Wrong format!** Use: `<status_tag> | <your message>`")
            return
        status_tag = parts[0].strip().lower()
        reply_content = parts[1].strip()
        valid_statuses = {
            'order_received': 'order received',
            'resend_build': 'build sent',
            'pass_test': 'test pass',
            'release_app': 'release app'
        }
        if status_tag not in valid_statuses:
            await message.channel.send(f"❌ **Invalid status tag!**\n\nValid tags: `order_received`, `resend_build`, `pass_test`, `release_app`\n\n**Example:** `order_received | Order received`")
            return
        original_message = message.reference.resolved
        original_message_id = original_message.id
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT m.message_id, m.partner_id, m.project_id, m.status, m.timestamp,
                   pt.partner_name, p.project_name, m.content
            FROM messages m
            JOIN partners pt ON m.partner_id = pt.partner_id
            JOIN projects p ON m.project_id = p.project_id
            WHERE m.discord_message_id = ?
        ''', (original_message_id,))
        messages_found = cur.fetchall()
        if not messages_found:
            conn.close()
            await message.channel.send("❌ **Message not found in database!**\n\nThis message was not sent through the bot system.")
            return
        if len(messages_found) > 1:
            await message.channel.send("⚠️ More than one message found in the DB with this discord_message_id! Please check your data.")
        message_data = messages_found[0]
        current_status = message_data[3]
        new_status = valid_statuses[status_tag]
        status_order = ['request', 'order received', 'build sent', 'test pass', 'release app']
        try:
            current_index = status_order.index(current_status)
            new_index = status_order.index(new_status)
            if new_index <= current_index:
                await message.channel.send(f"❌ **Invalid status progression!**\n\nCurrent status: **{current_status}**\nCannot go back to: **{new_status}**\n\n**Valid next status:** {status_order[current_index + 1] if current_index + 1 < len(status_order) else 'None (completed)'}")
                conn.close()
                return
        except ValueError:
            pass
        cur.execute('''
            UPDATE messages 
            SET status = ?, reply_timestamp = ?, reply_content = ?
            WHERE message_id = ?
        ''', (new_status, datetime.now().isoformat(), reply_content, message_data[0]))
        if cur.rowcount == 0:
            conn.close()
            await message.channel.send("❌ **Failed to update status!**")
            return
        conn.commit()
        conn.close()
        confirmation_msg = f"""✅ **Status Updated Successfully!**\n\n**Project:** {message_data[6]}\n**Partner:** {message_data[5]}\n**Previous Status:** {current_status}\n**New Status:** {new_status}\n**Your Reply:** {reply_content}\n\n**Status progression:** {current_status} → {new_status}"""
        log_action("STATUS_UPDATE", f"Partner {message_data[5]} updated status for {message_data[6]}: {current_status} → {new_status}")
        await message.channel.send(confirmation_msg)
    except Exception as e:
        log_action("ERROR", f"Status reply error: {e}")
        await message.channel.send(f"❌ Error processing reply: {str(e)}") 