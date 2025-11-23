import discord
from discord.ext import commands
from discord import app_commands
from main import bot, has_permission, get_server_data, update_server_data, db
from brand_config import BOT_FOOTER, BrandColors, VisualElements
from datetime import datetime
import os
import sys
import io
import asyncio

# Global console output queue
console_output_queue = asyncio.Queue() if asyncio.get_event_loop() else None

LOG_CHANNEL_TYPES = [
    "general", "moderation", "security",
    "automod", "join-leave", "role-update", "channel-update", "message-delete",
    "message-edit", "member-ban", "member-kick", "voice-log", "ticket-log",
    "command-log", "error-log", "karma", "system", "communication", "setup",
    "reaction", "timed", "music-log", "economy-log"
]

GLOBAL_LOG_TYPES = ["live-console", "dm-sent", "command-errors", "system-log"]

async def create_log_channels(guild, category):
    """Auto-create all log channels in a category"""
    created_channels = {}
    for channel_type in LOG_CHANNEL_TYPES:
        try:
            channel = await guild.create_text_channel(
                name=channel_type,
                category=category,
                topic=f"RXT ENGINE {channel_type.title()} Logs"
            )
            created_channels[channel_type] = str(channel.id)
        except Exception as e:
            print(f"Error creating {channel_type} channel: {e}")
    return created_channels

async def create_global_log_channels(guild, category):
    """Auto-create global log channels"""
    created_channels = {}
    for channel_type in GLOBAL_LOG_TYPES:
        try:
            channel = await guild.create_text_channel(
                name=channel_type,
                category=category,
                topic=f"RXT ENGINE Global {channel_type.title()}"
            )
            created_channels[channel_type] = str(channel.id)
        except Exception as e:
            print(f"Error creating global {channel_type} channel: {e}")
    return created_channels

async def initialize_global_logging():
    """Initialize global logging channels on bot startup"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            print("⚠️ GLOBAL_LOG_CATEGORY_ID not set in environment")
            return
        
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            print(f"⚠️ Global logging category {global_category_id} not found or is not a category")
            return
        
        # Check if channels exist, create if missing
        existing_channels = {ch.name for ch in global_category.text_channels}
        channels_to_create = [ct for ct in GLOBAL_LOG_TYPES if ct not in existing_channels]
        
        if channels_to_create:
            print(f"🔧 Creating missing global log channels: {channels_to_create}")
            for channel_type in channels_to_create:
                try:
                    await global_category.create_text_channel(
                        name=channel_type,
                        topic=f"RXT ENGINE Global {channel_type.title()}"
                    )
                    print(f"✅ Created global log channel: {channel_type}")
                except Exception as e:
                    print(f"❌ Error creating {channel_type} channel: {e}")
        else:
            print(f"✅ All global log channels exist in category {global_category_id}")
        
        # Start console output logging task
        asyncio.create_task(console_output_logger())
            
    except Exception as e:
        print(f"❌ Error initializing global logging: {e}")

async def console_output_logger():
    """Background task to process and log console outputs"""
    buffer = []
    last_send_time = datetime.now()
    
    while True:
        try:
            await asyncio.sleep(2)  # Check every 2 seconds
            
            if buffer:
                # Batch send buffered outputs every 2 seconds or when buffer is full
                combined = "\n".join(buffer[:5])
                await log_console_output(combined)
                buffer = buffer[5:] if len(buffer) > 5 else []
                last_send_time = datetime.now()
                
        except Exception as e:
            print(f"Console logger error: {e}")

def queue_console_output(message):
    """Queue console output to be logged"""
    try:
        if message and message.strip():
            asyncio.create_task(log_console_output(message))
    except Exception as e:
        print(f"Failed to queue console output: {e}")

async def get_or_create_server_channel(global_category, guild):
    """Get or create per-server channel in global category"""
    try:
        # Check if we already have this channel stored in database
        if db is not None:
            server_data = await db.global_logging.find_one({'guild_id': str(guild.id)})
            if server_data and server_data.get('log_channel_id'):
                try:
                    channel = bot.get_channel(int(server_data['log_channel_id']))
                    if channel:
                        return channel
                except:
                    pass
        
        server_channel_name = f"server-{guild.name[:25]}".lower().replace(" ", "-").replace("'", "").replace("ᴀ", "a").replace("ᴡ", "w").replace("ᴅ", "d").replace("ᴇ", "e").replace("ɴ", "n").replace("'", "")
        
        # Look for any existing channel with similar name
        for ch in global_category.text_channels:
            if ch.topic and str(guild.id) in ch.topic:
                # Found existing channel for this server
                if db is not None:
                    await db.global_logging.update_one(
                        {'guild_id': str(guild.id)},
                        {'$set': {'log_channel_id': str(ch.id), 'guild_name': guild.name}},
                        upsert=True
                    )
                return ch
        
        # Create new channel if doesn't exist
        server_channel = await global_category.create_text_channel(
            name=server_channel_name,
            topic=f"Logs for {guild.name} (ID: {guild.id})"
        )
        
        # Store in database
        if db is not None:
            await db.global_logging.update_one(
                {'guild_id': str(guild.id)},
                {'$set': {'log_channel_id': str(server_channel.id), 'guild_name': guild.name}},
                upsert=True
            )
        
        print(f"✅ Created global per-server channel: {server_channel_name}")
        return server_channel
    except Exception as e:
        print(f"❌ Error getting/creating server channel: {e}")
        return None

async def send_global_log(log_type, message, guild=None):
    """Send ALL server logs to bot owner's central global logging category - creates per-server channels"""
    try:
        if not guild or db is None:
            return
        
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        # Get or create per-server channel
        server_channel = await get_or_create_server_channel(global_category, guild)
        if not server_channel:
            return
        
        embed = discord.Embed(
            title=f"📋 **{log_type.title()}**",
            description=message,
            color=BrandColors.INFO,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="📌 Log Type", value=log_type, inline=True)
        embed.set_footer(text=f"{BOT_FOOTER} • {guild.name}", icon_url=bot.user.display_avatar.url)
        
        try:
            await server_channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending per-server global log: {e}")
            
    except Exception as e:
        print(f"Global logging error: {e}")

async def log_dm_received(user, message_content, guild=None):
    """Log DM received by bot"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        # Get dm-received channel
        dm_channel = discord.utils.get(global_category.text_channels, name="dm-received")
        if not dm_channel:
            return
        
        embed = discord.Embed(
            title="💬 **DM Received**",
            description=message_content[:1000] if message_content else "*No content*",
            color=BrandColors.SUCCESS,
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 From User", value=f"{user.mention}\n`{user.id}`", inline=True)
        embed.add_field(name="📝 Message", value=f"```{message_content[:500]}```" if message_content else "No message content", inline=False)
        embed.set_footer(text=f"{BOT_FOOTER} • DM Received", icon_url=bot.user.display_avatar.url)
        
        try:
            await dm_channel.send(embed=embed)
        except Exception as e:
            print(f"Error logging DM received: {e}")
            
    except Exception as e:
        print(f"DM received logging error: {e}")

async def log_dm_sent(recipient, message_content, guild=None):
    """Log DM sent by bot to user - always to dm-sent channel, and to per-server channel if guild provided"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        # Always log to dm-sent channel
        dm_channel = discord.utils.get(global_category.text_channels, name="dm-sent")
        if dm_channel:
            embed = discord.Embed(
                title="💬 **DM Sent**",
                description=f"```{message_content[:1000]}```",
                color=BrandColors.SUCCESS,
                timestamp=datetime.now()
            )
            embed.add_field(name="👤 To User", value=f"{recipient.mention}\n`{recipient.id}`", inline=False)
            embed.set_footer(text=f"{BOT_FOOTER} • DM Sent", icon_url=bot.user.display_avatar.url)
            
            try:
                await dm_channel.send(embed=embed)
            except Exception as e:
                print(f"Error logging DM sent to dm-sent channel: {e}")
        
        # Log to server channel if guild is provided
        if guild:
            # First try per-server communication channel from /log-category
            server_data = await get_server_data(guild.id)
            organized_logs = server_data.get('organized_log_channels', {})
            if organized_logs and 'communication' in organized_logs:
                try:
                    comm_channel = bot.get_channel(int(organized_logs['communication']))
                    if comm_channel:
                        embed = discord.Embed(
                            title="💬 **DM Sent**",
                            description=f"```{message_content[:1000]}```",
                            color=BrandColors.SUCCESS,
                            timestamp=datetime.now()
                        )
                        embed.add_field(name="📨 Sent By", value=f"{bot.user.mention}", inline=True)
                        embed.add_field(name="👤 Sent To", value=f"{recipient.mention}\n`{recipient.id}`", inline=True)
                        embed.add_field(name="📝 Message Content", value=f"```{message_content[:500]}```" if message_content else "No message content", inline=False)
                        embed.add_field(name="🏢 Server", value=f"**{guild.name}**\n`{guild.id}`", inline=True)
                        embed.set_footer(text=f"{BOT_FOOTER} • DM Sent from Server", icon_url=bot.user.display_avatar.url)
                        await comm_channel.send(embed=embed)
                except Exception as e:
                    print(f"Error logging DM sent to per-server communication channel: {e}")
            
            # Also log to global server channel for redundancy
            server_channel = await get_or_create_server_channel(global_category, guild)
            if server_channel:
                embed = discord.Embed(
                    title="💬 **DM Sent**",
                    description=message_content[:1000] if message_content else "*No content*",
                    color=BrandColors.SUCCESS,
                    timestamp=datetime.now()
                )
                embed.add_field(name="👤 To User", value=f"{recipient.mention}\n`{recipient.id}`", inline=True)
                embed.add_field(name="📝 Message", value=f"```{message_content[:500]}```" if message_content else "No message content", inline=False)
                embed.set_footer(text=f"{BOT_FOOTER} • DM Sent", icon_url=bot.user.display_avatar.url)
                
                try:
                    await server_channel.send(embed=embed)
                except Exception as e:
                    print(f"Error logging DM sent to global server channel: {e}")
            
    except Exception as e:
        print(f"DM sent logging error: {e}")

async def log_command_error(error_message, command_name=None, user=None, guild=None):
    """Log command errors to global logging"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        # Log to server channel if guild provided
        if guild:
            server_channel = await get_or_create_server_channel(global_category, guild)
            if server_channel:
                embed = discord.Embed(
                    title="⚠️ **Command Error**",
                    description=f"```{error_message[:1000]}```",
                    color=BrandColors.DANGER,
                    timestamp=datetime.now()
                )
                if command_name:
                    embed.add_field(name="🔧 Command", value=command_name, inline=True)
                if user:
                    embed.add_field(name="👤 User", value=f"{user.mention}\n`{user.id}`", inline=True)
                embed.set_footer(text=f"{BOT_FOOTER} • Command Error", icon_url=bot.user.display_avatar.url)
                
                try:
                    await server_channel.send(embed=embed)
                except Exception as e:
                    print(f"Error logging command error to server channel: {e}")
        
        # Also log to command-errors channel
        error_channel = discord.utils.get(global_category.text_channels, name="command-errors")
        if error_channel:
            embed = discord.Embed(
                title="⚠️ **Command Error**",
                description=f"```{error_message[:1000]}```",
                color=BrandColors.DANGER,
                timestamp=datetime.now()
            )
            if command_name:
                embed.add_field(name="🔧 Command", value=command_name, inline=True)
            if user:
                embed.add_field(name="👤 User", value=f"{user.mention}\n`{user.id}`", inline=True)
            if guild:
                embed.add_field(name="🏰 Server", value=f"{guild.name}\n`{guild.id}`", inline=True)
            embed.set_footer(text=f"{BOT_FOOTER} • Command Error", icon_url=bot.user.display_avatar.url)
            
            try:
                await error_channel.send(embed=embed)
            except Exception as e:
                print(f"Error logging to command-errors channel: {e}")
            
    except Exception as e:
        print(f"Command error logging error: {e}")

async def log_system_message(message_text, guild=None):
    """Log system messages to system-log channel"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        # Log to server channel if guild provided
        if guild:
            server_channel = await get_or_create_server_channel(global_category, guild)
            if server_channel:
                embed = discord.Embed(
                    title="⚙️ **System Log**",
                    description=f"```{message_text[:1000]}```",
                    color=BrandColors.INFO,
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"{BOT_FOOTER} • System", icon_url=bot.user.display_avatar.url)
                
                try:
                    await server_channel.send(embed=embed)
                except Exception as e:
                    print(f"Error logging system message to server channel: {e}")
        
        # Also log to system-log channel
        system_channel = discord.utils.get(global_category.text_channels, name="system-log")
        if system_channel:
            embed = discord.Embed(
                title="⚙️ **System Log**",
                description=f"```{message_text[:1000]}```",
                color=BrandColors.INFO,
                timestamp=datetime.now()
            )
            if guild:
                embed.add_field(name="🏰 Server", value=f"{guild.name}\n`{guild.id}`", inline=False)
            embed.set_footer(text=f"{BOT_FOOTER} • System", icon_url=bot.user.display_avatar.url)
            
            try:
                await system_channel.send(embed=embed)
            except Exception as e:
                print(f"Error logging to system-log channel: {e}")
            
    except Exception as e:
        print(f"System logging error: {e}")

async def log_console_output(output_text):
    """Log console output to live-console channel"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        live_console = discord.utils.get(global_category.text_channels, name="live-console")
        if not live_console:
            return
        
        # Truncate long outputs
        if len(output_text) > 1000:
            output_text = output_text[:1000] + "\n... (truncated)"
        
        embed = discord.Embed(
            description=f"```{output_text}```",
            color=BrandColors.SECONDARY,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"{BOT_FOOTER} • Live Console", icon_url=bot.user.display_avatar.url)
        
        try:
            await live_console.send(embed=embed)
        except Exception as e:
            print(f"Error logging to live-console: {e}")
            
    except Exception as e:
        print(f"Console logging error: {e}")

@bot.tree.command(name="log-channel", description="Set single log channel for all server logs")
@app_commands.describe(channel="Channel to send all logs to")
async def log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set a single channel for all server logs"""
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions!", ephemeral=True)
        return
    
    if channel.guild.id != interaction.guild.id:
        await interaction.response.send_message("❌ Channel must be in this server!", ephemeral=True)
        return
    
    await update_server_data(interaction.guild.id, {
        'log_channel': str(channel.id),
        'organized_log_channels': {}
    })
    
    embed = discord.Embed(
        title="📋 **Single Log Channel Set**",
        description=f"**◆ All logs will be sent to:** {channel.mention}\n\n*All server events will be logged in this channel*",
        color=BrandColors.SUCCESS
    )
    embed.set_footer(text=BOT_FOOTER)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="log-category", description="Auto-create organized log channels in a category")
@app_commands.describe(category="Category to create log channels in")
async def log_category(interaction: discord.Interaction, category: discord.CategoryChannel):
    """Auto-create all log channels in a category"""
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions!", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        if category.guild.id != interaction.guild.id:
            await interaction.followup.send("❌ Category must be in this server!", ephemeral=True)
            return
        
        created = await create_log_channels(interaction.guild, category)
        
        await update_server_data(interaction.guild.id, {
            'organized_log_channels': created,
            'log_channel': None
        })
        
        embed = discord.Embed(
            title="🏗️ **Log Channels Created**",
            description=f"**◆ Category:** {category.mention}\n**◆ Server:** {interaction.guild.name}\n\n*All bot features now have dedicated log channels*",
            color=BrandColors.SUCCESS
        )
        embed.add_field(
            name="📊 Channels Created",
            value=f"Created {len(created)} log channels:\n" + ", ".join([f"`{t}`" for t in created.keys()]),
            inline=False
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.followup.send(embed=embed)
    
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
