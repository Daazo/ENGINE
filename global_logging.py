
import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import os
from main import bot, get_server_data
from brand_config import BOT_NAME
from brand_config import BOT_FOOTER, BrandColors

# ==== GLOBAL LOGGING CONFIGURATION ====
SUPPORT_SERVER_ID = int(os.getenv('SUPPORT_SERVER_ID', '1404842638615777331'))
LOG_CATEGORY_ID = int(os.getenv('LOG_CATEGORY_ID', '1405764734812160053'))

# Global logging channels cache
global_log_channels = {}

async def get_or_create_global_channel(channel_name: str):
    """Get or create a global logging channel in the support server"""
    if not SUPPORT_SERVER_ID or not LOG_CATEGORY_ID:
        return None
    
    # Check cache first
    if channel_name in global_log_channels:
        channel = bot.get_channel(global_log_channels[channel_name])
        if channel:
            return channel
    
    try:
        support_guild = bot.get_guild(SUPPORT_SERVER_ID)
        if not support_guild:
            return None
            
        category = discord.utils.get(support_guild.categories, id=LOG_CATEGORY_ID)
        if not category:
            return None

        # Try to find existing channel
        channel = discord.utils.get(category.text_channels, name=channel_name.lower())
        if channel:
            global_log_channels[channel_name] = channel.id
            return channel

        # Create new channel
        channel = await support_guild.create_text_channel(
            name=channel_name.lower(),
            category=category,
            topic=f"Global logs for {channel_name} - RXT ENGINE"
        )
        global_log_channels[channel_name] = channel.id
        return channel
    except Exception as e:
        print(f"Error creating global log channel {channel_name}: {e}")
        return None

async def get_server_log_channel(guild_id: int):
    """Get or create a SINGLE unified log channel for a server (one channel per server only)"""
    # Check if server has custom log server configured
    try:
        server_data = await get_server_data(guild_id)
        custom_log_guild_id = server_data.get('global_log_server_id')
        
        if custom_log_guild_id and custom_log_guild_id != SUPPORT_SERVER_ID:
            # Try to send to custom log server
            custom_guild = bot.get_guild(int(custom_log_guild_id))
            if custom_guild:
                # Find or create "bot-logs" channel in custom server
                channel = discord.utils.get(custom_guild.text_channels, name="bot-logs")
                if channel:
                    return channel
                # Try to create if permissions allow
                try:
                    channel = await custom_guild.create_text_channel("bot-logs", topic="RXT ENGINE Bot Logs")
                    return channel
                except:
                    pass  # Fall back to default
    except:
        pass
    
    # Default: use support server with single unified channel
    if not SUPPORT_SERVER_ID or not LOG_CATEGORY_ID:
        return None
    
    guild = bot.get_guild(guild_id)
    if not guild or guild.id == SUPPORT_SERVER_ID:
        return None
    
    # Use clean server name for SINGLE unified channel per server
    clean_name = guild.name.lower().replace(" ", "-").replace("_", "-")
    clean_name = ''.join(c for c in clean_name if c.isalnum() or c == '-')[:45]
    channel_name = f"{clean_name}-logs"
    
    return await get_or_create_global_channel(channel_name)

async def log_to_global(channel_name: str, embed: discord.Embed):
    """Send log message to global logging channel"""
    try:
        channel = await get_or_create_global_channel(channel_name)
        if channel:
            await channel.send(embed=embed)
    except Exception as e:
        print(f"Error logging to global channel {channel_name}: {e}")

async def setup_global_channels():
    """Setup all global logging channels"""
    if not SUPPORT_SERVER_ID or not LOG_CATEGORY_ID:
        print("⚠️ Global logging disabled - SUPPORT_SERVER_ID and LOG_CATEGORY_ID not configured")
        return
    
    # Global channels to create (unified channels only)
    global_channels = [
        "dm-logs",
        "bot-dm-send-logs", 
        "live-console",
        "command-errors",
        "bot-events",
        "security-alerts"
    ]
    
    for channel_name in global_channels:
        await get_or_create_global_channel(channel_name)
    
    # Pre-create one channel per server (all server activity goes to ONE channel)
    for guild in bot.guilds:
        if guild.id != SUPPORT_SERVER_ID:
            await get_server_log_channel(guild.id)
    
    print(f"✅ Global logging system initialized with {len(global_log_channels)} unified channels (one per server)")

# Global logging functions
async def log_dm_received(message):
    """Log DMs received by bot"""
    embed = discord.Embed(
        title="📥 DM Received",
        description=f"**From:** {message.author} ({message.author.id})\n**Content:** {message.content[:1000]}",
        color=BrandColors.INFO,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"User ID: {message.author.id}")
    if message.author.display_avatar:
        embed.set_thumbnail(url=message.author.display_avatar.url)
    await log_to_global("dm-logs", embed)

async def log_dm_sent(recipient, content):
    """Log DMs sent by bot"""
    if not recipient:
        return  # Skip logging if recipient is None
        
    embed = discord.Embed(
        title="📤 DM Sent By Bot", 
        description=f"**To:** {recipient} ({recipient.id})\n**Content:** {content[:1000]}",
        color=BrandColors.SUCCESS,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Recipient ID: {recipient.id}")
    if recipient.display_avatar:
        embed.set_thumbnail(url=recipient.display_avatar.url)
    await log_to_global("bot-dm-send-logs", embed)

async def log_console_event(event_type: str, message: str):
    """Log console events like bot start/restart"""
    embed = discord.Embed(
        title=f"🖥️ Console Event: {event_type}",
        description=message,
        color=BrandColors.PRIMARY,
        timestamp=datetime.now()
    )
    embed.set_footer(text=BOT_FOOTER)
    await log_to_global("live-console", embed)

async def log_command_error(interaction_or_ctx, error):
    """Log command errors globally"""
    if hasattr(interaction_or_ctx, 'guild'):
        guild = interaction_or_ctx.guild
        user = interaction_or_ctx.user if hasattr(interaction_or_ctx, 'user') else interaction_or_ctx.author
        command = getattr(interaction_or_ctx, 'command', 'Unknown')
    else:
        guild = None
        user = None
        command = 'Unknown'
    
    embed = discord.Embed(
        title="❌ Command Error",
        description=f"**Guild:** {guild.name if guild else 'DM'} ({guild.id if guild else 'N/A'})\n"
                   f"**User:** {user} ({user.id if user else 'N/A'})\n"
                   f"**Command:** {command}\n"
                   f"**Error:** {str(error)[:1000]}",
        color=BrandColors.DANGER,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Error Type: {type(error).__name__}")
    await log_to_global("command-errors", embed)

async def log_guild_join_global(guild):
    """Log when bot joins a server"""
    # Create guild-specific log channel with clean name
    clean_name = guild.name.lower().replace(" ", "-").replace("_", "-")
    clean_name = ''.join(c for c in clean_name if c.isalnum() or c == '-')[:45]
    channel_name = f"{clean_name}-logs"
    await get_or_create_global_channel(channel_name)
    
    # Log the join event
    embed = discord.Embed(
        title="🎉 Bot Joined New Server",
        description=f"**Server:** {guild.name}\n**ID:** {guild.id}\n**Owner:** {guild.owner}\n**Members:** {guild.member_count}\n**Log Channel:** {channel_name}",
        color=BrandColors.SUCCESS,
        timestamp=datetime.now()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await log_to_global("bot-events", embed)

async def log_guild_remove_global(guild):
    """Log when bot leaves a server"""
    # Try to delete the server's log channel
    clean_name = guild.name.lower().replace(" ", "-").replace("_", "-")
    clean_name = ''.join(c for c in clean_name if c.isalnum() or c == '-')[:45]
    channel_name = f"{clean_name}-logs"
    
    try:
        support_guild = bot.get_guild(SUPPORT_SERVER_ID)
        if support_guild:
            category = discord.utils.get(support_guild.categories, id=LOG_CATEGORY_ID)
            if category:
                channel = discord.utils.get(category.text_channels, name=channel_name)
                if channel:
                    await channel.delete()
                    if channel_name in global_log_channels:
                        del global_log_channels[channel_name]
    except Exception as e:
        print(f"Error deleting log channel for {guild.name}: {e}")
    
    embed = discord.Embed(
        title="👋 Bot Left Server",
        description=f"**Server:** {guild.name}\n**ID:** {guild.id}\n**Members:** {guild.member_count}\n**Log Channel:** {channel_name} (deleted)",
        color=BrandColors.DANGER,
        timestamp=datetime.now()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await log_to_global("bot-events", embed)

async def log_global_activity(activity_type: str, guild_id: int, user_id: int, details: str):
    """Log general bot activity to unified per-server channel"""
    guild = bot.get_guild(guild_id) if guild_id else None
    user = bot.get_user(user_id) if user_id else None
    
    embed = discord.Embed(
        title=f"🔍 {activity_type}",
        description=f"**Server:** {guild.name if guild else 'Unknown'} ({guild_id})\n"
                   f"**User:** {user if user else 'Unknown'} ({user_id})\n"
                   f"**Details:** {details}",
        color=BrandColors.PRIMARY,
        timestamp=datetime.now()
    )
    
    # Log to unified server-specific channel
    if guild_id and guild_id != SUPPORT_SERVER_ID and guild:
        channel = await get_server_log_channel(guild_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send global activity log: {e}")

async def log_bot_command_activity(guild_id: int, command_type: str, user, details: str):
    """Log ALL bot command activities to SINGLE unified per-server channel"""
    guild = bot.get_guild(guild_id)
    if not guild or guild.id == SUPPORT_SERVER_ID:
        return
    
    # Get the unified server log channel (supports cross-server logging)
    channel = await get_server_log_channel(guild_id)
    if not channel:
        return
    
    # Expanded color mapping for ALL command types
    colors = {
        'economy': 0xf1c40f,        # Gold for economy
        'karma': 0x9b59b6,          # Purple for karma
        'security': 0xe74c3c,       # Red for security
        'moderation': 0xe74c3c,     # Red for moderation
        'voice': 0x3498db,          # Blue for voice
        'general': 0x95a5a6,        # Gray for general
        'communication': 0x43b581,  # Green for communication
        'setup': 0xf39c12,          # Orange for setup
        'tickets': 0x9b59b6,        # Purple for tickets
        'reaction_role': 0xe67e22,  # Orange for reaction roles
        'welcome': 0x43b581,        # Green for welcome
        'timed_roles': 0xf39c12,    # Orange for timed roles
        'timeout': 0xe74c3c,        # Red for timeout
        'profile': 0x3498db,        # Blue for profile
        'utility': 0x95a5a6,        # Gray for utility
        'autorole': 0x9b59b6,       # Purple for autorole
        'help': 0x3498db,           # Blue for help
        'info': 0x3498db,           # Blue for info
        'administration': 0xe74c3c, # Red for admin commands
        'fun': 0xf1c40f,            # Gold for fun commands
        'games': 0xf1c40f,          # Gold for games
        'verification': 0xe74c3c,   # Red for verification
        'whitelist': 0xe74c3c,      # Red for whitelist
        'reaction': 0xe67e22,       # Orange for reactions
        'reminder': 0x43b581,       # Green for reminders
        'poll': 0x43b581,           # Green for polls
        'embed': 0x43b581,          # Green for embeds
        'announce': 0xf39c12,       # Orange for announcements
        'dm': 0x9b59b6,             # Purple for DMs
        'say': 0x43b581,            # Green for say commands
        'slots': 0xf1c40f,          # Gold for slots
        'trivia': 0xf1c40f,         # Gold for trivia
        'daily': 0xf1c40f,          # Gold for daily
        'weekly': 0xf1c40f,         # Gold for weekly
        'work': 0xf1c40f,           # Gold for work
        'balance': 0xf1c40f,        # Gold for balance
        'deposit': 0xf1c40f,        # Gold for deposit
        'withdraw': 0xf1c40f,       # Gold for withdraw
        'trade': 0xf1c40f,          # Gold for trade
        'richest': 0xf1c40f,        # Gold for richest
        'givekarma': 0x9b59b6,      # Purple for give karma
        'karmaboard': 0x9b59b6,     # Purple for karma board
        'resetkarma': 0x9b59b6,     # Purple for reset karma
        'buykarma': 0x9b59b6,       # Purple for buy karma
        'mykarma': 0x9b59b6,        # Purple for my karma
        'ping': 0x3498db,           # Blue for ping
        'uptime': 0x3498db,         # Blue for uptime
        'userinfo': 0x3498db,       # Blue for user info
        'serverinfo': 0x3498db,     # Blue for server info
        'contact': 0x3498db,        # Blue for contact
        'synccommands': 0xe74c3c,   # Red for sync commands
        'servercard': 0x3498db,     # Blue for server card
        'botprofile': 0x3498db,     # Blue for bot profile
        'kick': 0xe74c3c,           # Red for kick
        'ban': 0xe74c3c,            # Red for ban
        'nuke': 0xe74c3c,           # Red for nuke
        'mute': 0xe74c3c,           # Red for mute
        'unmute': 0x43b581,         # Green for unmute
        'movevc': 0x3498db,         # Blue for move vc
        'vckick': 0xe74c3c,         # Red for vc kick
        'vclock': 0xe74c3c,         # Red for vc lock
        'vcunlock': 0x43b581,       # Green for vc unlock
        'vclimit': 0x3498db,        # Blue for vc limit
        'giverole': 0xf39c12,       # Orange for give role
        'removerole': 0xf39c12,     # Orange for remove role
        'timedroles': 0xf39c12,     # Orange for timed roles
        'ticketsetup': 0x9b59b6,    # Purple for ticket setup
        'reactionrole': 0xe67e22,   # Orange for reaction role
        'quickreactionrole': 0xe67e22, # Orange for quick reaction role
        'listreactionroles': 0xe67e22, # Orange for list reaction roles
        'verification-setup': 0xe74c3c, # Red for verification setup
        'timeout-settings': 0xe74c3c,  # Red for timeout settings
        'remove-timeout': 0x43b581,    # Green for remove timeout
        'timeout-stats': 0x3498db,     # Blue for timeout stats
        'addcoins': 0xf1c40f,          # Gold for add coins
        'removecoins': 0xe74c3c,       # Red for remove coins
        'seteconomycatogary': 0xf39c12, # Orange for economy category setup
        'setgamecatogary': 0xf39c12,    # Orange for game category setup
        'setbankcatogary': 0xf39c12,    # Orange for bank category setup
        'setecocategory': 0xf39c12,     # Orange for eco category
        'setgamecategory': 0xf39c12,    # Orange for game category
        'setbankcategory': 0xf39c12,    # Orange for bank category
        'setkarmacategory': 0xf39c12,   # Orange for karma category
        'createeconomychannels': 0xf39c12, # Orange for create economy channels
        'create_game_channels': 0xf39c12,  # Orange for create game channels
        'create_bank_channels': 0xf39c12   # Orange for create bank channels
    }
    
    # Set emoji based on command type for better visual identification
    emojis = {
        'economy': '🪙', 'karma': '✨', 'security': '🛡️', 'moderation': '🔨',
        'voice': '🔊', 'general': '🏠', 'communication': '💬', 'setup': '⚙️',
        'tickets': '🎫', 'reaction_role': '🎭', 'welcome': '👋', 'timed_roles': '⏰',
        'timeout': '🔒', 'profile': '👤', 'utility': '🔧', 'autorole': '🎭',
        'help': '📚', 'info': 'ℹ️', 'administration': '👑', 'fun': '🎮',
        'games': '🎯', 'verification': '✅', 'whitelist': '📝', 'reaction': '😀',
        'reminder': '⏰', 'poll': '📊', 'embed': '📋', 'announce': '📢',
        'dm': '📩', 'say': '🗣️', 'slots': '🎰', 'trivia': '🧠', 'daily': '📅',
        'weekly': '📆', 'work': '💼', 'balance': '💰', 'deposit': '🏦',
        'withdraw': '💸', 'trade': '🤝', 'richest': '👑', 'givekarma': '⭐',
        'karmaboard': '🏆', 'resetkarma': '🔄', 'buykarma': '🛒', 'mykarma': '📈',
        'ping': '🏓', 'uptime': '⏱️', 'userinfo': '👤', 'serverinfo': '🏰',
        'contact': '📞', 'synccommands': '🔄', 'servercard': '🎴', 'botprofile': '🤖',
        'kick': '👢', 'ban': '🔨', 'nuke': '💥', 'mute': '🔇', 'unmute': '🔊',
        'movevc': '🔄', 'vckick': '🚪', 'vclock': '🔒', 'vcunlock': '🔓',
        'vclimit': '🔢', 'giverole': '➕', 'removerole': '➖', 'timedroles': '⏰',
        'ticketsetup': '🎫', 'reactionrole': '🎭', 'quickreactionrole': '⚡',
        'listreactionroles': '📋', 'verification-setup': '✅', 'timeout-settings': '⚙️',
        'remove-timeout': '🔓', 'timeout-stats': '📊', 'addcoins': '💰',
        'removecoins': '💸', 'seteconomycatogary': '🏗️', 'setgamecatogary': '🎮',
        'setbankcatogary': '🏦', 'setecocategory': '🏗️', 'setgamecategory': '🎮',
        'setbankcategory': '🏦', 'setkarmacategory': '✨', 'createeconomychannels': '🏗️',
        'create_game_channels': '🎮', 'create_bank_channels': '🏦'
    }
    
    emoji = emojis.get(command_type.lower(), '🤖')
    color = colors.get(command_type.lower(), 0x3498db)
    
    embed = discord.Embed(
        title=f"{emoji} **Bot Activity - {command_type.title()}**",
        description=f"**User:** {user}\n**Details:** {details}",
        color=color,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Server: {guild.name} (ID: {guild.id})")
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Failed to send command activity log: {e}")

async def log_bot_content_shared(guild_id: int, command_used: str, user, content: str, channel_name: str = None):
    """Log content shared by bot through commands like /say, /announce, etc. - to SINGLE unified server channel"""
    guild = bot.get_guild(guild_id)
    if not guild or guild.id == SUPPORT_SERVER_ID:
        return
    
    # Get unified server log channel
    channel = await get_server_log_channel(guild_id)
    if not channel:
        return
    
    embed = discord.Embed(
        title=f"📢 Bot Content Shared - {command_used.upper()}",
        description=f"**Command:** {command_used}\n**User:** {user}\n**Channel:** {channel_name if channel_name else 'Current channel'}\n**Content:** {content[:800]}{'...' if len(content) > 800 else ''}",
        color=BrandColors.SUCCESS,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Server: {guild.name} (ID: {guild.id})")
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Failed to send content shared log: {e}")

async def log_all_server_activity(guild_id: int, activity_type: str, user, details: str):
    """Log ANY server activity to the single unified server channel"""
    guild = bot.get_guild(guild_id)
    if not guild or guild.id == SUPPORT_SERVER_ID:
        return
    
    # Get unified server log channel
    channel = await get_server_log_channel(guild_id)
    if not channel:
        return
    
    # Simple unified log format
    embed = discord.Embed(
        title=f"📋 **{activity_type}**",
        description=f"**User:** {user}\n**Details:** {details}",
        color=BrandColors.INFO,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Server: {guild.name} (ID: {guild.id})")
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Failed to send server activity log: {e}")

# Event handlers
async def global_on_message(message):
    """Global message handler for logging"""
    if message.author.bot:
        # Check if it's the bot sending a DM
        if message.author.id == bot.user.id and isinstance(message.channel, discord.DMChannel):
            await log_dm_sent(message.channel.recipient, message.content)
        return
    
    # Log DMs received
    if isinstance(message.channel, discord.DMChannel):
        await log_dm_received(message)

async def global_on_guild_join(guild):
    """Global guild join handler"""
    await log_guild_join_global(guild)

async def global_on_guild_remove(guild):
    """Global guild remove handler"""
    await log_guild_remove_global(guild)

async def global_on_app_command_error(interaction, error):
    """Global app command error handler"""
    await log_command_error(interaction, error)

async def log_all_command_usage(interaction):
    """Log ALL slash command usage to global system"""
    if not interaction.guild or interaction.guild.id == SUPPORT_SERVER_ID:
        return
    
    try:
        command_name = interaction.command.name if interaction.command else "unknown"
        user = interaction.user
        guild = interaction.guild
        
        # Create detailed log message
        details = f"/{command_name} used"
        if hasattr(interaction, 'data') and 'options' in interaction.data:
            # Add command options if available
            options = interaction.data.get('options', [])
            if options:
                option_strings = []
                for opt in options[:3]:  # Limit to first 3 options to avoid spam
                    if 'value' in opt:
                        option_strings.append(f"{opt['name']}:{opt['value']}")
                if option_strings:
                    details += f" ({', '.join(option_strings)})"
        
        # Route to appropriate category
        command_categories = {
            # Economy commands
            'balance': 'economy', 'daily': 'economy', 'weekly': 'economy', 'work': 'economy',
            'slots': 'economy', 'trivia': 'economy', 'richest': 'economy', 'deposit': 'economy',
            'withdraw': 'economy', 'trade': 'economy', 'addcoins': 'economy', 'removecoins': 'economy',
            'buykarma': 'economy', 'seteconomycatogary': 'economy', 'setgamecatogary': 'economy',
            'setbankcatogary': 'economy', 'setecocategory': 'economy', 'setgamecategory': 'economy',
            'setbankcategory': 'economy', 'createeconomychannels': 'economy', 'create_game_channels': 'economy',
            'create_bank_channels': 'economy',
            
            # Karma commands
            'givekarma': 'karma', 'karma': 'karma', 'mykarma': 'karma', 'karmaboard': 'karma',
            'resetkarma': 'karma', 'setkarmacategory': 'karma',
            
            # Moderation commands
            'kick': 'moderation', 'ban': 'moderation', 'nuke': 'moderation', 'mute': 'moderation',
            'unmute': 'moderation', 'timeout-settings': 'moderation', 'remove-timeout': 'moderation',
            'timeout-stats': 'moderation',
            
            # Voice commands
            'movevc': 'voice', 'vckick': 'voice', 'vclock': 'voice', 'vcunlock': 'voice',
            'vclimit': 'voice',
            
            # Communication commands
            'say': 'communication', 'embed': 'communication', 'announce': 'communication',
            'poll': 'communication', 'reminder': 'communication', 'dm': 'communication',
            
            # Setup commands
            'setup': 'setup', 'autorole': 'setup', 'ticketsetup': 'setup',
            
            # Timed roles commands
            'giverole': 'timed_roles', 'removerole': 'timed_roles', 'timedroles': 'timed_roles',
            
            # Reaction role commands
            'reactionrole': 'reaction_role', 'quickreactionrole': 'reaction_role', 'listreactionroles': 'reaction_role',
            
            # Security commands
            'security': 'security', 'verification-setup': 'security', 'whitelist': 'security',
            
            # Profile commands
            'profile': 'profile', 'servercard': 'profile', 'botprofile': 'profile',
            
            # General/Info commands
            'help': 'general', 'ping': 'general', 'uptime': 'general', 'userinfo': 'general',
            'serverinfo': 'general', 'contact': 'general', 'synccommands': 'general'
        }
        
        category = command_categories.get(command_name, 'general')
        
        # Log to global system
        await log_bot_command_activity(guild.id, category, user, details)
        
    except Exception as e:
        print(f"Error logging command usage: {e}")

async def global_on_command_error(ctx, error):
    """Global command error handler"""
    await log_command_error(ctx, error)

async def global_on_interaction(interaction):
    """Global interaction handler to log all command usage"""
    if interaction.type == discord.InteractionType.application_command:
        await log_all_command_usage(interaction)

def hook_into_events():
    """Hook into existing bot events without overriding them"""
    # Add global logging to existing events by adding listeners
    bot.add_listener(global_on_message, 'on_message')
    bot.add_listener(global_on_guild_join, 'on_guild_join')
    bot.add_listener(global_on_guild_remove, 'on_guild_remove')
    bot.add_listener(global_on_app_command_error, 'on_app_command_error')
    bot.add_listener(global_on_command_error, 'on_command_error')
    bot.add_listener(global_on_interaction, 'on_interaction')
    
    print("✅ Global logging event hooks installed")

# Function to initialize global logging
async def initialize_global_logging():
    """Initialize global logging system"""
    await setup_global_channels()
    hook_into_events()
    
    # Log bot startup
    await log_console_event("Bot Startup", f"✅ {BOT_NAME} started successfully!\n**Servers:** {len(bot.guilds)}\n**Commands:** {len(bot.tree.get_commands())}")

# Add logging status command
@bot.tree.command(name="logging-status", description="🔍 View comprehensive logging system status (Bot Owner only)")
async def logging_status(interaction: discord.Interaction):
    bot_owner_id = os.getenv('BOT_OWNER_ID')
    if str(interaction.user.id) != bot_owner_id:
        await interaction.response.send_message("❌ Only the bot owner can use this command!", ephemeral=True)
        return
    
    try:
        # Get logging stats
        total_servers = len(bot.guilds)
        support_server = bot.get_guild(SUPPORT_SERVER_ID)
        
        if not support_server:
            await interaction.response.send_message("❌ Support server not found!", ephemeral=True)
            return
        
        category = discord.utils.get(support_server.categories, id=LOG_CATEGORY_ID)
        if not category:
            await interaction.response.send_message("❌ Log category not found!", ephemeral=True)
            return
        
        # Count log channels
        server_log_channels = [ch for ch in category.channels if ch.name.endswith('-logs')]
        global_channels = [ch for ch in category.channels if not ch.name.endswith('-logs')]
        
        embed = discord.Embed(
            title=f"🔍 **{BOT_NAME} Global Logging Status**",
            description=f"**Comprehensive logging system monitoring {total_servers} servers**\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=BrandColors.SUCCESS
        )
        
        embed.add_field(
            name="📊 **Global Statistics**",
            value=f"**Total Servers:** {total_servers}\n**Server Log Channels:** {len(server_log_channels)}\n**Global Log Channels:** {len(global_channels)}\n**Support Server:** {support_server.name}",
            inline=False
        )
        
        # List what's being logged
        logged_categories = [
            "🪙 **Economy** - All coin transactions, daily/weekly claims, work, slots, trading",
            "✨ **Karma** - Karma giving, board views, purchases, level-ups, resets",
            "🔨 **Moderation** - Kicks, bans, mutes, timeouts, voice actions, nukings",
            "🔊 **Voice** - Channel joins/leaves, muting/unmuting, moves, locks/unlocks",
            "💬 **Communication** - Say, embed, announce, poll, reminder, DM commands",
            "⚙️ **Setup** - All configuration changes, role setups, channel setups",
            "⏰ **Timed Roles** - Role assignments with timers, removals, expirations",
            "🎭 **Reaction Roles** - Setup, assignments, list views",
            "🛡️ **Security** - Anti-raid, verification, whitelist, permission monitoring",
            "🎫 **Tickets** - Creation, closing, reopening, setup commands",
            "👋 **Welcome** - Member joins/leaves, auto role assignments",
            "🏠 **General** - Help, ping, uptime, user/server info, profiles",
            "👤 **Profile** - Profile cards, server cards, bot profile views",
            "🔧 **Utility** - Contact info, sync commands, administrative tools"
        ]
        
        embed.add_field(
            name="📋 **What Gets Logged (ALL Commands)**",
            value="\n".join(logged_categories[:7]),
            inline=False
        )
        
        embed.add_field(
            name="📋 **Additional Categories**",
            value="\n".join(logged_categories[7:]),
            inline=False
        )
        
        embed.add_field(
            name="🌐 **Per-Server Channels**",
            value=f"Each server gets its own `{'{server-name}'}-logs` channel where ALL their bot activity is logged in real-time.",
            inline=False
        )
        
        embed.add_field(
            name="📝 **Global Channels**",
            value="• `dm-logs` - All DMs received\n• `bot-dm-send-logs` - All DMs sent by bot\n• `command-errors` - Command errors\n• `bot-events` - Server joins/leaves\n• `security-alerts` - Security warnings\n• `live-console` - Bot status updates",
            inline=False
        )
        
        embed.set_footer(text=f"✅ Logging {len(server_log_channels)} servers • All commands captured")
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error checking logging status: {str(e)}", ephemeral=True)

print("✅ Global logging system loaded")
