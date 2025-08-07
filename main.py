
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
BOT_OWNER_DESCRIPTION = "Creator and developer of ᴠᴀᴀᴢʜᴀ bot. Passionate developer from Kerala, India."

# MongoDB setup
MONGO_URI = os.getenv('MONGO_URI')
if MONGO_URI:
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = mongo_client.vaazha_bot
else:
    mongo_client = None
    db = None

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=get_prefix, intents=intents, case_insensitive=True)
bot.remove_command('help')
bot.start_time = time.time()

# Cache for server settings
server_cache = {}

async def get_prefix(bot, message):
    """Get custom prefix for server"""
    if not message.guild:
        return '!'
    
    guild_id = str(message.guild.id)
    if guild_id in server_cache and 'prefix' in server_cache[guild_id]:
        return server_cache[guild_id]['prefix']
    
    if db:
        server_data = await db.servers.find_one({'guild_id': guild_id})
        if server_data and 'prefix' in server_data:
            if guild_id not in server_cache:
                server_cache[guild_id] = {}
            server_cache[guild_id]['prefix'] = server_data['prefix']
            return server_data['prefix']
    
    return '!'

async def get_server_data(guild_id):
    """Get server configuration from database"""
    guild_id = str(guild_id)
    if db:
        return await db.servers.find_one({'guild_id': guild_id}) or {}
    return {}

async def update_server_data(guild_id, data):
    """Update server configuration in database"""
    guild_id = str(guild_id)
    if db:
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
            await channel.send(embed=discord.Embed(description=message, color=0x3498db))
    
    # Send to combined logs if set
    if 'all' in log_channels:
        channel = bot.get_channel(int(log_channels['all']))
        if channel:
            await channel.send(embed=discord.Embed(description=message, color=0x3498db))

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
    if not db:
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
    
    # Check for bot owner mention
    owner_id = os.getenv('BOT_OWNER_ID')
    if owner_id and f"<@{owner_id}>" in message.content:
        embed = discord.Embed(
            title="😎 That's my Dev!",
            description=f"This awesome bot was crafted by <@{owner_id}>\nTreat him well – without him, I wouldn't even exist! 🤖💙",
            color=0x3498db
        )
        embed.add_field(name="Developer", value=BOT_OWNER_NAME, inline=True)
        embed.add_field(name="About", value=BOT_OWNER_DESCRIPTION, inline=False)
        await message.channel.send(embed=embed)
    
    # Bot mention reply
    if bot.user in message.mentions and not message.content.startswith('/'):
        embed = discord.Embed(
            title="👋 Heya! I'm your assistant bot 🤖",
            description="Need help? Try using `/help` to explore my features.\nModerators can use setup commands too!\n\nLet's make this server awesome together 💫",
            color=0x3498db
        )
        
        view = discord.ui.View()
        help_button = discord.ui.Button(label="📜 Commands", style=discord.ButtonStyle.primary)
        help_button.callback = lambda i: help_command_callback(i)
        view.add_item(help_button)
        
        await message.channel.send(embed=embed, view=view)
    
    # XP System
    if message.guild:
        xp_gain = random.randint(5, 15)
        level_up = await add_xp(message.author.id, message.guild.id, xp_gain)
        
        if level_up:
            server_data = await get_server_data(message.guild.id)
            xp_channel_id = server_data.get('xp_channel')
            
            if xp_channel_id:
                xp_channel = bot.get_channel(int(xp_channel_id))
                if xp_channel:
                    user_data = await db.users.find_one({'user_id': str(message.author.id), 'guild_id': str(message.guild.id)})
                    level = user_data.get('level', 1)
                    
                    embed = discord.Embed(
                        title="🎉 Level Up!",
                        description=f"{message.author.mention} reached **Level {level}**!",
                        color=0xf39c12
                    )
                    
                    # Try to create rank image
                    rank_image = await create_rank_image(message.author, user_data.get('xp', 0), level)
                    if rank_image:
                        file = discord.File(rank_image, filename="levelup.png")
                        embed.set_image(url="attachment://levelup.png")
                        await xp_channel.send(embed=embed, file=file)
                    else:
                        await xp_channel.send(embed=embed)
    
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    """Send welcome message and DM"""
    server_data = await get_server_data(member.guild.id)
    
    # Send welcome message to channel
    welcome_channel_id = server_data.get('welcome_channel')
    welcome_message = server_data.get('welcome_message', f"Welcome to {member.guild.name}!")
    
    if welcome_channel_id:
        welcome_channel = bot.get_channel(int(welcome_channel_id))
        if welcome_channel:
            embed = discord.Embed(
                title="👋 Welcome!",
                description=welcome_message.format(user=member.mention, server=member.guild.name),
                color=0x43b581
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await welcome_channel.send(embed=embed)
    
    # Send DM to new member
    try:
        embed = discord.Embed(
            title=f"👋 Hii, I'm **{BOT_NAME}** – your helpful assistant!",
            description=f"Welcome to **{member.guild.name}** 🎊\nWe're thrilled to have you here!\n\nGet comfy, explore the channels, and feel free to say hi 👀\nIf you ever need help, just mention me or use a command!\n\nLet's make this server even more awesome together 💫",
            color=0x3498db
        )
        
        view = discord.ui.View()
        invite_button = discord.ui.Button(label="🤖 Invite Bot", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands")
        view.add_item(invite_button)
        
        await member.send(embed=embed, view=view)
    except:
        pass  # User has DMs disabled

@bot.event
async def on_member_remove(member):
    """Send goodbye DM"""
    try:
        embed = discord.Embed(
            title=f"Hey {member.display_name}, we noticed you left **{member.guild.name}** 😔",
            description=f"Just wanted to say thank you for being a part of our community.\nWe hope you had a good time there, and we'll always have a spot saved if you return 💙\n\nTake care and stay awesome! ✨\n— {BOT_NAME}",
            color=0xe74c3c
        )
        
        view = discord.ui.View()
        invite_button = discord.ui.Button(label="🤖 Invite Bot", style=discord.ButtonStyle.link, url=f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands")
        view.add_item(invite_button)
        
        await member.send(embed=embed, view=view)
    except:
        pass  # User has DMs disabled

# Help Command Callback
async def help_command_callback(interaction):
    """Callback for help button"""
    embed = discord.Embed(
        title="🤖 ᴠᴀᴀᴢʜᴀ Help Menu",
        description="**Namaskaram! Need help?**\n\n**ᴠᴀᴀᴢʜᴀ-ʙᴏᴛ undu. Chill aanu!**\n\nSelect a category below to view all commands.\nUse `/setup` commands to configure the bot per server.\n\n🔐 Role Restricted Commands:\n- 🟢 Everyone\n- 🔵 Junior Moderator\n- 🔴 Main Moderator",
        color=0x3498db
    )
    
    view = HelpView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Help View Class
class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__()
    
    @discord.ui.button(label="🧩 General", style=discord.ButtonStyle.secondary)
    async def general_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🧩 General Commands", color=0x3498db)
        embed.add_field(name="🟢 /help", value="Show this help menu", inline=False)
        embed.add_field(name="🟢 /userinfo", value="Show user information", inline=False)
        embed.add_field(name="🟢 /serverinfo", value="Show server information", inline=False)
        embed.add_field(name="🔵 /ping", value="Check bot latency", inline=False)
        embed.add_field(name="🔵 /uptime", value="Show bot uptime", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🛡 Moderation", style=discord.ButtonStyle.secondary)
    async def moderation_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛡 Moderation Commands", color=0xe74c3c)
        embed.add_field(name="🔴 /kick", value="Kick a user from server", inline=False)
        embed.add_field(name="🔴 /ban", value="Ban a user from server", inline=False)
        embed.add_field(name="🔴 /nuke", value="Delete all messages in channel", inline=False)
        embed.add_field(name="🔵 /mute", value="Mute user in voice channel", inline=False)
        embed.add_field(name="🔵 /unmute", value="Unmute user in voice channel", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🛠 Setup", style=discord.ButtonStyle.secondary)
    async def setup_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛠 Setup Commands", color=0xf39c12)
        embed.add_field(name="🔴 /setup main_moderator", value="Set main moderator role", inline=False)
        embed.add_field(name="🔴 /setup junior_moderator", value="Set junior moderator role", inline=False)
        embed.add_field(name="🔴 /setup welcome", value="Configure welcome messages", inline=False)
        embed.add_field(name="🔴 /setup logs", value="Configure logging channels", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="📣 Communication", style=discord.ButtonStyle.secondary)
    async def communication_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="📣 Communication Commands", color=0x9b59b6)
        embed.add_field(name="🔵 /say", value="Make bot say something", inline=False)
        embed.add_field(name="🔵 /embed", value="Send rich embed message", inline=False)
        embed.add_field(name="🔴 /announce", value="Send announcement", inline=False)
        embed.add_field(name="🔵 /poll", value="Create a poll", inline=False)
        embed.add_field(name="🔵 /reminder", value="Set a reminder", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

# Slash Commands
@bot.tree.command(name="help", description="Show help menu with all commands")
async def help_command(interaction: discord.Interaction):
    await help_command_callback(interaction)

@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latency: {latency}ms", color=0x43b581)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="uptime", description="Show bot uptime")
async def uptime(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    uptime_seconds = time.time() - bot.start_time
    uptime_str = str(timedelta(seconds=int(uptime_seconds)))
    
    embed = discord.Embed(title="⏰ Bot Uptime", description=f"I've been running for: **{uptime_str}**", color=0x3498db)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Show information about a user")
async def userinfo(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user
    
    embed = discord.Embed(title=f"👤 {user.display_name}", color=user.color)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="📅 Joined Server", value=user.joined_at.strftime("%B %d, %Y"), inline=True)
    embed.add_field(name="📅 Account Created", value=user.created_at.strftime("%B %d, %Y"), inline=True)
    embed.add_field(name="🎭 Roles", value=f"{len(user.roles)-1} roles", inline=True)
    embed.add_field(name="🆔 User ID", value=user.id, inline=True)
    embed.add_field(name="📱 Status", value=str(user.status).title(), inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Show server information")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    
    embed = discord.Embed(title=f"🏰 {guild.name}", color=0x3498db)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
    embed.add_field(name="📅 Created", value=guild.created_at.strftime("%B %d, %Y"), inline=True)
    embed.add_field(name="🔒 Verification Level", value=str(guild.verification_level).title(), inline=True)
    embed.add_field(name="📂 Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="🆔 Server ID", value=guild.id, inline=True)
    
    await interaction.response.send_message(embed=embed)

# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Please set DISCORD_BOT_TOKEN in your secrets!")
    else:
        bot.run(token)
