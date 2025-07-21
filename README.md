# 91_chualang Discord Bot

A modular Discord bot for managing partners, projects, and cross-server message sending.

## Features

### 🚀 Core Features
- **Cross-server messaging**: Send messages to channels across different Discord servers
- **Partner management**: Manage partners and their associated projects
- **Project tracking**: Track projects and their Discord channels
- **Message history**: Keep track of sent messages and their status

### 📋 Commands

#### Send Commands
- `!send -p "partner_name" -c -all | message` - Send to all channels of a partner
- `!send -p "partner_name" -c "channel_name" | message` - Send to specific channel
- `!send -p "partner1" -c -all -p "partner2" -c "channel" | message` - Send to multiple partners
- `!send -all | message` - Send to all partners and all their projects

#### Management Commands
- `!list_partners` - List all partners
- `!list_projects` - List all projects
- `!list_messages` - List message history
- `!update_projects -p "partner_name"` - Sync Discord channels with database

#### Status Commands
- `!message_status <message_id>` - Check message status
- `!reply_rules` - Show reply rules
- `!status_reply <message_id>` - Check reply status

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/NguyenAnhDucDev/bot_mass.git
   cd bot_mass
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment**
   - Create `.env` file with your Discord bot token:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   ```

4. **Run the bot**
   ```bash
   python bot.py
   ```

## 📁 Project Structure

```
bot_mass/
├── bot.py                 # Main bot file
├── modules/
│   ├── constants.py       # Constants and configurations
│   ├── db_utils.py       # Database utilities
│   ├── message.py        # Message handling commands
│   ├── partner.py        # Partner management
│   ├── project.py        # Project management
│   ├── project_update.py # Project update commands
│   └── utils.py          # Utility functions
├── requirements.txt       # Python dependencies
├── setup.py             # Database setup
└── README.md            # This file
```

## 🗄️ Database Schema

### Partners Table
- `partner_id` (PRIMARY KEY)
- `partner_name`
- `server_id`
- `timezone`
- `created_at`

### Projects Table
- `project_id` (PRIMARY KEY)
- `partner_id` (FOREIGN KEY)
- `project_name`
- `channel_id`
- `created_at`

### Partner Discord Users Table
- `id` (PRIMARY KEY)
- `partner_id` (FOREIGN KEY)
- `discord_username`
- `tag_type`
- `created_at`

### Messages Table
- `message_id` (PRIMARY KEY)
- `partner_id` (FOREIGN KEY)
- `project_id` (FOREIGN KEY)
- `content`
- `discord_message_id`
- `status`
- `timestamp`

## 🔧 Configuration

### Discord Bot Setup
1. Create a Discord application at https://discord.com/developers/applications
2. Create a bot and get the token
3. Add the bot to your servers with appropriate permissions:
   - Send Messages
   - Read Message History
   - Mention Everyone (if needed)

### Database Setup
Run the setup script to initialize the database:
```bash
python setup.py
```

## 📝 Usage Examples

### Send to specific partner
```
!send -p "hoàng_thượng" -c -all | Hello, this is a test message!
```

### Send to multiple partners
```
!send -p "hoàng_thượng" -c -all -p "huy" -c "apb868" | Cross-server message
```

### Send to all partners
```
!send -all | Mass notification to all partners
```

## 🔄 Recent Updates

### Cross-Server Messaging
- ✅ Fixed cross-server channel detection
- ✅ Added support for sending to channels across different servers
- ✅ Improved error handling for missing channels

### Message Tagging
- ✅ Implemented proper Discord mentions with notifications
- ✅ Added "Dear @username," format for better user experience
- ✅ Fixed tag message generation for all partners

### Send Report
- ✅ Comprehensive send report tracking all partners
- ✅ Shows which projects received messages
- ✅ Includes partners not explicitly mentioned in command

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

If you encounter any issues or have questions, please create an issue on GitHub.

---

**Developed by Nguyen Anh Duc** 🚀 