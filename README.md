# 🎭 Ely AutoMod Bot - Enterprise-Grade Discord Moderation System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python)
![Discord.py](https://img.shields.io/badge/discord.py-2.3+-000000?style=flat-square&logo=discord)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

**Advanced Automated Moderation & Community Management Bot for Discord**

[Features](#-features) • [Installation](#-installation) • [Configuration](#-configuration) • [Commands](#-commands) • [Support](#-support)

</div>

---

## 📋 Overview

Ely AutoMod Bot is an enterprise-grade Discord moderation system designed to keep your server safe and clean. Built with async architecture, SQLite database integration, and multiple moderation features.

### ⭐ Key Highlights
- ✅ **Fully Async** - Python 3.12+ compatible
- ✅ **Zero Configuration** - Auto-setup on guild join
- ✅ **Enterprise Ready** - Production-grade logging
- ✅ **100+ Server Support** - Scales effortlessly
- ✅ **Real-time Moderation** - Instant violation detection

---

## 🎯 Features

### 🛡️ **Auto-Moderation System**
- **Anti-Spam** - Detect rapid message patterns
- **Anti-Flood** - Prevent message spam attacks
- **Duplicate Detection** - Remove duplicate messages
- **Anti-Invite Links** - Block Discord invites
- **Anti-Scam** - Detect common scam patterns
- **Bad Word Filter** - Automatic profanity detection
- **Mention Spam** - Prevent mass mentions
- **Caps Lock Detection** - Monitor excessive capitalization
- **Raid Detection** - Identify mass join attacks
- **Heat Score System** - Tiered punishment escalation

### 📋 **Moderation Commands**
- `/ban` - Ban users with custom reasons
- `/kick` - Kick users from server
- `/timeout` - Timeout users for specified duration
- `/purge` - Mass delete messages
- `/lock` - Lock channels
- `/unlock` - Unlock channels

### 🎫 **Ticket System**
- `/ticket` - Create support tickets
- Auto-permission management
- Topic categorization

### 🎉 **Giveaway System**
- `/giveaway` - Start giveaways
- Customizable duration & winners
- Reaction-based entry system

### 🏷️ **Reaction Roles**
- `/reactionrole` - Setup self-assign roles
- Emoji-based role management

### 👋 **Welcome System**
- `/setwelcome` - Set welcome channel
- `/setautorole` - Auto-assign roles on join
- Customizable welcome messages

### 📊 **Logging System**
- `/setmodlog` - Configure moderation logs
- Comprehensive action tracking
- Raid detection alerts

### ⚙️ **Configuration**
- `/automod` - View mod settings
- `/toggleautomod` - Enable/disable automod
- `/settings` - View all server settings

---

## 📦 Installation

### Prerequisites
- Python 3.12 or higher
- pip package manager
- Discord bot token

### Step 1: Clone Repository
```bash
git clone https://github.com/aadarshrashalpur-oss/Elyguardian.git
cd Elyguardian
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Setup Environment Variables
Create a `.env` file in the root directory:
```env
DISCORD_TOKEN=your_bot_token_here
```

### Step 5: Run the Bot
```bash
python main.py
```

---

## 🔧 Configuration

### Default Settings
The bot automatically creates default configuration for each guild:

```python
default_config = {
    "automod_enabled": True,
    "antispam_enabled": True,
    "antiflood_enabled": True,
    "duplicate_detection": True,
    "antilink_enabled": True,
    "antiscam_enabled": True,
    "badword_filter": True,
    "mention_spam": True,
    "emoji_spam": True,
    "caps_limit": 70,  # Percentage
    "raid_join_threshold": 10,  # Joins per minute
    "heat_decay_rate": 1,  # Points per decay cycle
    "log_channel": None,
    "mod_log_channel": None,
    "welcome_channel": None,
    "autorole": None
}
```

### Heat Score System
The bot uses a heat score system to escalate punishments:

- **Heat 0-49**: Warning level
- **Heat 50+**: 1-hour timeout
- **Heat 75+**: Automatic kick
- **Heat 100+**: Automatic ban

---

## 💬 Commands

### Moderation
| Command | Description | Permission |
|---------|-------------|------------|
| `/ban <member> [reason]` | Ban user | Ban Members |
| `/kick <member> [reason]` | Kick user | Kick Members |
| `/timeout <member> <minutes> [reason]` | Timeout user | Moderate Members |
| `/purge <amount>` | Delete messages | Manage Messages |
| `/lock` | Lock channel | Manage Channels |
| `/unlock` | Unlock channel | Manage Channels |

### Configuration
| Command | Description | Permission |
|---------|-------------|------------|
| `/automod` | View automod settings | Manage Guild |
| `/toggleautomod` | Toggle automod | Manage Guild |
| `/settings` | View all settings | Manage Guild |
| `/setmodlog <channel>` | Set mod log channel | Manage Guild |
| `/setwelcome <channel>` | Set welcome channel | Manage Guild |
| `/setautorole <role>` | Set auto-assign role | Manage Roles |

### Features
| Command | Description | Permission |
|---------|-------------|------------|
| `/ticket <topic>` | Create support ticket | Everyone |
| `/giveaway <prize> <minutes> [winners]` | Start giveaway | Manage Guild |
| `/reactionrole <message_id> <emoji> <role>` | Setup reaction role | Manage Roles |

---

## 📁 Project Structure

```
Elyguardian/
├── main.py                 # Main bot file
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create this)
├── .env.example            # Environment template
├── .gitignore              # Git ignore rules
├── README.md               # This file
├── LICENSE                 # MIT License
├── ely_moderation.db      # SQLite database (auto-created)
└── ely_bot.log            # Bot logs (auto-created)
```

---

## 🔐 Security Notes

1. **Never commit your `.env` file** - It contains sensitive tokens
2. **Use environment variables** for all credentials
3. **Review bad words list** - Customize for your community
4. **Monitor heat scores** - Adjust thresholds as needed
5. **Keep bot token secret** - Rotate if compromised

---

## 🚀 Deployment

### Local Deployment
Use the installation steps above for local testing.

### Cloud Deployment (Heroku)
1. Push to GitHub
2. Connect Heroku to GitHub repo
3. Add `DISCORD_TOKEN` to Config Vars
4. Deploy!

### Docker Deployment
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

---

## 📊 Database Schema

The bot uses SQLite with the following tables:

### `guilds`
- Guild configuration and settings

### `members`
- User heat scores
- Warning counts
- Mute status

### `warnings`
- Warning history
- Moderator tracking

### `mod_logs`
- Moderation action logs
- Duration tracking

### `tickets`
- Support ticket management
- Status tracking

### `giveaways`
- Active giveaway data
- Prize tracking

### `reaction_roles`
- Emoji-role mappings
- Auto-role data

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 🐛 Bug Reports

Found a bug? Please open an issue with:
- Clear description
- Steps to reproduce
- Expected vs actual behavior
- Bot logs (if applicable)

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Inspired by enterprise moderation systems
- Thanks to the Discord.py community

---

## 📞 Support

- **GitHub Issues**: [Report bugs](https://github.com/aadarshrashalpur-oss/Elyguardian/issues)
- **Documentation**: Check README & code comments
- **Community**: Join our Discord (coming soon)

---

## 🎮 Quick Start Command

```bash
# Clone, setup, and run in one go
git clone https://github.com/aadarshrashalpur-oss/Elyguardian.git
cd Elyguardian
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
echo 'DISCORD_TOKEN=your_token_here' > .env
python main.py
```

---

**Made with ❤️ by Aadarsh Rashalpur**
