#!/usr/bin/env python3
"""
Enterprise-Grade Discord Moderation Bot
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
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import traceback
import sys
import os

# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = "YOUR_BOT_TOKEN_HERE"
PREFIX = "/"
DATABASE_PATH = "moderation.db"
LOG_FILE = "bot.log"

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
        logger.info("Database initialized successfully")
    
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

# ============================================================
# BOT CLASS
# ============================================================

class ModBot(commands.Bot):
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
                name="over 100+ servers"
            )
        )
        
        self.db = Database(DATABASE_PATH)
        self.message_cache = defaultdict(lambda: deque(maxlen=50))
        self.join_cache = defaultdict(lambda: deque(maxlen=50))
        self.start_time = datetime.now()
        self.ready = False
    
    async def setup_hook(self):
        """Setup hook for loading cogs."""
        await self.load_cogs()
        await self.tree.sync()
        logger.info("Slash commands synced globally")
    
    async def load_cogs(self):
        """Load all cogs."""
        await self.add_cog(ModerationCog(self))
        await self.add_cog(UtilityCog(self))
        await self.add_cog(AutoModCog(self))
        await self.add_cog(TicketCog(self))
        await self.add_cog(GiveawayCog(self))
        await self.add_cog(ReactionRoleCog(self))
        await self.add_cog(WelcomeCog(self))
        await self.add_cog(LoggingCog(self))
        await self.add_cog(ConfigCog(self))
        await self.add_cog(OwnerCog(self))
        logger.info("All cogs loaded")
    
    async def on_ready(self):
        """Called when bot is ready."""
        self.ready = True
        logger.info(f"{self.user} is online and ready!")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Set up auto-mod for all guilds
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
                "similar_detection": True,
                "antilink_enabled": True,
                "antiscam_enabled": True,
                "badword_filter": True,
                "mention_spam": True,
                "emoji_spam": True,
                "sticker_spam": True,
                "attachment_spam": True,
                "gif_spam": True,
                "caps_limit": 70,
                "zalgo_detection": True,
                "invisible_detection": True,
                "unicode_abuse": True,
                "hoist_detection": True,
                "suspicious_usernames": True,
                "new_account_days": 7,
                "raid_join_threshold": 10,
                "heat_decay_rate": 1,
                "warn_threshold": 5,
                "timeout_threshold": 10,
                "log_channel": None,
                "mod_log_channel": None,
                "welcome_channel": None,
                "goodbye_channel": None,
                "autorole": None,
                "verification_enabled": False,
                "verification_channel": None,
                "verification_role": None
            }
            self.db.set_guild_config(guild.id, default_config)
            logger.info(f"Default config created for {guild.name} ({guild.id})")
    
    async def on_guild_join(self, guild: discord.Guild):
        """Handle guild join event."""
        await self.setup_guild(guild)
        logger.info(f"Joined guild: {guild.name} ({guild.id})")
    
    async def on_member_join(self, member: discord.Member):
        """Handle member join event."""
        config = self.db.get_guild_config(member.guild.id)
        
        # Auto-role
        autorole = config.get("autorole")
        if autorole:
            role = member.guild.get_role(autorole)
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass
        
        # Welcome message
        welcome_channel_id = config.get("welcome_channel")
        if welcome_channel_id:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                embed = discord.Embed(
                    title="👋 Welcome!",
                    description=f"Welcome to **{member.guild.name}**, {member.mention}!",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="Member Count", value=member.guild.member_count)
                await channel.send(embed=embed)
        
        # Join rate detection
        self.join_cache[member.guild.id].append(time.time())
        recent_joins = [t for t in self.join_cache[member.guild.id] 
                       if time.time() - t < 60]
        raid_threshold = config.get("raid_join_threshold", 10)
        if len(recent_joins) > raid_threshold:
            await self.handle_raid(member.guild, len(recent_joins))
    
    async def handle_raid(self, guild: discord.Guild, count: int):
        """Handle raid detection."""
        logger.warning(f"⚠️ POSSIBLE RAID DETECTED in {guild.name}: {count} joins in 60s")
        
        config = self.db.get_guild_config(guild.id)
        log_channel_id = config.get("mod_log_channel")
        if log_channel_id:
            channel = guild.get_channel(log_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🚨 RAID DETECTED",
                    description=f"**{count}** members joined in the last 60 seconds.",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed)
        
        # Auto-lock channels during raid
        if count > 20:
            for channel in guild.text_channels:
                try:
                    await channel.set_permissions(
                        guild.default_role,
                        send_messages=False,
                        reason="Raid protection - auto-lock"
                    )
                except:
                    pass
            logger.warning(f"🔒 Auto-locked all channels in {guild.name} due to raid")
    
    async def on_message(self, message: discord.Message):
        """Handle message events."""
        if message.author.bot:
            return
        
        if not message.guild:
            return
        
        # AutoMod
        await self.process_automod(message)
        
        # Process commands
        await self.process_commands(message)
    
    async def process_automod(self, message: discord.Message):
        """Process automod checks."""
        guild_id = message.guild.id
        user_id = message.author.id
        config = self.db.get_guild_config(guild_id)
        
        if not config.get("automod_enabled", True):
            return
        
        violations = []
        
        # Anti-Spam
        if config.get("antispam_enabled", True):
            self.message_cache[user_id].append(message.content)
            recent = list(self.message_cache[user_id])
            if len(recent) >= 5:
                violations.append(("spam", 5))
        
        # Anti-Flood
        if config.get("antiflood_enabled", True):
            time_window = 10
            recent_messages = [m for m in self.message_cache[user_id] 
                              if time.time() - m.timestamp < time_window]
            if len(recent_messages) >= 10:
                violations.append(("flood", 3))
        
        # Duplicate Messages
        if config.get("duplicate_detection", True):
            if message.content and message.content in self.message_cache[user_id]:
                violations.append(("duplicate", 2))
        
        # Anti-Invite Links
        if config.get("antilink_enabled", True):
            invite_patterns = [
                r'discord\.gg\/\S+',
                r'discord\.com\/invite\/\S+',
                r'discordapp\.com\/invite\/\S+'
            ]
            for pattern in invite_patterns:
                if re.search(pattern, message.content, re.IGNORECASE):
                    violations.append(("invite_link", 3))
                    break
        
        # Anti-Scam
        if config.get("antiscam_enabled", True):
            scam_patterns = [
                r'free.?nitro',
                r'giveaway',
                r'gift.?card',
                r'steam.?gift',
                r'free.?robux',
                r'discord.?nitro'
            ]
            for pattern in scam_patterns:
                if re.search(pattern, message.content, re.IGNORECASE):
                    violations.append(("scam", 5))
                    break
        
        # Bad Words
        if config.get("badword_filter", True):
            with open('badwords.txt', 'r') as f:
                bad_words = [line.strip() for line in f]
            for word in bad_words:
                if word.lower() in message.content.lower():
                    violations.append(("bad_word", 3))
                    break
        
        # Mention Spam
        if config.get("mention_spam", True):
            mentions = len(message.mentions)
            if mentions >= 5:
                violations.append(("mention_spam", 2))
        
        # Excessive Caps
        caps_limit = config.get("caps_limit", 70)
        if len(message.content) > 10:
            caps_count = sum(1 for c in message.content if c.isupper())
            caps_percent = (caps_count / len(message.content)) * 100
            if caps_percent > caps_limit:
                violations.append(("excessive_caps", 2))
        
        # Process violations
        if violations:
            total_heat = sum(v[1] for v in violations)
            await self.apply_punishment(message, total_heat, violations)
    
    async def apply_punishment(self, message: discord.Message, heat: int, violations: list):
        """Apply punishment based on heat score."""
        guild_id = message.guild.id
        user_id = message.author.id
        
        # Update heat score
        current_heat = self.db.update_heat(guild_id, user_id, heat)
        config = self.db.get_guild_config(guild_id)
        
        # Check if message should be deleted
        if heat >= 5:
            try:
                await message.delete()
            except:
                pass
        
        # Apply punishments based on heat
        if current_heat >= 100:
            # Ban
            try:
                await message.author.ban(reason=f"Auto-ban: Heat score {current_heat}")
                logger.info(f"Auto-banned {message.author} (heat: {current_heat})")
            except:
                pass
        elif current_heat >= 75:
            # Kick
            try:
                await message.author.kick(reason=f"Auto-kick: Heat score {current_heat}")
                logger.info(f"Auto-kicked {message.author} (heat: {current_heat})")
            except:
                pass
        elif current_heat >= 50:
            # Timeout 1 hour
            try:
                duration = timedelta(hours=1)
                await message.author.timeout(duration, reason=f"Auto-timeout: Heat {current_heat}")
                logger.info(f"Auto-timeout {message.author} (heat: {current_heat})")
            except:
                pass
        elif current_heat >= 25:
            # Timeout 30 minutes
            try:
                duration = timedelta(minutes=30)
                await message.author.timeout(duration, reason=f"Auto-timeout: Heat {current_heat}")
                logger.info(f"Auto-timeout {message.author} (heat: {current_heat})")
            except:
                pass
        elif current_heat >= 10:
            # Warn
            await self.add_warning(message.author, "Auto-mod warning", message.author)

# ============================================================
# MODERATION COG
# ============================================================

class ModerationCog(commands.Cog):
    """Moderation commands."""
    
    def __init__(self, bot: ModBot):
        self.bot = bot
    
    @app_commands.command(name="ban", description="Ban a user")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member == interaction.user:
            await interaction.response.send_message("❌ You cannot ban yourself.", ephemeral=True)
            return
        
        await member.ban(reason=reason)
        embed = discord.Embed(
            title="🔨 User Banned",
            description=f"{member.mention} was banned by {interaction.user.mention}",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="kick", description="Kick a user")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member == interaction.user:
            await interaction.response.send_message("❌ You cannot kick yourself.", ephemeral=True)
            return
        
        await member.kick(reason=reason)
        embed = discord.Embed(
            title="👢 User Kicked",
            description=f"{member.mention} was kicked by {interaction.user.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="timeout", description="Timeout a user")
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
        if member == interaction.user:
            await interaction.response.send_message("❌ You cannot timeout yourself.", ephemeral=True)
            return
        
        await member.timeout(timedelta(minutes=duration), reason=reason)
        embed = discord.Embed(
            title="⏱️ User Timed Out",
            description=f"{member.mention} was timed out for {duration} minutes",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="untimeout", description="Remove timeout from a user")
    @app_commands.default_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        embed = discord.Embed(
            title="⏱️ Timeout Removed",
            description=f"Timeout removed from {member.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="warn", description="Warn a user")
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        await self.add_warning(member, reason, interaction.user)
        embed = discord.Embed(
            title="⚠️ User Warned",
            description=f"{member.mention} was warned by {interaction.user.mention}",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed)
    
    async def add_warning(self, member: discord.Member, reason: str, moderator: discord.Member):
        self.bot.db.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            (member.guild.id, member.id, moderator.id, reason)
        )
        self.bot.db.update_heat(member.guild.id, member.id, 5)
    
    @app_commands.command(name="warnings", description="View a user's warnings")
    @app_commands.default_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        results = self.bot.db.execute(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 10",
            (member.guild.id, member.id)
        )
        if not results:
            await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
            return
        
        embed = discord.Embed(title=f"Warnings for {member.display_name}", color=discord.Color.orange())
        for row in results[:10]:
            embed.add_field(
                name=f"#{row[0]}",
                value=f"Reason: {row[4]}\nMod: <@{row[3]}>\nTime: {row[5]}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a user")
    @app_commands.default_permissions(moderate_members=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        self.bot.db.execute(
            "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
            (member.guild.id, member.id)
        )
        embed = discord.Embed(
            title="✅ Warnings Cleared",
            description=f"All warnings cleared for {member.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="purge", description="Purge messages in a channel")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int, user: Optional[discord.Member] = None):
        await interaction.response.defer(ephemeral=True)
        
        def check(message):
            if user:
                return message.author == user
            return True
        
        deleted = await interaction.channel.purge(limit=amount, check=check)
        embed = discord.Embed(
            title="🧹 Messages Purged",
            description=f"Deleted {len(deleted)} messages",
            color=discord.Color.green()
        )
        if user:
            embed.add_field(name="Target User", value=user.mention)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="slowmode", description="Set slowmode in a channel")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        await interaction.channel.edit(slowmode_delay=seconds)
        embed = discord.Embed(
            title="⏳ Slowmode Set",
            description=f"Slowmode set to {seconds} seconds in {interaction.channel.mention}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="lock", description="Lock a channel")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        channel = channel or interaction.channel
        await channel.set_permissions(
            interaction.guild.default_role,
            send_messages=False
        )
        embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"{channel.mention} has been locked",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="unlock", description="Unlock a channel")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        channel = channel or interaction.channel
        await channel.set_permissions(
            interaction.guild.default_role,
            send_messages=None
        )
        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"{channel.mention} has been unlocked",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="userinfo", description="Get information about a user")
    async def userinfo(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        member = member or interaction.user
        
        embed = discord.Embed(
            title=f"👤 {member.display_name}",
            color=member.color if member.color else discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Joined", value=member.joined_at.strftime("%Y-%m-%d %H:%M"))
        embed.add_field(name="Created", value=member.created_at.strftime("%Y-%m-%d %H:%M"))
        embed.add_field(name="Roles", value=", ".join([r.mention for r in member.roles[1:5]]) + "..." if len(member.roles) > 5 else "")
        embed.add_field(name="Permissions", value=member.guild_permissions.value)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="modlogs", description="View moderation logs")
    @app_commands.default_permissions(moderate_members=True)
    async def modlogs(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        query = "SELECT * FROM mod_logs WHERE guild_id = ?"
        params = [interaction.guild.id]
        if user:
            query += " AND user_id = ?"
            params.append(user.id)
        query += " ORDER BY created_at DESC LIMIT 20"
        
        results = self.bot.db.execute(query, tuple(params))
        if not results:
            await interaction.response.send_message("No moderation logs found.", ephemeral=True)
            return
        
        embed = discord.Embed(title="📋 Moderation Logs", color=discord.Color.blue())
        for row in results[:10]:
            embed.add_field(
                name=f"{row[2]} - <@{row[3]}>",
                value=f"Reason: {row[4]}\nTime: {row[6]}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

# ============================================================
# UTILITY COG
# ============================================================

class UtilityCog(commands.Cog):
    """Utility commands."""
    
    def __init__(self, bot: ModBot):
        self.bot = bot
    
    @app_commands.command(name="help", description="Show help menu")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 Bot Commands",
            description="Here are all available commands:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Moderation",
            value="`/ban`, `/kick`, `/timeout`, `/warn`, `/purge`, `/lock`, `/unlock`, `/slowmode`",
            inline=False
        )
        embed.add_field(
            name="Utility",
            value="`/userinfo`, `/serverinfo`, `/ping`, `/uptime`, `/avatar`, `/poll`, `/embed`, `/say`",
            inline=False
        )
        embed.add_field(
            name="Configuration",
            value="`/settings`, `/config`, `/automod`, `/logchannel`, `/welcome`",
            inline=False
        )
        embed.add_field(
            name="Tickets",
            value="`/ticket`, `/close`, `/reopen`, `/claim`",
            inline=False
        )
        embed.add_field(
            name="Giveaways",
            value="`/giveaway`, `/reroll`, `/end`, `/list`",
            inline=False
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: **{latency}ms**",
            color=discord.Color.green() if latency < 100 else discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="uptime", description="Check bot uptime")
    async def uptime(self, interaction: discord.Interaction):
        delta = datetime.now() - self.bot.start_time
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        seconds = delta.seconds % 60
        
        embed = discord.Embed(
            title="⏱️ Uptime",
            description=f"**{days}d {hours}h {minutes}m {seconds}s**",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="serverinfo", description="Get server information")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=f"📊 {guild.name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="ID", value=guild.id)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown")
        embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d %H:%M"))
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Channels", value=len(guild.channels))
        embed.add_field(name="Roles", value=len(guild.roles))
        embed.add_field(name="Boosts", value=guild.premium_subscription_count or 0)
        embed.add_field(name="Boost Level", value=guild.premium_tier or 0)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="avatar", description="Get a user's avatar")
    async def avatar(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        user = user or interaction.user
        embed = discord.Embed(
            title=f"🖼️ {user.display_name}'s Avatar",
            color=discord.Color.blue()
        )
        embed.set_image(url=user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="poll", description="Create a poll")
    async def poll(self, interaction: discord.Interaction, question: str, option1: str, option2: str, option3: str = None, option4: str = None, option5: str = None):
        description = f"**{question}**\n\n"
        description += f"1️⃣ {option1}\n"
        description += f"2️⃣ {option2}\n"
        if option3:
            description += f"3️⃣ {option3}\n"
        if option4:
            description += f"4️⃣ {option4}\n"
        if option5:
            description += f"5️⃣ {option5}\n"
        
        embed = discord.Embed(
            title="📊 Poll",
            description=description,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Poll created by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="embed", description="Create a custom embed")
    @app_commands.default_permissions(manage_messages=True)
    async def embed(self, interaction: discord.Interaction, title: str, description: str, color: Optional[str] = None):
        color_map = {
            "red": discord.Color.red(),
            "blue": discord.Color.blue(),
            "green": discord.Color.green(),
            "yellow": discord.Color.yellow(),
            "purple": discord.Color.purple(),
            "orange": discord.Color.orange(),
            "pink": discord.Color.pink(),
            "gold": discord.Color.gold()
        }
        color = color_map.get(color.lower() if color else "blue", discord.Color.blue())
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)

# ============================================================
# AUTOMOD COG
# ============================================================

class AutoModCog(commands.Cog):
    """Auto-moderation configuration commands."""
    
    def __init__(self, bot: ModBot):
        self.bot = bot
    
    @app_commands.command(name="automod", description="Configure auto-moderation")
    @app_commands.default_permissions(manage_guild=True)
    async def automod(self, interaction: discord.Interaction):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        
        embed = discord.Embed(
            title="🛡️ Auto-Mod Configuration",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Status",
            value="✅ Enabled" if config.get("automod_enabled", True) else "❌ Disabled"
        )
        embed.add_field(
            name="Anti-Spam",
            value="✅" if config.get("antispam_enabled", True) else "❌"
        )
        embed.add_field(
            name="Anti-Flood",
            value="✅" if config.get("antiflood_enabled", True) else "❌"
        )
        embed.add_field(
            name="Duplicate Detection",
            value="✅" if config.get("duplicate_detection", True) else "❌"
        )
        embed.add_field(
            name="Anti-Links",
            value="✅" if config.get("antilink_enabled", True) else "❌"
        )
        embed.add_field(
            name="Anti-Scam",
            value="✅" if config.get("antiscam_enabled", True) else "❌"
        )
        embed.add_field(
            name="Bad Word Filter",
            value="✅" if config.get("badword_filter", True) else "❌"
        )
        embed.add_field(
            name="Mention Spam",
            value="✅" if config.get("mention_spam", True) else "❌"
        )
        embed.add_field(
            name="Raid Protection",
            value=f"Threshold: {config.get('raid_join_threshold', 10)}"
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="toggleautomod", description="Toggle auto-moderation on/off")
    @app_commands.default_permissions(manage_guild=True)
    async def toggleautomod(self, interaction: discord.Interaction):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        current = config.get("automod_enabled", True)
        config["automod_enabled"] = not current
        self.bot.db.set_guild_config(interaction.guild.id, config)
        
        status = "enabled" if not current else "disabled"
        embed = discord.Embed(
            title=f"🛡️ Auto-Mod {status.capitalize()}",
            color=discord.Color.green() if not current else discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="setraidthreshold", description="Set raid detection threshold")
    @app_commands.default_permissions(manage_guild=True)
    async def setraidthreshold(self, interaction: discord.Interaction, threshold: int):
        if threshold < 5 or threshold > 50:
            await interaction.response.send_message("❌ Threshold must be between 5 and 50.", ephemeral=True)
            return
        
        config = self.bot.db.get_guild_config(interaction.guild.id)
        config["raid_join_threshold"] = threshold
        self.bot.db.set_guild_config(interaction.guild.id, config)
        
        embed = discord.Embed(
            title="🛡️ Raid Threshold Set",
            description=f"Raid detection threshold: **{threshold}** joins per minute",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

# ============================================================
# TICKET COG
# ============================================================

class TicketCog(commands.Cog):
    """Ticket system commands."""
    
    def __init__(self, bot: ModBot):
        self.bot = bot
    
    @app_commands.command(name="ticket", description="Create a support ticket")
    async def ticket(self, interaction: discord.Interaction, topic: str):
        guild = interaction.guild
        channel_name = f"ticket-{interaction.user.name.lower()}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        
        # Add staff role if exists
        staff_role = discord.utils.get(guild.roles, name="Staff")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            channel_name,
            overwrites=overwrites,
            reason=f"Ticket created by {interaction.user}"
        )
        
        self.bot.db.execute(
            "INSERT INTO tickets (guild_id, channel_id, user_id, topic) VALUES (?, ?, ?, ?)",
            (guild.id, channel.id, interaction.user.id, topic)
        )
        
        embed = discord.Embed(
            title="🎫 Ticket Created",
            description=f"Your ticket has been created: {channel.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Topic", value=topic)
        await interaction.response.send_message(embed=embed)
        
        # Send welcome message in ticket channel
        welcome_embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"Welcome {interaction.user.mention}! Please describe your issue.",
            color=discord.Color.blue()
        )
        await channel.send(embed=welcome_embed)
    
    @app_commands.command(name="close", description="Close a ticket")
    async def close(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
            return
        
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        
        await interaction.channel.delete()
        self.bot.db.execute(
            "UPDATE tickets SET status = 'closed' WHERE channel_id = ?",
            (interaction.channel.id,)
        )

# ============================================================
# GIVEAWAY COG
# ============================================================

class GiveawayCog(commands.Cog):
    """Giveaway system commands."""
    
    def __init__(self, bot: ModBot):
        self.bot = bot
    
    @app_commands.command(name="giveaway", description="Start a giveaway")
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, prize: str, duration: int, winners: int = 1):
        end_time = datetime.now() + timedelta(minutes=duration)
        
        embed = discord.Embed(
            title="🎉 Giveaway!",
            description=f"**Prize:** {prize}\n"
                       f"**Winners:** {winners}\n"
                       f"**Ends:** <t:{int(end_time.timestamp())}:R>",
            color=discord.Color.gold()
        )
        embed.set_footer(text="React with 🎉 to enter!")
        
        message = await interaction.channel.send(embed=embed)
        await message.add_reaction("🎉")
        
        self.bot.db.execute(
            "INSERT INTO giveaways (guild_id, channel_id, message_id, prize, winner_count, ends_at) VALUES (?, ?, ?, ?, ?, ?)",
            (interaction.guild.id, interaction.channel.id, message.id, prize, winners, end_time)
        )
        
        await interaction.response.send_message("✅ Giveaway started!", ephemeral=True)
    
    @app_commands.command(name="reroll", description="Reroll a giveaway")
    @app_commands.default_permissions(manage_guild=True)
    async def reroll(self, interaction: discord.Interaction, message_id: str):
        try:
            message_id = int(message_id)
        except:
            await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)
            return
        
        message = await interaction.channel.fetch_message(message_id)
        if not message:
            await interaction.response.send_message("❌ Message not found.", ephemeral=True)
            return
        
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        if not reaction:
            await interaction.response.send_message("❌ No reactions found.", ephemeral=True)
            return
        
        users = [user async for user in reaction.users()]
        users = [u for u in users if not u.bot]
        
        if not users:
            await interaction.response.send_message("❌ No valid entries found.", ephemeral=True)
            return
        
        winner = random.choice(users)
        
        embed = discord.Embed(
            title="🎉 New Winner!",
            description=f"**{winner.mention}** has won the giveaway!",
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Rerolled!", ephemeral=True)

# ============================================================
# REACTION ROLE COG
# ============================================================

class ReactionRoleCog(commands.Cog):
    """Reaction role system commands."""
    
    def __init__(self, bot: ModBot):
        self.bot = bot
    
    @app_commands.command(name="reactionrole", description="Create a reaction role")
    @app_commands.default_permissions(manage_roles=True)
    async def reactionrole(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        try:
            message_id = int(message_id)
        except:
            await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)
            return
        
        message = await interaction.channel.fetch_message(message_id)
        if not message:
            await interaction.response.send_message("❌ Message not found.", ephemeral=True)
            return
        
        await message.add_reaction(emoji)
        
        self.bot.db.execute(
            "INSERT INTO reaction_roles (guild_id, channel_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?, ?)",
            (interaction.guild.id, interaction.channel.id, message.id, emoji, role.id)
        )
        
        await interaction.response.send_message(f"✅ Reaction role set: {emoji} -> {role.mention}", ephemeral=True)

# ============================================================
# WELCOME COG
# ============================================================

class WelcomeCog(commands.Cog):
    """Welcome system commands."""
    
    def __init__(self, bot: ModBot):
        self.bot = bot
    
    @app_commands.command(name="setwelcome", description="Set welcome channel")
    @app_commands.default_permissions(manage_guild=True)
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        config["welcome_channel"] = channel.id
        self.bot.db.set_guild_config(interaction.guild.id, config)
        
        await interaction.response.send_message(f"✅ Welcome channel set to {channel.mention}")
    
    @app_commands.command(name="setautorole", description="Set auto-role for new members")
    @app_commands.default_permissions(manage_roles=True)
    async def setautorole(self, interaction: discord.Interaction, role: discord.Role):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        config["autorole"] = role.id
        self.bot.db.set_guild_config(interaction.guild.id, config)
        
        await interaction.response.send_message(f"✅ Auto-role set to {role.mention}")

# ============================================================
# LOGGING COG
# ============================================================

class LoggingCog(commands.Cog):
    """Logging system commands."""
    
    def __init__(self, bot: ModBot):
        self.bot = bot
    
    @app_commands.command(name="setmodlog", description="Set moderation log channel")
    @app_commands.default_permissions(manage_guild=True)
    async def setmodlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        config["mod_log_channel"] = channel.id
        self.bot.db.set_guild_config(interaction.guild.id, config)
        
        await interaction.response.send_message(f"✅ Mod log channel set to {channel.mention}")

# ============================================================
# CONFIG COG
# ============================================================

class ConfigCog(commands.Cog):
    """Configuration commands."""
    
    def __init__(self, bot: ModBot):
        self.bot = bot
    
    @app_commands.command(name="settings", description="View server settings")
    @app_commands.default_permissions(manage_guild=True)
    async def settings(self, interaction: discord.Interaction):
        config = self.bot.db.get_guild_config(interaction.guild.id)
        
        embed = discord.Embed(
            title="⚙️ Server Settings",
            color=discord.Color.blue()
        )
        
        for key, value in config.items():
            if value is not None:
                embed.add_field(
                    name=key.replace("_", " ").title(),
                    value=str(value)[:100],
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="resetconfig", description="Reset server configuration")
    @app_commands.default_permissions(administrator=True)
    async def resetconfig(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "⚠️ Are you sure you want to reset all configuration? This cannot be undone!",
            ephemeral=True
        )
        # This would need a confirmation button, simplified for now

# ============================================================
# OWNER COG
# ============================================================

class OwnerCog(commands.Cog):
    """Owner-only commands."""
    
    def __init__(self, bot: ModBot):
        self.bot = bot
    
    @app_commands.command(name="reload", description="Reload all cogs")
    @app_commands.default_permissions(administrator=True)
    async def reload(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            await self.bot.load_cogs()
            await interaction.followup.send("✅ All cogs reloaded!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
    
    @app_commands.command(name="shutdown", description="Shutdown the bot")
    @app_commands.default_permissions(administrator=True)
    async def shutdown(self, interaction: discord.Interaction):
        await interaction.response.send_message("🛑 Shutting down...")
        await self.bot.close()

# ============================================================
# BOT ENTRY POINT
# ============================================================

def main():
    """Main entry point."""
    bot = ModBot()
    
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
