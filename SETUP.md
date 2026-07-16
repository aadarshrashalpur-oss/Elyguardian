# 🚀 Ely AutoMod Bot - Setup Guide

## Table of Contents
1. [Discord Bot Setup](#discord-bot-setup)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Bot](#running-the-bot)
5. [Troubleshooting](#troubleshooting)

---

## Discord Bot Setup

### Step 1: Create Discord Application
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Name your bot (e.g., "Ely AutoMod")
4. Accept Terms of Service
5. Click "Create"

### Step 2: Create Bot User
1. In your application, go to "Bot" section
2. Click "Add Bot"
3. Under TOKEN, click "Copy" to copy your bot token
4. Save this token securely (you'll need it later)

### Step 3: Set Bot Permissions
1. Go to "OAuth2" → "URL Generator"
2. Select scopes:
   - ✅ bot
   - ✅ applications.commands
3. Select permissions:
   - ✅ Send Messages
   - ✅ Read Messages/View Channels
   - ✅ Ban Members
   - ✅ Kick Members
   - ✅ Manage Messages
   - ✅ Manage Channels
   - ✅ Manage Roles
   - ✅ Moderate Members (timeout)
   - ✅ Manage Guild
4. Copy the generated URL

### Step 4: Invite Bot to Server
1. Paste the OAuth2 URL in your browser
2. Select your Discord server
3. Click "Authorize"
4. Complete CAPTCHA if prompted

### Step 5: Enable Privileged Intents
1. Go back to Developer Portal
2. In your application, go to "Bot"
3. Scroll to "Privileged Gateway Intents"
4. Enable:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
   - ✅ Presence Intent (optional)

---

## Installation

### Prerequisites
- Python 3.12+
- pip (Python package manager)
- Git (optional, for cloning)

### Quick Start
```bash
# Clone repository
git clone https://github.com/aadarshrashalpur-oss/Elyguardian.git
cd Elyguardian

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

### Step 1: Create .env File
Create a new file named `.env` in your project root:

```env
DISCORD_TOKEN=your_bot_token_here
```

### Step 2: Replace Token
1. Open `.env` file
2. Replace `your_bot_token_here` with your actual Discord bot token
3. Save the file

⚠️ **IMPORTANT**: Never share your bot token publicly!

---

## Running the Bot

### Start the Bot
```bash
# Make sure virtual environment is activated
python main.py
```

### Expected Output
```
2024-01-15 10:30:45 - __main__ - INFO - ✅ Database initialized successfully
2024-01-15 10:30:46 - __main__ - INFO - ✅ All cogs loaded and commands synced
2024-01-15 10:30:47 - __main__ - INFO - ✅ YourBotName#1234 is online and ready!
2024-01-15 10:30:47 - __main__ - INFO - 📡 Connected to X guilds
```

---

## Troubleshooting

### Bot Won't Start

**Error: "DISCORD_TOKEN not found in environment variables"**
- ✅ Solution: Create `.env` file with your token

**Error: "ModuleNotFoundError: No module named 'discord'"**
- ✅ Solution: Run `pip install -r requirements.txt`

**Error: "Python 3.X not compatible"**
- ✅ Solution: Update Python to 3.12 or higher

### Bot Doesn't Respond to Commands

**Commands don't appear in Discord**
- ✅ Solution: Make sure you enabled Privileged Intents
- ✅ Solution: Invite bot with `applications.commands` scope
- ✅ Solution: Wait 5 minutes for Discord to sync commands

**"Missing Permissions" error**
- ✅ Solution: Grant bot required permissions in Discord
- ✅ Solution: Make sure bot role is higher than target user

### Connection Issues

**Bot keeps disconnecting**
- ✅ Solution: Check internet connection
- ✅ Solution: Check Discord API status
- ✅ Solution: Restart the bot

---

**Happy moderating! 🎉**
