from datetime import datetime, timezone, timedelta

def format_time_with_timezones(utc_timestamp, my_timezone='+07:00', partner_timezone=None):
    try:
        if isinstance(utc_timestamp, str):
            utc_time = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
        else:
            utc_time = utc_timestamp
        if utc_time.tzinfo is None:
            utc_time = utc_time.replace(tzinfo=timezone.utc)
        elif utc_time.tzinfo != timezone.utc:
            utc_time = utc_time.astimezone(timezone.utc)
        if my_timezone.startswith('+'):
            my_offset = timedelta(hours=int(my_timezone[1:3]), minutes=int(my_timezone[4:6]))
        else:
            my_offset = timedelta(hours=-int(my_timezone[1:3]), minutes=-int(my_timezone[4:6]))
        my_tz = timezone(my_offset)
        my_time = utc_time.astimezone(my_tz)
        my_formatted = my_time.strftime("%Y-%m-%d %H:%M:%S")
        if not partner_timezone or partner_timezone == my_timezone:
            return f"{my_formatted} ({my_timezone})"
        if partner_timezone.startswith('+'):
            partner_offset = timedelta(hours=int(partner_timezone[1:3]), minutes=int(partner_timezone[4:6]))
        else:
            partner_offset = timedelta(hours=-int(partner_timezone[1:3]), minutes=-int(partner_timezone[4:6]))
        partner_tz = timezone(partner_offset)
        partner_time = utc_time.astimezone(partner_tz)
        partner_formatted = partner_time.strftime("%Y-%m-%d %H:%M:%S")
        return f"{my_formatted} ({my_timezone})\n{partner_formatted} ({partner_timezone})"
    except Exception as e:
        return f"{utc_timestamp} (UTC)"

def normalize_name(name):
    return name.strip().lower().replace(' ', '_')

def format_timezone_display(timezone_str):
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

def get_partner_time_with_timezone(timezone_str):
    try:
        if not timezone_str:
            timezone_str = '+07:00'
        if timezone_str.startswith('+'):
            hours = int(timezone_str[1:3])
            minutes = int(timezone_str[4:6]) if len(timezone_str) > 5 else 0
            offset = timedelta(hours=hours, minutes=minutes)
        elif timezone_str.startswith('-'):
            hours = int(timezone_str[1:3])
            minutes = int(timezone_str[4:6]) if len(timezone_str) > 5 else 0
            offset = timedelta(hours=-hours, minutes=-minutes)
        else:
            offset = timedelta(hours=7)
        utc_now = datetime.now(timezone.utc)
        partner_time = utc_now.astimezone(timezone(offset))
        return partner_time.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def validate_message_content(content):
    if not content or len(content.strip()) == 0:
        return False, "Message content cannot be empty."
    if len(content) > 2000:
        return False, "Message content is too long (maximum 2000 characters)."
    return True, ""

def create_tag_message(conn, partner_id):
    try:
        cur = conn.cursor()
        
        # Lấy tên partner
        cur.execute('SELECT partner_name FROM partners WHERE partner_id = ?', (partner_id,))
        partner_result = cur.fetchone()
        if not partner_result:
            return "Dear @everyone,"
        
        partner_name = partner_result[0]
        
        # Lấy Discord username của partner
        cur.execute('''
            SELECT discord_username, tag_type
            FROM partner_discord_users
            WHERE partner_id = ?
        ''', (partner_id,))
        discord_users = cur.fetchall()
        
        if not discord_users:
            # Nếu không có Discord user, sử dụng tên partner
            clean_partner_name = normalize_name(partner_name)
            return f"Dear @{clean_partner_name},"
        
        # Lấy username đầu tiên
        user = discord_users[0]
        if hasattr(user, 'keys'):  # Nếu là dict-like object
            discord_username = user['discord_username']
        else:  # Nếu là tuple
            discord_username = user[0]
        
        # Sử dụng Discord ID để tạo mention thực sự
        if discord_username.startswith('<@') and discord_username.endswith('>'):
            # Nếu đã có format mention, sử dụng luôn
            return f"Dear {discord_username},"
        elif discord_username.isdigit():
            # Nếu là Discord ID số, tạo mention format
            return f"Dear <@{discord_username}>,"
        else:
            # Nếu là username thực tế, cần lấy Discord ID từ database hoặc API
            # Tạm thời sử dụng username nhưng không có notification
            clean_username = discord_username.replace('@', '')
            return f"Dear @{clean_username},"
        
    except Exception as e:
        print(f"Error in create_tag_message: {e}")
        return "Dear @everyone," 