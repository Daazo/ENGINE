

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
BOT_TAGLINE = "𝓨𝓸𝓾𝓻 𝓯𝓻𝓲𝓮𝓷𝓭𝓵𝔂 𝓼𝓮𝓻𝓿𝓮𝓻 𝓪𝓼𝓼𝓲𝓼𝓽𝓪𝓷𝓽 𝓯𝓻𝓸𝓶 𝓖𝓸𝓭'𝓼 𝓞𝔀𝓷 𝓒𝓸𝓾𝓷𝓽𝓻𝔂 🌴"
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
    print(f'🌴 {bot.user} has landed in Kerala! 🌴')
    print(f"🌐 Connected to {len(bot.guilds)} servers")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers"
        )
    )
    
    # Force command sync to ensure new commands are registered
    try:
        print("🔄 Syncing slash commands...")
        synced = await bot.tree.sync()
        print(f"✅ Successfully synced {len(synced)} command(s)")
        
        # List all synced commands for debugging
        command_names = [cmd.name for cmd in synced]
        print(f"📋 All synced commands: {', '.join(sorted(command_names))}")
        
        # Check if new commands are included
        new_commands = ['adoptpet', 'petinfo', 'feedpet', 'playpet', 'dailypet', 'giverole', 'removerole', 'timedroles', 'profile', 'profilesetup']
        missing_commands = []
        present_commands = []
        
        for cmd in new_commands:
            if cmd in command_names:
                present_commands.append(cmd)
            else:
                missing_commands.append(cmd)
        
        if present_commands:
            print(f"✅ NEW COMMANDS REGISTERED: {', '.join(present_commands)}")
        if missing_commands:
            print(f"❌ MISSING COMMANDS: {', '.join(missing_commands)}")
        
        print(f"🎯 COMMAND SYNC STATUS: {len(present_commands)}/{len(new_commands)} new commands registered")
                
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
        import traceback
        traceback.print_exc()
    
    # Add persistent views for ticket system
    try:
        from ticket_system import TicketOpenView, TicketControlView, ReopenTicketView
        bot.add_view(TicketOpenView("persistent"))
        bot.add_view(TicketControlView())
        bot.add_view(ReopenTicketView())
        print("✅ Persistent views added for ticket system")
    except Exception as e:
        print(f"❌ Failed to add persistent views: {e}")
        import traceback
        traceback.print_exc()
    
    # Start MongoDB ping task
    if mongo_client:
        try:
            bot.loop.create_task(ping_mongodb())
            print("✅ MongoDB ping task started")
            # Test MongoDB connection
            await mongo_client.admin.command('ping')
            print("✅ MongoDB connection verified")
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
    else:
        print("⚠️ No MongoDB URI found - database features disabled")
    
    print("🎉 VAAZHA Bot startup complete! All systems ready.")
    print(f"🚀 Bot is now online and serving {len(bot.guilds)} servers!")

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
    
    # Handle pet XP from messages
    try:
        from pet_system import handle_pet_message_xp
        await handle_pet_message_xp(message)
    except Exception as e:
        print(f"Pet XP error: {e}")
    
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
    """Send welcome message, DM, and assign auto role"""
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
        invite_button = discord.ui.Button(label="🤖 Invite Bot", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🤖")
        view.add_item(invite_button)
        
        await member.send(embed=embed, view=view)
    except:
        pass  # User has DMs disabled

@bot.event
async def on_member_remove(member):
    """Send goodbye DM"""
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
    except:
        pass  # User has DMs disabled

# Help Command Callback
async def help_command_callback(interaction):
    """Callback for help button"""
    embed = discord.Embed(
        title="🌴 **VAAZHA-BOT Command Center** 🌴",
        description=f"**Machanne! 🤙🏼**\n\nNeed some help? I'm Vaazha-Bot, ready to assist!\n\nSelect a category from the buttons below to explore my commands. For details on any specific command, just type `/` followed by the command name (e.g., `/userinfo`).\n\n**🚦 Aarkokke Enthokke Cheyyam? (Permission Levels)**\n\n🟢 **Everyone** - Can use all general, karma, and ticket commands\n🟡 **Junior Moderator (Cheriya Muthalali)** - Limited moderation access (use /setup and select junior moderator and select the role you want has junior moderator)\n🔴 **Main Moderator (Valiya Muthalali)** - Full access to moderation and setup (use /setup then main moderator and select the role you want has main moderator)\n👑 **Server Owner** - God-level. Ellam cheyyam! (Can do everything!)",
        color=0x43b581
    )
    embed.set_footer(text="Your friendly server assistant from God's Own Country 🌴 Made with ❤️ by Daazo", icon_url=bot.user.display_avatar.url)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    view = HelpView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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
            value="**`/mute @user`** - Mute user in voice channel\n**`/unmute @user`** - Unmute user in voice channel\n**`/movevc @user #channel`** - Move user to different voice channel\n**`/vckick @user`** - Kick user from voice channel\n**`/vclock`** - Lock current voice channel\n**`/vcunlock`** - Unlock voice channel\n**`/vclimit <0-99>`** - Set voice channel user limit", 
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
            value="**Usage:** `/setup welcome channel:#channel value:\"Welcome {user}!\"`\n**Description:** Configure welcome messages and channel\n**Variables:** {user}, {server}", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup logs value channel`", 
            value="**Usage:** `/setup logs value:all channel:#logs`\n**Types:** all, moderation, xp, communication, tickets\n**Description:** Set up logging channels for different bot activities", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup xp channel`", 
            value="**Usage:** `/setup xp channel:#xp-announcements`\n**Description:** Set channel for XP level-up announcements", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup ticket_support_role role`", 
            value="**Usage:** `/setup ticket_support_role role:@support`\n**Description:** Set support role to be mentioned when tickets are created", 
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
            name="🔧 **Admin Setup Commands**", 
            value="**🔴 `/setkarmachannel channel:#channel`** - Set karma announcement channel\n**🔴 `/resetkarma scope:user user:@member`** - Reset specific user's karma\n**🔴 `/resetkarma scope:server`** - Reset all server karma data", 
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔴 = Main Moderator • ⚠️ Old XP system completely removed!")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Tickets & Support", style=discord.ButtonStyle.secondary, emoji="🎫", row=1)
    async def ticket_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎫 **Tickets & Support System**",
            description="*A complete ticket system for users to create tickets and get private support from the staff.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x9b59b6
        )
        embed.add_field(
            name="🔴 `/ticketsetup action category channel description`", 
            value="**Usage:** `/ticketsetup action:open category:#tickets channel:#support description:\"Need help?\"`\n**Description:** Setup professional ticket system with clickable buttons\n**Actions:** open (setup button), close (set close category)", 
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
    
    @discord.ui.button(label="Advanced Features", style=discord.ButtonStyle.danger, emoji="🎭", row=1)
    async def advanced_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎭 **Advanced Features & Tools**",
            description="*Powerful features like reaction roles, timed roles, pets, and profile cards.*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xe67e22
        )
        embed.add_field(
            name="🔴 `/reactionrole message emoji role channel`", 
            value="**Usage:** `/reactionrole message:\"React for roles!\" emoji:😀 role:@Member channel:#roles`\n**Description:** Setup reaction roles for automatic self-assignment\n**Features:** Users get/lose roles by reacting to messages", 
            inline=False
        )
        
        embed.add_field(
            name="⏰ **Timed Role System** (NEW!)", 
            value="**🟡 `/giverole @user <role> <duration>`** - Assign role that expires automatically\n**🟡 `/removerole @user <role>`** - Manually remove roles\n**🟡 `/timedroles`** - View all active timed roles\n**Auto-removal:** Roles expire automatically with DM notifications\n**Examples:** `/giverole @user @TrialMod 7d` (7 days)", 
            inline=False
        )
        
        embed.add_field(
            name="🐾 **Virtual Pet System** (NEW!)", 
            value="**🟢 `/adoptpet <name>`** - Adopt your virtual companion\n**🟢 `/petinfo [@user]`** - Check pet stats and status\n**🟢 `/feedpet`** - Feed pet to improve mood (1h cooldown)\n**🟢 `/playpet`** - Play with pet for XP (1h cooldown)\n**🟢 `/dailypet`** - Daily login bonus (24h cooldown)\n**Auto-Growth:** Pets gain XP from your messages and level up!", 
            inline=False
        )
        
        embed.add_field(
            name="🎨 **Profile Cards** (NEW!)", 
            value="**🟢 `/profile [@user]`** - Generate beautiful visual profile cards\n**🟢 `/profilesetup background:<style> color:<hex>`** - Customize card appearance\n**Features:** Shows karma, pet info, roles, join date, and rank with stunning graphics", 
            inline=False
        )
        
        embed.add_field(
            name="🌐 **Multi-Server Intelligence**", 
            value="✅ **MongoDB integration** - Persistent data storage\n✅ **Per-server configuration** - Roles, channels, settings\n✅ **Separated tracking** - Each server independent\n✅ **Individual server settings** - Customize per server\n✅ **Database-backed** - Never lose your data", 
            inline=False
        )
        
        embed.set_footer(text="🟢 = Everyone • 🟡 = Junior Moderator • 🔴 = Main Moderator • 👑 = Server Owner")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Bot Info", style=discord.ButtonStyle.secondary, emoji="🤖", row=1)
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
            value=f"**Name:** {BOT_NAME}\n**Tagline:** {BOT_TAGLINE}\n**Currently Serving:** {len(bot.guilds)} servers\n**Built With:** Python (discord.py)\n**Database:** MongoDB for persistence", 
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
    
    @discord.ui.button(label="Contact & Support", style=discord.ButtonStyle.secondary, emoji="📞", row=2)
    async def contact_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await contact_info(interaction)
    
    @discord.ui.button(label="Recent Updates", style=discord.ButtonStyle.success, emoji="🌴", row=2)
    async def recent_updates_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🌴 **Recent Updates & Poli Fixes** ✨",
            description="*Hey everyone! I've been fine-tuned by my creator, Daazo chettan, to work even better. Here's what's new:*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x43b581
        )
        embed.add_field(
            name="🆕 **THREE MAJOR NEW FEATURES!** (Latest!)", 
            value="⏰ **Timed Roles** - Assign roles that expire automatically!\n🐾 **Virtual Pet System** - Adopt and level up cute companions!\n🎨 **Profile Cards** - Beautiful visual profile cards with PIL graphics!\n\n*These are HUGE additions with full MongoDB integration!*", 
            inline=False
        )
        embed.add_field(
            name="⏰ **Timed Role System Details**", 
            value="**NEW Commands:** `/giverole`, `/removerole`, `/timedroles`\n**Smart Features:** Auto-removal with DM notifications\n**Duration Support:** 5m, 2h, 3d, 1w formats\n**Perfect for:** Trial staff, event roles, temporary access", 
            inline=False
        )
        embed.add_field(
            name="🐾 **Virtual Pet System Details**", 
            value="**Pet Commands:** `/adoptpet`, `/petinfo`, `/feedpet`, `/playpet`, `/dailypet`\n**Growth System:** Pets level up from messages and interactions\n**Karma Rewards:** Pet level-ups give bonus karma points!\n**Mood System:** Happy pets give better XP bonuses", 
            inline=False
        )
        embed.add_field(
            name="🎨 **Profile Card System Details**", 
            value="**Visual Profiles:** Beautiful generated cards with PIL\n**Custom Backgrounds:** Multiple styles and custom hex colors\n**Complete Stats:** Shows karma, pet, roles, join date, progress bars\n**High Quality:** 800x600 PNG images with gradients and decorations", 
            inline=False
        )
        embed.add_field(
            name="🔄 **Previous Updates**", 
            value="✨ **Enhanced Karma System** - Negative reactions, reduced cooldowns\n👋 **Better Welcome System** - Images, embeds, DMs\n🔧 **Fixed Mentions** - Bot and owner mentions work perfectly", 
            inline=False
        )
        embed.set_footer(text="🌴 Made with ❤️ by Daazo from God's Own Country • MAJOR UPDATE TODAY!", icon_url=bot.user.display_avatar.url)
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

# Contact info command
@bot.tree.command(name="synccommands", description="🔄 Manually sync slash commands (Owner only)")
async def sync_commands(interaction: discord.Interaction):
    # Check if user is the bot owner
    bot_owner_id = os.getenv('BOT_OWNER_ID')
    if bot_owner_id and str(interaction.user.id) != bot_owner_id:
        await interaction.response.send_message("❌ Only the bot owner can use this command!", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        synced = await bot.tree.sync()
        embed = discord.Embed(
            title="🔄 **Commands Synced Successfully!**",
            description=f"✅ **Synced {len(synced)} slash commands**\n\nAll commands should now be available! Try using:\n🐾 `/adoptpet`\n⏰ `/giverole`\n🎨 `/profile`",
            color=0x43b581
        )
        embed.set_footer(text="🌴 Commands updated!")
        await interaction.followup.send(embed=embed)
        print(f"✅ Manual sync successful: {len(synced)} commands")
    except Exception as e:
        embed = discord.Embed(
            title="❌ **Sync Failed**",
            description=f"Error syncing commands: {str(e)}",
            color=0xe74c3c
        )
        await interaction.followup.send(embed=embed)
        print(f"❌ Manual sync failed: {e}")

@bot.tree.command(name="contact", description="📞 Get bot contact information and support details")
async def contact_info(interaction: discord.Interaction):
    bot_owner_id = os.getenv('BOT_OWNER_ID')
    contact_email = os.getenv('CONTACT_EMAIL')
    support_server = os.getenv('SUPPORT_SERVER_LINK')
    
    owner_mention = f"<@{bot_owner_id}>" if bot_owner_id else "Contact via server"
    email_text = contact_email if contact_email else "Not available"
    support_text = support_server if support_server else "Contact owner for invite"
    
    embed = discord.Embed(
        title="📞 **Contact Information & Support**",
        description=f"*Need help or want to get in touch? Here's how to reach us!*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        color=0x3498db
    )
    
    embed.add_field(
        name="👨‍💻 **Bot Developer**",
        value=f"**Name:** {BOT_OWNER_NAME}\n**Discord:** {owner_mention}\n**About:** {BOT_OWNER_DESCRIPTION}",
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
        name="🤖 **Bot Information**",
        value=f"**Servers:** {len(bot.guilds)}\n**Invite Bot:** [Click Here](https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands)\n**Version:** Latest",
        inline=False
    )
    
    embed.add_field(
        name="⚡ **Quick Support**",
        value="🔸 **Mention the owner** in any server with the bot\n🔸 **Use `/help`** for command assistance\n🔸 **Check recent updates** with help menu",
        inline=False
    )
    
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="ᴠᴀᴀᴢʜᴀ", icon_url=bot.user.display_avatar.url)
    
    view = discord.ui.View()
    if support_server:
        support_button = discord.ui.Button(label="🏠 Support Server", style=discord.ButtonStyle.link, url=support_server, emoji="🏠")
        view.add_item(support_button)
    
    invite_button = discord.ui.Button(label="🤖 Invite Bot", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🤖")
    view.add_item(invite_button)
    
    await interaction.response.send_message(embed=embed, view=view)

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
print("🔄 Loading core command modules...")

try:
    from setup_commands import *
    print("✅ Setup commands loaded")
except Exception as e:
    print(f"❌ Setup commands failed: {e}")

try:
    from moderation_commands import *
    print("✅ Moderation commands loaded")
except Exception as e:
    print(f"❌ Moderation commands failed: {e}")

try:
    from communication_commands import *
    print("✅ Communication commands loaded")
except Exception as e:
    print(f"❌ Communication commands failed: {e}")

try:
    from xp_commands import *  # Karma system only
    print("✅ Karma system loaded")
except Exception as e:
    print(f"❌ Karma system failed: {e}")

try:
    from reaction_roles import *
    print("✅ Reaction roles loaded")
except Exception as e:
    print(f"❌ Reaction roles failed: {e}")

try:
    from ticket_system import *
    print("✅ Ticket system loaded")
except Exception as e:
    print(f"❌ Ticket system failed: {e}")

try:
    from timeout_system import *
    print("✅ Timeout system loaded")
except Exception as e:
    print(f"❌ Timeout system failed: {e}")

# Import new features - ensure they load properly
print("🔄 Loading NEW FEATURES...")

try:
    from timed_roles import *
    print("✅ Timed roles system loaded (commands: giverole, removerole, timedroles)")
except Exception as e:
    print(f"❌ CRITICAL: Timed roles failed to load: {e}")
    import traceback
    traceback.print_exc()

try:
    from pet_system import *
    print("✅ Pet system loaded (commands: adoptpet, petinfo, feedpet, playpet, dailypet)")
except Exception as e:
    print(f"❌ CRITICAL: Pet system failed to load: {e}")
    import traceback
    traceback.print_exc()

try:
    from profile_cards import *
    print("✅ Profile cards system loaded (commands: profile, profilesetup)")
except Exception as e:
    print(f"❌ CRITICAL: Profile cards failed to load: {e}")
    import traceback
    traceback.print_exc()

try:
    from autorole import *
    print("✅ Auto role system loaded")
except Exception as e:
    print(f"❌ Auto role system failed: {e}")

print("✅ All command modules loading complete!")

# Try to import voice commands
try:
    from voice_commands import *
except ImportError:
    print("Voice commands module not found, skipping...")

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
