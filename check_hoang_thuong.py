import sqlite3

conn = sqlite3.connect('bot_database.db')
cur = conn.cursor()

# Kiểm tra tất cả partners
cur.execute('SELECT partner_id, partner_name FROM partners')
partners = cur.fetchall()
print('All Partners:', partners)

# Kiểm tra tất cả projects
cur.execute('SELECT project_id, project_name, partner_id FROM projects')
projects = cur.fetchall()
print('All Projects:', projects)

# Kiểm tra partner hoàng_thượng
cur.execute('SELECT partner_id, partner_name FROM partners WHERE partner_name LIKE "%hoàng_thượng%"')
partners_hoang = cur.fetchall()
print('Partners hoàng_thượng:', partners_hoang)

if partners_hoang:
    partner_id = partners_hoang[0][0]
    print(f'Partner ID: {partner_id}')
    
    # Kiểm tra projects của partner này
    cur.execute('SELECT project_id, project_name, channel_id FROM projects WHERE partner_id = ?', (partner_id,))
    projects_hoang = cur.fetchall()
    print(f'Projects for hoàng_thượng: {projects_hoang}')
    print(f'Total projects: {len(projects_hoang)}')

conn.close() 