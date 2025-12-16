import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import aiohttp
import time
import os
import re
import random
import sys
from datetime import datetime, timedelta
import motor.motor_asyncio
from typing import Optional, Union
import json
from PIL import Image, ImageDraw, ImageFont
import io
import requests

# Bot configuration - Import from brand config
from brand_config import (
    BOT_NAME, BOT_VERSION, BOT_TAGLINE, BOT_DESCRIPTION, BOT_FOOTER, 
    BOT_OWNER_NAME, BOT_OWNER_DESCRIPTION,
    BrandColors, VisualElements, EmbedStyles, MessageTemplates, PERSONALITY
)

# Owner configuration
BOT_OWNER_ID = os.getenv('BOT_OWNER_ID')  # Get owner ID from environment

# MongoDB setup
MONGO_URI = os.getenv('MONGO_URI')
if MONGO_URI:
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = mongo_client.rxt_engine_bot
else:
    mongo_client = None
    db = None

# Cache for server settings
server_cache = {}

# Bot setup
intents = discord.Intents.all()
intents.message_content = True  # Explicitly enable message content intent
bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)
bot.remove_command('help')
bot.start_time = time.time()

async def get_server_data(guild_id):
    """Get server configuration from database"""
    guild_id = str(guild_id)
    if db is not None:
        return await db.servers.find_one({'guild_id': guild_id}) or {}
    return {}

async def update_server_data(guild_id, data):
    """Update server configuration in database"""
    guild_id = str(guild_id)
    if db is not None:
        await db.servers.update_one(
            {'guild_id': guild_id},
            {'$set': data},
            upsert=True
        )
    # Update cache
    if guild_id not in server_cache:
        server_cache[guild_id] = {}
    server_cache[guild_id].update(data)

async def log_action(guild_id, log_type, message):
    """Log actions to appropriate channels with support for single channel, organized, and global logging"""
    server_data = await get_server_data(guild_id)
    
    # Try global logging first (async fire-and-forget)
    try:
        guild = bot.get_guild(int(guild_id))
        if guild:
            from advanced_logging import send_global_log
            asyncio.create_task(send_global_log(log_type, message, guild))
    except Exception as e:
        print(f"Global logging attempt error: {e}")
    
    # Determine target color based on log type
    color_map = {
        "general": BrandColors.INFO,
        "moderation": BrandColors.DANGER,
        "setup": BrandColors.WARNING,
        "communication": BrandColors.SUCCESS,
        "karma": BrandColors.PRIMARY,
        "tickets": BrandColors.INFO,
        "ticket": BrandColors.INFO,
        "reaction_role": BrandColors.ACCENT,
        "reaction": BrandColors.ACCENT,
        "welcome": BrandColors.SUCCESS,
        "voice": BrandColors.PRIMARY,
        "voice-log": BrandColors.PRIMARY,
        "timed_roles": BrandColors.WARNING,
        "timed": BrandColors.WARNING,
        "security": BrandColors.DANGER,
        "profile": BrandColors.INFO,
        "utility": BrandColors.INFO,
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
        "ticket-log": BrandColors.PRIMARY,
        "economy-log": BrandColors.SECONDARY,
        "music-log": BrandColors.SECONDARY,
        "command-log": BrandColors.INFO,
        "error-log": BrandColors.DANGER,
        "system": BrandColors.INFO,
        "events": BrandColors.PRIMARY,
        "ai_chat": BrandColors.ACCENT,
        "ai": BrandColors.ACCENT
    }

    # Check for single log channel
    single_log = server_data.get('log_channel')
    if single_log:
        channel = bot.get_channel(int(single_log))
        if channel:
            embed = discord.Embed(
                description=message,
                color=color_map.get(log_type, BrandColors.INFO),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"{BOT_FOOTER} • {log_type.title()}", icon_url=bot.user.display_avatar.url)
            try:
                await channel.send(embed=embed)
                return
            except Exception as e:
                print(f"Error sending single log: {e}")

    # Check for organized logging system
    organized_logs = server_data.get('organized_log_channels', {})
    if organized_logs:
        # Map log types to organized channels
        log_mapping = {
            "general": "general",
            "moderation": "moderation",
            "setup": "setup",
            "communication": "communication",
            "karma": "karma",
            "tickets": "ticket-log",
            "ticket": "ticket-log",
            "reaction_role": "reaction",
            "welcome": "join-leave",
            "voice": "voice-log",
            "timed_roles": "timed",
            "security": "security",
            "quarantine": "security",
            "anti-raid": "security",
            "anti-nuke": "security",
            "antirole": "security",
            "automod": "automod",
            "join-leave": "join-leave",
            "role-update": "role-update",
            "channel-update": "channel-update",
            "message-delete": "message-delete",
            "message-edit": "message-edit",
            "member-ban": "member-ban",
            "member-kick": "member-kick",
            "command-log": "general",
            "error-log": "error-log",
            "music-log": "music-log",
            "economy-log": "economy-log",
            "system": "system",
            "profile": "general",
            "utility": "general"
        }

        mapped_channel = log_mapping.get(log_type, log_type)
        if mapped_channel in organized_logs:
            channel = bot.get_channel(int(organized_logs[mapped_channel]))
            if channel:
                embed = discord.Embed(
                    description=message,
                    color=color_map.get(log_type, BrandColors.INFO),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"{BOT_FOOTER} • {log_type.title()}", icon_url=bot.user.display_avatar.url)
                try:
                    await channel.send(embed=embed)
                    return
                except Exception as e:
                    print(f"Error sending organized log: {e}")

async def has_permission(interaction, permission_level):
    """Check if user has required permission level"""
    if interaction.user.id == interaction.guild.owner_id:
        return True

    server_data = await get_server_data(interaction.guild.id)

    if permission_level == "main_moderator":
        main_mod_role_id = server_data.get('main_moderator_role')
        if main_mod_role_id:
            main_mod_role = interaction.guild.get_role(int(main_mod_role_id))
            return main_mod_role in interaction.user.roles

    elif permission_level == "junior_moderator":
        # Junior mods can access if they have junior role OR main role
        junior_mod_role_id = server_data.get('junior_moderator_role')
        main_mod_role_id = server_data.get('main_moderator_role')

        if junior_mod_role_id:
            junior_mod_role = interaction.guild.get_role(int(junior_mod_role_id))
            if junior_mod_role in interaction.user.roles:
                return True

        if main_mod_role_id:
            main_mod_role = interaction.guild.get_role(int(main_mod_role_id))
            if main_mod_role in interaction.user.roles:
                return True

    return False

# Karma system will be handled in xp_commands.py (now karma_commands.py)

# ═══════════════════════════════════════════════════════════════════════════
# CUSTOM VC CLEANUP TASK - DEFINED BEFORE on_ready() SO IT EXISTS WHEN NEEDED
# ═══════════════════════════════════════════════════════════════════════════

@tasks.loop(seconds=30)
async def cleanup_empty_custom_vcs():
    """Auto-delete empty custom VCs after 1 minute of inactivity"""
    if db is None:
        return
    
    try:
        cutoff_time = datetime.utcnow() - timedelta(minutes=1)
        expired_vcs = await db.custom_vcs.find({'last_activity': {'$lt': cutoff_time}}).to_list(length=None)
        
        if expired_vcs:
            print(f"🔍 [CLEANUP SCAN] Found {len(expired_vcs)} expired VCs to check")
        
        for vc_data in expired_vcs:
            try:
                guild_id = int(vc_data['guild_id'])
                channel_id = int(vc_data['channel_id'])
                channel_name = vc_data.get('channel_name', 'Unknown')
                
                guild = bot.get_guild(guild_id)
                if not guild:
                    await db.custom_vcs.delete_one({'_id': vc_data['_id']})
                    continue
                
                channel = guild.get_channel(channel_id)
                if not channel:
                    await db.custom_vcs.delete_one({'_id': vc_data['_id']})
                    continue
                
                if len(channel.members) == 0:
                    await channel.delete(reason="Auto-cleanup - 1 min inactivity")
                    await db.custom_vcs.delete_one({'_id': vc_data['_id']})
                    print(f"✅ [CLEANUP] Deleted {channel_name}")
                    await log_action(guild_id, "custom_vc", f"🗑️ [VC DELETED] {channel_name} - auto cleanup")
            except Exception as e:
                print(f"❌ [CLEANUP ERROR] {e}")
                try:
                    await db.custom_vcs.delete_one({'_id': vc_data['_id']})
                except:
                    pass
    except Exception as e:
        print(f"❌ [CLEANUP FATAL] {e}")

# Bot Events
@bot.event
async def on_ready():
    print(f'⚡ {bot.user} | RXT ENGINE Online')
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers | Powered by R!O</>"
        )
    )

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")

        # Debug: List all registered commands
        all_commands = [cmd.name for cmd in bot.tree.get_commands()]
        print(f"📋 Registered commands: {', '.join(all_commands)}")

        # Check specifically for timed role commands
        timed_role_commands = [cmd for cmd in ['giverole', 'removerole', 'timedroles'] if cmd in all_commands]
        if timed_role_commands:
            print(f"✅ Timed role commands registered: {', '.join(timed_role_commands)}")
        else:
            print("⚠️ Timed role commands not found in registered commands")

    except Exception as e:
        print(f"Failed to sync commands: {e}")

    # Add persistent views for ticket system
    from ticket_system import TicketSelectionView, TicketControlView, ReopenDeleteTicketView
    bot.add_view(TicketSelectionView())
    bot.add_view(TicketControlView())
    bot.add_view(ReopenDeleteTicketView())
    print("✅ Persistent views added for ticket system")
    
    # Start custom VC cleanup task - startup verification
    try:
        if not cleanup_empty_custom_vcs.is_running():
            cleanup_empty_custom_vcs.start()
            print("✅ Custom VC cleanup task STARTED (30s interval)")
            print("✅ Empty VCs will auto-delete after 1 minute of inactivity")
        else:
            print("⚠️ Custom VC cleanup task already running")
    except Exception as e:
        print(f"❌ CRITICAL: Cleanup task startup failed: {e}")
        import traceback
        traceback.print_exc()

    # Add persistent views for security system
    from security_system import VerificationView
    bot.add_view(VerificationView())  # No dummy role ID - will load from database
    print("✅ Persistent views added for security system")

    # Start timed roles background task
    from timed_roles import start_timed_roles_task
    start_timed_roles_task()

    # Start MongoDB ping task
    if mongo_client:
        bot.loop.create_task(ping_mongodb())


    # Initialize server list monitoring
    try:
        from server_list import start_server_list_monitoring
        start_server_list_monitoring()
        print("✅ Server list monitoring initialized")
    except Exception as e:
        print(f"⚠️ Failed to initialize server list monitoring: {e}")

    # Initialize global logging channels
    try:
        from advanced_logging import initialize_global_logging
        await initialize_global_logging()
        print("✅ Global logging system initialized")
    except Exception as e:
        print(f"⚠️ Failed to initialize global logging: {e}")
    
    # Enable console output capture for live console logging
    try:
        if not isinstance(sys.stdout, ConsoleCapture):
            sys.stdout = ConsoleCapture(sys.stdout)
            print("✅ Console output capture enabled - live console logging active")
    except Exception as e:
        print(f"⚠️ Failed to enable console capture: {e}")

@bot.event
async def on_guild_join(guild):
    """Update presence when joining new server"""
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers"
        )
    )
    
    # Update server list immediately
    try:
        from server_list import on_guild_join_server_list_update
        await on_guild_join_server_list_update(guild)
    except Exception as e:
        print(f"Error updating server list on guild join: {e}")

@bot.event
async def on_guild_remove(guild):
    """Update presence when leaving server"""
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers"
        )
    )
    
    # Update server list immediately
    try:
        from server_list import on_guild_remove_server_list_update
        await on_guild_remove_server_list_update(guild)
    except Exception as e:
        print(f"Error updating server list on guild remove: {e}")

# Removed first duplicate on_message handler - merged into the main one below at line 659

async def has_permission_user(member, guild, permission_level):
    """Check if user has required permission level (for message events)"""
    if member.id == guild.owner_id:
        return True

    server_data = await get_server_data(guild.id)

    if permission_level == "main_moderator":
        main_mod_role_id = server_data.get('main_moderator_role')
        if main_mod_role_id:
            main_mod_role = guild.get_role(int(main_mod_role_id))
            return main_mod_role in member.roles

    elif permission_level == "junior_moderator":
        junior_mod_role_id = server_data.get('junior_moderator_role')
        main_mod_role_id = server_data.get('main_moderator_role')

        if junior_mod_role_id:
            junior_mod_role = guild.get_role(int(junior_mod_role_id))
            if junior_mod_role in member.roles:
                return True

        if main_mod_role_id:
            main_mod_role = guild.get_role(int(main_mod_role_id))
            if main_mod_role in member.roles:
                return True

    return False

# Command error handler for automatic help
@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle slash command errors and provide help"""
    # Log command error to global logging
    try:
        from advanced_logging import log_command_error
        error_msg = f"{type(error).__name__}: {str(error)}"
        asyncio.create_task(log_command_error(error_msg, interaction.command.name if interaction.command else "unknown", interaction.user, interaction.guild))
    except Exception as e:
        print(f"Failed to log command error: {e}")
    
    if isinstance(error, app_commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ **Access Denied**",
            description="**Missing Permissions**\nYou don't have the required permissions to use this command.",
            color=BrandColors.DANGER
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    elif isinstance(error, app_commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏳ **Cooldown Active**",
            description=f"**Please wait {error.retry_after:.1f}s** before using this command again.\n\n⚡ RXT ENGINE optimizes command usage.",
            color=BrandColors.WARNING
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    else:
        # Get command help information
        command_name = interaction.command.name if interaction.command else "unknown"
        await send_command_help(interaction, command_name)

async def send_command_help(interaction: discord.Interaction, command_name: str):
    """Send detailed help for specific command"""
    command_help = {
        "kick": {
            "title": "👢 **KICK Command Help**",
            "description": "**Usage:** `/kick @user [reason]`\n\n**What it does:** Removes a user from the server\n**Permission:** 🔴 Main Moderator only\n\n**Example:** `/kick @BadUser Breaking rules`",
            "color": BrandColors.DANGER
        },
        "ban": {
            "title": "🔨 **BAN Command Help**",
            "description": "**Usage:** `/ban @user [reason]`\n\n**What it does:** Permanently bans a user from the server\n**Permission:** 🔴 Main Moderator only\n\n**Example:** `/ban @Spammer Repeated spam messages`",
            "color": BrandColors.DANGER
        },
        "mute": {
            "title": "🔇 **MUTE Command Help**",
            "description": "**Usage:** `/mute @user`\n\n**What it does:** Mutes a user in voice channel\n**Permission:** 🔵 Junior Moderator+\n\n**Example:** `/mute @NoisyUser`",
            "color": BrandColors.WARNING
        },
        "unmute": {
            "title": "🔊 **UNMUTE Command Help**",
            "description": "**Usage:** `/unmute @user`\n\n**What it does:** Unmutes a user in voice channel\n**Permission:** 🔵 Junior Moderator+\n\n**Example:** `/unmute @User`",
            "color": BrandColors.SUCCESS
        },
        "say": {
            "title": "💬 **SAY Command Help**",
            "description": "**Usage:** `/say message:\"text\" [channel:#channel]`\n\n**What it does:** Makes the bot say something\n**Permission:** 🔵 Junior Moderator+\n\n**Example:** `/say message:\"Hello everyone!\" channel:#general`",
            "color": BrandColors.PRIMARY
        },
        "embed": {
            "title": "📋 **EMBED Command Help**",
            "description": "**Usage:** `/embed title:\"Title\" description:\"Text\" [color:blue]`\n\n**What it does:** Sends a rich embedded message\n**Permission:** 🔵 Junior Moderator+\n\n**Example:** `/embed title:\"Rules\" description:\"Be nice to everyone!\" color:green`",
            "color": BrandColors.PRIMARY
        },
        "announce": {
            "title": "📢 **ANNOUNCE Command Help**",
            "description": "**Usage:** `/announce channel:#channel message:\"text\" [mention:@role]`\n\n**What it does:** Sends official server announcements\n**Permission:** 🔴 Main Moderator only\n\n**Example:** `/announce channel:#announcements message:\"Server update!\" mention:@everyone`",
            "color": BrandColors.WARNING
        },
        "poll": {
            "title": "📊 **POLL Command Help**",
            "description": "**Usage:** `/poll question:\"Question?\" option1:\"Yes\" option2:\"No\" [option3] [option4]`\n\n**What it does:** Creates interactive polls with reactions\n**Permission:** 🔵 Junior Moderator+\n\n**Example:** `/poll question:\"Pizza party?\" option1:\"Yes!\" option2:\"No\"`",
            "color": BrandColors.SUCCESS
        },
        "reactionrole": {
            "title": "🎭 **REACTION ROLE Command Help**",
            "description": "**Usage:** `/reactionrole message:\"text\" emoji:😀 role:@role channel:#channel`\n\n**What it does:** Sets up reaction roles for users\n**Permission:** 🔴 Main Moderator only\n\n**Example:** `/reactionrole message:\"React for roles!\" emoji:😀 role:@Member channel:#roles`",
            "color": BrandColors.PRIMARY
        },

        "ticketsetup": {
            "title": "🎫 **TICKET SETUP Command Help**",
            "description": "**Usage:** `/ticketsetup action:open category:#tickets channel:#support description:\"Need help?\"`\n\n**What it does:** Sets up support ticket system\n**Actions:** open, close\n**Permission:** 🔴 Main Moderator only\n\n**Example:** `/ticketsetup action:open category:#tickets channel:#support`",
            "color": BrandColors.PRIMARY
        }
    }

    if command_name.lower() in command_help:
        help_info = command_help[command_name.lower()]
        embed = discord.Embed(
            title=help_info["title"],
            description=help_info["description"],
            color=help_info["color"]
        )
        embed.set_footer(text="🟢 = Everyone • 🔵 = Junior Moderator • 🔴 = Main Moderator")

        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass
    else:
        embed = discord.Embed(
            title="💠 **Quantum Command Help**",
            description=f"{VisualElements.CIRCUIT_LINE}\nUse `/help` to access the complete quantum command core.\n\n**Tip:** Navigate using category buttons for detailed protocols.",
            color=BrandColors.PRIMARY
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass

@bot.event
async def on_member_join(member):
    """Send welcome message, DM, and assign auto role"""
    # Log to global system
    try:
        from global_logging import log_per_server_activity
        await log_per_server_activity(member.guild.id, f"**New member joined:** {member} ({member.id})")
    except:
        pass

    server_data = await get_server_data(member.guild.id)

    # Auto role assignment
    auto_role_id = server_data.get('auto_role')
    if auto_role_id:
        auto_role = member.guild.get_role(int(auto_role_id))
        if auto_role:
            try:
                await member.add_roles(auto_role, reason="Auto role assignment")
                await log_action(member.guild.id, "moderation", f"🎭 [AUTO ROLE] {auto_role.name} assigned to {member}")
            except discord.Forbidden:
                print(f"Missing permissions to assign auto role to {member}")
            except Exception as e:
                print(f"Failed to assign auto role: {e}")

    # Send welcome message to channel
    welcome_channel_id = server_data.get('welcome_channel')
    welcome_message = server_data.get('welcome_message', f"Welcome {member.mention} to {member.guild.name}!")
    welcome_title = server_data.get('welcome_title', "⚡ **Quantum Network — New Node Detected**")
    welcome_image = server_data.get('welcome_image')

    if welcome_channel_id:
        welcome_channel = bot.get_channel(int(welcome_channel_id))
        if welcome_channel:
            # Replace placeholders safely
            formatted_message = welcome_message.replace("{user}", member.mention).replace("{server}", member.guild.name)
            formatted_title = welcome_title.replace("{user}", member.name).replace("{server}", member.guild.name)

            embed = discord.Embed(
                title=formatted_title,
                description=f"{formatted_message}\n\n*Neural connection established* 💠",
                color=BrandColors.SUCCESS
            )
            embed.set_thumbnail(url=member.display_avatar.url)

            # Add welcome image/gif if set
            if welcome_image:
                embed.set_image(url=welcome_image)

            embed.set_footer(text=f"{BOT_FOOTER} • Member #{member.guild.member_count}", icon_url=member.guild.icon.url if member.guild.icon else None)
            await welcome_channel.send(embed=embed)

    # Log member joining to join-leave channel
    await log_action(member.guild.id, "join-leave", f"🎊 [MEMBER JOIN] {member} ({member.id}) joined the server - Member #{member.guild.member_count}")

    # Send invite tracker message
    try:
        from invite_tracker import (
            get_invite_tracker, get_previous_invites, find_inviter, 
            render_tracker_message, check_rejoin, record_member_join
        )
        
        tracker_config = await get_invite_tracker(member.guild.id)
        
        if tracker_config.get('enabled'):
            channel_id = tracker_config.get('channel_id')
            tracker_channel = bot.get_channel(int(channel_id)) if channel_id else None
            
            if tracker_channel:
                # Check if rejoin
                is_rejoin = await check_rejoin(member.guild.id, member.id)
                
                # Get previous invites and find inviter only on first join
                inviter = None
                invite = None
                invite_count = 0
                
                if not is_rejoin:
                    before_invites = await get_previous_invites(str(member.guild.id))
                    inviter, invite = await find_inviter(str(member.guild.id), before_invites)
                    invite_count = invite.uses if invite else 0
                
                # Record the join
                await record_member_join(member.guild.id, member.id)
                
                # Render and send tracker message
                tracker_embed = await render_tracker_message(member, inviter, invite_count, tracker_config)
                
                if tracker_embed:
                    rejoin_tag = " **(REJOIN)**" if is_rejoin else ""
                    await tracker_channel.send(
                        content=f"{member.mention} joined{rejoin_tag}" + (f" (Invited by {inviter.mention})" if inviter else ""),
                        embed=tracker_embed
                    )
                    
                    # Log the tracker event
                    rejoin_text = " (REJOIN)" if is_rejoin else ""
                    inviter_text = f"by {inviter}" if inviter else "source unknown"
                    await log_action(member.guild.id, "join-leave", f"📊 [INVITE TRACKER] {member} joined {inviter_text}{rejoin_text}")
    except Exception as e:
        print(f"❌ [INVITE TRACKER ERROR] {e}")

    # Send DM to new member (combine server welcome + bot message)
    try:
        # Get server's custom welcome message for DM
        dm_welcome_message = server_data.get('welcome_message')
        dm_welcome_title = server_data.get('welcome_title')
        
        # Build DM embed with server's message if available
        if dm_welcome_message:
            formatted_dm_message = dm_welcome_message.replace("{user}", member.mention).replace("{server}", member.guild.name)
            formatted_dm_title = dm_welcome_title.replace("{user}", member.name).replace("{server}", member.guild.name) if dm_welcome_title else f"Welcome to {member.guild.name}!"
            
            server_embed = discord.Embed(
                title=formatted_dm_title,
                description=formatted_dm_message,
                color=BrandColors.SUCCESS
            )
            server_embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else None)
            if welcome_image:
                server_embed.set_image(url=welcome_image)
            server_embed.set_footer(text=f"Message from {member.guild.name}")
            
            await member.send(embed=server_embed)
            # Log DM sent
            from advanced_logging import log_dm_sent
            await log_dm_sent(member, formatted_dm_message, member.guild)
        
        # Always send bot's message after server message
        bot_content = f"**Neural connection established with {member.guild.name}**\n\n{VisualElements.CIRCUIT_LINE}\n\n◆ **System initialized — explore quantum channels and protocols**\n◆ **Assistance protocol active — mention core or execute commands**\n◆ **Holographic network operational**\n\n{VisualElements.CIRCUIT_LINE}\n\n*{BOT_TAGLINE}*"
        bot_embed = discord.Embed(
            title=f"💠 **{BOT_NAME} — Quantum Core Online**",
            description=bot_content,
            color=BrandColors.PRIMARY
        )
        bot_embed.set_thumbnail(url=bot.user.display_avatar.url)
        bot_embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)

        view = discord.ui.View()
        invite_button = discord.ui.Button(label="🤖 Invite Bot to Other Servers", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🤖")
        view.add_item(invite_button)

        await member.send(embed=bot_embed, view=view)
        # Log DM sent
        from advanced_logging import log_dm_sent
        await log_dm_sent(member, bot_content, member.guild)
    except:
        pass  # User has DMs disabled

@bot.event
async def on_message(message):
    """Handle all message events including DMs and security checks"""
    print(f"🟢 [DEBUG] on_message triggered! Author: {message.author}, Bot: {message.author.bot}")
    
    # Process commands first
    await bot.process_commands(message)
    
    # Skip bot messages
    if message.author.bot:
        print(f"🤖 [DEBUG] Skipping bot message from {message.author}")
        return
    
    print(f"🔍 [ON_MESSAGE] Message from {message.author} in {message.guild.name if message.guild else 'DM'}: {message.content[:100]}")
    
    # Handle Reaction Role Setup (text-based command)
    if message.guild and message.content.startswith("reaction role setup"):
        if not await has_permission(message, "main_moderator"):
            await message.channel.send("❌ Only Main Moderators can set up reaction roles!")
            return
        
        await message.channel.send("Please provide the message ID, emoji, role, and channel for the reaction role.")
        
        def check(m):
            return m.author == message.author and m.channel == message.channel
        
        try:
            # Get message ID
            msg_prompt = await bot.wait_for("message", check=check, timeout=60)
            message_id = int(msg_prompt.content.split()[0])
            message_to_react = await message.channel.fetch_message(message_id)
            
            # Get emoji
            emoji_prompt = await bot.wait_for("message", check=check, timeout=60)
            emoji_str = emoji_prompt.content
            
            # Get role name
            role_prompt = await bot.wait_for("message", check=check, timeout=60)
            role_name = role_prompt.content
            role = discord.utils.get(message.guild.roles, name=role_name)
            if not role:
                await message.channel.send(f"❌ Role '{role_name}' not found.")
                return
            
            # Add reaction to message
            try:
                await message_to_react.add_reaction(emoji_str)
            except discord.HTTPException:
                await message.channel.send("❌ Invalid emoji provided.")
                return
            
            await message.channel.send("✅ Reaction role setup complete!")
            
        except asyncio.TimeoutError:
            await message.channel.send("❌ Timeout. Please try the command again.")
        except Exception as e:
            await message.channel.send(f"❌ An error occurred: {e}")
        return
    
    # Handle AI chat in designated channels (must be after reaction role check)
    if message.guild:
        print(f"📤 [AI HANDLER] handle_ai_message is: {handle_ai_message}")
        if handle_ai_message:
            try:
                print(f"🚀 [AI HANDLER] Calling handle_ai_message for: {message.content[:50]}")
                await handle_ai_message(message)
            except Exception as e:
                print(f"❌ [AI CHAT ERROR] {e}")
        else:
            print(f"⚠️ [AI HANDLER] handle_ai_message is None!")
    
    # Handle DM mentions
    if not message.guild:  # This is a DM
        # Log DM received to global logging
        try:
            from advanced_logging import log_dm_received
            await log_dm_received(message.author, message.content)
        except Exception as e:
            print(f"Failed to log DM received: {e}")
        
        # Check for bot mention in DMs - Send contact info
        if (bot.user in message.mentions or
            f"<@{bot.user.id}>" in message.content or
            f"<@!{bot.user.id}>" in message.content):

            # Send contact info in DMs
            bot_owner_id = os.getenv('BOT_OWNER_ID')
            contact_email = os.getenv('CONTACT_EMAIL')
            support_server = os.getenv('SUPPORT_SERVER')

            owner_mention = f"<@{bot_owner_id}>" if bot_owner_id else "Contact via server"
            email_text = contact_email if contact_email else "Not available"
            support_text = support_server if support_server else "Contact owner for invite"

            embed = discord.Embed(
                title="📞 **Contact Information & Support**",
                description=f"*Hello! Here's how to get help or get in touch:*\n\n**👨‍💻 Developer:** {owner_mention}\n**📧 Email:** `{email_text}`\n**🏠 Support Server:** {support_text}\n\n*Need quick help? Use `/help` in any server!*",
                color=BrandColors.PRIMARY
            )
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)

            view = discord.ui.View()
            if support_server:
                support_button = discord.ui.Button(label="🏠 Support Server", style=discord.ButtonStyle.link, url=support_server, emoji="🏠")
                view.add_item(support_button)

            invite_button = discord.ui.Button(label="🔗 Invite Bot", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🔗")
            view.add_item(invite_button)

            sent_message = await message.channel.send(embed=embed, view=view)

            # Log DM sent globally
            try:
                from advanced_logging import log_dm_sent
                asyncio.create_task(log_dm_sent(message.author, "Contact information sent - Bot mention detected"))
            except Exception as e:
                print(f"Failed to log DM sent: {e}")

            # Auto delete after 1 minute
            await asyncio.sleep(60)
            try:
                await sent_message.delete()
            except:
                pass
            return

        # Check for owner mention in DMs
        owner_id = os.getenv('BOT_OWNER_ID')
        if owner_id and (f"<@{owner_id}>" in message.content or
                        f"<@!{owner_id}>" in message.content or
                        "daazo" in message.content.lower()):
            owner_mention = f"<@{owner_id}>" if owner_id else "Contact via server"
            embed = discord.Embed(
                title="📢 **Developer Mention**",
                description=f"**Developer:** {owner_mention}\n\n**About:** {BOT_OWNER_DESCRIPTION}\n\n**Need Help?** Use `/help` or contact the support server.",
                color=BrandColors.ACCENT
            )
            embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            sent_message = await message.channel.send(embed=embed)
            
            # Log DM sent globally
            try:
                from advanced_logging import log_dm_sent
                asyncio.create_task(log_dm_sent(message.author, "Developer information sent - Owner mention detected"))
            except Exception as e:
                print(f"Failed to log DM sent: {e}")
            
            # Auto delete after 1 minute
            await asyncio.sleep(60)
            try:
                await sent_message.delete()
            except:
                pass
            return

        return  # Don't process other DM messages

@bot.event
async def on_message_delete(message):
    """Log deleted messages to message-delete channel"""
    if message.author.bot:
        return
    
    if not message.guild:
        return
    
    # Create embed for deleted message
    embed = discord.Embed(
        title="🗑️ **Message Deleted**",
        description=f"**Author:** {message.author.mention} ({message.author})\n**Channel:** {message.channel.mention}\n**Content:** {message.content[:1000] if message.content else '*No content (may be embed/attachment only)*'}",
        color=BrandColors.WARNING,
        timestamp=datetime.now()
    )
    
    if message.attachments:
        attachment_list = "\n".join([f"[{att.filename}]({att.url})" for att in message.attachments[:3]])
        embed.add_field(name="📎 Attachments", value=attachment_list, inline=False)
    
    embed.set_footer(text=f"{BOT_FOOTER} • User ID: {message.author.id}", icon_url=bot.user.display_avatar.url)
    embed.set_thumbnail(url=message.author.display_avatar.url)
    
    # Log to message-delete log channel via advanced logging system
    await log_action(message.guild.id, "message-delete", f"🗑️ [MESSAGE DELETE] {message.author} in {message.channel.mention}\nContent: {message.content[:100] if message.content else '(No text content)'}")

@bot.event
async def on_message_edit(before, after):
    """Log edited messages with content to message-edit channel"""
    if after.author.bot:
        return
    
    if not after.guild:
        return
    
    # Ignore if content didn't actually change
    if before.content == after.content:
        return
    
    # Create embed for edited message with before/after content
    embed = discord.Embed(
        title="✏️ **Message Edited**",
        description=f"**Author:** {after.author.mention} ({after.author})\n**Channel:** {after.channel.mention}",
        color=BrandColors.WARNING,
        timestamp=datetime.now()
    )
    
    # Show before and after content
    before_content = before.content[:500] if before.content else "*No previous content*"
    after_content = after.content[:500] if after.content else "*No content*"
    
    embed.add_field(name="📝 Before", value=f"```{before_content}```", inline=False)
    embed.add_field(name="✨ After", value=f"```{after_content}```", inline=False)
    
    embed.set_footer(text=f"{BOT_FOOTER} • User ID: {after.author.id}", icon_url=bot.user.display_avatar.url)
    embed.set_thumbnail(url=after.author.display_avatar.url)
    
    # Send to message-edit log channels
    server_data = await get_server_data(after.guild.id)
    organized_logs = server_data.get('organized_log_channels', {})
    
    # Try organized logging first
    if organized_logs and 'message-edit' in organized_logs:
        channel = bot.get_channel(int(organized_logs['message-edit']))
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"Error sending message edit log: {e}")
    
    # Try single log channel
    single_log = server_data.get('log_channel')
    if single_log and not organized_logs:
        channel = bot.get_channel(int(single_log))
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"Error sending message edit to single log: {e}")
    
    # Also log to global system
    await log_action(after.guild.id, "message-edit", f"✏️ [MESSAGE EDIT] {after.author} in {after.channel.mention}\nBefore: {before_content[:100]}\nAfter: {after_content[:100]}")

@bot.event
async def on_voice_state_update(member, before, after):
    """Log voice channel activities to voice-log channel"""
    if member.bot:
        return

    # Member joined a voice channel
    if before.channel is None and after.channel is not None:
        await log_action(member.guild.id, "voice-log", f"🔊 [VOICE JOIN] {member} joined {after.channel.name}")
        try:
            from global_logging import log_global_activity
            await log_global_activity("Voice Activity", member.guild.id, member.id, f"Joined voice channel: {after.channel.name}")
        except:
            pass

    # Member left a voice channel
    elif before.channel is not None and after.channel is None:
        await log_action(member.guild.id, "voice-log", f"🔇 [VOICE LEAVE] {member} left {before.channel.name}")
        try:
            from global_logging import log_global_activity
            await log_global_activity("Voice Activity", member.guild.id, member.id, f"Left voice channel: {before.channel.name}")
        except:
            pass

    # Member moved between voice channels
    elif before.channel is not None and after.channel is not None and before.channel != after.channel:
        await log_action(member.guild.id, "voice-log", f"🔄 [VOICE MOVE] {member} moved from {before.channel.name} to {after.channel.name}")
        try:
            from global_logging import log_global_activity
            await log_global_activity("Voice Activity", member.guild.id, member.id, f"Moved from {before.channel.name} to {after.channel.name}")
        except:
            pass

    # Member was muted/unmuted
    if before.mute != after.mute:
        status = "muted" if after.mute else "unmuted"
        await log_action(member.guild.id, "voice-log", f"🔇 [VOICE MUTE] {member} was {status} in {after.channel.name if after.channel else 'voice'}")
        try:
            from global_logging import log_global_activity
            await log_global_activity("Voice Moderation", member.guild.id, member.id, f"Was {status}")
        except:
            pass

    # Member was deafened/undeafened
    if before.deaf != after.deaf:
        status = "deafened" if after.deaf else "undeafened"
        await log_action(member.guild.id, "voice-log", f"🔇 [VOICE DEAF] {member} was {status} in {after.channel.name if after.channel else 'voice'}")
        try:
            from global_logging import log_global_activity
            await log_global_activity("Voice Moderation", member.guild.id, member.id, f"Was {status}")
        except:
            pass

@bot.event
async def on_member_remove(member):
    """Send goodbye DM and log"""
    # Log member leaving to join-leave channel
    await log_action(member.guild.id, "join-leave", f"👋 [MEMBER LEAVE] {member} ({member.id}) left the server")

    # Log to global system
    try:
        from global_logging import log_per_server_activity
        await log_per_server_activity(member.guild.id, f"**Member left:** {member} ({member.id})")
    except:
        pass

    # Send goodbye DM
    try:
        embed = discord.Embed(
            title=f"💠 **Neural Disconnection Detected: {member.display_name}**",
            description=f"**Quantum core acknowledges departure from {member.guild.name}**\n\n{VisualElements.CIRCUIT_LINE}\n\n**◆ Connection archived to quantum memory banks**\n**◆ Neural pathway preserved for potential reconnection**\n**◆ System status: Nominal**\n\n{VisualElements.CIRCUIT_LINE}\n\n*— {BOT_NAME} Quantum Core*",
            color=BrandColors.DANGER
        )
        embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else bot.user.display_avatar.url)
        embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)

        view = discord.ui.View()
        invite_button = discord.ui.Button(label="🤖 Invite Bot to Other Servers", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🤖")
        view.add_item(invite_button)

        await member.send(embed=embed, view=view)

        # Log goodbye DM globally
        try:
            from global_logging import log_dm_sent
            await log_dm_sent(member, f"Goodbye message - Thank you for being part of {member.guild.name}")
        except:
            pass
    except:
        pass  # User has DMs disabled

@bot.event
async def on_member_ban(guild, user):
    """Log member ban to member-ban channel"""
    await log_action(guild.id, "member-ban", f"🔨 [MEMBER BAN] {user} ({user.id}) was banned from {guild.name}")


@bot.event
async def on_guild_role_create(role):
    """Log role creation to role-update channel"""
    await log_action(role.guild.id, "role-update", f"✨ [ROLE CREATE] {role.name} role created with permissions")

@bot.event
async def on_guild_role_delete(role):
    """Log role deletion to role-update channel"""
    await log_action(role.guild.id, "role-update", f"🗑️ [ROLE DELETE] {role.name} role was deleted")

@bot.event
async def on_guild_role_update(before, after):
    """Log role updates to role-update channel"""
    changes = []
    if before.name != after.name:
        changes.append(f"Name: {before.name} → {after.name}")
    if before.color != after.color:
        changes.append(f"Color: {before.color} → {after.color}")
    if before.permissions != after.permissions:
        changes.append(f"Permissions changed")
    
    if changes:
        change_text = " | ".join(changes)
        await log_action(after.guild.id, "role-update", f"📝 [ROLE UPDATE] {after.name} role updated: {change_text}")

@bot.event
async def on_guild_channel_create(channel):
    """Log channel creation to channel-update channel"""
    channel_type = "Category" if isinstance(channel, discord.CategoryChannel) else "Text" if isinstance(channel, discord.TextChannel) else "Voice"
    await log_action(channel.guild.id, "channel-update", f"✨ [CHANNEL CREATE] {channel_type} channel {channel.mention} created")

@bot.event
async def on_guild_channel_delete(channel):
    """Log channel deletion to channel-update channel"""
    channel_type = "Category" if isinstance(channel, discord.CategoryChannel) else "Text" if isinstance(channel, discord.TextChannel) else "Voice"
    await log_action(channel.guild.id, "channel-update", f"🗑️ [CHANNEL DELETE] {channel_type} channel {channel.name} was deleted")

@bot.event
async def on_guild_channel_update(before, after):
    """Log channel updates to channel-update channel"""
    changes = []
    if before.name != after.name:
        changes.append(f"Name: {before.name} → {after.name}")
    if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
        if before.topic != after.topic:
            changes.append("Topic changed")
        if before.slowmode_delay != after.slowmode_delay:
            changes.append(f"Slowmode: {before.slowmode_delay}s → {after.slowmode_delay}s")
    
    if changes:
        change_text = " | ".join(changes)
        await log_action(after.guild.id, "channel-update", f"📝 [CHANNEL UPDATE] {after.name} updated: {change_text}")

# Help Command Callback
async def help_command_callback(interaction):
    """Callback for help button"""
    embed = discord.Embed(
        title=f"💠 **{BOT_NAME} • Quantum Command Core**",
        description=f"**◆ SYSTEM READY**\n{VisualElements.CIRCUIT_LINE}\n\nWelcome to RXT ENGINE—an advanced AI core for complete server automation.\n\nSelect a category below to access quantum-powered commands. For command details, type `/` followed by the command name.\n\n**⚡ AUTHORIZATION LEVELS**\n\n🟣 **Everyone** — General access to karma, tickets, and public commands\n🟡 **Junior Moderator** — Basic moderation capabilities\n🔴 **Main Moderator** — Full moderation and configuration access  \n👑 **Server Owner** — Complete quantum core control",
        color=BrandColors.PRIMARY
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
    embed.set_thumbnail(url=bot.user.display_avatar.url)

    view = HelpView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    await log_action(interaction.guild.id, "general", f"📋 [HELP] {interaction.user} used help command")

# Professional Help View Class
class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(HelpSelect())

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="General", value="general", emoji="🏠", description="Core utilities and info commands"),
            discord.SelectOption(label="Moderation", value="moderation", emoji="⚔️", description="Security and enforcement tools"),
            discord.SelectOption(label="Security", value="security", emoji="🛡️", description="Anti-raid, anti-nuke, quarantine system"),
            discord.SelectOption(label="Setup", value="setup", emoji="⚙️", description="Configuration and customization"),
            discord.SelectOption(label="Messages", value="messages", emoji="💬", description="Communication and announcements"),
            discord.SelectOption(label="Karma", value="karma", emoji="⭐", description="Community recognition system"),
            discord.SelectOption(label="Tickets", value="tickets", emoji="🎫", description="Support and issue tracking"),
            discord.SelectOption(label="Verification", value="verification", emoji="✅", description="CAPTCHA verification system"),
            discord.SelectOption(label="Advanced", value="advanced", emoji="🎭", description="Reaction roles and automation"),
            discord.SelectOption(label="About", value="about", emoji="ℹ️", description="Bot info and specifications"),
            discord.SelectOption(label="Updates", value="updates", emoji="🆕", description="Recent changes and updates"),
        ]
        super().__init__(placeholder="Select a help category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selection = self.values[0]
        
        if selection == "general":
            await self.show_general_help(interaction)
        elif selection == "moderation":
            await self.show_moderation_help(interaction)
        elif selection == "security":
            await self.show_security_help(interaction)
        elif selection == "setup":
            await self.show_setup_help(interaction)
        elif selection == "messages":
            await self.show_communication_help(interaction)
        elif selection == "karma":
            await self.show_karma_help(interaction)
        elif selection == "tickets":
            await self.show_ticket_help(interaction)
        elif selection == "verification":
            await self.show_verification_help(interaction)
        elif selection == "advanced":
            await self.show_advanced_help(interaction)
        elif selection == "about":
            await self.show_bot_info_help(interaction)
        elif selection == "updates":
            await self.show_recent_updates_help(interaction)

    async def show_general_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💠 **General Commands**",
            description=f"*Core system utilities for user/server information, diagnostics, and statistics.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PRIMARY
        )
        embed.add_field(
            name="🟢 `/help`",
            value="**Usage:** `/help`\n**Description:** Display this comprehensive help menu with all commands",
            inline=False
        )
        embed.add_field(
            name="🟢 `/userinfo [user]`",
            value="**Usage:** `/userinfo [user:@member]`\n**Description:** Show detailed user information including join date, roles, status, avatar",
            inline=False
        )
        embed.add_field(
            name="🟢 `/serverinfo`",
            value="**Usage:** `/serverinfo`\n**Description:** Display comprehensive server information - owner, member count, creation date, channels",
            inline=False
        )
        embed.add_field(
            name="🟡 `/ping`",
            value="**Usage:** `/ping`\n**Description:** Check bot latency and connection status to Discord servers",
            inline=False
        )
        embed.add_field(
            name="🟡 `/uptime`",
            value="**Usage:** `/uptime`\n**Description:** Display how long the bot has been running continuously",
            inline=False
        )
        embed.add_field(
            name="🎨 **Profile & Visual Commands**",
            value="**🟢 `/profile [user]`** - Generate beautiful profile cards with stats\n**🟡 `/servercard`** - Create server overview cards\n**🟢 `/botprofile`** - View bot information card\n**🟢 `/contact`** - Get bot contact information and support",
            inline=False
        )
        embed.set_footer(text="🟣 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=HelpView())

    async def show_moderation_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚔️ **Moderation Commands**",
            description=f"*Security enforcement protocols for maintaining server order and safety.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.DANGER
        )
        embed.add_field(
            name="🔴 `/kick user [reason]`",
            value="**Usage:** `/kick user:@member [reason:\"text\"]`\n**Description:** Remove user from server with optional reason and logging",
            inline=False
        )
        embed.add_field(
            name="🔴 `/ban user [reason]`",
            value="**Usage:** `/ban user:@member [reason:\"text\"]`\n**Description:** Permanently ban user from server with logging",
            inline=False
        )
        embed.add_field(
            name="🔴 `/nuke`",
            value="**Usage:** `/nuke`\n**Description:** Delete ALL messages in current channel (⚠️ IRREVERSIBLE! Use with extreme caution)",
            inline=False
        )
        embed.add_field(
            name="🟡 **Voice Moderation Commands**",
            value="**`/mute @user`** - Mute user in voice channel\n**`/unmute @user`** - Unmute user in voice channel\n**`/movevc @user #channel`** - Move user to different voice channel\n**`/vckick @user`** - Kick user from voice channel\n**`/vckick`** - Lock current voice channel\n**`/vcunlock`** - Unlock voice channel\n**`/vclimit <0-99>`** - Set voice channel user limit",
            inline=False
        )
        embed.add_field(
            name="🎭 **Timed Role Management**",
            value="**🔴 `/giverole @user <role> <duration>`** - Give role for specific time (e.g., 1h30m, 2d)\n**🔴 `/removerole @user <role>`** - Manually remove role (cancels timed roles)\n**🟡 `/timedroles`** - View all active timed roles in server\n**Auto-expiry:** Roles removed automatically when time expires",
            inline=False
        )

        embed.set_footer(text="🟣 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=HelpView())

    async def show_security_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ **RXT Security System**",
            description=f"*Advanced multi-layer protection protocols for comprehensive server defense.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.WARNING
        )
        embed.add_field(
            name="⚡ **9-Module Protection Suite**",
            value="**🔴 `/antiraid`** - Detect suspicious join patterns, account age checks, username filtering\n**🔴 `/antinuke`** - Prevent mass channel/role deletion and ban/kick attacks\n**🔴 `/antispam`** - Message rate limiting with configurable thresholds\n**🔴 `/antilink`** - Block malicious links with domain whitelist support\n**🔴 `/webhookguard`** - Detect and remove unauthorized webhooks\n**🔴 `/antirole`** - Prevent high-permission role creation/escalation\n**🔴 `/massmention`** - Block unauthorized @everyone/@here mentions\n**👑 `/timeout`** - Manual timeout management (Discord native)\n**👑 `/whitelist`** - Bypass protection for trusted users, roles, bots",
            inline=False
        )
        embed.add_field(
            name="🔒 **Quarantine System**",
            value="**Automatic Containment:** Suspicious users automatically moved to quarantine category\n**Persistent Tracking:** Violation history survives across sessions\n**Role Protection:** Quarantined users cannot receive sensitive roles\n**Manual Control:** `/quarantine action:info/release` for staff override\n**Evidence Logging:** Full violation history with timestamps and details",
            inline=False
        )
        embed.add_field(
            name="⏱️ **Timeout System**",
            value="**Discord Native:** Uses Discord's built-in timeout API (ToS-compliant)\n**Complete Silence:** Prevents ALL user communication during timeout\n**No Messages, No Reactions, No Voice:** Complete communication blackout\n**Manual Management:** `/timeout @user <time>` and `/untimeout @user`\n**Moderator Notifications:** Optional timeout channel for staff logging",
            inline=False
        )
        embed.add_field(
            name="🟩 **Whitelist System**",
            value="**User Bypass:** `/whitelist add:user @member` - Skip protections for trusted users\n**Role Bypass:** `/whitelist add:role @trusted-role` - Exempt entire roles\n**Bot Bypass:** `/whitelist add:bot @bot-name` - Trusted bots bypass checks\n**Server Owner:** Automatically whitelisted at all times\n**Full Management:** `/whitelist remove/list` to manage exceptions",
            inline=False
        )
        embed.add_field(
            name="⚙️ **Main Security Control Panel**",
            value="**🔴 `/security`** - Enable/disable/status/config all protections\n**Setup:** `/security action:enable` to activate security system\n**Status:** `/security action:status` to check all module states\n**Customize:** `/security action:config module:<name>` for fine-tuning\n**Features:** Per-module enable/disable, configurable thresholds, logging",
            inline=False
        )
        embed.add_field(
            name="📊 **Advanced Features**",
            value="**Real-time Monitoring:** Live threat detection with instant response\n**Severity Tracking:** Violation levels escalate with repeat offenses\n**Whitelisted User Protection:** Premium members never quarantined\n**Role Escalation Prevention:** Blocks privilege elevation attempts\n**Webhook Monitoring:** Detects unauthorized channel integrations\n**Cross-Session Persistence:** Violation history never resets",
            inline=False
        )
        embed.set_footer(text="🟣 = Everyone • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=HelpView())

    async def show_setup_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚙️ **Setup & Configuration**",
            description=f"*Quantum core configuration protocols for system customization and automation.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PANEL
        )
        embed.add_field(
            name="👑 `/setup main_moderator role`",
            value="**Usage:** `/setup main_moderator role:@role`\n**Description:** Set main moderator role (Server Owner only) - Full bot permissions",
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup junior_moderator role`",
            value="**Usage:** `/setup junior_moderator role:@role`\n**Description:** Set junior moderator role - Limited safe moderation commands",
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup welcome channel value`",
            value="**Usage:** `/setup welcome channel:#channel value:\"Welcome {user}!\"`\n**Description:** Configure welcome messages and channel\n**Variables:** {user}, {server}\n**Image support:** Add image URLs for welcome cards\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🔴 `/autorole action role`",
            value="**Usage:** `/autorole action:set role:@role` or `/autorole action:remove`\n**Description:** Set or remove auto role for new members\n**Auto-assigns:** Role given to all new members on join",
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup karma_channel channel`",
            value="**Usage:** `/setup karma_channel channel:#karma`\n**Description:** Set channel for karma level-up announcements and milestones",
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup ticket_support_role role`",
            value="**Usage:** `/setup ticket_support_role role:@support`\n**Description:** Set support role to be mentioned when tickets are created\n\u200b",
            inline=False
        )
        embed.set_footer(text="🟣 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=HelpView())

    async def show_communication_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💬 **Communication & Messaging**",
            description=f"*Quantum messaging protocols for announcements, polls, and direct communication.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.SUCCESS
        )
        embed.add_field(
            name="🟡 `/say message [channel]`",
            value="**Usage:** `/say message:\"Hello everyone!\" [channel:#general]`\n**Description:** Make bot send a message to specified channel or current channel",
            inline=False
        )
        embed.add_field(
            name="🟡 `/embed title description [color]`",
            value="**Usage:** `/embed title:\"Title\" description:\"Text\" [color:blue]`\n**Description:** Send rich embedded message with custom styling and colors\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🔴 `/announce channel message [mention]`",
            value="**Usage:** `/announce channel:#announcements message:\"Big news!\" [mention:@everyone]`\n**Description:** Send official server announcements with professional formatting",
            inline=False
        )
        embed.add_field(
            name="🟡 `/poll question option1 option2 [option3] [option4]`",
            value="**Usage:** `/poll question:\"Pizza party?\" option1:\"Yes!\" option2:\"No\"`\n**Description:** Create interactive polls with automatic reactions (up to 4 options)",
            inline=False
        )
        embed.add_field(
            name="🟡 `/reminder message time`",
            value="**Usage:** `/reminder message:\"Meeting time!\" time:1h30m`\n**Description:** Set personal reminders - I'll DM you when time's up!\n**Formats:** 1h30m, 45s, 2d (max 7 days)\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🔴 `/dm user message`",
            value="**Usage:** `/dm user:@member message:\"Your ticket was closed\"`\n**Description:** Send DM to user from server (staff use) - Professional server-branded DMs",
            inline=False
        )
        embed.set_footer(text="🟣 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=HelpView())

    async def show_karma_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⭐ **Karma System**",
            description=f"*Community recognition protocol—appreciate members and earn quantum karma points for positive contributions.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.SECONDARY
        )
        embed.add_field(
            name="🟢 `/givekarma @user [reason]`",
            value="**Usage:** `/givekarma user:@member reason:\"helping with code\"`\n**Description:** Give 1-2 karma points to someone for their contribution\n**Cooldown:** 3 minutes between giving karma to same user\n**Example:** `/givekarma @John reason:\"Great help with coding!\"`",
            inline=False
        )
        embed.add_field(
            name="🟢 `/karma [user]` & `/mykarma`",
            value="**Usage:** `/karma user:@member` or `/mykarma`\n**Description:** Check karma points, server rank, and progress to next milestone\n**Features:** Beautiful progress bars, rankings, and milestone tracking",
            inline=False
        )
        embed.add_field(
            name="🟢 `/karmaboard`",
            value="**Usage:** `/karmaboard`\n**Description:** Show top 10 karma earners with medals and rankings\n**Features:** Community leaderboard highlighting positive contributors with 🥇🥈🥉",
            inline=False
        )
        embed.add_field(
            name="⭐ **Reaction Karma** (Auto-Karma)",
            value="**Positive:** 👍 ⭐ ❤️ 🔥 💯 ✨ = +1 karma\n**Negative:** 👎 💀 😴 🤮 🗿 = -1 karma\n**How it works:** Reacting to messages gives/removes karma automatically\n**Cooldown:** 3 minutes between reactions to same user\n**Anti-abuse:** Can't react to your own messages for karma\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🎉 **Milestones & Level-Ups**",
            value="**Every 5 karma:** Celebration announcement with motivational quotes\n**Animated GIFs:** Level-up messages include celebration animations\n**Progress tracking:** Visual progress bars toward next 5-karma milestone\n**Channel announcements:** Set with `/setup karma_channel #channel`\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🎨 **Profile & Visual Cards**",
            value="**🟢 `/profile [user]`** - Generate beautiful profile card with avatar and karma\n**🟡 `/servercard`** - Create server overview card with stats and member info\n**🟢 `/botprofile`** - View bot information card with system status\n**Features:** Circular avatars, progress bars, karma levels, server stats\n**Design:** Modern futuristic design with professional UI",
            inline=False
        )
        embed.add_field(
            name="🔧 **Admin Setup Commands**",
            value="**🔴 `/resetkarma scope:user user:@member`** - Reset specific user's karma\n**🔴 `/resetkarma scope:server`** - Reset all server karma data\n**Setup:** Use `/setup karma_channel #channel` for level-up announcements",
            inline=False
        )
        embed.set_footer(text="🟣 = Everyone • 🔴 = Main Moderator")
        await interaction.response.edit_message(embed=embed, view=HelpView())

    async def show_ticket_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 **Tickets & Support System**",
            description=f"*Advanced support protocol with custom categories and dynamic form fields.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PRIMARY
        )
        embed.add_field(
            name="📋 **Main Setup Commands**",
            value="**🔴 `/ticketpanel`** - Create ticket selection panel with dropdown menu\n**🔴 `/ticketcategory category_number`** - Configure ticket category (1-7 options available)\n**🔴 `/ticketfields category_number`** - Set custom form fields for each category\n**🔴 `/setup ticket_support_role role:@support`** - Set support role to mention on ticket creation\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🎯 **Multi-Category System**",
            value="**Up to 7 Categories:** Support, Billing, Bug Reports, Suggestions, Appeals, Custom 1, Custom 2\n**Custom Names & Emojis:** Each category has unique icon and description\n**Category Controls:** Enable/disable categories per server\n**Automatic Counters:** Ticket numbers tracked per category\n**Dynamic Routing:** Users select category before filling form\n\u200b",
            inline=False
        )
        embed.add_field(
            name="📝 **Custom Form Fields**",
            value="**Up to 5 Fields Per Category:** Configure custom questions for each ticket type\n**Field Types:** Short text or long text format\n**Customizable Labels:** Name each field specifically (e.g., 'Account Email', 'Error Code')\n**Field Emojis:** Add visual indicators for each form field\n**Validation:** Required/optional fields with character limits\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🎫 **Complete Ticket Flow**",
            value="**1.** User clicks ticket panel → selects category via dropdown menu\n**2.** Modal form appears with category-specific custom fields\n**3.** Private ticket channel created automatically\n**4.** Support role mentioned (if configured)\n**5.** Staff can close/reopen/delete tickets with control buttons\n**6.** 10-minute cooldown between ticket creation\n**7.** Ticket naming: `category-username-ticketnumber`\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🔧 **Ticket Control Panel**",
            value="**✅ Close** - Archive ticket (staff only)\n**🔄 Reopen** - Reopen closed ticket\n**🗑️ Delete** - Permanently delete ticket\n**📝 Rename** - Use `/tnamechange` to rename ticket channel\n**Permissions:** User + Staff roles can see ticket channel\n\u200b",
            inline=False
        )
        embed.add_field(
            name="⚡ **Quick Setup Steps**",
            value="**Step 1:** `/ticketcategory 1 name:Support emoji:🛟 description:\"General support\"`\n**Step 2:** `/ticketfields 1` - Add custom form fields\n**Step 3:** `/setup ticket_support_role role:@support`\n**Step 4:** `/ticketpanel` - Post ticket panel to channel\n**Done!** Users can now create tickets with custom forms!",
            inline=False
        )
        embed.set_footer(text="🟣 = Everyone • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=HelpView())

    async def show_verification_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✅ **Verification System**",
            description=f"*CAPTCHA-based member verification system for new member screening.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.SUCCESS
        )
        embed.add_field(
            name="🔴 `/verification-setup #channel @role [remove_role]`",
            value="**Usage:** `/verification-setup channel:#verify verified_role:@verified [remove_role:@unverified]`\n**Description:** Setup CAPTCHA verification system for new members\n**Features:** Prevents unverified access, reduces bot/spam accounts",
            inline=False
        )
        embed.add_field(
            name="✅ **How It Works**",
            value="**1.** Bot posts verification button in specified channel\n**2.** New members click \"✅ Verify Me\" button\n**3.** Bot generates unique CAPTCHA image\n**4.** Member enters code to verify\n**5.** Verified role assigned automatically\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🎯 **Verification Features**",
            value="**✓ CAPTCHA-based verification** - Prevents automated bot accounts\n**✓ Custom verified role** - Assign role upon successful verification\n**✓ Optional unverified role removal** - Remove unverified role after verification\n**✓ Persistent system** - Verification button survives bot restarts\n**✓ Unique codes** - Each CAPTCHA is generated uniquely per user\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🔧 **Setup Example**",
            value="**Step 1:** Create roles: @Verified and @Unverified\n**Step 2:** Use `/verification-setup channel:#verification verified_role:@Verified remove_role:@Unverified`\n**Step 3:** Set @Unverified as auto-role with `/setup auto_role role:@Unverified`\n**Done!** New members will need to verify to access server",
            inline=False
        )
        embed.set_footer(text="🟣 = Everyone • 🔴 = Main Moderator")
        await interaction.response.edit_message(embed=embed, view=HelpView())

    async def show_advanced_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎭 **Advanced Features & Tools**",
            description=f"*Extended capabilities—reaction roles, automation, and intelligent systems.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PANEL
        )
        embed.add_field(
            name="🎭 **Multi-Reaction Role System**",
            value="**🔴 `/reactionrole message emoji role channel [remove_role]`** - Setup single reaction role\n**🔴 `/quickreactionrole`** - Interactive multi-role setup (up to 10 pairs)\n**🟡 `/listreactionroles`** - View all active reaction role setups\n**Features:** Multiple roles per message, auto-remove roles, persistent storage\n\u200b",
            inline=False
        )
        embed.add_field(
            name="✨ **Reaction Role Features**",
            value="**Multiple Emoji/Roles:** Up to 10 emoji:role pairs per message\n**Auto-Remove Role:** Automatically remove specified role when user gets any reaction role\n**Interactive Setup:** User-friendly forms for complex setups\n**Persistent:** Survives bot restarts with database storage\n**Format:** Supports both single and batch reaction role creation\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🌐 **Multi-Server Intelligence**",
            value="✅ **MongoDB integration** - Persistent data storage\n✅ **Per-server configuration** - Roles, channels, settings\n✅ **Separated tracking** - Each server independent\n✅ **Individual server settings** - Customize per server\n✅ **Database-backed** - Never lose your data\n\u200b",
            inline=False
        )
        embed.add_field(
            name="🤖 **Automatic Background Features**",
            value="👋 **Welcome DMs** - Professional messages to new members\n💔 **Goodbye DMs** - Farewell messages when members leave\n🎉 **Level Up Cards** - Beautiful rank card generation\n📊 **Live Server Count** - Bot status shows current servers\n⚡ **Real-time Activity** - Instant system-wide monitoring",
            inline=False
        )
        embed.set_footer(text="🟣 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=HelpView())

    async def show_bot_info_help(self, interaction: discord.Interaction):
        bot_owner_id = os.getenv('BOT_OWNER_ID')
        owner_mention = f"<@{bot_owner_id}>" if bot_owner_id else "Contact via server"
        support_server = os.getenv('SUPPORT_SERVER')
        contact_email = os.getenv('CONTACT_EMAIL')
        email_text = contact_email if contact_email else "Not available"

        embed = discord.Embed(
            title="💠 **About RXT ENGINE**",
            description=f"*Quantum AI Core Information—system specifications and developer credentials.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PRIMARY
        )
        embed.add_field(
            name="◆ **Quantum Core Specifications**",
            value=f"**AI Core:** {BOT_NAME}\n**Version:** {BOT_VERSION}\n**Status:** {VisualElements.STATUS_ONLINE}\n**Active Servers:** {len(bot.guilds)}\n**Architecture:** Python-based quantum engine\n**Neural Storage:** MongoDB distributed database",
            inline=False
        )
        embed.add_field(
            name="⚡ **System Architect**",
            value=f"**Creator:** {BOT_OWNER_NAME}\n**Contact:** {owner_mention}\n**Role:** {BOT_OWNER_DESCRIPTION}\n**Support Protocol:** Mention owner in any server",
            inline=False
        )
        embed.add_field(
            name="📞 **Contact Information**",
            value=f"**📩 Email:** `{email_text}`\n**💬 Discord:** {owner_mention}\n**🏠 Support Server:** {'Available via button below' if support_server else 'Contact owner for invite'}",
            inline=False
        )
        embed.add_field(
            name="💠 **Quantum Capabilities**",
            value="◆ **Holographic UI** — Advanced quantum purple interface\n◆ **AI Moderation** — Intelligent enforcement protocols\n◆ **Karma Matrix** — Community recognition system\n◆ **Support Grid** — Multi-channel ticket resolution\n◆ **Neural Storage** — Persistent data architecture\n◆ **Security Core** — Multi-layer protection systems",
            inline=False
        )
        embed.add_field(
            name="🔗 **Quick Links**",
            value=f"**💠 Bot Invite:** [Add to Your Server](https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands)\n**💬 DM Developer:** [Click Here](https://discord.com/users/{bot_owner_id if bot_owner_id else '0'})\n{f'**🏠 Support Server:** [Join Here]({support_server})' if support_server else ''}\n\n**⚡ Engineered by R!O</>**",
            inline=False
        )
        embed.set_footer(text=BOT_FOOTER)
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        
        await interaction.response.edit_message(embed=embed, view=HelpView())

    async def show_recent_updates_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🆕 **Quantum Core Updates**",
            description=f"*Latest system enhancements and feature deployments for RXT ENGINE.*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.SUCCESS
        )
        embed.add_field(
            name="🛡️ **RXT Security System** (Multi-Layer Protection) - LATEST",
            value="**9-Module Protection Suite:** Anti-raid, anti-nuke, anti-spam, anti-link, webhook guard, anti-role, mass mention blocker, timeout system, whitelist\n**🚫 Quarantine System:** Automatic containment of suspicious users with persistent violation tracking\n**⏱️ Timeout Management:** Discord native timeouts with complete communication blackout\n**📊 Violation Tracking:** Cross-session persistence tracking threat severity\n**Commands:** `/security`, `/antiraid`, `/antinuke`, `/antispam`, `/antilink`, `/webhookguard`, `/antirole`, `/massmention`, `/timeout`, `/whitelist`",
            inline=False
        )
        embed.add_field(
            name="✨ **Karma System** (Community Recognition)",
            value="**🟢 `/givekarma @user [reason]`** - Give karma points to members\n**⭐ Reaction Karma** - Positive reactions (👍 ⭐ ❤️ 🔥 💯) give karma\n**📊 `/karmaboard`** - View server's top karma earners\n**🎉 Level-up celebrations** with motivational quotes and GIFs",
            inline=False
        )
        embed.add_field(
            name="🎨 **Profile & Server Cards** (Visual Stats)",
            value="**🟢 `/profile [user]`** - Beautiful profile cards with avatar and karma\n**🏰 `/servercard`** - Generate server overview cards with statistics\n**🤖 `/botprofile`** - View bot information, security features, and system specs\n**🟢 `/contact`** - Get bot contact information\n**Circular avatars** with progress bars and modern theme",
            inline=False
        )
        embed.add_field(
            name="🎫 **Support & Automation**",
            value="**🎫 Ticket System** - Professional support ticket management\n**✅ Verification System** - CAPTCHA-based member verification\n**🎭 Reaction Roles** - Easy role assignment with reactions\n**⏰ Timed Roles** - Assign roles for specific durations\n**📢 Announcements** - Professional server announcements",
            inline=False
        )
        embed.add_field(
            name="🔧 **How to Get Started**",
            value="**Step 1:** `/security action:enable` - Activate security protections\n**Step 2:** `/setup main_moderator role:@moderator` - Configure permissions\n**Step 3:** Use `/help` to explore the Security section\n**Step 4:** `/givekarma` to start community recognition!\n**Advanced:** `/whitelist` to add trusted users/bots to security bypass",
            inline=False
        )
        embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=HelpView())

# Slash Commands
@bot.tree.command(name="help", description="📜 Show comprehensive help menu with all commands")
async def help_command(interaction: discord.Interaction):
    await help_command_callback(interaction)

@bot.tree.command(name="ping", description="🏓 Check bot latency and connection status")
async def ping(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("Junior Moderator", ephemeral=True)
        return

    latency = round(bot.latency * 1000)

    if latency < 100:
        color = BrandColors.SUCCESS
        status = "Optimal"
        emoji = "⚡"
    elif latency < 200:
        color = BrandColors.WARNING
        status = "Good"
        emoji = "◆"
    else:
        color = BrandColors.WARNING
        status = "High Latency"
        emoji = "◆"

    embed = discord.Embed(
        title=f"{emoji} **Quantum Network Diagnostic**",
        description=f"{VisualElements.CIRCUIT_LINE}\n**⚡ Latency:** `{latency}ms`\n**◆ Status:** {status}\n**🟣 Connection:** ACTIVE\n{VisualElements.CIRCUIT_LINE}",
        color=color
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

    await log_action(interaction.guild.id, "general", f"🏓 [PING] {interaction.user} checked bot latency ({latency}ms)")

@bot.tree.command(name="uptime", description="⏰ Show how long the bot has been running")
async def uptime(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("Junior Moderator", ephemeral=True)
        return

    uptime_seconds = time.time() - bot.start_time
    uptime_str = str(timedelta(seconds=int(uptime_seconds)))

    embed = discord.Embed(
        title="⚡ **Quantum Core Runtime Status**",
        description=f"{VisualElements.CIRCUIT_LINE}\n**{VisualElements.STATUS_ACTIVE}** — System operational for `{uptime_str}`\n**💠 Active Servers:** {len(bot.guilds)}\n**◆ Neural Status:** All systems nominal\n{VisualElements.CIRCUIT_LINE}",
        color=BrandColors.PRIMARY
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

    await log_action(interaction.guild.id, "general", f"⏰ [UPTIME] {interaction.user} checked bot uptime ({uptime_str})")

@bot.tree.command(name="userinfo", description="👤 Show detailed information about a user")
async def userinfo(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user

    # Calculate join position
    join_pos = sorted(interaction.guild.members, key=lambda m: m.joined_at).index(user) + 1

    embed = discord.Embed(
        title=f"💠 **{user.display_name}**",
        description=f"*User data profile for {user.mention}*\n{VisualElements.THIN_LINE}",
        color=user.color if user.color.value != 0 else BrandColors.PRIMARY
    )
    embed.set_thumbnail(url=user.display_avatar.url)

    embed.add_field(
        name="📅 **Joined Server**",
        value=f"`{user.joined_at.strftime('%B %d, %Y')}`\n*#{join_pos} to join*",
        inline=True
    )
    embed.add_field(
        name="📅 **Account Created**",
        value=f"`{user.created_at.strftime('%B %d, %Y')}`\n*{(datetime.now() - user.created_at.replace(tzinfo=None)).days} days ago*",
        inline=True
    )
    embed.add_field(
        name="🎭 **Roles**",
        value=f"`{len(user.roles)-1}` roles" + (f"\nHighest: {user.top_role.mention}" if len(user.roles) > 1 else ""),
        inline=True
    )
    embed.add_field(name="🆔 **User ID**", value=f"`{user.id}`", inline=True)
    embed.add_field(name="📱 **Status**", value=f"`{str(user.status).title()}`", inline=True)
    embed.add_field(name="🤖 **Bot Account**", value=f"`{'Yes' if user.bot else 'No'}`", inline=True)

    embed.set_footer(text=f"{BOT_FOOTER} • Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

    await log_action(interaction.guild.id, "general", f"👤 [USERINFO] {interaction.user} viewed info for {user}")

@bot.tree.command(name="serverinfo", description="🏰 Show detailed server information")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild

    # Calculate server stats
    online_members = sum(1 for member in guild.members if member.status != discord.Status.offline)
    bot_count = sum(1 for member in guild.members if member.bot)
    human_count = guild.member_count - bot_count

    embed = discord.Embed(
        title=f"◆ **{guild.name}**",
        description=f"*Quantum server analytics and statistics*\n{VisualElements.CIRCUIT_LINE}",
        color=BrandColors.PRIMARY
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="👑 **Owner**", value=guild.owner.mention, inline=True)
    embed.add_field(name="👥 **Members**", value=f"`{guild.member_count}` total\n`{human_count}` humans\n`{bot_count}` bots", inline=True)
    embed.add_field(name="🟢 **Online**", value=f"`{online_members}` members", inline=True)

    embed.add_field(name="📅 **Created**", value=f"`{guild.created_at.strftime('%B %d, %Y')}`\n*{(datetime.now() - guild.created_at.replace(tzinfo=None)).days} days ago*", inline=True)
    embed.add_field(name="🔒 **Verification**", value=f"`{str(guild.verification_level).title()}`", inline=True)
    embed.add_field(name="📂 **Channels**", value=f"`{len(guild.channels)}` total\n`{len(guild.text_channels)}` text\n`{len(guild.voice_channels)}` voice", inline=True)

    embed.add_field(name="🎭 **Roles**", value=f"`{len(guild.roles)}` roles", inline=True)
    embed.add_field(name="😀 **Emojis**", value=f"`{len(guild.emojis)}`", inline=True)
    embed.add_field(name="🆔 **Server ID**", value=f"`{guild.id}`", inline=True)

    embed.set_footer(text=f"{BOT_FOOTER} • Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

    await log_action(interaction.guild.id, "general", f"🏰 [SERVERINFO] {interaction.user} viewed server information")

# Contact info command
@bot.tree.command(name="synccommands", description="🔄 Force sync all bot commands (Owner only)")
async def sync_commands(interaction: discord.Interaction):
    bot_owner_id = os.getenv('BOT_OWNER_ID')
    if str(interaction.user.id) != bot_owner_id:
        await interaction.response.send_message("❌ Only the bot owner can use this command!", ephemeral=True)
        return

    try:
        # Sync globally first
        synced_global = await bot.tree.sync()

        # Also sync to current guild for immediate visibility
        synced_guild = await bot.tree.sync(guild=interaction.guild)

        # Get all registered commands
        all_commands = [cmd.name for cmd in bot.tree.get_commands()]
        all_commands.sort()  # Sort alphabetically for better readability

        # Check for specific command groups
        timed_role_commands = [cmd for cmd in ['giverole', 'removerole', 'timedroles'] if cmd in all_commands]
        moderation_commands = [cmd for cmd in ['kick', 'ban', 'mute', 'unmute', 'timeout-settings'] if cmd in all_commands]
        setup_commands = [cmd for cmd in ['setup', 'autorole', 'ticketsetup'] if cmd in all_commands]
        karma_commands = [cmd for cmd in ['givekarma', 'karma', 'karmaboard', 'setkarmachannel'] if cmd in all_commands]

        embed = discord.Embed(
            title="⚡ **Quantum Commands Synchronized**",
            description=f"{VisualElements.CIRCUIT_LINE}\n**◆ Global Sync:** {len(synced_global)} commands\n**◆ Guild Sync:** {len(synced_guild)} commands\n**◆ Total Active:** {len(all_commands)}\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PRIMARY
        )

        embed.add_field(
            name="🎭 **Timed Role Commands**",
            value=f"`{', '.join(timed_role_commands) if timed_role_commands else 'Not found!'}`",
            inline=False
        )

        embed.add_field(
            name="🛡️ **Moderation Commands**",
            value=f"`{', '.join(moderation_commands[:10]) if moderation_commands else 'Not found!'}`",
            inline=True
        )

        embed.add_field(
            name="✨ **Karma Commands**",
            value=f"`{', '.join(karma_commands) if karma_commands else 'Not found!'}`",
            inline=True
        )

        embed.add_field(
            name="⚙️ **Setup Commands**",
            value=f"`{', '.join(setup_commands) if setup_commands else 'Not found!'}`",
            inline=True
        )

        # Show all commands in a compact format
        commands_text = ', '.join(all_commands[:30])  # Limit to first 30 to avoid embed limits
        if len(all_commands) > 30:
            commands_text += f"... (+{len(all_commands) - 30} more)"

        embed.add_field(
            name="📋 **All Commands**",
            value=f"`{commands_text}`",
            inline=False
        )

        embed.set_footer(text=f"{BOT_FOOTER} • Guild sync makes commands appear immediately!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"❌ Sync failed: {str(e)}", ephemeral=True)

@bot.tree.command(name="contact", description="📞 Get bot contact information and support details")
async def contact_info(interaction: discord.Interaction):
    await log_action(interaction.guild.id, "general", f"📞 [CONTACT] {interaction.user} viewed contact information")
    bot_owner_id = os.getenv('BOT_OWNER_ID')
    contact_email = os.getenv('CONTACT_EMAIL')
    support_server = os.getenv('SUPPORT_SERVER')

    owner_mention = f"<@{bot_owner_id}>" if bot_owner_id else "Contact via server"
    email_text = contact_email if contact_email else "Not available"
    support_text = support_server if support_server else "Contact owner for invite"

    # Get owner status if possible
    owner_status = "Unknown"
    owner_status_emoji = "⚫"
    if bot_owner_id:
        try:
            if interaction.guild:
                owner_member = interaction.guild.get_member(int(bot_owner_id))
                if owner_member:
                    status_map = {
                        discord.Status.online: ("🟢", "Online"),
                        discord.Status.idle: ("🟡", "Idle"),
                        discord.Status.dnd: ("🔴", "Do Not Disturb"),
                        discord.Status.offline: ("⚫", "Offline")
                    }
                    owner_status_emoji, owner_status = status_map.get(owner_member.status, ("⚫", "Unknown"))
        except:
            pass

    # Bot uptime calculation
    uptime_seconds = time.time() - bot.start_time
    uptime_str = str(timedelta(seconds=int(uptime_seconds)))

    # Try to create bot profile card
    try:
        from profile_cards import create_bot_profile_card
        await interaction.response.defer()

        card_image = await create_bot_profile_card(bot, owner_status, owner_status_emoji, uptime_str, len(bot.guilds))

        if card_image:
            # Save image to bytes
            import io
            img_bytes = io.BytesIO()
            card_image.save(img_bytes, format='PNG', quality=95)
            img_bytes.seek(0)

            # Create Discord file
            file = discord.File(img_bytes, filename=f"bot_contact_{bot.user.id}.png")

            embed = discord.Embed(
                title="💠 **RXT ENGINE Contact Protocols**",
                description=f"*{BOT_TAGLINE}*\n\n{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.PRIMARY
            )
            embed.set_image(url=f"attachment://bot_contact_{bot.user.id}.png")

            embed.add_field(
                name="📞 **Contact Information**",
                value=f"**Developer:** {owner_mention} {owner_status_emoji}\n**Status:** {owner_status}\n**Email:** `{email_text}`\n**Support:** {support_text}",
                inline=False
            )

            embed.add_field(
                name="⚡ **Quick Support**",
                value="🔸 **Mention the owner** in any server with the bot\n🔸 **Use `/help`** for command assistance\n🔸 **Check recent updates** with help menu",
                inline=False
            )

            embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)

            view = discord.ui.View()
            if support_server:
                support_button = discord.ui.Button(label="🏠 Support Server", style=discord.ButtonStyle.link, url=support_server, emoji="🏠")
                view.add_item(support_button)

            invite_button = discord.ui.Button(label="🤖 Invite Bot", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🤖")
            view.add_item(invite_button)

            await interaction.followup.send(embed=embed, file=file, view=view)
        else:
            raise Exception("Failed to generate profile card")

    except Exception as e:
        print(f"Error creating bot profile card: {e}")
        # Fallback to regular embed
        embed = discord.Embed(
            title="💠 **Quantum Core Contact Protocols**",
            description=f"*System contact interface — access support and developer credentials*\n\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PRIMARY
        )

        embed.add_field(
            name="🤖 **RXT ENGINE Information**",
            value=f"**Name:** {BOT_NAME}\n**Version:** {BOT_VERSION}\n**Tagline:** {BOT_TAGLINE}\n**Servers:** {len(bot.guilds)}\n**Uptime:** {uptime_str}\n**Status:** 🟢 Online & Ready",
            inline=False
        )

        embed.add_field(
            name="👨‍💻 **Bot Developer**",
            value=f"**Name:** {BOT_OWNER_NAME}\n**Discord:** {owner_mention} {owner_status_emoji}\n**Status:** {owner_status}\n**About:** {BOT_OWNER_DESCRIPTION}",
            inline=False
        )

        embed.add_field(
            name="📧 **Email Support**",
            value=f"**Email:** `{email_text}`\n*For business inquiries, partnerships, or detailed support*",
            inline=False
        )

        embed.add_field(
            name="🏠 **Support Server**",
            value=f"**Join:** {support_text}\n*Get instant help, report bugs, suggest features, and chat with the community*",
            inline=False
        )

        embed.add_field(
            name="⚡ **Quick Support**",
            value="🔸 **Mention the owner** in any server with the bot\n🔸 **Use `/help`** for command assistance\n🔸 **Check recent updates** with help menu",
            inline=False
        )

        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="🌴 Made with ❤️ from Advanced Community Management", icon_url=bot.user.display_avatar.url)

        view = discord.ui.View()
        if support_server:
            support_button = discord.ui.Button(label="🏠 Support Server", style=discord.ButtonStyle.link, url=support_server, emoji="🏠")
            view.add_item(support_button)

        invite_button = discord.ui.Button(label="🤖 Invite Bot", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🤖")
        view.add_item(invite_button)

        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)

# MongoDB keep-alive function
async def ping_mongodb():
    """Ping MongoDB to keep connection alive"""
    while True:
        try:
            if mongo_client:
                await mongo_client.admin.command('ping')
                print("🔄 MongoDB ping successful")
        except Exception as e:
            print(f"❌ MongoDB ping failed: {e}")
        await asyncio.sleep(300)  # Ping every 5 minutes

# Console output capture class
class ConsoleCapture:
    """Captures print output for live console logging"""
    def __init__(self, original):
        self.original = original
        self.buffer = []
    
    def write(self, message):
        """Capture and forward output"""
        self.original.write(message)
        if message and message.strip():
            try:
                from advanced_logging import queue_console_output
                queue_console_output(message.strip())
            except Exception:
                pass
    
    def flush(self):
        """Flush the original stdout"""
        self.original.flush()

# Import command modules
from setup_commands import *
from moderation_commands import *
from communication_commands import *
from xp_commands import *  # Karma system only
from reaction_roles import *
from ticket_system import *
from autorole import *
from security_system import *  # CAPTCHA verification only

# Import timed roles system - ensure commands are loaded
from timed_roles import *

# Import advanced logging system
try:
    from advanced_logging import *
    print("✅ Advanced logging system loaded")
except ImportError as e:
    print(f"⚠️ Advanced logging module not found: {e}")

# Try to import voice commands
try:
    from voice_commands import *
except ImportError:
    print("Voice commands module not found, skipping...")

# Import profile cards system
try:
    from profile_cards import *
    print("✅ Profile cards system loaded")
except ImportError as e:
    print(f"⚠️ Profile cards module not found: {e}")

# Import and setup RXT Security System
try:
    import rxt_security
    rxt_security.setup(bot, get_server_data, update_server_data, log_action, has_permission, None)
    print("✅ RXT Security System loaded and configured")
except ImportError as e:
    print(f"⚠️ RXT Security System not found: {e}")
except Exception as e:
    print(f"⚠️ RXT Security System setup failed: {e}")

# Import server list monitoring system
try:
    from server_list import *
    print("✅ Server list monitoring system loaded")
except ImportError as e:
    print(f"⚠️ Server list module not found: {e}")

# Import role commands
try:
    from role_commands import *
    print("✅ Role commands system loaded")
except ImportError as e:
    print(f"⚠️ Role commands module not found: {e}")

# Import event system
try:
    from event_commands import *
    print("✅ Event system loaded")
except ImportError as e:
    print(f"⚠️ Event system module not found: {e}")

# Import and setup AI chat system
handle_ai_message = None
try:
    import ai_chat
    ai_chat.setup(bot, db, has_permission, log_action, create_error_embed, create_permission_denied_embed)
    handle_ai_message = ai_chat.handle_ai_message
    print("✅ AI Chat system loaded (Gemini)")
    print(f"✅ handle_ai_message assigned: {handle_ai_message}")
except ImportError as e:
    print(f"⚠️ AI Chat module not found: {e}")
    handle_ai_message = None
except Exception as e:
    print(f"⚠️ AI Chat setup failed: {e}")
    print(f"Exception details: {type(e).__name__}: {e}")
    handle_ai_message = None

# Import and setup invite tracker system
try:
    import invite_tracker
    invite_tracker.setup(bot, db, get_server_data, update_server_data, log_action, has_permission, create_error_embed)
    
    @bot.event
    async def on_ready():
        """Add cog after bot is ready"""
        try:
            if not any(isinstance(cog, invite_tracker.InviteTrackerCog) for cog in bot.cogs.values()):
                await bot.add_cog(invite_tracker.InviteTrackerCog(bot))
        except Exception as e:
            print(f"⚠️ Failed to add invite tracker cog: {e}")
    
    print("✅ Invite tracker system loaded")
except ImportError as e:
    print(f"⚠️ Invite tracker module not found: {e}")
except Exception as e:
    print(f"⚠️ Invite tracker setup failed: {e}")

# Music system removed due to compatibility issues


# Run the bot with error handling
if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Please set DISCORD_BOT_TOKEN in your secrets!")
        sys.exit(1)
    else:
        try:
            print(f"⚡ {BOT_NAME} is starting...")
            bot.run(token)
        except discord.LoginFailure:
            print("❌ Invalid bot token! Please check your DISCORD_BOT_TOKEN.")
            sys.exit(1)
        except discord.HTTPException as e:
            print(f"❌ HTTP Error: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user.")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)