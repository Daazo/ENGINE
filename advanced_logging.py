import discord
from discord.ext import commands
from discord import app_commands
from main import bot, has_permission, get_server_data, update_server_data, db
from brand_config import BOT_FOOTER, BrandColors, VisualElements
from datetime import datetime
import os

LOG_CHANNEL_TYPES = [
    "moderation", "security", "quarantine", "anti-raid", "anti-nuke",
    "automod", "join-leave", "role-update", "channel-update", "message-delete",
    "message-edit", "member-ban", "member-kick", "voice-log", "ticket-log",
    "command-log", "error-log", "karma", "system"
]

GLOBAL_LOG_TYPES = ["live-console", "dm-received", "dm-sent", "command-errors", "system-log"]

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
            
    except Exception as e:
        print(f"❌ Error initializing global logging: {e}")

async def send_global_log(log_type, message, guild=None):
    """Send ALL server logs to bot owner's central global logging category"""
    try:
        if not guild or db is None:
            return
        
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        system_channel = discord.utils.get(global_category.text_channels, name="system-log")
        if not system_channel:
            return
        
        embed = discord.Embed(
            title=f"📋 **{log_type.title()} - {guild.name}**",
            description=message,
            color=BrandColors.INFO,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="🏰 Server", value=f"{guild.name}\n`{guild.id}`", inline=True)
        embed.add_field(name="📌 Log Type", value=log_type, inline=True)
        embed.set_footer(text=f"{BOT_FOOTER} • Server Log", icon_url=bot.user.display_avatar.url)
        
        try:
            await system_channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending global system log: {e}")
            
    except Exception as e:
        print(f"Global logging error: {e}")

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
