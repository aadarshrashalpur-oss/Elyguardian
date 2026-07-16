#!/usr/bin/env python3
"""
Ely AutoMod Bot - Enterprise-Grade Moderation System
Python 3.12+ | discord.py 2.x | SQLite | Async Architecture
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import sqlite3
import json
import logging
import re
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from collections import defaultdict, deque
import traceback
import os
import sys

# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN", "")
PREFIX = "/"
DATABASE_PATH = "ely_moderation.db"
LOG_FILE = "ely_bot.log"

# ============================================================
# LOGGING SETUP
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# DATABASE CLASS
# ============================================================

class Database:
    """SQLite database manager with async wrapper."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()
    
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_tables(self):
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Guilds config
        cur.execute("""
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                config TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Members
        cur.execute("""
            CREATE TABLE IF NOT EXISTS members (
                guild_id INTEGER,
                user_id INTEGER,
                heat_score INTEGER DEFAULT 0,
                warnings INTEGER DEFAULT 0,
                muted_until TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # Warnings
        cur.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Moderation logs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mod_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                action TEXT,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                duration INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tickets
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                user_id INTEGER,
                staff_id INTEGER,
                status TEXT DEFAULT 'open',
                topic TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Giveaways
        cur.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                prize TEXT,
                winner_count INTEGER DEFAULT 1,
                entries INTEGER DEFAULT 0,
                ended INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ends_at TIMESTAMP
            )
        """)
        
        # Reaction Roles
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                emoji TEXT,
                role_id INTEGER
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Database initialized successfully")
    
    def execute(self, query: str, params: tuple = ()):
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        result = cur.fetchall()
        conn.commit()
        cur.close()
        conn.close()
        return result
    
    def execute_one(self, query: str, params: tuple = ()):
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return result
    
    def get_guild_config(self, guild_id: int) -> dict:
        result = self.execute_one(
            "SELECT config FROM guilds WHERE guild_id = ?", (guild_id,)
        )
        if result:
            return json.loads(result[0])
        return {}
    
    def set_guild_config(self, guild_id: int, config: dict):
        self.execute(
            "INSERT INTO guilds (guild_id, config) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET config = ?",
            (guild_id, json.dumps(config), json.dumps(config))
        )
    
    def update_heat(self, guild_id: int, user_id: int, heat: int) -> int:
        """Update heat score for a user."""
        current = self.execute_one(
            "SELECT heat_score FROM members WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        new_heat = (current[0] if current else 0) + heat
        self.execute(
            "INSERT INTO members (guild_id, user_id, heat_score) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET heat_score = ?",
            (guild_id, user_id, new_heat, new_heat)
        )
        return new_heat

# ============================================================
# BOT CLASS
# ============================================================

class AutoModBot(commands.Bot):
    """Main bot class with all moderation features."""
    
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.moderation = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="🌙 over 100+ servers"
            )
        )
        
        self.db = Database(DATABASE_PATH)
        self.message_cache = defaultdict(lambda: deque(maxlen=50))
        self.join_cache = defaultdict(lambda: deque(maxlen=50))
        self.start_time = datetime.now()
        self.ready = False
    
    async def setup_hook(self):
        """Setup hook for loading cogs."""
        await self.add_cog(ModerationCog(self))
        await self.add_cog(AutoModCog(self))
        await self.add_cog(TicketCog(self))
        await self.add_cog(GiveawayCog(self))
        await self.add_cog(ReactionRoleCog(self))
        await self.add_cog(WelcomeCog(self))
        await self.add_cog(LoggingCog(self))
        await self.add_cog(ConfigCog(self))
        await self.tree.sync()
        logger.info("✅ All cogs loaded and commands synced")
    
    async def on_ready(self):
        """Called when bot is ready."""
        self.ready = True
        logger.info(f"✅ {self.user} is online and ready!")
        logger.info(f"📡 Connected to {len(self.guilds)} guilds")
        
        for guild in self.guilds:
            await self.setup_guild(guild)
    
    async def setup_guild(self, guild: discord.Guild):
        """Setup default configuration for a new guild."""
        config = self.db.get_guild_config(guild.id)
        if not config:
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
                "caps_limit": 70,
                "raid_join_threshold": 10,
                "heat_decay_rate": 1,
                "log_channel": None,
                "mod_log_channel": None,
                "welcome_channel": None,
                "autorole": None
            }
            self.db.set_guild_config(guild.id, default_config)
            logger.info(f"✅ Default config created for {guild.name}")
    
    async def on_guild_join(self, guild: discord.Guild):
        """Handle guild join event."""
        await self.setup_guild(guild)
        logger.info(f"📥 Joined guild: {guild.name}")
    
    async def on_member_join(self, member: discord.Member):
        """Handle member join event."""
        config = self.db.get_guild_config(member.guild.id)
        
        autorole = config.get("autorole")
        if autorole:
            role = member.guild.get_role(autorole)
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass
        
        welcome_channel_id = config.get("welcome_channel")
        if welcome_channel_id:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🌸 Welcome!",
                    description=f"Welcome to **{member.guild.name}**, {member.mention}!",
                    color=0xFFB6C1
                )
                await channel.send(embed=embed)
        
        self.join_cache[member.guild.id].append(time.time())
        recent_joins = [t for t in self.join_cache[member.guild.id] 
                       if time.time() - t < 60]
        raid_threshold = config.get("raid_join_threshold", 10)
        if len(recent_joins) > raid_threshold:
            await self.handle_raid(member.guild, len(recent_joins))
    
    async def handle_raid(self, guild: discord.Guild, count: int):
        """Handle raid detection."""
        logger.warning(f"⚠️ RAID DETECTED in {guild.name}: {count} joins in 60s")
        
        config = self.db.get_guild_config(guild.id)
        log_channel_id = config.get("mod_log_channel")
        if log_channel_id:
            channel = guild.get_channel(log_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🚨 RAID DETECTED",
                    description=f"**{count}** members joined in the last 60 seconds.",
                    color=0xFF0000
                )
                await channel.send(embed=embed)
    
    async def on_message(self, message: discord.Message):
        """Handle message events."""
        if message.author.bot or not message.guild:
            return
        
        await self.process_automod(message)
        await self.process_commands(message)
    
    async def process_automod(self, message: discord.Message):
        """Process automod checks."""
        guild_id = message.guild.id
        user_id = message.author.id
        config = self.db.get_guild_config(guild_id)
        
        if not config.get("automod_enabled", True):
            return
        
        violations = []
        heat = 0
        
        # Anti-Spam
        if config.get("antispam_enabled", True):
            self.message_cache[user_id].append(message.content)
            recent = list(self.message_cache[user_id])
            if len(recent) >= 5:
                violations.append("spam")
                heat += 5
        
        # Anti-Flood
        if config.get("antiflood_enabled", True):
            time_window = 10
            recent_messages = [m for m in self.message_cache[user_id]]
            if len(recent_messages) >= 10:
                violations.append("flood")
                heat += 3
        
        # Duplicate Messages
        if config.get("duplicate_detection", True):
            if message.content and message.content in self.message_cache[user_id]:
                violations.append("duplicate")
                heat += 2
        
        # Anti-Invite Links
        if config.get("antilink_enabled", True):
            invite_patterns = [
                r'discord\.gg\/\S+',
                r'discord\.com\/invite\/\S+',
                r'discordapp\.com\/invite\/\S+'
            ]
            for pattern in invite_patterns:
                if re.search(pattern, message.content, re.IGNORECASE):
                    violations.append("invite")
                    heat += 3
                    break
        
        # Anti-Scam
        if config.get("antiscam_enabled", True):
            scam_patterns = [
                r'free.?nitro', r'giveaway', r'gift.?card',
                r'steam.?gift', r'free.?robux', r'discord.?nitro'
            ]
            for pattern in scam_patterns:
                if re.search(pattern, message.content, re.IGNORECASE):
                    violations.append("scam")
                    heat += 5
                    break
        
        # Bad Words
        if config.get("badword_filter", True):
            bad_words = ['fuck', 'shit', 'bitch', 'cunt', 'nigga', 'nigger', 
                        'retard', 'dick', 'pussy', 'asshole', 'bastard', 'whore']
            for word in bad_words:
                if word.lower() in message.content.lower():
                    violations.append("badword")
                    heat += 3
                    break
        
        # Mention Spam
        if config.get("mention_spam", True):
            mentions = len(message.mentions)
            if mentions >= 5:
                violations.append("mention")
                heat += 2
        
        # Excessive Caps
        caps_limit = config.get("caps_limit", 70)
        if len(message.content) > 10:
            caps_count = sum(1 for c in message.content if c.isupper())
            caps_percent = (caps_count / len(message.content)) * 100
            if caps_percent > caps_limit:
                violations.append("caps")
                heat += 2
        
        # Apply punishments if violations found
        if violations:
            await self.apply_punishment(message, heat, violations)
    
    async def apply_punishment(self, message: discord.Message, heat: int, violations: list):
        """Apply punishment based on heat score."""
        guild_id = message.guild.id
        user_id = message.author.id
        
        current_heat = self.db.update_heat(guild_id, user_id, heat)
        
        if heat >= 5:
            try:
                await message.delete()
            except:
                pass
        
        if current_heat >= 100:
            try:
                await message.author.ban(reason=f"Auto-ban: Heat {current_heat}")
                logger.info(f"🔨 Auto-banned {message.author}")
            except:
                pass
        elif current_heat >= 75:
            try:
                await message.author.kick(reason=f"Auto-kick: Heat {current_heat}")
                logger.info(f"👢 Auto-kicked {message.author}")
            except:
                pass
        elif current_heat >= 50:
            try:
                await message.author.timeout(timedelta(hours=1), reason=f"Auto-timeout: Heat {current_heat}")
                logger.info(f"⏱️ Auto-timeout {message.author}")
            except:
                pass

# ============================================================
# COGS
# ============================================================

class ModerationCog(commands.Cog):
    """Moderation commands."""
    
    def __init__(self, bot: AutoModBot):
        self.bot = bot
    
    @app_commands.command(name="ban", description="Ban a user")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 Banned", description=f"{member.mention} banned", color=0xFF0000)
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="kick", description="Kick a user")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Kicked", description=f"{member.mention} kicked", color=0xFF8C00)
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="timeout", description="Timeout a user")
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason"):
        await member.timeout(timedelta(minutes=minutes), reason=reason)
        embed = discord.Embed(title="⏱️ Timed Out", description=f"{member.mention} timed out for {minutes}m", color=0xFFD700)
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="purge", description="Purge messages")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 Deleted {len(deleted)} messages", ephemeral=True)
    
    @app_commands.command(name="lock", description="Lock a channel")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(
            interaction.guild.default_role, send_messages=False
        )
        await interaction.response.send_message("🔒 Channel locked")
    
    @app_commands.command(name="unlock", description="Unlock a channel")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(
            interaction.guild.default_role, send_messages=None
        )
        await interaction.response.send_message("🔓 Channel unlocked")

class AutoModCog(commands.Cog):
    """Auto-moderation configuration."""
    
    def __init__(self, bot: AutoModBot):
        self.bot = bot
    
    @app_commands.command(name="automod", description="View auto-mod settings")
    @app_commands.default_permissions(manage_guild=True)
    async def automod(self, interaction: discord.Interaction):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        embed = discord.Embed(title="🛡️ Auto-Mod Settings", color=0x00BFFF)
        embed.add_field(name="Status", value="✅ Enabled" if config.get("automod_enabled", True) else "❌ Disabled")
        embed.add_field(name="Anti-Spam", value="✅" if config.get("antispam_enabled", True) else "❌")
        embed.add_field(name="Anti-Links", value="✅" if config.get("antilink_enabled", True) else "❌")
        embed.add_field(name="Anti-Scam", value="✅" if config.get("antiscam_enabled", True) else "❌")
        embed.add_field(name="Bad Word Filter", value="✅" if config.get("badword_filter", True) else "❌")
        embed.add_field(name="Mention Spam", value="✅" if config.get("mention_spam", True) else "❌")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="toggleautomod", description="Toggle auto-mod on/off")
    @app_commands.default_permissions(manage_guild=True)
    async def toggleautomod(self, interaction: discord.Interaction):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        config["automod_enabled"] = not config.get("automod_enabled", True)
        self.bot.db.set_guild_config(interaction.guild.id, config)
        status = "enabled" if config["automod_enabled"] else "disabled"
        await interaction.response.send_message(f"🛡️ Auto-mod {status}")

class TicketCog(commands.Cog):
    """Ticket system."""
    
    def __init__(self, bot: AutoModBot):
        self.bot = bot
    
    @app_commands.command(name="ticket", description="Create a ticket")
    async def ticket(self, interaction: discord.Interaction, topic: str):
        guild = interaction.guild
        channel = await guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
        )
        embed = discord.Embed(title="🎫 Ticket Created", description=f"{channel.mention}", color=0x00FF7F)
        embed.add_field(name="Topic", value=topic)
        await interaction.response.send_message(embed=embed)
        await channel.send(f"{interaction.user.mention} - Please describe your issue.")

class GiveawayCog(commands.Cog):
    """Giveaway system."""
    
    def __init__(self, bot: AutoModBot):
        self.bot = bot
    
    @app_commands.command(name="giveaway", description="Start a giveaway")
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, prize: str, duration: int, winners: int = 1):
        end_time = datetime.now() + timedelta(minutes=duration)
        embed = discord.Embed(title="🎉 Giveaway!", color=0xFFD700)
        embed.add_field(name="Prize", value=prize)
        embed.add_field(name="Winners", value=winners)
        embed.add_field(name="Ends", value=f"<t:{int(end_time.timestamp())}:R>")
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction("🎉")
        await interaction.response.send_message("✅ Giveaway started!", ephemeral=True)

class ReactionRoleCog(commands.Cog):
    """Reaction roles."""
    
    def __init__(self, bot: AutoModBot):
        self.bot = bot
    
    @app_commands.command(name="reactionrole", description="Setup reaction role")
    @app_commands.default_permissions(manage_roles=True)
    async def reactionrole(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
            await msg.add_reaction(emoji)
            self.bot.db.execute(
                "INSERT INTO reaction_roles VALUES (NULL, ?, ?, ?, ?, ?)",
                (interaction.guild.id, interaction.channel.id, msg.id, emoji, role.id)
            )
            await interaction.response.send_message(f"✅ Reaction role set: {emoji} -> {role.mention}", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Message not found", ephemeral=True)

class WelcomeCog(commands.Cog):
    """Welcome system."""
    
    def __init__(self, bot: AutoModBot):
        self.bot = bot
    
    @app_commands.command(name="setwelcome", description="Set welcome channel")
    @app_commands.default_permissions(manage_guild=True)
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        config["welcome_channel"] = channel.id
        self.bot.db.set_guild_config(interaction.guild.id, config)
        await interaction.response.send_message(f"✅ Welcome channel set to {channel.mention}")
    
    @app_commands.command(name="setautorole", description="Set auto-role")
    @app_commands.default_permissions(manage_roles=True)
    async def setautorole(self, interaction: discord.Interaction, role: discord.Role):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        config["autorole"] = role.id
        self.bot.db.set_guild_config(interaction.guild.id, config)
        await interaction.response.send_message(f"✅ Auto-role set to {role.mention}")

class LoggingCog(commands.Cog):
    """Logging system."""
    
    def __init__(self, bot: AutoModBot):
        self.bot = bot
    
    @app_commands.command(name="setmodlog", description="Set mod log channel")
    @app_commands.default_permissions(manage_guild=True)
    async def setmodlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        config["mod_log_channel"] = channel.id
        self.bot.db.set_guild_config(interaction.guild.id, config)
        await interaction.response.send_message(f"✅ Mod log channel set to {channel.mention}")

class ConfigCog(commands.Cog):
    """Configuration commands."""
    
    def __init__(self, bot: AutoModBot):
        self.bot = bot
    
    @app_commands.command(name="settings", description="View server settings")
    @app_commands.default_permissions(manage_guild=True)
    async def settings(self, interaction: discord.Interaction):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        embed = discord.Embed(title="⚙️ Settings", color=0x00BFFF)
        for key, value in config.items():
            if value is not None:
                embed.add_field(name=key.replace("_", " ").title(), value=str(value)[:100], inline=False)
        await interaction.response.send_message(embed=embed)

# ============================================================
# RUN THE BOT
# ============================================================

def main():
    """Main entry point."""
    if not TOKEN:
        logger.error("❌ DISCORD_TOKEN not found in environment variables")
        sys.exit(1)
    bot = AutoModBot()
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
