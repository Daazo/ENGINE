

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import aiohttp
import time
import os
import re
import random
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

# XP System Functions
async def add_xp(user_id, guild_id, amount):
    """Add XP to user"""
    if db is None:
        return
    
    user_data = await db.users.find_one({'user_id': str(user_id), 'guild_id': str(guild_id)})
    if not user_data:
        user_data = {'user_id': str(user_id), 'guild_id': str(guild_id), 'xp': 0, 'level': 1, 'last_xp_gain': 0}
    
    # Check cooldown (60 seconds)
    current_time = time.time()
    if current_time - user_data.get('last_xp_gain', 0) < 60:
        return False
    
    user_data['xp'] += amount
    user_data['last_xp_gain'] = current_time
    
    # Calculate new level
    old_level = user_data.get('level', 1)
    new_level = calculate_level(user_data['xp'])
    level_up = new_level > old_level
    user_data['level'] = new_level
    
    await db.users.update_one(
        {'user_id': str(user_id), 'guild_id': str(guild_id)},
        {'$set': user_data},
        upsert=True
    )
    
    return level_up

def calculate_level(xp):
    """Calculate level based on XP"""
    return int((xp / 100) ** 0.5) + 1

def xp_for_level(level):
    """Calculate XP required for level"""
    return ((level - 1) ** 2) * 100

async def create_rank_image(user, xp, level, rank=None):
    """Create rank card image"""
    try:
        # Create image
        img = Image.new('RGB', (800, 200), color='#2f3136')
        draw = ImageDraw.Draw(img)
        
        # Download user avatar
        avatar_response = requests.get(str(user.display_avatar.url))
        avatar = Image.open(io.BytesIO(avatar_response.content)).resize((150, 150))
        
        # Paste avatar
        img.paste(avatar, (25, 25))
        
        # Draw text
        draw.text((200, 30), user.display_name, fill='white', font_size=30)
        draw.text((200, 70), f"Level {level}", fill='#7289da', font_size=25)
        draw.text((200, 110), f"XP: {xp}/{xp_for_level(level + 1)}", fill='white', font_size=20)
        
        if rank:
            draw.text((200, 140), f"Rank: #{rank}", fill='#43b581', font_size=20)
        
        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return img_bytes
    except:
        return None

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
    except Exception as e:
        print(f"Failed to sync commands: {e}")

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
        # Check for bot mention in DMs
        if (bot.user in message.mentions or 
            f"<@{bot.user.id}>" in message.content or 
            f"<@!{bot.user.id}>" in message.content):
            embed = discord.Embed(
                title="🌱 Enne vilicho?",
                description="Njan *ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ* aanu 😄\nEnte Dev aanu ente thala! 💻\nEnthelum help venamo? Just type /help ✨\nvaazha ila pidichu nadakkam 🌴",
                color=0x43b581
            )
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(text="ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ", icon_url=bot.user.display_avatar.url)
            
            view = discord.ui.View()
            help_button = discord.ui.Button(label="📋 Commands", style=discord.ButtonStyle.primary, emoji="📋")
            help_button.callback = lambda i: help_command_callback(i)
            invite_button = discord.ui.Button(label="🔗 Invite Bot", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🔗")
            view.add_item(help_button)
            view.add_item(invite_button)
            
            await message.channel.send(embed=embed, view=view)
            return
        
        # Check for owner mention in DMs
        owner_id = os.getenv('BOT_OWNER_ID')
        if owner_id and (f"<@{owner_id}>" in message.content or 
                        f"<@!{owner_id}>" in message.content or 
                        "daazo" in message.content.lower()):
            embed = discord.Embed(
                title="👨‍💻 My Dev!",
                description="*Daazo | Rio* aanu ente Developer 😎\n\nVaazha ila pidich nadakan paripichavan 🌱",
                color=0x3498db
            )
            embed.set_footer(text="ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ", icon_url=bot.user.display_avatar.url)
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            await message.channel.send(embed=embed)
            return
        
        return  # Don't process other DM messages
    
    # Check server data for automod settings
    server_data = await get_server_data(message.guild.id)
    automod_settings = server_data.get('automod', {})
    disabled_channels = automod_settings.get('disabled_channels', [])
    
    # Skip automod for moderators
    should_skip_automod = (
        str(message.channel.id) in disabled_channels or 
        await has_permission_user(message.author, message.guild, "junior_moderator")
    )
    
    # Process automod if not skipped
    if not should_skip_automod:
        # Check for bad words
        if automod_settings.get('bad_words', False):
            content_lower = message.content.lower()
            for bad_word in ['fuck', 'thayoli', 'poori', 'thandha', 'stupid', 'bitch', 'dick', 'andi', 
                           'pussy', 'whore', 'vedi', 'vedichi', 'slut', 'punda', 'nayinta mon', 'gay']:
                if bad_word in content_lower:
                    await message.delete()
                    embed = discord.Embed(
                        title="🚫 Message Deleted",
                        description=f"**{message.author.mention}**, your message contained inappropriate language!",
                        color=0xe74c3c
                    )
                    warning_msg = await message.channel.send(embed=embed)
                    await asyncio.sleep(5)
                    await warning_msg.delete()
                    await log_action(message.guild.id, "moderation", f"🚫 [AUTOMOD] Bad word detected from {message.author} in {message.channel}")
                    return
        
        # Check for links
        if automod_settings.get('links', False):
            import re
            URL_PATTERN = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
            if URL_PATTERN.search(message.content):
                await message.delete()
                embed = discord.Embed(
                    title="🔗 Link Blocked",
                    description=f"**{message.author.mention}**, links are not allowed in this channel!",
                    color=0xe74c3c
                )
                warning_msg = await message.channel.send(embed=embed)
                await asyncio.sleep(5)
                await warning_msg.delete()
                await log_action(message.guild.id, "moderation", f"🔗 [AUTOMOD] Link blocked from {message.author} in {message.channel}")
                return
    
    # Check for owner mention - PRIORITY CHECK
    owner_id = os.getenv('BOT_OWNER_ID')
    if owner_id and (f"<@{owner_id}>" in message.content or 
                    f"<@!{owner_id}>" in message.content or 
                    "daazo" in message.content.lower()):
        embed = discord.Embed(
            title="👨‍💻 My Dev!",
            description="*Daazo | Rio* aanu ente Developer 😎\n\nVaazha ila pidich nadakan paripichavan 🌱",
            color=0x3498db
        )
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ", icon_url=bot.user.display_avatar.url)
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        await message.channel.send(embed=embed)
        return
    
    # Check for bot mention - PRIORITY CHECK  
    if (bot.user in message.mentions or 
        f"<@{bot.user.id}>" in message.content or 
        f"<@!{bot.user.id}>" in message.content) and not message.content.startswith('/'):
        embed = discord.Embed(
            title="🌱 Enne vilicho?",
            description="Njan *ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ* aanu 😄\nEnte Dev aanu ente thala! 💻\nEnthelum help venamo? Just type /help ✨\nvaazha ila pidichu nadakkam 🌴",
            color=0x43b581
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ", icon_url=bot.user.display_avatar.url)
        
        view = discord.ui.View()
        help_button = discord.ui.Button(label="📋 Commands", style=discord.ButtonStyle.primary, emoji="📋")
        help_button.callback = lambda i: help_command_callback(i)
        invite_button = discord.ui.Button(label="🔗 Invite Bot", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands", emoji="🔗")
        view.add_item(help_button)
        view.add_item(invite_button)
        
        await message.channel.send(embed=embed, view=view)
        return
    
    # XP System - Give XP for ALL messages in guilds
    if not message.author.bot:
        xp_gain = random.randint(5, 15)
        level_up = await add_xp(message.author.id, message.guild.id, xp_gain)
        
        if level_up and db:
            xp_channel_id = server_data.get('xp_channel')
            
            if xp_channel_id:
                xp_channel = bot.get_channel(int(xp_channel_id))
                if xp_channel:
                    user_data = await db.users.find_one({'user_id': str(message.author.id), 'guild_id': str(message.guild.id)})
                    level = user_data.get('level', 1)
                    
                    embed = discord.Embed(
                        title="🎉 **Level Up!** ✨",
                        description=f"**{message.author.mention} reached Level {level}!** 🚀\n\n*Keep chatting to gain more XP!* 💪",
                        color=0xf39c12
                    )
                    embed.set_thumbnail(url=message.author.display_avatar.url)
                    embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ XP System", icon_url=bot.user.display_avatar.url)
                    await xp_channel.send(embed=embed)
    
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
        "automod": {
            "title": "🛡️ **AUTOMOD Command Help**",
            "description": "**Usage:** `/automod feature:bad_words enabled:True`\n\n**What it does:** Configure auto moderation features\n**Features:** bad_words, links, spam, disable_channel\n**Permission:** 🔴 Main Moderator only\n\n**Example:** `/automod feature:bad_words enabled:True`",
            "color": 0xe74c3c
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
    """Send welcome message and DM"""
    server_data = await get_server_data(member.guild.id)
    
    # Send welcome message to channel
    welcome_channel_id = server_data.get('welcome_channel')
    welcome_message = server_data.get('welcome_message', f"Welcome {member.mention} to {member.guild.name}!")
    
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
        title="🌴 **ᴠᴀᴀᴢʜᴀ Command Center** 🤖",
        description=f"**✨ Namaskaram! Need help? ✨**\n\n**🌴 ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ undu. Chill aanu! 🌴**\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n📋 **Select a category below to explore commands**\n⚙️ **Use `/setup` commands to configure bot per server**\n❓ **Type any command for instant usage help!**\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n**🔐 Permission Levels:**\n🟢 **Everyone** - All server members can use\n🔵 **Junior Moderator** - Limited moderation access  \n🔴 **Main Moderator** - Full access (Server Owner level)\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        color=0x3498db
    )
    embed.set_footer(text=f"🌴 {BOT_TAGLINE}", icon_url=bot.user.display_avatar.url)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    view = HelpView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Professional Help View Class
class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__()
    
    @discord.ui.button(label="General", style=discord.ButtonStyle.primary, emoji="🏠")
    async def general_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🏠 **General Commands**",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x3498db
        )
        embed.add_field(
            name="🟢 `/help`", 
            value="**Usage:** `/help`\n**Description:** Display this comprehensive help menu with all commands\n**Aliases:** None", 
            inline=False
        )
        embed.add_field(
            name="🟢 `/userinfo`", 
            value="**Usage:** `/userinfo [user:@member]`\n**Description:** Show detailed user information including join date, roles, status\n**Features:** Avatar, creation date, server join date, role count", 
            inline=False
        )
        embed.add_field(
            name="🟢 `/serverinfo`", 
            value="**Usage:** `/serverinfo`\n**Description:** Display comprehensive server information\n**Features:** Owner, member count, creation date, verification level, channels, roles", 
            inline=False
        )
        embed.add_field(
            name="🔵 `/ping`", 
            value="**Usage:** `/ping`\n**Description:** Check bot latency and connection status\n**Shows:** WebSocket latency to Discord", 
            inline=False
        )
        embed.add_field(
            name="🔵 `/uptime`", 
            value="**Usage:** `/uptime`\n**Description:** Display how long the bot has been running continuously\n**Format:** Days, hours, minutes, seconds", 
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔵 = Junior Moderator • 🔴 = Main Moderator")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Moderation", style=discord.ButtonStyle.danger, emoji="🛡️")
    async def moderation_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛡️ **Moderation Commands**",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xe74c3c
        )
        embed.add_field(
            name="🔴 `/kick`", 
            value="**Usage:** `/kick user:@member [reason:\"text\"]`\n**Description:** Remove user from server with optional reason\n**Logs:** Moderation channel", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/ban`", 
            value="**Usage:** `/ban user:@member [reason:\"text\"]`\n**Description:** Permanently ban user from server\n**Logs:** Moderation channel", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/nuke`", 
            value="**Usage:** `/nuke`\n**Description:** Delete ALL messages in current channel (⚠️ IRREVERSIBLE!)\n**Warning:** Use with extreme caution", 
            inline=False
        )
        embed.add_field(
            name="🔵 Voice Moderation", 
            value="**`/mute @user`** - Mute user in voice channel\n**`/unmute @user`** - Unmute user in voice\n**`/movevc @user #channel`** - Move user to voice channel\n**`/vckick @user`** - Kick from voice channel\n**`/vclock`** - Lock current voice channel\n**`/vcunlock`** - Unlock voice channel\n**`/vclimit <0-99>`** - Set voice channel user limit", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/automod`", 
            value="**Usage:** `/automod feature:bad_words enabled:True`\n**Features:** bad_words, links, spam, disable_channel\n**Description:** Configure automatic moderation system", 
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔵 = Junior Moderator • 🔴 = Main Moderator")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Setup & Config", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def setup_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚙️ **Setup & Configuration Commands**",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xf39c12
        )
        embed.add_field(
            name="🔴 `/setup main_moderator`", 
            value="**Usage:** `/setup main_moderator role:@role`\n**Description:** Set main moderator role (Server Owner only)\n**Access:** Full bot permissions", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup junior_moderator`", 
            value="**Usage:** `/setup junior_moderator role:@role`\n**Description:** Set junior moderator role\n**Access:** Limited safe moderation commands", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup welcome`", 
            value="**Usage:** `/setup welcome channel:#channel value:\"Welcome {user}!\"`\n**Description:** Configure welcome messages and channel\n**Variables:** {user}, {server}", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/setup prefix`", 
            value="**Usage:** `/setup prefix value:!`\n**Description:** Set custom command prefix for server\n**Limit:** 5 characters maximum", 
            inline=False
        )
        embed.add_field(
            name="🔴 Logging Setup", 
            value="**`/setup logs value:all channel:#logs`** - Combined logs\n**`/setup logs value:moderation channel:#mod-logs`** - Mod actions\n**`/setup logs value:xp channel:#xp-logs`** - Level ups\n**`/setup logs value:tickets channel:#ticket-logs`** - Ticket events\n**`/setup xp channel:#xp`** - XP announcements", 
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔵 = Junior Moderator • 🔴 = Main Moderator")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Communication", style=discord.ButtonStyle.success, emoji="💬")
    async def communication_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💬 **Communication & Messaging Commands**",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x43b581
        )
        embed.add_field(
            name="🔵 `/say`", 
            value="**Usage:** `/say message:\"Hello!\" [channel:#general]`\n**Description:** Make bot send a message to channel\n**Features:** Optional channel targeting", 
            inline=False
        )
        embed.add_field(
            name="🔵 `/embed`", 
            value="**Usage:** `/embed title:\"Title\" description:\"Text\" [color:blue]`\n**Description:** Send rich embedded message with custom styling\n**Colors:** red, green, blue, yellow, purple, orange, or hex codes", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/announce`", 
            value="**Usage:** `/announce channel:#announcements message:\"News!\" [mention:@everyone]`\n**Description:** Send official server announcements\n**Features:** Role mentions, professional formatting", 
            inline=False
        )
        embed.add_field(
            name="🔵 `/poll`", 
            value="**Usage:** `/poll question:\"Pizza party?\" option1:\"Yes\" option2:\"No\" [option3] [option4]`\n**Description:** Create interactive polls with automatic reactions\n**Supports:** Up to 4 options", 
            inline=False
        )
        embed.add_field(
            name="🔵 `/reminder`", 
            value="**Usage:** `/reminder message:\"Meeting!\" time:1h30m`\n**Description:** Set personal reminders (DM notifications)\n**Formats:** 1h30m, 45s, 2d (max 7 days)", 
            inline=False
        )
        embed.add_field(
            name="🔴 `/dm`", 
            value="**Usage:** `/dm user:@member message:\"Your ticket closed\"`\n**Description:** Send DM to user from server (staff use)\n**Features:** Professional server-branded DMs", 
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔵 = Junior Moderator • 🔴 = Main Moderator")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="XP & Ranking", style=discord.ButtonStyle.primary, emoji="📊")
    async def xp_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📊 **XP & Leveling System**",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xf39c12
        )
        embed.add_field(
            name="🟢 `/rank`", 
            value="**Usage:** `/rank [user:@member]`\n**Description:** Show beautiful XP rank card with level, XP, and server ranking\n**Features:** Custom avatars, progress bars, rank position", 
            inline=False
        )
        embed.add_field(
            name="🟢 `/leaderboard`", 
            value="**Usage:** `/leaderboard`\n**Description:** Display top 10 users by XP with rankings\n**Features:** Server-wide leaderboard, level display", 
            inline=False
        )
        embed.add_field(
            name="📈 **XP System Mechanics**", 
            value="**XP Gain:** 5-15 XP per message (60s cooldown per user)\n**Level Formula:** `√(XP/100) + 1`\n**Anti-Spam:** Cooldown prevents XP farming\n**Rewards:** Automatic level-up announcements with rank cards", 
            inline=False
        )
        embed.add_field(
            name="⚙️ **XP Configuration**", 
            value="**`/setup xp channel:#xp-logs`** - Set level-up announcement channel\n**Auto Features:** Beautiful rank card generation, progress tracking\n**Per-Server:** Each server has separate XP tracking", 
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔵 = Junior Moderator • 🔴 = Main Moderator")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Tickets & Support", style=discord.ButtonStyle.secondary, emoji="🎫")
    async def ticket_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎫 **Ticket & Support System**",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x9b59b6
        )
        embed.add_field(
            name="🔴 `/ticketsetup`", 
            value="**Usage:** `/ticketsetup action:open category:#tickets channel:#support description:\"Need help?\"`\n**Description:** Setup professional ticket system with buttons\n**Actions:** open (setup button), close (set close category)", 
            inline=False
        )
        embed.add_field(
            name="🎯 **Ticket Features**", 
            value="**✅ Professional ticket creation with forms**\n**✅ Auto-categorization (open/closed)**\n**✅ Role-based permissions (staff only access)**\n**✅ 10-minute cooldown to prevent spam**\n**✅ Ticket reopening (Main Mods only)**", 
            inline=False
        )
        embed.add_field(
            name="📝 **Ticket Flow**", 
            value="**1.** User clicks \"🎫 Open Support Ticket\" button\n**2.** Fills form: Name, Issue, Urgency (Low/Medium/High)\n**3.** Private channel created with staff access\n**4.** Staff can close/reopen with buttons\n**5.** Full logging to ticket logs channel", 
            inline=False
        )
        embed.add_field(
            name="🔧 **Setup Process**", 
            value="**1.** `/ticketsetup action:open category:#open-tickets channel:#support`\n**2.** `/ticketsetup action:close category:#closed-tickets`\n**3.** Set ticket logs: `/setup logs value:tickets channel:#ticket-logs`\n**4.** Ready to use!", 
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔵 = Junior Moderator • 🔴 = Main Moderator")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Advanced Features", style=discord.ButtonStyle.danger, emoji="🚀")
    async def advanced_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🚀 **Advanced Features & Tools**",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0xe67e22
        )
        embed.add_field(
            name="🎭 `/reactionrole`", 
            value="**Usage:** `/reactionrole message:\"React for roles!\" emoji:😀 role:@Member channel:#roles`\n**Description:** Setup reaction roles for self-assignment\n**Features:** Automatic role assignment/removal on reaction", 
            inline=False
        )
        embed.add_field(
            name="🛡️ **Auto Moderation**", 
            value="**`/automod feature:bad_words enabled:True`** - Filter inappropriate language\n**`/automod feature:links enabled:True`** - Block links\n**`/automod feature:spam enabled:True`** - Anti-spam with timeouts\n**`/automod feature:disable_channel channel:#spam`** - Disable automod in specific channels", 
            inline=False
        )
        embed.add_field(
            name="📊 **Comprehensive Logging**", 
            value="**All Logs:** Combined logging channel for all events\n**Moderation:** Ban, kick, mute, voice actions\n**XP System:** Level ups and XP events\n**Tickets:** Creation, closing, reopening\n**Setup:** Configuration changes\n**Communication:** Announcements, polls, messages", 
            inline=False
        )
        embed.add_field(
            name="🌐 **Multi-Server Support**", 
            value="**✅ MongoDB integration for persistent data**\n**✅ Per-server configuration (roles, channels, settings)**\n**✅ Separated XP tracking per server**\n**✅ Individual automod settings per server**\n**✅ Custom prefixes per server**", 
            inline=False
        )
        embed.add_field(
            name="🤖 **Automatic Features**", 
            value="**👋 Welcome DMs** - Professional welcome messages to new members\n**💔 Goodbye DMs** - Farewell messages when members leave\n**🎉 Level Up Cards** - Beautiful rank card generation\n**📊 Live Server Count** - Bot status shows server count\n**⚡ Real-time Logs** - Instant logging with timestamps", 
            inline=False
        )
        embed.set_footer(text="🟢 = Everyone • 🔵 = Junior Moderator • 🔴 = Main Moderator")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Bot Info", style=discord.ButtonStyle.secondary, emoji="🤖")
    async def bot_info_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot_owner_id = os.getenv('BOT_OWNER_ID')
        owner_mention = f"<@{bot_owner_id}>" if bot_owner_id else "Contact via server"
        
        embed = discord.Embed(
            title="🤖 **About ᴠᴀᴀᴢʜᴀ Bot**",
            description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=0x3498db
        )
        embed.add_field(
            name="🌴 **Bot Information**", 
            value=f"**Name:** {BOT_NAME}\n**Tagline:** {BOT_TAGLINE}\n**Servers:** {len(bot.guilds)} servers\n**Language:** Python (discord.py)", 
            inline=False
        )
        embed.add_field(
            name="👨‍💻 **Developer Information**", 
            value=f"**Developer:** {BOT_OWNER_NAME}\n**Owner Account:** {owner_mention}\n**About:** {BOT_OWNER_DESCRIPTION}\n**Contact:** Mention bot owner for support", 
            inline=False
        )
        embed.add_field(
            name="✨ **Special Features**", 
            value="**🇮🇳 Made in Kerala, India (God's Own Country)**\n**🌴 Malayalam phrases and cultural touch**\n**🏆 Professional moderation & XP system**\n**🎫 Advanced ticket system with forms**\n**🛡️ Smart auto-moderation**\n**📊 MongoDB database for persistence**", 
            inline=False
        )
        embed.add_field(
            name="🔗 **Links**", 
            value=f"**Invite Bot:** [Click Here](https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands)\n**Support:** Mention {owner_mention} in any server\n**Made with ❤️ from Kerala 🌴**", 
            inline=False
        )
        embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ - Your friendly Kerala assistant")
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

# Import command modules
from setup_commands import *
from moderation_commands import *
from communication_commands import *
from xp_commands import *
from reaction_roles import *
from ticket_system import *
from automod import *

# Try to import voice commands
try:
    from voice_commands import *
except ImportError:
    print("Voice commands module not found, skipping...")

# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Please set DISCORD_BOT_TOKEN in your secrets!")
    else:
        bot.run(token)
