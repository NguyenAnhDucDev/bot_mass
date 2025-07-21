from modules.db_utils import get_db_connection, log_action
from modules.utils import normalize_name, format_time_with_timezones
from modules.partner import find_partner_by_name_or_username
import discord
import shlex

# Hàm tìm project theo partner_id và mã project (6 ký tự đầu, không phân biệt hoa thường)
def find_project_by_code(conn, partner_id, project_code):
    cur = conn.cursor()
    cur.execute('''
        SELECT project_id, project_name, created_at
        FROM projects
        WHERE partner_id = ? AND LOWER(SUBSTR(project_name, 1, 6)) = LOWER(?)
        ORDER BY project_id
    ''', (partner_id, project_code[:6]))
    return cur.fetchone()

# Hàm xử lý lệnh !list_projects
async def handle_list_projects(message):
    """Handle !list_projects command (English)"""
    try:
        args = shlex.split(message.content)
        
        # Parse arguments
        partners = []
        show_all = False
        
        i = 1
        while i < len(args):
            if args[i] == '-p':
                if i + 1 < len(args):
                    partners.append(args[i + 1].strip())
                    i += 2
                else:
                    await message.channel.send('❌ Sai cú pháp! Sau -p phải có tên partner')
                    return
            elif args[i] == '-all':
                show_all = True
                i += 1
            else:
                i += 1
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        if show_all:
            # Hiển thị tất cả projects của tất cả partners
            cur.execute('''
                SELECT p.project_name, p.created_at, pt.partner_name, pt.timezone
                FROM projects p
                JOIN partners pt ON p.partner_id = pt.partner_id
                ORDER BY pt.partner_name, p.project_name
            ''')
            rows = cur.fetchall()
            
            if not rows:
                conn.close()
                await message.channel.send('❌ No projects found in the system.')
                return
            
            # Tạo message
            msg = '**�� All Projects:**\n\n'
            
            current_partner = None
            for row in rows:
                if current_partner != row['partner_name']:
                    current_partner = row['partner_name']
                    msg += f'**👥 {current_partner}:**\n'
                
                formatted_time = format_time_with_timezones(row['created_at'], '+07:00', row['timezone'])
                msg += f'• **{row["project_name"]}** - {formatted_time}\n'
            
            conn.close()
            await message.channel.send(msg)
            
        elif partners:
            # Hiển thị projects của các partners cụ thể
            all_projects = []
            
            for partner_name in partners:
                partner = find_partner_by_name_or_username(conn, partner_name)
                if not partner:
                    await message.channel.send(f'❌ Không tìm thấy partner: **{partner_name}**')
                    continue
                
                cur.execute('''
                    SELECT project_name, created_at
                    FROM projects
                    WHERE partner_id = ?
                    ORDER BY project_name
                ''', (partner['partner_id'],))
                projects = cur.fetchall()
                
                if projects:
                    all_projects.append({
                        'partner_name': partner['partner_name'],
                        'timezone': partner.get('timezone', '+07:00'),
                        'projects': projects
                    })
            
            conn.close()
            
            if not all_projects:
                await message.channel.send('❌ Không tìm thấy projects cho các partners đã chỉ định.')
                return
            
            # Tạo message
            msg = '**📁 Danh sách Projects:**\n\n'
            
            for partner_data in all_projects:
                msg += f'**👥 {partner_data["partner_name"]}:**\n'
                for project in partner_data['projects']:
                    formatted_time = format_time_with_timezones(project['created_at'], '+07:00', partner_data['timezone'])
                    msg += f'• **{project["project_name"]}** - {formatted_time}\n'
                msg += '\n'
            
            await message.channel.send(msg)
            
        else:
            # Hiển thị tất cả projects (mặc định)
            cur.execute('''
                SELECT p.project_name, p.created_at, pt.partner_name, pt.timezone
                FROM projects p
                JOIN partners pt ON p.partner_id = pt.partner_id
                ORDER BY pt.partner_name, p.project_name
            ''')
            rows = cur.fetchall()
            
            if not rows:
                conn.close()
                await message.channel.send('❌ No projects found in the system.')
                return
            
            # Tạo message
            msg = '**📁 All Projects:**\n\n'
            
            current_partner = None
            for row in rows:
                if current_partner != row['partner_name']:
                    current_partner = row['partner_name']
                    msg += f'**👥 {current_partner}:**\n'
                
                formatted_time = format_time_with_timezones(row['created_at'], '+07:00', row['timezone'])
                msg += f'• **{row["project_name"]}** - {formatted_time}\n'
            
            conn.close()
            await message.channel.send(msg)
        
    except Exception as e:
        log_action("ERROR", f"List projects error: {e}")
        await message.channel.send(f'❌ Error: {e}')

# Hàm xử lý lệnh !info_project
async def handle_info_project(message):
    """Handle !info_project command (English)"""
    try:
        args = shlex.split(message.content)
        partner_name = None
        project_code = None
        # Parse flags
        i = 1
        while i < len(args):
            if args[i] == '-p' and i+1 < len(args):
                partner_name = args[i+1].strip()
                i += 2
            elif args[i] == '-c' and i+1 < len(args):
                project_code = args[i+1].strip()
                i += 2
            else:
                # Nếu không có flag, lấy luôn làm project_code (giữ tương thích cũ)
                if not project_code:
                    project_code = args[i].strip()
                i += 1
        if not project_code:
            await message.channel.send('❌ Sai cú pháp! Dùng: !info_project -p <partner> -c <mã_project> hoặc !info_project <mã_project>')
            return
        conn = get_db_connection()
        cur = conn.cursor()
        if partner_name:
            # Tìm partner
            partner = find_partner_by_name_or_username(conn, partner_name)
            if not partner:
                conn.close()
                await message.channel.send(f'❌ Không tìm thấy partner: **{partner_name}**')
                return
            # Tìm project theo partner
            cur.execute('''
                SELECT p.project_id, p.project_name, p.created_at, pt.partner_name, pt.timezone
                FROM projects p
                JOIN partners pt ON p.partner_id = pt.partner_id
                WHERE p.partner_id = ? AND LOWER(SUBSTR(p.project_name, 1, 6)) = LOWER(?)
                ORDER BY pt.partner_name, p.project_name
            ''', (partner['partner_id'], project_code[:6]))
            projects = cur.fetchall()
        else:
            # Tìm toàn bộ
            cur.execute('''
                SELECT p.project_id, p.project_name, p.created_at, pt.partner_name, pt.timezone
                FROM projects p
                JOIN partners pt ON p.partner_id = pt.partner_id
                WHERE LOWER(SUBSTR(p.project_name, 1, 6)) = LOWER(?)
                ORDER BY pt.partner_name, p.project_name
            ''', (project_code[:6],))
            projects = cur.fetchall()
        if not projects:
            conn.close()
            await message.channel.send(f'❌ Không tìm thấy project với mã: {project_code}')
            return
        # Nếu có nhiều projects, hiển thị danh sách
        if len(projects) > 1:
            msg = f'**🔍 Tìm thấy {len(projects)} projects với mã "{project_code}":**\n\n'
            for project in projects:
                formatted_time = format_time_with_timezones(project['created_at'], '+07:00', project['timezone'])
                msg += f'• **{project["project_name"]}** ({project["partner_name"]}) - {formatted_time}\n'
            msg += f'\n💡 **Gợi ý:** Sử dụng tên partner cụ thể để xem chi tiết hơn.'
            conn.close()
            await message.channel.send(msg)
            return
        # Nếu chỉ có 1 project, hiển thị chi tiết
        project = projects[0]
        # Lấy thống kê messages cho project này
        cur.execute('''
            SELECT 
                COUNT(*) as total_messages,
                SUM(CASE WHEN status = 'request' THEN 1 ELSE 0 END) as request_count,
                SUM(CASE WHEN status IN ('nhận order', 'order received') THEN 1 ELSE 0 END) as order_count,
                SUM(CASE WHEN status IN ('gửi lại bản build', 'build sent') THEN 1 ELSE 0 END) as build_count,
                SUM(CASE WHEN status = 'test pass' THEN 1 ELSE 0 END) as test_count,
                SUM(CASE WHEN status = 'release app' THEN 1 ELSE 0 END) as release_count
            FROM messages
            WHERE project_id = ?
        ''', (project['project_id'],))
        stats = cur.fetchone()
        
        # Lấy tin nhắn gần đây
        cur.execute('''
            SELECT content, status, timestamp, reply_timestamp
            FROM messages
            WHERE project_id = ?
            ORDER BY timestamp DESC
            LIMIT 5
        ''', (project['project_id'],))
        recent_messages = cur.fetchall()
        
        conn.close()
        
        # Tạo message
        msg = f'**📊 Project Information: {project["project_name"]}**\n\n'
        msg += f'**🔧 Basic Information:**\n'
        msg += f'• **Partner:** {project["partner_name"]}\n'
        msg += f'• **Project ID:** {project["project_id"]}\n'
        msg += f'• **Created:** {format_time_with_timezones(project["created_at"], "+07:00", project["timezone"])}\n\n'
        
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
        
        # Tin nhắn gần đây
        if recent_messages:
            msg += f'**💬 Recent messages:**\n'
            status_emoji = {
                'request': '📝',
                'order received': '📥',
                'build sent': '📦',
                'test pass': '✅',
                'release app': '🚀',
                'nhận order': '📥',
                'gửi lại bản build': '📦'
            }
            for msg_data in recent_messages:
                status = msg_data['status']
                timestamp = msg_data['timestamp']
                reply_timestamp = msg_data['reply_timestamp']
                emoji = status_emoji.get(status, '💬')
                # Thời gian cập nhật trạng thái (reply_timestamp nếu có, nếu không thì timestamp)
                update_time = reply_timestamp if reply_timestamp else timestamp
                # Định dạng ngắn cho update_time
                update_time_str = ''
                if update_time:
                    try:
                        update_time_str = str(update_time)[:19].replace('T', ' ')
                    except:
                        update_time_str = str(update_time)
                formatted_time = format_time_with_timezones(timestamp, '+07:00', project['timezone'])
                content = msg_data['content']
                msg += f'{emoji} {status} ({update_time_str})\n{content}\n{formatted_time}\n'
        await message.channel.send(msg)
    except Exception as e:
        log_action("ERROR", f"Info project error: {e}")
        await message.channel.send(f'❌ Error: {e}')

# Hàm xử lý lệnh !delete_project
async def handle_delete_project(message):
    """Handle !delete_project command (English)"""
    try:
        args = shlex.split(message.content)
        if len(args) < 2:
            await message.channel.send('❌ Invalid syntax! Use: !delete_project <project_name>')
            return
        project_name = args[1].strip()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT p.project_id, p.project_name, pt.partner_name
            FROM projects p
            JOIN partners pt ON p.partner_id = pt.partner_id
            WHERE p.project_name = ?
        ''', (project_name,))
        project = cur.fetchone()
        if not project:
            conn.close()
            await message.channel.send(f'❌ Project not found: **{project_name}**')
            return
        cur.execute('DELETE FROM messages WHERE project_id = ?', (project['project_id'],))
        cur.execute('DELETE FROM projects WHERE project_id = ?', (project['project_id'],))
        conn.commit()
        conn.close()
        log_action("DELETE_PROJECT", f"User {message.author} deleted project: {project_name} from {project['partner_name']}")
        await message.channel.send(f'✅ Project **{project_name}** deleted from partner **{project["partner_name"]}**')
    except Exception as e:
        log_action("ERROR", f"Delete project error: {e}")
        await message.channel.send(f'❌ Error: {e}') 