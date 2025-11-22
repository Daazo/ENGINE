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

async def create_server_log_channel(guild, category):
    """Create a per-server log channel in global category"""
    try:
        channel = await guild.create_text_channel(
            name=f"server-log-{guild.name[:25]}".lower().replace(" ", "-"),
            category=category,
            topic=f"Global logs for {guild.name} (ID: {guild.id})"
        )
        return str(channel.id)
    except Exception as e:
        print(f"Error creating server log channel: {e}")
        return None

async def send_log_embed(channel, title, log_type, description, executor=None, target=None, guild=None):
    """Send formatted log embed to channel"""
    if not channel:
        return
    
    # Determine color based on log type
    color_map = {
        "moderation": BrandColors.DANGER,
        "security": BrandColors.DANGER,
        "quarantine": BrandColors.WARNING,
        "anti-raid": BrandColors.DANGER,
        "anti-nuke": BrandColors.DANGER,
        "automod": BrandColors.WARNING,
        "join-leave": BrandColors.SUCCESS,
        "role-update": BrandColors.INFO,
        "channel-update": BrandColors.INFO,
        "message-delete": BrandColors.WARNING,
        "message-edit": BrandColors.WARNING,
        "member-ban": BrandColors.DANGER,
        "member-kick": BrandColors.DANGER,
        "voice-log": BrandColors.SECONDARY,
        "ticket-log": BrandColors.PRIMARY,
        "economy-log": BrandColors.SECONDARY,
        "music-log": BrandColors.SECONDARY,
        "command-log": BrandColors.INFO,
        "error-log": BrandColors.DANGER,
        "karma": BrandColors.PRIMARY,
        "system": BrandColors.INFO,
        "live-console": BrandColors.INFO,
        "dm-received": BrandColors.SUCCESS,
        "dm-sent": BrandColors.SUCCESS,
        "command-errors": BrandColors.DANGER,
        "system-log": BrandColors.INFO
    }
    
    embed = discord.Embed(
        title=f"{'🛡️' if 'security' in log_type else '📋'} **{title}**",
        description=f"```{description}```",
        color=color_map.get(log_type, BrandColors.INFO),
        timestamp=datetime.now()
    )
    
    if executor:
        embed.add_field(
            name="⚡ Executor",
            value=f"{executor.mention}\n`{executor.id}`",
            inline=True
        )
    
    if target:
        embed.add_field(
            name="🎯 Target",
            value=f"{target.mention if hasattr(target, 'mention') else target}\n`{target.id if hasattr(target, 'id') else target}`",
            inline=True
        )
    
    if guild:
        embed.add_field(
            name="🏰 Server",
            value=f"{guild.name}\n`{guild.id}`",
            inline=True
        )
    
    embed.set_footer(text=f"{BOT_FOOTER} • {log_type.title()}", icon_url=bot.user.display_avatar.url)
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Error sending log embed: {e}")

async def send_global_log(log_type, message, guild=None):
    """Send to global logging system"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        # Get global category
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        # Find the log channel
        channel_name = log_type.lower().replace("_", "-")
        channel = discord.utils.get(global_category.text_channels, name=channel_name)
        
        if channel:
            embed = discord.Embed(
                description=message,
                color=BrandColors.INFO,
                timestamp=datetime.now()
            )
            
            if guild:
                embed.add_field(name="🏰 Server", value=f"{guild.name}\n`{guild.id}`", inline=False)
            
            embed.set_footer(text=f"{BOT_FOOTER} • Global {log_type}", icon_url=bot.user.display_avatar.url)
            await channel.send(embed=embed)
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

@bot.tree.command(name="log-category", description="Auto-create all log channels in a category")
@app_commands.describe(
    category="Category to create log channels in",
    target_guild="Optional: Target server ID to redirect logs to (for cross-server logging)"
)
async def log_category(interaction: discord.Interaction, category: discord.CategoryChannel, target_guild: str = None):
    """Auto-create all log channels in a category or redirect to another server"""
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions!", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # Handle cross-server logging
        if target_guild:
            try:
                target_id = int(target_guild)
                target_guild_obj = bot.get_guild(target_id)
                if not target_guild_obj:
                    await interaction.followup.send("❌ Target server not found!", ephemeral=True)
                    return
                
                # Create category in target server
                target_category = await target_guild_obj.create_category(
                    name=f"RXT-ENGINE-LOGS ({interaction.guild.name})"
                )
                
                # Create channels in target server
                created = await create_log_channels(target_guild_obj, target_category)
                
                # Store cross-server config
                await update_server_data(interaction.guild.id, {
                    'cross_server_logging': {
                        'target_guild_id': str(target_id),
                        'log_channels': created,
                        'category_id': str(target_category.id)
                    },
                    'log_channel': None,
                    'organized_log_channels': {}
                })
                
                embed = discord.Embed(
                    title="🌐 **Cross-Server Logging Enabled**",
                    description=f"**◆ Source Server:** {interaction.guild.name}\n**◆ Target Server:** {target_guild_obj.name}\n**◆ Category:** {target_category.mention}\n\n*All logs from this server will be sent to {target_guild_obj.name}*",
                    color=BrandColors.SUCCESS
                )
                embed.add_field(
                    name="📊 Channels Created",
                    value=f"Created {len(created)} log channels",
                    inline=False
                )
                embed.set_footer(text=BOT_FOOTER)
                await interaction.followup.send(embed=embed)
                
            except ValueError:
                await interaction.followup.send("❌ Invalid server ID!", ephemeral=True)
        else:
            # Local category logging
            if category.guild.id != interaction.guild.id:
                await interaction.followup.send("❌ Category must be in this server!", ephemeral=True)
                return
            
            created = await create_log_channels(interaction.guild, category)
            
            await update_server_data(interaction.guild.id, {
                'organized_log_channels': created,
                'log_channel': None,
                'cross_server_logging': None
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

@bot.tree.command(name="setup-global-logging", description="Setup global bot-wide logging system")
@app_commands.describe(
    guild_id="Guild ID where global logs will be stored",
    category_name="Optional: Category name for global logs (default: RXT-ENGINE-GLOBAL)"
)
async def setup_global_logging(interaction: discord.Interaction, guild_id: str, category_name: str = "RXT-ENGINE-GLOBAL"):
    """Setup global logging for all bot activity"""
    if interaction.user.id != int(os.getenv('BOT_OWNER_ID', 0)):
        await interaction.response.send_message("❌ Only bot owner can setup global logging!", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        target_guild = bot.get_guild(int(guild_id))
        if not target_guild:
            await interaction.followup.send("❌ Guild not found!", ephemeral=True)
            return
        
        # Create global category
        global_category = await target_guild.create_category(name=category_name)
        
        # Create global log channels
        global_channels = await create_global_log_channels(target_guild, global_category)
        
        # Store in database
        if db is not None:
            await db.global_config.update_one(
                {'_id': 'logging'},
                {'$set': {
                    'global_category_id': str(global_category.id),
                    'global_channels': global_channels
                }},
                upsert=True
            )
        
        embed = discord.Embed(
            title="🌍 **Global Logging Setup Complete**",
            description=f"**◆ Category:** {global_category.mention}\n**◆ Server:** {target_guild.name}\n\n*All bot-wide logs will be stored here*",
            color=BrandColors.SUCCESS
        )
        embed.add_field(
            name="📊 Global Channels Created",
            value=", ".join([f"`{t}`" for t in global_channels.keys()]),
            inline=False
        )
        embed.add_field(
            name="⚠️ Next Step",
            value="Set environment variable: `GLOBAL_LOG_CATEGORY_ID=" + str(global_category.id) + "`",
            inline=False
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.followup.send(embed=embed)
        
        print(f"✅ Global logging setup: Category ID {global_category.id}")
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="log-status", description="Check current logging configuration")
async def log_status(interaction: discord.Interaction):
    """Check logging status for the server"""
    server_data = await get_server_data(interaction.guild.id)
    
    embed = discord.Embed(
        title="📊 **Logging Status**",
        description=f"**Server:** {interaction.guild.name}",
        color=BrandColors.PRIMARY
    )
    
    # Single channel logging
    if server_data.get('log_channel'):
        channel = bot.get_channel(int(server_data['log_channel']))
        embed.add_field(
            name="📌 Single Log Channel",
            value=f"✓ {channel.mention if channel else 'Channel not found'}\n`{server_data['log_channel']}`",
            inline=False
        )
    
    # Organized logging
    organized = server_data.get('organized_log_channels', {})
    if organized:
        channel_list = "\n".join([f"• `{t}` → <#{c}>" for t, c in list(organized.items())[:5]])
        if len(organized) > 5:
            channel_list += f"\n• +{len(organized) - 5} more..."
        
        embed.add_field(
            name=f"🏗️ Organized Logging ({len(organized)} channels)",
            value=channel_list,
            inline=False
        )
    
    # Cross-server logging
    cross = server_data.get('cross_server_logging')
    if cross:
        target_guild = bot.get_guild(int(cross.get('target_guild_id', 0)))
        embed.add_field(
            name="🌐 Cross-Server Logging",
            value=f"✓ Enabled → {target_guild.name if target_guild else 'Server not found'}\n`{cross.get('target_guild_id')}`",
            inline=False
        )
    
    if not server_data.get('log_channel') and not organized and not cross:
        embed.description += "\n\n❌ **No logging configured**\nUse `/log-channel` or `/log-category` to set up logging"
    
    embed.set_footer(text=BOT_FOOTER)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="log-disable", description="Disable logging for this server")
async def log_disable(interaction: discord.Interaction):
    """Disable all logging for the server"""
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions!", ephemeral=True)
        return
    
    await update_server_data(interaction.guild.id, {
        'log_channel': None,
        'organized_log_channels': {},
        'cross_server_logging': None
    })
    
    embed = discord.Embed(
        title="🔇 **Logging Disabled**",
        description="All logging has been disabled for this server.",
        color=BrandColors.WARNING
    )
    embed.set_footer(text=BOT_FOOTER)
    await interaction.response.send_message(embed=embed)
