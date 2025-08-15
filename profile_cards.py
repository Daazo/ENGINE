import discord
from discord.ext import commands
from discord import app_commands
from main import bot, db, has_permission, get_server_data, log_action
from xp_commands import get_karma_level_info
from economy_system import get_user_economy
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import os
import asyncio
import io

# Default template colors and settings
CARD_WIDTH = 800
CARD_HEIGHT = 400
BACKGROUND_COLOR = (45, 47, 49)  # Discord dark theme
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (67, 181, 129)  # Vaazha green
KARMA_COLOR = (243, 156, 18)  # Gold
COIN_COLOR = (241, 196, 15)  # Yellow gold

async def download_avatar(avatar_url):
    """Download user avatar from URL"""
    try:
        response = requests.get(avatar_url, timeout=10)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"Error downloading avatar: {e}")

    # Return default avatar if download fails
    default_avatar = Image.new('RGB', (128, 128), (114, 137, 218))
    draw = ImageDraw.Draw(default_avatar)
    draw.text((64, 64), "?", fill=(255, 255, 255), anchor="mm")
    return default_avatar

def create_circular_avatar(avatar_image, size=120):
    """Convert avatar to circular shape"""
    # Resize avatar
    avatar = avatar_image.resize((size, size), Image.Resampling.LANCZOS)

    # Create circular mask
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)

    # Apply mask to create circular avatar
    circular_avatar = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    circular_avatar.paste(avatar, (0, 0))
    circular_avatar.putalpha(mask)

    return circular_avatar

def draw_progress_bar(draw, x, y, width, height, progress, max_value, color, bg_color=(70, 70, 70)):
    """Draw a progress bar"""
    # Background bar
    draw.rounded_rectangle([x, y, x + width, y + height], radius=height//2, fill=bg_color)

    # Progress bar
    if max_value > 0:
        progress_width = int((progress / max_value) * width)
        if progress_width > 0:
            draw.rounded_rectangle([x, y, x + progress_width, y + height], radius=height//2, fill=color)

def get_default_font(size):
    """Get default font with fallback"""
    try:
        # Try to use a nice font if available
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        try:
            return ImageFont.truetype("/System/Library/Fonts/Arial.ttf", size)
        except:
            return ImageFont.load_default()

async def create_profile_card(user, guild, karma_data, economy_data):
    """Create a profile card image for the user"""
    # Create base image
    card = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(card)

    # Load fonts
    title_font = get_default_font(32)
    subtitle_font = get_default_font(20)
    text_font = get_default_font(16)
    small_font = get_default_font(14)

    # Download and process avatar
    avatar_url = str(user.display_avatar.url)
    avatar_image = await download_avatar(avatar_url)
    circular_avatar = create_circular_avatar(avatar_image, 100)

    # Paste avatar
    avatar_x = 50
    avatar_y = 50
    card.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)

    # Draw avatar border
    draw.ellipse([avatar_x-2, avatar_y-2, avatar_x+102, avatar_y+102], outline=ACCENT_COLOR, width=3)

    # User information section
    info_x = 180
    info_y = 50

    # Username and tag
    display_name = user.display_name
    if len(display_name) > 20:
        display_name = display_name[:17] + "..."

    draw.text((info_x, info_y), display_name, fill=TEXT_COLOR, font=title_font)
    draw.text((info_x, info_y + 40), f"@{user.name}", fill=(150, 150, 150), font=subtitle_font)

    # Join date
    join_date = user.joined_at.strftime("%B %d, %Y") if user.joined_at else "Unknown"
    draw.text((info_x, info_y + 70), f"Joined: {join_date}", fill=(200, 200, 200), font=text_font)

    # Server position
    members_sorted = sorted(guild.members, key=lambda m: m.joined_at or guild.created_at)
    join_position = members_sorted.index(user) + 1
    draw.text((info_x, info_y + 95), f"Member #{join_position}", fill=(200, 200, 200), font=text_font)

    # Stats section
    stats_y = 200

    # Karma information
    karma = karma_data.get('karma', 0) if karma_data else 0
    current_level, next_level = get_karma_level_info(karma)
    level_title = current_level["title"] if current_level else "🌱 New Member"

    draw.text((50, stats_y), "✨ KARMA LEVEL", fill=KARMA_COLOR, font=subtitle_font)
    draw.text((50, stats_y + 30), f"{karma} points", fill=TEXT_COLOR, font=text_font)
    draw.text((50, stats_y + 55), level_title, fill=KARMA_COLOR, font=text_font)

    # Karma progress bar
    if next_level:
        if current_level:
            progress = karma - current_level["milestone"]
            max_progress = next_level["milestone"] - current_level["milestone"]
        else:
            progress = karma
            max_progress = next_level["milestone"]

        draw_progress_bar(draw, 50, stats_y + 80, 200, 20, progress, max_progress, KARMA_COLOR)
        draw.text((260, stats_y + 82), f"{progress}/{max_progress}", fill=(200, 200, 200), font=small_font)
    else:
        draw.text((50, stats_y + 80), "MAX LEVEL!", fill=KARMA_COLOR, font=text_font)

    # Economy information
    coins = economy_data.get('coins', 0) if economy_data else 0
    bank = economy_data.get('bank', 0) if economy_data else 0
    total_wealth = coins + bank

    draw.text((400, stats_y), "🪙 VAAZHA COINS", fill=COIN_COLOR, font=subtitle_font)
    draw.text((400, stats_y + 30), f"{total_wealth:,} total", fill=TEXT_COLOR, font=text_font)
    draw.text((400, stats_y + 55), f"💰 {coins:,} wallet | 🏦 {bank:,} bank", fill=(200, 200, 200), font=small_font)

    # Roles section
    top_roles = [role for role in user.roles if role.name != "@everyone" and role.name != "Admin"][:3]
    if top_roles:
        draw.text((400, stats_y + 80), "🎭 TOP ROLES", fill=ACCENT_COLOR, font=text_font)
        role_text = ", ".join([role.name[:15] for role in top_roles])
        if len(role_text) > 35:
            role_text = role_text[:32] + "..."
        draw.text((400, stats_y + 105), role_text, fill=(200, 200, 200), font=small_font)

    # Status indicators
    status_y = CARD_HEIGHT - 80

    # Server rank based on karma
    if db is not None:
        users_sorted = await db.karma.find({'guild_id': str(guild.id)}).sort('karma', -1).to_list(None)
        rank = next((i + 1 for i, u in enumerate(users_sorted) if u['user_id'] == str(user.id)), "Unranked")
    else:
        rank = "N/A"

    draw.text((50, status_y), f"🏆 Server Rank: #{rank}", fill=ACCENT_COLOR, font=text_font)

    # User status
    status_emoji = {"online": "🟢", "idle": "🟡", "dnd": "🔴", "offline": "⚫"}.get(str(user.status), "⚫")
    draw.text((400, status_y), f"{status_emoji} {str(user.status).title()}", fill=TEXT_COLOR, font=text_font)

    # Footer
    draw.text((50, CARD_HEIGHT - 30), "🌴 Generated by VAAZHA-BOT • Made with ❤️ from Kerala", fill=(100, 100, 100), font=small_font)

    return card

async def create_bot_profile_card(bot, owner_status, owner_status_emoji, uptime_str, server_count):
    """Create a profile card for the bot with information"""
    from main import BOT_NAME, BOT_TAGLINE, BOT_OWNER_NAME
    import time

    # Create base image with gradient background
    card = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(card)

    # Load fonts
    title_font = get_default_font(28)
    subtitle_font = get_default_font(18)
    text_font = get_default_font(16)
    small_font = get_default_font(14)

    # Download and process bot avatar
    avatar_url = str(bot.user.display_avatar.url)
    avatar_image = await download_avatar(avatar_url)
    circular_avatar = create_circular_avatar(avatar_image, 120)

    # Paste avatar with special border for bot
    avatar_x = 50
    avatar_y = 40
    card.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)

    # Draw special bot border (gradient-like with multiple colors)
    draw.ellipse([avatar_x-3, avatar_y-3, avatar_x+123, avatar_y+123], outline=ACCENT_COLOR, width=2)
    draw.ellipse([avatar_x-5, avatar_y-5, avatar_x+125, avatar_y+125], outline=KARMA_COLOR, width=1)

    # Bot information section
    info_x = 200
    info_y = 50

    # Bot name and tag
    draw.text((info_x, info_y), BOT_NAME, fill=TEXT_COLOR, font=title_font)
    draw.text((info_x, info_y + 35), f"@{bot.user.name}", fill=(150, 150, 150), font=subtitle_font)
    draw.text((info_x, info_y + 60), "🤖 Discord Bot", fill=ACCENT_COLOR, font=text_font)

    # Tagline (properly formatted for display)
    draw.text((info_x, info_y + 85), BOT_TAGLINE, fill=(200, 200, 200), font=small_font)

    # Stats section
    stats_y = 180

    # Server count and uptime
    draw.text((50, stats_y), "🏰 SERVER STATISTICS", fill=ACCENT_COLOR, font=subtitle_font)
    draw.text((50, stats_y + 30), f"{server_count} servers", fill=TEXT_COLOR, font=text_font)
    draw.text((50, stats_y + 55), f"⏰ Uptime: {uptime_str}", fill=(200, 200, 200), font=text_font)
    draw.text((50, stats_y + 80), "🟢 Status: Online & Ready", fill=(46, 204, 113), font=text_font)

    # Owner information
    draw.text((400, stats_y), "👨‍💻 BOT DEVELOPER", fill=KARMA_COLOR, font=subtitle_font)
    draw.text((400, stats_y + 30), BOT_OWNER_NAME, fill=TEXT_COLOR, font=text_font)

    # Better status display
    if owner_status == "Offline":
        status_color = (128, 128, 128)
    elif owner_status == "Online":
        status_color = (46, 204, 113)
    elif owner_status == "Idle":
        status_color = (255, 193, 7)
    elif owner_status == "Do Not Disturb":
        status_color = (220, 53, 69)
    else:
        status_color = (200, 200, 200)

    draw.text((400, stats_y + 55), f"{owner_status_emoji} {owner_status}", fill=status_color, font=text_font)
    draw.text((400, stats_y + 80), "🇮🇳 From God's Own Country", fill=ACCENT_COLOR, font=text_font)

    # Features section - reorganized to avoid overlap
    features_y = 270
    draw.text((50, features_y), "⚡ KEY FEATURES", fill=COIN_COLOR, font=subtitle_font)

    # Column 1 features
    draw.text((50, features_y + 25), "✨ Karma System", fill=(200, 200, 200), font=small_font)
    draw.text((50, features_y + 45), "🪙 Economy", fill=(200, 200, 200), font=small_font)
    draw.text((50, features_y + 65), "🎫 Tickets", fill=(200, 200, 200), font=small_font)

    # Column 2 features
    draw.text((180, features_y + 25), "🛡️ Moderation", fill=(200, 200, 200), font=small_font)
    draw.text((180, features_y + 45), "🎮 Games", fill=(200, 200, 200), font=small_font)
    draw.text((180, features_y + 65), "🎭 Roles", fill=(200, 200, 200), font=small_font)

    # Version and build info - moved to the right side
    draw.text((500, features_y), "🔧 BUILD INFO", fill=(155, 89, 182), font=subtitle_font)
    draw.text((500, features_y + 25), "Version: Latest Stable", fill=(200, 200, 200), font=small_font)
    draw.text((500, features_y + 45), "Framework: discord.py", fill=(200, 200, 200), font=small_font)

    # Footer with special message
    footer_y = CARD_HEIGHT - 35
    draw.text((50, footer_y), "🌴 VAAZHA-BOT Profile Card • Your friendly Kerala assistant! • Made with ❤️", fill=(100, 100, 100), font=small_font)

    return card

@bot.tree.command(name="profile", description="🎨 Show a beautiful profile card with user stats and avatar")
@app_commands.describe(user="User to show profile for (optional)")
async def profile_card(interaction: discord.Interaction, user: discord.Member = None):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in servers!", ephemeral=True)
        return

    target_user = user or interaction.user

    # Defer response as image generation takes time
    await interaction.response.defer()

    try:
        # Get user data from databases
        karma_data = None
        economy_data = None

        if db is not None:
            karma_data = await db.karma.find_one({'user_id': str(target_user.id), 'guild_id': str(interaction.guild.id)})
            economy_data = await get_user_economy(target_user.id, interaction.guild.id)

        # Create profile card
        card_image = await create_profile_card(target_user, interaction.guild, karma_data, economy_data)

        # Save image to bytes
        img_bytes = BytesIO()
        card_image.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)

        # Create Discord file
        file = discord.File(img_bytes, filename=f"profile_{target_user.id}.png")

        # Create embed
        embed = discord.Embed(
            title=f"🎨 **{target_user.display_name}'s Profile Card**",
            description=f"*Beautiful profile generated for {target_user.mention}*",
            color=0x43b581
        )
        embed.set_image(url=f"attachment://profile_{target_user.id}.png")
        embed.set_footer(text="🌴 Use /karma and /balance for detailed stats!", icon_url=bot.user.display_avatar.url)

        await interaction.followup.send(embed=embed, file=file)

        await log_action(interaction.guild.id, "general", f"🎨 [PROFILE] {interaction.user} generated profile card for {target_user}")

    except Exception as e:
        print(f"Error creating profile card: {e}")

        # Fallback embed if image generation fails
        karma_data = await db.karma.find_one({'user_id': str(target_user.id), 'guild_id': str(interaction.guild.id)}) if db is not None else None
        karma = karma_data.get('karma', 0) if karma_data else 0
        economy_data = await get_user_economy(target_user.id, interaction.guild.id) if db is not None else None
        coins = economy_data.get('coins', 0) + economy_data.get('bank', 0) if economy_data else 0

        embed = discord.Embed(
            title=f"👤 **{target_user.display_name}'s Profile**",
            description=f"*Profile information for {target_user.mention}*",
            color=target_user.color if target_user.color.value != 0 else 0x3498db
        )
        embed.add_field(name="✨ Karma", value=f"`{karma}` points", inline=True)
        embed.add_field(name="🪙 Vaazha Coins", value=f"`{coins}` coins", inline=True)
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")

        await interaction.followup.send(embed=embed)

@bot.tree.command(name="servercard", description="🏰 Generate a beautiful server overview card")
async def server_card(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        guild = interaction.guild

        # Create server card
        card = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(card)

        # Load fonts
        title_font = get_default_font(36)
        subtitle_font = get_default_font(22)
        text_font = get_default_font(18)

        # Server icon
        if guild.icon:
            icon_url = str(guild.icon.url)
            icon_image = await download_avatar(icon_url)
            circular_icon = create_circular_avatar(icon_image, 120)
            card.paste(circular_icon, (50, 50), circular_icon)
            draw.ellipse([48, 48, 172, 172], outline=ACCENT_COLOR, width=4)

        # Server name
        server_name = guild.name
        if len(server_name) > 25:
            server_name = server_name[:22] + "..."

        draw.text((200, 70), server_name, fill=TEXT_COLOR, font=title_font)
        draw.text((200, 115), f"Created: {guild.created_at.strftime('%B %d, %Y')}", fill=(200, 200, 200), font=text_font)

        # Member stats
        online_members = sum(1 for member in guild.members if member.status != discord.Status.offline)
        bot_count = sum(1 for member in guild.members if member.bot)
        human_count = guild.member_count - bot_count

        stats_y = 200
        draw.text((50, stats_y), "📊 SERVER STATISTICS", fill=ACCENT_COLOR, font=subtitle_font)
        draw.text((50, stats_y + 40), f"👥 {guild.member_count} total members", fill=TEXT_COLOR, font=text_font)
        draw.text((50, stats_y + 65), f"🟢 {online_members} online • 👤 {human_count} humans • 🤖 {bot_count} bots", fill=(200, 200, 200), font=text_font)

        # Channels
        draw.text((400, stats_y), "📁 CHANNELS", fill=COIN_COLOR, font=subtitle_font)
        draw.text((400, stats_y + 40), f"💬 {len(guild.text_channels)} text channels", fill=TEXT_COLOR, font=text_font)
        draw.text((400, stats_y + 65), f"🔊 {len(guild.voice_channels)} voice channels", fill=TEXT_COLOR, font=text_font)

        # Footer
        draw.text((50, CARD_HEIGHT - 30), f"🌴 {guild.name} Server Overview • Generated by VAAZHA-BOT", fill=(100, 100, 100), font=get_default_font(12))

        # Save and send
        img_bytes = BytesIO()
        card.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)

        file = discord.File(img_bytes, filename=f"server_{guild.id}.png")

        embed = discord.Embed(
            title=f"🏰 **{guild.name} Server Card**",
            description="*Beautiful server overview generated*",
            color=0x43b581
        )
        embed.set_image(url=f"attachment://server_{guild.id}.png")

        await interaction.followup.send(embed=embed, file=file)

        await log_action(interaction.guild.id, "general", f"🏰 [SERVERCARD] {interaction.user} generated server card")

    except Exception as e:
        print(f"Error creating server card: {e}")
        await interaction.followup.send("❌ Server card generation failed. Please try again later.", ephemeral=True)

@bot.tree.command(name="botprofile", description="🤖 Show the bot's profile card")
async def bot_profile(interaction: discord.Interaction):
    """Shows the bot's profile card."""
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in servers!", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        # Get bot owner status and uptime
        owner_status = "Offline"
        owner_status_emoji = "⚫"

        # Assuming you have a way to track bot owner's status,
        # e.g., through another bot or a shared variable.
        # For now, we'll use placeholder values.
        # If you have a bot owner object, you can access its status.
        # Example: owner_status = owner.status (if owner is a discord.User object)

        # Calculate uptime (this requires storing the bot's start time)
        # Example: uptime_str = str(datetime.datetime.now() - bot.start_time)
        uptime_str = "Calculating..." # Placeholder

        server_count = len(bot.guilds) if hasattr(bot, 'guilds') else 0

        # Create the bot profile card
        bot_card_image = await create_bot_profile_card(bot, owner_status, owner_status_emoji, uptime_str, server_count)

        if bot_card_image:
            img_bytes = BytesIO()
            bot_card_image.save(img_bytes, format='PNG', quality=95)
            img_bytes.seek(0)

            file = discord.File(img_bytes, filename="bot_profile.png")

            embed = discord.Embed(
                title=f"🤖 **{bot.user.name}'s Profile Card**",
                description="*Here's a glimpse into VAAZHA-BOT's world!*",
                color=0x43b581
            )
            embed.set_image(url="attachment://bot_profile.png")
            embed.set_footer(text="🌴 Proudly serving you!", icon_url=bot.user.display_avatar.url)

            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send("❌ Failed to generate the bot profile card.", ephemeral=True)

        await log_action(interaction.guild.id, "bot_info", f"{interaction.user} viewed bot profile.")

    except Exception as e:
        print(f"Error generating bot profile card: {e}")
        await interaction.followup.send("❌ An error occurred while generating the bot profile card. Please try again later.", ephemeral=True)