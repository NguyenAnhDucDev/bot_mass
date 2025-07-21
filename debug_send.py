import sqlite3
import shlex

# Test parse command
command = '!send -p "hoàng_thượng" -c -all -p "huy" -c "apb868" | test report2'
command_part, message_content = command.split('|', 1)
print(f"Command part: {command_part}")
print(f"Message content: {message_content}")

# Parse arguments
args = shlex.split(command_part)
print(f"Args: {args}")

partners_config = []
current_partner = None
current_channels = []
current_send_all = False

i = 1
while i < len(args):
    if args[i] == '-p':
        # Save previous partner config if exists
        if current_partner:
            partners_config.append((current_partner, current_channels, current_send_all))
        
        # Start new partner
        if i + 1 < len(args):
            current_partner = args[i + 1].strip()
            current_channels = []
            current_send_all = False
            i += 2
        else:
            print('❌ Invalid syntax! -p must be followed by a partner name')
            exit(1)
    elif args[i] == '-c':
        if i + 1 < len(args):
            if args[i + 1].strip() == '-all':
                current_send_all = True
                i += 2
            else:
                current_channels.append(args[i + 1].strip())
                i += 2
        else:
            print('❌ Invalid syntax! -c must be followed by a channel name or -all')
            exit(1)
    else:
        i += 1

# Add last partner config
if current_partner:
    partners_config.append((current_partner, current_channels, current_send_all))

print(f"Partners config: {partners_config}")

# Test database
conn = sqlite3.connect('bot_database.db')
cur = conn.cursor()

# Check all partners
cur.execute('SELECT partner_id, partner_name FROM partners')
partners = cur.fetchall()
print(f"All partners: {partners}")

# Check all projects
cur.execute('SELECT project_id, project_name, partner_id FROM projects')
projects = cur.fetchall()
print(f"All projects: {projects}")

conn.close() 