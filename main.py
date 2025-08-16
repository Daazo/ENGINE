import discord
from discord.ext import commands
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

# Bot configuration
BOT_NAME = "ᴠᴀᴀᴢʜᴀ"
BOT_VERSION = "v3.2.1"  # Update this version with each major update
BOT_TAGLINE = "Your friendly server assistant from God's Own Country"
BOT_OWNER_NAME = "Daazo|Rio"
BOT_OWNER_DESCRIPTION = "Creator and developer of ᴠᴀᴀᴢʜᴀ bot. Passionate developer from Kerala, India 🇮🇳"

# MongoDB setup
MONGO_URI = os.getenv('MONGO_URI')
if MONGO_URI:
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = mongo_client.vaazha_bot
else:
    mongo_client = None
    db = None

# Cache for server settings
server_cache = {}

# Bot setup
intents = discord.Intents.all()
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
    """Log actions to appropriate channels"""
    server_data = await get_server_data(guild_id)

    # Send ALL actions to global logging system FIRST (PRIORITY)
    try:
        from global_logging import log_bot_command_activity
        # Extract user from message if possible
        user_info = "System"
        if "] " in message and " by " in message:
            parts = message.split(" by ")
            if len(parts) > 1:
                user_info = parts[1].split(" ")[0]
        
        # Log ALL command types to global system - SINGLE CHANNEL PER SERVER
        await log_bot_command_activity(guild_id, log_type, user_info, message)
    except Exception as e:
        print(f"Global logging error: {e}")
        pass

    # ALSO handle LOCAL logging for this server - both systems work together
    # Check for organized logging system first
    organized_logs = server_data.get('organized_log_channels', {})
    if organized_logs:
        # Map log types to organized channels
        log_mapping = {
            "general": "general",
            "moderation": "moderation",
            "setup": "setup",
            "communication": "communication",
            "karma": "karma",
            "economy": "economy",
            "tickets": "ticket",
            "reaction_role": "reaction",
            "welcome": "welcome",
            "voice": "voice",
            "timed_roles": "timed",
            "timeout": "timeout",
            "security": "security",  # Add security logs mapping
            "profile": "general",  # Route profile logs to general
            "utility": "general"   # Route utility logs to general
        }

        mapped_channel = log_mapping.get(log_type)
        if mapped_channel and mapped_channel in organized_logs:
            channel = bot.get_channel(int(organized_logs[mapped_channel]))
            if channel:
                # Determine embed color based on log type
                colors = {
                    "general": 0x3498db,
                    "moderation": 0xe74c3c,
                    "setup": 0xf39c12,
                    "communication": 0x43b581,
                    "karma": 0x9b59b6,
                    "economy": 0xf1c40f,
                    "tickets": 0x3498db,
                    "reaction_role": 0xe67e22,
                    "welcome": 0x43b581,
                    "voice": 0x9b59b6,
                    "timed_roles": 0xf39c12,
                    "timeout": 0xe74c3c,
                    "security": 0xff0000  # Red color for security alerts
                }

                embed = discord.Embed(
                    description=message,
                    color=colors.get(log_type, 0x3498db),
                    timestamp=datetime.now()
                )
                embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ Logs", icon_url=bot.user.display_avatar.url)
                await channel.send(embed=embed)
                return

    # Fallback to old logging system
    log_channels = server_data.get('log_channels', {})

    # Send to specific log channel if set
    if log_type in log_channels:
        channel = bot.get_channel(int(log_channels[log_type]))
        if channel:
            embed = discord.Embed(
                description=message,
                color=0x3498db,
                timestamp=datetime.now()
            )
            embed.set_footer(text="ᴠᴀᴀᴢʜᴀ Logs", icon_url=bot.user.display_avatar.url)
            await channel.send(embed=embed)

    # Send to combined logs if set
    if 'all' in log_channels:
        channel = bot.get_channel(int(log_channels['all']))
        if channel:
            embed = discord.Embed(
                description=message,
                color=0x3498db,
                timestamp=datetime.now()
            )
            embed.set_footer(text="ᴠᴀᴀᴢʜᴀ Logs", icon_url=bot.user.display_avatar.url)
            await channel.send(embed=embed)

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

# Bot Events
@bot.event
async def on_ready():
    print(f'{bot.user} has landed in Kerala! 🌴')
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers"
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
    from ticket_system import TicketOpenView, TicketControlView, ReopenTicketView, CloseReopenedTicketView
    bot.add_view(TicketOpenView("persistent"))
    bot.add_view(TicketControlView())
    bot.add_view(ReopenTicketView())
    bot.add_view(CloseReopenedTicketView())
    print("✅ Persistent views added for ticket system")

    # Add persistent views for security system
    from security_system import VerificationView
    bot.add_view(VerificationView(0))  # Dummy role ID, will be updated when used
    print("✅ Persistent views added for security system")

    # Start timed roles background task
    from timed_roles import start_timed_roles_task
    start_timed_roles_task()

    # Start MongoDB ping task
    if mongo_client:
        bot.loop.create_task(ping_mongodb())

    # Initialize global logging system
    try:
        from global_logging import initialize_global_logging
        await initialize_global_logging()
        print("✅ Global logging fully integrated")
    except Exception as e:
        print(f"⚠️ Failed to initialize global logging: {e}")

@bot.event
async def on_guild_join(guild):
    """Update presence when joining new server"""
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers"
        )
    )

@bot.event
async def on_guild_remove(guild):
    """Update presence when leaving server"""
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers"
        )
    )

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Handle DM mentions
    if not message.guild:  # This is a DM
        # Check for bot mention in DMs - Send contact info
        if (bot.user in message.mentions or
            f"<@{bot.user.id}>" in message.content or
            f"<@!{bot.user.id}>" in message.content):

            # Send contact info in DMs
            bot_owner_id = os.getenv('BOT_OWNER_ID')
            contact_email = os.getenv('CONTACT_EMAIL')
            support_server = os.getenv('SUPPORT_SERVER_LINK')

            owner_mention = f"<@{bot_owner_id}>" if bot_owner_id else "Contact via server"
            email_text = contact_email if contact_email else "Not available"
            support_text = support_server if support_server else "Contact owner for invite"

            embed = discord.Embed(
                title="📞 **Contact Information & Support**",
                description=f"*Hello! Here's how to get help or get in touch:*\n\n**👨‍💻 Developer:** {owner_mention}\n**📧 Email:** `{email_text}`\n**🏠 Support Server:** {support_text}\n\n*Need quick help? Use `/help` in any server!*",
                color=0x3498db
            )
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(text="ᴠᴀᴀᴢʜᴀ", icon_url=bot.user.display_avatar.url)

            view = discord.ui.View()
            if support_server:
                support_button = discord.ui.Button(label="🏠 Support Server", style=discord.ButtonStyle.link, url=support_server, emoji="🏠")
                view.add_item(support_button)

            invite_button = discord.ui.Button(label="🔗 Invite Bot", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🔗")
            view.add_item(invite_button)

            sent_message = await message.channel.send(embed=embed, view=view)

            # Log DM interaction globally
            try:
                from global_logging import log_to_global
                log_embed = discord.Embed(
                    title="🤖 Bot Mention in DM",
                    description=f"**User:** {message.author} ({message.author.id})\n**Trigger:** Bot mention/contact\n**Response:** Contact info sent",
                    color=0x3498db,
                    timestamp=datetime.now()
                )
                await log_to_global("dm-logs", log_embed)
            except:
                pass

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
                title="📢 DEVELOPER MENTION",
                description=f"✨DAAZO ne vilicho: {owner_mention} aanu Vaazha Bot inte Developer🚀.\n🛠 For support, `/help` use cheyyu allenkil 💬 ee bot-ne DM cheyyu.",
                color=0x3498db
            )
            embed.set_footer(text="ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ", icon_url=bot.user.display_avatar.url)
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            sent_message = await message.channel.send(embed=embed)
            # Auto delete after 1 minute
            await asyncio.sleep(60)
            try:
                await sent_message.delete()
            except:
                pass
            return

        return  # Don't process other DM messages



    # Check for owner mention - PRIORITY CHECK
    owner_id = os.getenv('BOT_OWNER_ID')
    if owner_id and (f"<@{owner_id}>" in message.content or
                    f"<@!{owner_id}>" in message.content or
                    "daazo" in message.content.lower()):
        owner_mention = f"<@{owner_id}>" if owner_id else "Contact via server"
        embed = discord.Embed(
            title="📢 DEVELOPER MENTION",
                description=f"✨DAAZO ne vilicho: {owner_mention} aanu Vaazha Bot inte Developer🚀.\n🛠 For support, `/help` use cheyyu allenkil 💬 ee bot-ne DM cheyyu.",
            color=0x3498db
        )
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ", icon_url=bot.user.display_avatar.url)
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        sent_message = await message.channel.send(embed=embed)
        # Auto delete after 1 minute
        await asyncio.sleep(60)
        try:
            await sent_message.delete()
        except:
            pass
        return

    # Check for bot mention - PRIORITY CHECK
    if (bot.user in message.mentions or
        f"<@{bot.user.id}>" in message.content or
        f"<@!{bot.user.id}>" in message.content) and not message.content.startswith('/'):
        owner_id = os.getenv('BOT_OWNER_ID')
        owner_mention = f"<@{owner_id}>" if owner_id else "Contact via server"

        embed = discord.Embed(
            title="👋🏼 Hello, I'm Vaazha Bot",
                description=f"🍁Vaazha Bot anne – your server's assistant.\n🌴 Enthenkilum help venel, type /help.\nNeed assistance? Contact: {owner_mention}",
            color=0x43b581
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ", icon_url=bot.user.display_avatar.url)

        view = discord.ui.View()
        help_button = discord.ui.Button(label="📋 Commands", style=discord.ButtonStyle.primary, emoji="📋")
        help_button.callback = lambda i: help_command_callback(i)
        view.add_item(help_button)

        sent_message = await message.channel.send(embed=embed, view=view)
        # Auto delete after 1 minute
        await asyncio.sleep(60)
        try:
            await sent_message.delete()
        except:
            pass
        return

    # Karma system is handled via reactions and commands

    await bot.process_commands(message)

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
    if isinstance(error, app_commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ **Missing Permissions**",
            description="You don't have the required permissions to use this command!",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    elif isinstance(error, app_commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏳ **Command on Cooldown**",
            description=f"Please wait {error.retry_after:.2f} seconds before using this command again!",
            color=0xf39c12
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
            "color": 0xe74c3c
        },
        "ban": {
            "title": "🔨 **BAN Command Help**",
            "description": "**Usage:** `/ban @user [reason]`\n\n**What it does:** Permanently bans a user from the server\n**Permission:** 🔴 Main Moderator only\n\n**Example:** `/ban @Spammer Repeated spam messages`",
            "color": 0xe74c3c
        },
        "mute": {
            "title": "🔇 **MUTE Command Help**",
            "description": "**Usage:** `/mute @user`\n\n**What it does:** Mutes a user in voice channel\n**Permission:** 🔵 Junior Moderator+\n\n**Example:** `/mute @NoisyUser`",
            "color": 0xf39c12
        },
        "unmute": {
            "title": "🔊 **UNMUTE Command Help**",
            "description": "**Usage:** `/unmute @user`\n\n**What it does:** Unmutes a user in voice channel\n**Permission:** 🔵 Junior Moderator+\n\n**Example:** `/unmute @User`",
            "color": 0x43b581
        },
        "say": {
            "title": "💬 **SAY Command Help**",
            "description": "**Usage:** `/say message:\"text\" [channel:#channel]`\n\n**What it does:** Makes the bot say something\n**Permission:** 🔵 Junior Moderator+\n\n**Example:** `/say message:\"Hello everyone!\" channel:#general`",
            "color": 0x9b59b6
        },
        "embed": {
            "title": "📋 **EMBED Command Help**",
            "description": "**Usage:** `/embed title:\"Title\" description:\"Text\" [color:blue]`\n\n**What it does:** Sends a rich embedded message\n**Permission:** 🔵 Junior Moderator+\n\n**Example:** `/embed title:\"Rules\" description:\"Be nice to everyone!\" color:green`",
            "color": 0x3498db
        },
        "announce": {
            "title": "📢 **ANNOUNCE Command Help**",
            "description": "**Usage:** `/announce channel:#channel message:\"text\" [mention:@role]`\n\n**What it does:** Sends official server announcements\n**Permission:** 🔴 Main Moderator only\n\n**Example:** `/announce channel:#announcements message:\"Server update!\" mention:@everyone`",
            "color": 0xf39c12
        },
        "poll": {
            "title": "📊 **POLL Command Help**",
            "description": "**Usage:** `/poll question:\"Question?\" option1:\"Yes\" option2:\"No\" [option3] [option4]`\n\n**What it does:** Creates interactive polls with reactions\n**Permission:** 🔵 Junior Moderator+\n\n**Example:** `/poll question:\"Pizza party?\" option1:\"Yes!\" option2:\"No\"`",
            "color": 0x43b581
        },
        "reactionrole": {
            "title": "🎭 **REACTION ROLE Command Help**",
            "description": "**Usage:** `/reactionrole message:\"text\" emoji:😀 role:@role channel:#channel`\n\n**What it does:** Sets up reaction roles for users\n**Permission:** 🔴 Main Moderator only\n\n**Example:** `/reactionrole message:\"React for roles!\" emoji:😀 role:@Member channel:#roles`",
            "color": 0x9b59b6
        },

        "ticketsetup": {
            "title": "🎫 **TICKET SETUP Command Help**",
            "description": "**Usage:** `/ticketsetup action:open category:#tickets channel:#support description:\"Need help?\"`\n\n**What it does:** Sets up support ticket system\n**Actions:** open, close\n**Permission:** 🔴 Main Moderator only\n\n**Example:** `/ticketsetup action:open category:#tickets channel:#support`",
            "color": 0x3498db
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
            title="❓ **Command Help**",
            description=f"Use `/help` to see all available commands!\n\n**Tip:** Type `/help` and click the category buttons for detailed command information.",
            color=0x3498db
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
    """Send welcome message, DM, assign auto role, and run security checks"""
    # Run security checks first
    await on_member_join_security_check(member)

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
    welcome_image = server_data.get('welcome_image')

    if welcome_channel_id:
        welcome_channel = bot.get_channel(int(welcome_channel_id))
        if welcome_channel:
            # Replace placeholders safely
            formatted_message = welcome_message.replace("{user}", member.mention).replace("{server}", member.guild.name)

            embed = discord.Embed(
                title="👋 **Welcome to the Community!** 🎊",
                description=f"**{formatted_message}**\n\n*We're excited to have you here!* ✨",
                color=0x43b581
            )
            embed.set_thumbnail(url=member.display_avatar.url)

            # Add welcome image/gif if set
            if welcome_image:
                embed.set_image(url=welcome_image)

            embed.set_footer(text=f"🌴 Member #{member.guild.member_count}", icon_url=member.guild.icon.url if member.guild.icon else None)
            await welcome_channel.send(embed=embed)

    # Log member joining
    await log_action(member.guild.id, "welcome", f"🎊 [MEMBER JOIN] {member} ({member.id}) joined the server - Member #{member.guild.member_count}")

    # Send DM to new member
    try:
        embed = discord.Embed(
            title=f"👋 **Hii, I'm {BOT_NAME}** – your helpful assistant! 🤖",
            description=f"**Welcome to {member.guild.name}** 🎊\n\n*We're thrilled to have you here!*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🏠 **Get comfy, explore the channels, and feel free to say hi!** 👀\n🤖 **If you ever need help, just mention me or use a command!**\n\n**Let's make this server even more awesome together!** 💫\n\n*{BOT_TAGLINE}*",
            color=0x3498db
        )
        embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else bot.user.display_avatar.url)
        embed.set_footer(text="🌴 Welcome to the community!", icon_url=bot.user.display_avatar.url)

        view = discord.ui.View()
        invite_button = discord.ui.Button(label="🤖 Invite Bot to Other Servers", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🤖")
        view.add_item(invite_button)

        await member.send(embed=embed, view=view)

        # Log welcome DM globally
        try:
            from global_logging import on_bot_dm_send
            await on_bot_dm_send(member, f"Welcome message sent to new member in {member.guild.name}")
        except:
            pass
    except:
        pass  # User has DMs disabled

@bot.event
async def on_voice_state_update(member, before, after):
    """Log voice channel activities"""
    if member.bot:
        return

    # Member joined a voice channel
    if before.channel is None and after.channel is not None:
        await log_action(member.guild.id, "voice", f"🔊 [VOICE JOIN] {member} joined {after.channel.name}")
        try:
            from global_logging import log_global_activity
            await log_global_activity("Voice Activity", member.guild.id, member.id, f"Joined voice channel: {after.channel.name}")
        except:
            pass

    # Member left a voice channel
    elif before.channel is not None and after.channel is None:
        await log_action(member.guild.id, "voice", f"🔇 [VOICE LEAVE] {member} left {before.channel.name}")
        try:
            from global_logging import log_global_activity
            await log_global_activity("Voice Activity", member.guild.id, member.id, f"Left voice channel: {before.channel.name}")
        except:
            pass

    # Member moved between voice channels
    elif before.channel is not None and after.channel is not None and before.channel != after.channel:
        await log_action(member.guild.id, "voice", f"🔄 [VOICE MOVE] {member} moved from {before.channel.name} to {after.channel.name}")
        try:
            from global_logging import log_global_activity
            await log_global_activity("Voice Activity", member.guild.id, member.id, f"Moved from {before.channel.name} to {after.channel.name}")
        except:
            pass

    # Member was muted/unmuted
    if before.mute != after.mute:
        status = "muted" if after.mute else "unmuted"
        await log_action(member.guild.id, "voice", f"🔇 [VOICE MUTE] {member} was {status} in {after.channel.name if after.channel else 'voice'}")
        try:
            from global_logging import log_global_activity
            await log_global_activity("Voice Moderation", member.guild.id, member.id, f"Was {status}")
        except:
            pass

    # Member was deafened/undeafened
    if before.deaf != after.deaf:
        status = "deafened" if after.deaf else "undeafened"
        await log_action(member.guild.id, "voice", f"🔇 [VOICE DEAF] {member} was {status} in {after.channel.name if after.channel else 'voice'}")
        try:
            from global_logging import log_global_activity
            await log_global_activity("Voice Moderation", member.guild.id, member.id, f"Was {status}")
        except:
            pass

@bot.event
async def on_member_remove(member):
    """Send goodbye DM and log"""
    # Log member leaving
    await log_action(member.guild.id, "welcome", f"👋 [MEMBER LEAVE] {member} ({member.id}) left the server")

    # Log to global system
    try:
        from global_logging import log_per_server_activity
        await log_per_server_activity(member.guild.id, f"**Member left:** {member} ({member.id})")
    except:
        pass

    try:
        embed = discord.Embed(
            title=f"**Hey {member.display_name}, we noticed you left {member.guild.name}** 😔",
            description=f"**Just wanted to say thank you for being a part of our community.** 💙\n\n*We hope you had a good time there, and we'll always have a spot saved if you return.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n**Take care and stay awesome!** ✨\n\n— **{BOT_NAME}** 🌴",
            color=0xe74c3c
        )
        embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else bot.user.display_avatar.url)
        embed.set_footer(text="🌴 Hope to see you again!", icon_url=bot.user.display_avatar.url)

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

# Security event hooks
@bot.event
async def on_guild_channel_delete(channel):
    """Security hook for channel deletions"""
    await on_guild_channel_delete_security(channel)

@bot.event
async def on_member_update(before, after):
    """Security hook for member updates"""
    await on_member_update_security(before, after)

# Help Command Callback
async def help_command_callback(interaction):
    """Callback for help button"""
    embed = discord.Embed(
        title=f"🌴 **VAAZHA-BOT {BOT_VERSION} Command Center** 🌴",
        description=f"**Machanne! 🤙🏼**\n\nNeed some help? I'm Vaazha-Bot, ready to assist!\n\nSelect a category from the buttons below to explore my commands. For details on any specific command, just type `/` followed by the command name (e.g., `/userinfo`).\n\n**🚦 Aarkokke Enthokke Cheyyam? (Permission Levels)**\n\n🟢 **Everyone** - Can use all general, karma, and ticket commands\n🟡 **Junior Moderator (Cheriya Muthalali)** - Limited moderation access (use /setup and select junior moderator and select the role you want has junior moderator)\n🔴 **Main Moderator (Valiya Muthalali)** - Full access to moderation and setup (use /setup then main moderator and select the role you want has main moderator)\n👑 **Server Owner** - God-level. Ellam cheyyam! (Can do everything!)",
        color=0x43b581
    )
    embed.set_footer(text=f"VAAZHA-BOT {BOT_VERSION} • Your friendly Kerala assistant 🌴 Made with ❤️ by Daazo", icon_url=bot.user.display_avatar.url)
    embed.set_thumbnail(url=bot.user.display_avatar.url)

    view = HelpView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    await log_action(interaction.guild.id, "general", f"📋 [HELP] {interaction.user} used help command")

# Professional Help View Class
class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="General", style=discord.ButtonStyle.secondary, emoji="🏠", row=0)
    async def general_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🏠 **General Commands**",
            description="*Commands for user/server info, checking my ping, uptime, and other general utilities.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x3498db
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
        embed.set_footer(text="🟢 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Moderation", style=discord.ButtonStyle.danger, emoji="🛡️", row=0)
    async def moderation_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛡️ **Moderation Commands**",
            description="*Keep the server clean and in order. For moderators to handle kicks, bans, mutes, and more.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xe74c3c
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
            name="🤖 **Auto-Timeout System**",
            value="**🔴 `/timeout-settings feature:spam enabled:true`** - Configure auto-timeouts\n**🟡 `/remove-timeout @user`** - Remove timeout early\n**🟡 `/timeout-stats @user`** - View user timeout statistics\n**Features:** Bad words (10m), Spam (5m), Links (8m) - Escalating penalties",
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

        embed.set_footer(text="🟢 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Setup & Config", style=discord.ButtonStyle.secondary, emoji="⚙️", row=0)
    async def setup_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚙️ **Setup & Configuration Commands**",
            description="*Configure welcome messages, logging channels, moderator roles, tickets, and other bot settings.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xf39c12
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
            value="**Usage:** `/setup welcome channel:#channel value:\"Welcome {user}!\"`\n**Description:** Configure welcome messages and channel\n**Variables:** {user}, {server}\n**Image support:** Add image URLs for welcome cards",
            inline=False
        )
        embed.add_field(
            name="🔴 `/autorole action role`",
            value="**Usage:** `/autorole action:set role:@role` or `/autorole action:remove`\n**Description:** Set or remove auto role for new members\n**Auto-assigns:** Role given to all new members on join",
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup logs value channel`",
            value="**Usage:** `/setup logs value:all channel:#logs`\n**Types:** all, moderation, karma, communication, tickets\n**Description:** Set up logging channels for different bot activities\n**Advanced:** Use `/setup log_category #category` for organized logs",
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup karma_channel channel`",
            value="**Usage:** `/setup karma_channel channel:#karma`\n**Description:** Set channel for karma level-up announcements and milestones",
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup ticket_support_role role`",
            value="**Usage:** `/setup ticket_support_role role:@support`\n**Description:** Set support role to be mentioned when tickets are created",
            inline=False
        )
        embed.add_field(
            name="🔴 **Category Setup Commands**",
            value="**`/setecocategory #category`** - Setup organized economy channels\n**`/setgamecategory #category`** - Setup game channels for slots/trivia\n**`/setbankcategory #category`** - Setup banking channels for deposits/trades\n**`/setkarmacategory #category`** - Setup karma system channels\n**Auto-creates:** Themed channels with proper permissions and topics",
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Communication", style=discord.ButtonStyle.success, emoji="💬", row=0)
    async def communication_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💬 **Communication & Messaging Commands**",
            description="*Make announcements, create adipoli polls, or use me to send messages and set reminders.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x43b581
        )
        embed.add_field(
            name="🟡 `/say message [channel]`",
            value="**Usage:** `/say message:\"Hello everyone!\" [channel:#general]`\n**Description:** Make bot send a message to specified channel or current channel",
            inline=False
        )
        embed.add_field(
            name="🟡 `/embed title description [color]`",
            value="**Usage:** `/embed title:\"Title\" description:\"Text\" [color:blue]`\n**Description:** Send rich embedded message with custom styling and colors",
            inline=False
        )
        embed.add_field(
            name="🔴 `/announce channel message [mention]`",
            value="**Usage:** `/announce channel:#announcements message:\"Big news!\" [mention:@everyone]`\n**Description:** Send official server announcements with professional formatting",
            inline=False
        )
        embed.add_field(
            name="🟡 `/poll question option1 option2 [option3] [option4]`",
            value="**Usage:** `/poll question:\"Pizza party?\" option1:\"Yes!\" option2:\"No\"`\n**Description:** Create adipoli interactive polls with automatic reactions (up to 4 options)",
            inline=False
        )
        embed.add_field(
            name="🟡 `/reminder message time`",
            value="**Usage:** `/reminder message:\"Meeting time!\" time:1h30m`\n**Description:** Set personal reminders - I'll DM you when time's up!\n**Formats:** 1h30m, 45s, 2d (max 7 days)",
            inline=False
        )
        embed.add_field(
            name="🔴 `/dm user message`",
            value="**Usage:** `/dm user:@member message:\"Your ticket was closed\"`\n**Description:** Send DM to user from server (staff use) - Professional server-branded DMs",
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Karma System", style=discord.ButtonStyle.primary, emoji="✨", row=1)
    async def karma_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✨ **Karma System** (Replaced XP System)",
            description="*Appreciate community members and earn karma points for positive contributions! This completely replaces the old XP/ranking system.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xf39c12
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
            value="**Positive:** 👍 ⭐ ❤️ 🔥 💯 ✨ = +1 karma\n**Negative:** 👎 💀 😴 🤮 🗿 = -1 karma\n**How it works:** Reacting to messages gives/removes karma automatically\n**Cooldown:** 3 minutes between reactions to same user\n**Anti-abuse:** Can't react to your own messages for karma",
            inline=False
        )
        embed.add_field(
            name="🎉 **Milestones & Level-Ups**",
            value="**Every 5 karma:** Celebration announcement with motivational quotes\n**Animated GIFs:** Level-up messages include celebration animations\n**Progress tracking:** Visual progress bars toward next 5-karma milestone\n**Channel announcements:** Set with `/setkarmachannel`",
            inline=False
        )
        embed.add_field(
            name="🎨 **Profile & Visual Cards**",
            value="**🟢 `/profile [user]`** - Generate beautiful profile card with avatar, karma, coins\n**🟡 `/servercard`** - Create server overview card with stats and member info\n**🟢 `/botprofile`** - View bot information card with system status\n**Features:** Circular avatars, progress bars, karma levels, wealth display, server stats\n**Design:** Kerala-themed with coconut trees and professional layouts",
            inline=False
        )
        embed.add_field(
            name="🔧 **Admin Setup Commands**",
            value="**🔴 `/setkarmacategory #category`** - Setup organized karma channels\n**🔴 `/resetkarma scope:user user:@member`** - Reset specific user's karma\n**🔴 `/resetkarma scope:server`** - Reset all server karma data\n**Auto-creates:** Rules, level-ups, and karma zone channels",
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔴 = Main Moderator • ⚠️ Old XP system completely removed!")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Tickets & Support", style=discord.ButtonStyle.secondary, emoji="🎫", row=2)
    async def ticket_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎫 **Tickets & Support System**",
            description="*A complete ticket system for users to create tickets and get private support from the staff.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x9b59b6
        )
        embed.add_field(
            name="🔴 `/ticketsetup action category channel description`",
            value="**Usage:** `/ticketsetup action:open category:#tickets channel:#support description:\"Need help?\"`\n**Description:** Setup professional ticket system with clickable buttons\n**Actions:** open, close\n**Example:** `/ticketsetup action:open category:#tickets channel:#support`",
            inline=False
        )
        embed.add_field(
            name="🎯 **What Users Get**",
            value="🟢 **Anyone can create tickets** - Click button to open\n✅ **Professional forms** - Name, issue description, urgency level\n✅ **Private channels** - Only user and staff can see\n✅ **10-minute cooldown** - Prevents ticket spam\n✅ **Easy controls** - Close/reopen with buttons",
            inline=False
        )
        embed.add_field(
            name="📝 **Complete Ticket Flow**",
            value="**1.** User clicks \"🎫 Open Support Ticket\" button\n**2.** Fills detailed form: Name, Issue, Urgency (Low/Medium/High)\n**3.** Private channel created instantly with staff access\n**4.** Staff can close/reopen tickets with buttons\n**5.** Full logging to ticket logs channel for tracking",
            inline=False
        )
        embed.add_field(
            name="🔧 **Quick Setup Guide**",
            value="**Step 1:** `/ticketsetup action:open category:#open-tickets channel:#support`\n**Step 2:** `/ticketsetup action:close category:#closed-tickets`\n**Step 3:** `/setup logs value:tickets channel:#ticket-logs`\n**Step 4:** `/setup ticket_support_role role:@support` (optional)\n**Done!** Users can now create tickets!",
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Economy System", style=discord.ButtonStyle.success, emoji="🪙", row=1)
    async def economy_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🪙 **Vaazha Coins Economy System** 🍌",
            description="*Earn, spend, and trade Vaazha Coins in our Kerala-themed economy! Fully integrated with karma system.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xf1c40f
        )
        embed.add_field(
            name="💰 **Basic Economy Commands**",
            value="**🟢 `/balance [user]`** - Check coin wallet and bank balance\n**🟢 `/daily`** - Claim daily reward (50+ coins, streak bonus)\n**🟢 `/weekly`** - Claim weekly jackpot (300+ coins)\n**🟢 `/work`** - Work Kerala-themed jobs for coins (1h cooldown)",
            inline=False
        )
        embed.add_field(
            name="🎮 **Mini-Games & Fun**",
            value="**🟢 `/slots <bet>`** - Play banana-themed slot machine (10-500 coins)\n**🟢 `/trivia`** - Answer Kerala trivia questions for rewards\n**🟢 `/richest`** - View top coin holders leaderboard",
            inline=False
        )
        embed.add_field(
            name="🏦 **Banking & Trading**",
            value="**🟢 `/deposit <amount>`** - Store coins safely in bank\n**🟢 `/withdraw <amount>`** - Take coins from bank to wallet\n**🟢 `/trade @user <amount>`** - Send coins to other users (2% tax)",
            inline=False
        )
        embed.add_field(
            name="✨ **Karma Integration**",
            value="**🟢 `/buykarma <amount>`** - Buy karma with coins (1 karma = 10 coins)\n**Perfect synergy:** Earn coins, buy karma, boost your server rank!\n**Strategic:** Balance economy progression with karma advancement",
            inline=False
        )
        embed.add_field(
            name="🔧 **Admin Commands**",
            value="**🔴 `/addcoins @user <amount>`** - Give coins to users (1-10,000)\n**🔴 `/removecoins @user <amount>`** - Remove coins from users\n**🔴 `/createeconomychannels`, `/create_game_channels`, `/create_bank_channels`** - Manual channel creation\n**🔴 Category Setup:** `/setecocategory`, `/setgamecategory`, `/setbankcategory`\n**Full logging:** All economy actions logged automatically",
            inline=False
        )
        embed.add_field(
            name="🍌 **Special Features**",
            value="**Daily Streaks:** Consecutive daily claims = bonus coins\n**Kerala Theme:** Banana harvesting, coconut selling, backwater tours\n**Smart Economics:** Interest, taxes, anti-inflation measures\n**Random Events:** Bonus rewards, special messages, monkey mischief!",
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔴 = Main Moderator • 🌴 Welcome to God's Own Economy!")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Security & Safety", style=discord.ButtonStyle.danger, emoji="🛡️", row=2)
    async def security_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛡️ **Security & Safety Features**",
            description="*Comprehensive security system to protect your server from raids, spam, malicious links, and unauthorized actions.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xe74c3c
        )
        embed.add_field(
            name="🔴 `/security feature enabled [threshold]`",
            value="**Features:** anti_raid, anti_nuke, permission_monitoring, auto_ban, verification_system\n**Description:** Configure all security features with custom thresholds\n**Example:** `/security anti_raid enabled:true threshold:10`",
            inline=False
        )
        embed.add_field(
            name="✅ **Verification System**",
            value="**🔴 `/verification-setup #channel @role`** - Setup member verification\n**🟢 Click verification button** - New members verify to access server\n**Features:** Prevents unverified access, reduces bot/spam accounts",
            inline=False
        )
        embed.add_field(
            name="🛡️ **Anti-Raid Protection**",
            value="**Auto-detects mass joins** (configurable threshold, default: 10 in 1 minute)\n**Sends instant alerts** to staff channels\n**Logs all raid attempts** with timestamps and member counts\n**Configurable sensitivity** for different server sizes",
            inline=False
        )
        embed.add_field(
            name="🚫 **Anti-Nuke Protection**",
            value="**Monitors mass deletions** - channels, roles, bans\n**Instant staff alerts** when thresholds exceeded\n**Tracks suspicious activity** patterns\n**Protects against compromised accounts** performing mass actions",
            inline=False
        )
        embed.add_field(
            name="⚠️ **Auto-Timeout System** (Already Active)",
            value="**🔴 `/timeout-settings feature enabled`** - Configure auto-timeouts\n**Bad Words:** Auto-timeout for inappropriate language (10m+)\n**Spam Detection:** Auto-timeout for message spam (5m+)\n**Link Protection:** Auto-timeout for unauthorized links (8m+)\n**Anti-Spam & Anti-Link:** Already integrated with timeout system\n**Escalating Penalties:** Longer timeouts for repeat offenders",
            inline=False
        )
        embed.add_field(
            name="🤖 **Security Whitelist System**",
            value="**🔴 `/whitelist action:add type:bot target:@bot`** - Add bot to whitelist\n**🔴 `/whitelist action:add type:role target:@role`** - Add role to whitelist\n**🔴 `/whitelist action:remove type:bot target:@bot`** - Remove from whitelist\n**🔴 `/whitelist action:list`** - View current whitelisted bots/roles\n**Protection:** Only whitelisted bots can perform sensitive actions",
            inline=False
        )
        embed.add_field(
            name="👁️ **Advanced Monitoring**",
            value="**Permission Monitoring:** Alerts when users get admin/dangerous permissions\n**Auto-Ban System:** Automatically bans suspicious/new accounts\n**Security Logs:** Detailed logs of all security events and actions\n**Real-time Alerts:** Instant notifications to staff channels",
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔴 = Main Moderator • 🛡️ = Advanced Server Protection")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Advanced Features", style=discord.ButtonStyle.secondary, emoji="🎭", row=3)
    async def advanced_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎭 **Advanced Features & Tools**",
            description="*Powerful features like reaction roles and automated systems.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xe67e22
        )
        embed.add_field(
            name="🎭 **Multi-Reaction Role System**",
            value="**🔴 `/reactionrole message emoji role channel [remove_role]`** - Setup single reaction role\n**🔴 `/quickreactionrole`** - Interactive multi-role setup (up to 10 pairs)\n**🟡 `/listreactionroles`** - View all active reaction role setups\n**Features:** Multiple roles per message, auto-remove roles, persistent storage",
            inline=False
        )
        embed.add_field(
            name="✨ **Reaction Role Features**",
            value="**Multiple Emoji/Roles:** Up to 10 emoji:role pairs per message\n**Auto-Remove Role:** Automatically remove specified role when user gets any reaction role\n**Interactive Setup:** User-friendly forms for complex setups\n**Persistent:** Survives bot restarts with database storage\n**Format:** Supports both single and batch reaction role creation",
            inline=False
        )

        embed.add_field(
            name="📊 **Comprehensive Logging System**",
            value="**All Logs:** Combined logging channel for everything\n**Moderation:** Kicks, bans, mutes, voice actions\n**Economy:** Coin transactions, karma purchases, admin actions\n**Tickets:** Creation, closing, reopening events\n**Setup:** All configuration changes\n**Communication:** Announcements, polls, messages\n**Security:** Anti-raid, anti-nuke, permission changes",
            inline=False
        )
        embed.add_field(
            name="🌐 **Multi-Server Intelligence**",
            value="✅ **MongoDB integration** - Persistent data storage\n✅ **Per-server configuration** - Roles, channels, settings\n✅ **Separated tracking** - Each server independent\n✅ **Individual server settings** - Customize per server\n✅ **Database-backed** - Never lose your data",
            inline=False
        )
        embed.add_field(
            name="🤖 **Automatic Background Features**",
            value="👋 **Welcome DMs** - Professional messages to new members\n💔 **Goodbye DMs** - Farewell messages when members leave\n🎉 **Level Up Cards** - Beautiful rank card generation\n📊 **Live Server Count** - Bot status shows current servers\n⚡ **Real-time Logs** - Instant logging with timestamps",
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Bot Info", style=discord.ButtonStyle.secondary, emoji="🤖", row=2)
    async def bot_info_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot_owner_id = os.getenv('BOT_OWNER_ID')
        owner_mention = f"<@{bot_owner_id}>" if bot_owner_id else "Contact via server"

        embed = discord.Embed(
            title="🤖 **About VAAZHA-BOT**",
            description="*Learn more about me, my creator, and my current status.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x3498db
        )
        embed.add_field(
            name="🌴 **Bot Information**",
            value=f"**Name:** {BOT_NAME}\n**Version:** {BOT_VERSION}\n**Tagline:** {BOT_TAGLINE}\n**Currently Serving:** {len(bot.guilds)} servers\n**Built With:** Python (discord.py)\n**Database:** MongoDB for persistence",
            inline=False
        )
        embed.add_field(
            name="👨‍💻 **Developer Information**",
            value=f"**Developer:** {BOT_OWNER_NAME}\n**Owner Account:** {owner_mention}\n**About:** {BOT_OWNER_DESCRIPTION}\n**Contact:** Mention my owner in any server for support",
            inline=False
        )
        embed.add_field(
            name="✨ **What Makes Me Special**",
            value="🇮🇳 **Made in Kerala, India (God's Own Country)**\n🌴 **Malayalam phrases and cultural touch**\n🏆 **Professional moderation & XP system**\n🎫 **Advanced ticket system with interactive forms**\n🛡️ **Smart auto-moderation that learns**\n📊 **Persistent database - never lose data**\n🎭 **Reaction roles and advanced features**",
            inline=False
        )
        embed.add_field(
            name="🔗 **Important Links**",
            value=f"**🤖 Invite Me:** [Add VAAZHA-BOT to Your Server](https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands)\n**💬 Support:** Mention {owner_mention} in any server I'm in\n**❤️ Made with love from Kerala 🌴**",
            inline=False
        )
        embed.set_footer(text="🌴 VAAZHA-BOT - Your friendly Kerala assistant, ready to help! Chill aanu! 😎")
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Contact & Support", style=discord.ButtonStyle.secondary, emoji="📞", row=3)
    async def contact_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await contact_info(interaction)

    @discord.ui.button(label="Recent Updates", style=discord.ButtonStyle.success, emoji="🌴", row=3)
    async def recent_updates_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🌴 **Latest Features & Updates** ✨",
            description="*Hey everyone! Here are the major features now available in VAAZHA-BOT:*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x43b581
        )
        embed.add_field(
            name="✨ **Karma System** (Community Recognition)",
            value="**🟢 `/givekarma @user [reason]`** - Give karma points to members\n**⭐ Reaction Karma** - Positive reactions (👍 ⭐ ❤️ 🔥 💯) give karma\n**📊 `/karmaboard`** - View server's top karma earners\n**🎉 Level-up celebrations** with motivational quotes and GIFs",
            inline=False
        )
        embed.add_field(
            name="🪙 **Economy System** (Vaazha Coins)",
            value="**🌅 `/daily` & `/weekly`** - Claim coin rewards with streak bonuses\n**💼 `/work`** - Kerala-themed jobs for earning coins\n**🎰 `/slots` & `/trivia`** - Fun mini-games to test your luck\n**🏦 Banking system** with `/deposit`, `/withdraw`, `/trade`\n**⭐ `/buykarma`** - Purchase karma points with coins",
            inline=False
        )
        embed.add_field(
            name="🎨 **Profile & Server Cards** (Visual Stats)",
            value="**🟢 `/profile [user]`** - Beautiful profile cards with avatar, karma, coins\n**🏰 `/servercard`** - Generate server overview cards with statistics\n**🤖 Contact cards** with bot info and owner status\n**Circular avatars** with progress bars and Kerala theme",
            inline=False
        )
        embed.add_field(
            name="🔧 **How to Get Started**",
            value="**Step 1:** Use `/givekarma` to appreciate helpful members\n**Step 2:** Try `/daily` to start earning Vaazha Coins\n**Step 3:** Generate your `/profile` to see your beautiful stats card\n**Step 4:** Use `/help` to explore all available commands!",
            inline=False
        )
        embed.set_footer(text="🌴 Made with ❤️ by Daazo from God's Own Country • Ready to serve!", icon_url=bot.user.display_avatar.url)
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)

# Slash Commands
@bot.tree.command(name="help", description="📜 Show comprehensive help menu with all commands")
async def help_command(interaction: discord.Interaction):
    await help_command_callback(interaction)

@bot.tree.command(name="ping", description="🏓 Check bot latency and connection status")
async def ping(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return

    latency = round(bot.latency * 1000)

    if latency < 100:
        color = 0x43b581
        status = "Excellent"
        emoji = "🟢"
    elif latency < 200:
        color = 0xf39c12
        status = "Good"
        emoji = "🟡"
    else:
        color = 0xe74c3c
        status = "Poor"
        emoji = "🔴"

    embed = discord.Embed(
        title="🏓 **Pong!** ⚡",
        description=f"**{emoji} Latency:** `{latency}ms`\n**Status:** {status}\n\n*Connection to Discord is stable!* ✨",
        color=color
    )
    embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ Network Status", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

    await log_action(interaction.guild.id, "general", f"🏓 [PING] {interaction.user} checked bot latency ({latency}ms)")

@bot.tree.command(name="uptime", description="⏰ Show how long the bot has been running")
async def uptime(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return

    uptime_seconds = time.time() - bot.start_time
    uptime_str = str(timedelta(seconds=int(uptime_seconds)))

    embed = discord.Embed(
        title="⏰ **Bot Uptime** 🚀",
        description=f"**🟢 I've been running for:** `{uptime_str}`\n\n*Serving {len(bot.guilds)} servers with ❤️* 🌴",
        color=0x43b581
    )
    embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ System Status", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

    await log_action(interaction.guild.id, "general", f"⏰ [UPTIME] {interaction.user} checked bot uptime ({uptime_str})")

@bot.tree.command(name="userinfo", description="👤 Show detailed information about a user")
async def userinfo(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user

    # Calculate join position
    join_pos = sorted(interaction.guild.members, key=lambda m: m.joined_at).index(user) + 1

    embed = discord.Embed(
        title=f"👤 **{user.display_name}**",
        description=f"*User information for {user.mention}*",
        color=user.color if user.color.value != 0 else 0x3498db
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

    embed.set_footer(text=f"🌴 Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
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
        title=f"🏰 **{guild.name}**",
        description=f"*Server information and statistics*",
        color=0x3498db
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

    embed.set_footer(text=f"🌴 Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
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
            title="🔄 **Commands Synced Successfully**",
            description=f"**Global Sync:** {len(synced_global)} commands\n**Guild Sync:** {len(synced_guild)} commands\n**Total Registered:** {len(all_commands)}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x43b581
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

        embed.set_footer(text="Guild sync makes commands appear immediately! 🌴")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"❌ Sync failed: {str(e)}", ephemeral=True)

@bot.tree.command(name="contact", description="📞 Get bot contact information and support details")
async def contact_info(interaction: discord.Interaction):
    await log_action(interaction.guild.id, "general", f"📞 [CONTACT] {interaction.user} viewed contact information")
    bot_owner_id = os.getenv('BOT_OWNER_ID')
    contact_email = os.getenv('CONTACT_EMAIL')
    support_server = os.getenv('SUPPORT_SERVER_LINK')

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
                title="🤖 **VAAZHA-BOT Contact & Information**",
                description=f"*{BOT_TAGLINE}*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                color=0x43b581
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

            embed.set_footer(text="🌴 Made with ❤️ from God's Own Country", icon_url=bot.user.display_avatar.url)

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
            title="📞 **Contact Information & Support**",
            description=f"*Need help or want to get in touch? Here's how to reach us!*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x3498db
        )

        embed.add_field(
            name="🤖 **VAAZHA-BOT Information**",
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
        embed.set_footer(text="🌴 Made with ❤️ from God's Own Country", icon_url=bot.user.display_avatar.url)

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

# Import command modules
from setup_commands import *
from moderation_commands import *
from communication_commands import *
from xp_commands import *  # Karma system only
from reaction_roles import *
from ticket_system import *
from timeout_system import *
from autorole import *
from economy_system import *  # Vaazha Coins economy
from economy_setup import *  # Economy category setup
from security_system import *  # Security features

# Import timed roles system - ensure commands are loaded
from timed_roles import *

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

# Import global logging system
try:
    from global_logging import *
    print("✅ Global logging system loaded")
except ImportError as e:
    print(f"⚠️ Global logging module not found: {e}")

# Music system removed due to compatibility issues

# Run the bot with error handling
if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Please set DISCORD_BOT_TOKEN in your secrets!")
        sys.exit(1)
    else:
        try:
            print("🌴 VAAZHA Bot is starting...")
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