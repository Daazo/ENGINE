import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
from datetime import datetime, timedelta
from main import bot, has_permission, get_server_data, update_server_data, log_action, has_permission_user
import re

# Bad words list (comprehensive but family-friendly for code)
BAD_WORDS = [
    # Malayalam/Manglish terms
    "thendi", "thengai", "thevudiya", "thevdiya", "thevidiya", "thevdi",
    "pund", "punda", "pundy", "pundai", "veriyan",

    # Hindi terms (censored)
    "madarchod", "madarch0d", "behanchod", "bhenchod", "bhench0d",
    "lund", "l0nd", "chut",

    # English terms (censored)
    "ass", "bastard", "basterd", "bullsh*t", "b0llocks",
    "crap", "d*ck", "d1ck", "d!ck", "dick",
    "f*ck", "f@ck", "fck", "f*kin", "f**kin", "f*cked", "fcked", "fcuk",
    "motherf*cker", "m0therf*cker", "mf", "mthr fkr", "mother f***er",
    "pr*ck", "p*ss", "piss", "p1ss", "s*hit", "sh*t", "sh1t", "s#it",
    "sl*t", "s1ut", "s!ut", "wh*re", "w#ore", "w0re", "wank", "w@nker",

    # Common variations and leetspeak
    "a**hole", "a55", "a$$", "b*tch", "b1tch", "bi+ch",
    "c*nt", "c@nt", "k***a", "k@**a", "ka*di", "kaam",
    "p*nd", "p*nday", "p0nday"
]

# User message tracking for spam detection
user_messages = {}

@bot.event
async def on_message_timeout_check(message):
    """Check messages for timeout triggers"""
    if message.author.bot or not message.guild:
        return

    # Skip if user has moderator permissions
    if await has_permission_user(message.author, message.guild, "junior_moderator"):
        return

    server_data = await get_server_data(message.guild.id)
    timeout_settings = server_data.get('timeout_settings', {
        'bad_words': True,
        'spam': True,
        'links': True,
        'enabled': True
    })

    if not timeout_settings.get('enabled', True):
        return

    user_id = str(message.author.id)
    guild_id = str(message.guild.id)

    # Initialize user data if not exists
    if guild_id not in user_messages:
        user_messages[guild_id] = {}
    if user_id not in user_messages[guild_id]:
        user_messages[guild_id][user_id] = {
            'messages': [],
            'bad_word_count': 0,
            'spam_count': 0,
            'link_count': 0
        }

    user_data = user_messages[guild_id][user_id]

    # Check for bad words
    if timeout_settings.get('bad_words', True):
        if contains_bad_words(message.content.lower()):
            user_data['bad_word_count'] += 1
            duration = 10 * user_data['bad_word_count']  # 10, 20, 30 minutes...
            await timeout_user(message.author, message.guild, duration, "Bad Language", message.content, user_data['bad_word_count'])
            try:
                await message.delete()
            except:
                pass
            return

    # Check for links
    if timeout_settings.get('links', True):
        if contains_links(message.content):
            user_data['link_count'] += 1
            duration = 8 * user_data['link_count']  # 8, 16, 24 minutes...
            await timeout_user(message.author, message.guild, duration, "Unauthorized Links", message.content, user_data['link_count'])
            try:
                await message.delete()
            except:
                pass
            return

    # Check for spam
    if timeout_settings.get('spam', True):
        current_time = time.time()
        user_data['messages'].append(current_time)

        # Remove messages older than 10 seconds
        user_data['messages'] = [msg_time for msg_time in user_data['messages'] if current_time - msg_time <= 10]

        # Check if more than 5 messages in 10 seconds
        if len(user_data['messages']) > 5:
            user_data['spam_count'] += 1
            duration = 5 * user_data['spam_count']  # 5, 10, 15 minutes...
            await timeout_user(message.author, message.guild, duration, "Spam", f"Sent {len(user_data['messages'])} messages in 10 seconds", user_data['spam_count'])
            # Clear message history after timeout
            user_data['messages'] = []
            return

def contains_bad_words(text):
    """Check if text contains bad words"""
    words = re.findall(r'\b\w+\b', text.lower())
    text_clean = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())

    for bad_word in BAD_WORDS:
        # Check exact word match
        if bad_word in words:
            return True
        # Check substring match for variations
        if bad_word in text_clean:
            return True

    return False

def contains_links(text):
    """Check if text contains links"""
    link_patterns = [
        r'http[s]?://',
        r'www\.',
        r'[a-zA-Z0-9-]+\.[a-zA-Z]{2,}',
        r'discord\.gg',
        r'bit\.ly',
        r'tinyurl\.com'
    ]

    for pattern in link_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False

async def timeout_user(member, guild, timeout_duration, offense_type, message_content, offense_count):
    """Timeout a user and send notifications"""
    # Get log channel
    server_data = await get_server_data(guild.id)
    log_channels = server_data.get('log_channels', {})
    log_channel = None

    if 'moderation' in log_channels:
        log_channel = bot.get_channel(int(log_channels['moderation']))
    elif 'all' in log_channels:
        log_channel = bot.get_channel(int(log_channels['all']))

    try:
        # Check if bot has timeout permissions
        if not guild.me.guild_permissions.moderate_members:
            print(f"❌ [TIMEOUT ERROR] Bot lacks 'Moderate Members' permission in {guild.name}")
            return False

        # Check if target member can be timed out
        if member.top_role >= guild.me.top_role:
            print(f"❌ [TIMEOUT ERROR] Cannot timeout {member} - role hierarchy")
            return False

        # Apply timeout
        duration = timedelta(minutes=timeout_duration)
        await member.timeout(duration, reason=f"Auto-timeout: {offense_type.title()} violation")

        # Send DM to user
        try:
            dm_embed = discord.Embed(
                title="⏰ You've been timed out",
                description=f"**Server:** {guild.name}\n**Reason:** {offense_type.title()} violation\n**Duration:** {timeout_duration} minutes",
                color=0xf39c12
            )
            dm_embed.add_field(
                name="⚠️ Warning",
                value=f"Repeated offenses will result in longer timeouts. This is your #{offense_count} offense.",
                inline=False
            )
            dm_embed.set_footer(text="Please follow server rules")
            await member.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled

        # Log in staff channel
        if log_channel:
            log_embed = discord.Embed(
                title="🔇 Auto-Timeout Applied",
                color=0xf39c12
            )
            log_embed.add_field(name="User", value=f"{member.mention} ({member})", inline=True)
            log_embed.add_field(name="Reason", value=offense_type.title(), inline=True)
            log_embed.add_field(name="Duration", value=f"{timeout_duration} minutes", inline=True)
            log_embed.add_field(name="Offense Count", value=f"#{offense_count}", inline=True)
            if message_content:
                log_embed.add_field(name="Message", value=f"```{message_content[:100]}```", inline=False)
            log_embed.set_footer(text=f"Auto-moderation • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await log_channel.send(embed=log_embed)

        print(f"⏰ [TIMEOUT] {member} timed out for {timeout_duration}m - {offense_type}")
        return True

    except discord.Forbidden:
        print(f"❌ [TIMEOUT ERROR] Cannot timeout {member} - insufficient permissions")
        return False
    except discord.HTTPException as e:
        print(f"❌ [TIMEOUT ERROR] HTTP error when timing out {member}: {e}")
        return False
    except Exception as e:
        print(f"❌ [TIMEOUT ERROR] Failed to timeout {member}: {e}")
        return False

@bot.tree.command(name="timeout-settings", description="⚙️ Configure auto-timeout system")
@app_commands.describe(
    feature="Which feature to toggle",
    enabled="Enable or disable the feature"
)
@app_commands.choices(feature=[
    app_commands.Choice(name="bad_words", value="bad_words"),
    app_commands.Choice(name="spam", value="spam"),
    app_commands.Choice(name="links", value="links"),
    app_commands.Choice(name="all_features", value="enabled")
])
async def timeout_settings(
    interaction: discord.Interaction,
    feature: str,
    enabled: bool
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    timeout_settings = server_data.get('timeout_settings', {})

    timeout_settings[feature] = enabled
    await update_server_data(interaction.guild.id, {'timeout_settings': timeout_settings})

    feature_names = {
        'bad_words': 'Bad Words Detection',
        'spam': 'Spam Detection',
        'links': 'Link Detection',
        'enabled': 'Auto-Timeout System'
    }

    status = "✅ Enabled" if enabled else "❌ Disabled"

    embed = discord.Embed(
        title="⚙️ **Timeout Settings Updated**",
        description=f"**Feature:** {feature_names.get(feature, feature)}\n**Status:** {status}",
        color=0x43b581 if enabled else 0xe74c3c
    )
    embed.set_footer(text="🤖 ᴠᴀᴀᴢʜᴀ Auto-Moderation", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "setup", f"⚙️ [TIMEOUT SETTINGS] {feature_names.get(feature, feature)} {status.lower()} by {interaction.user}")

@bot.tree.command(name="remove-timeout", description="🔓 Remove timeout from a user early")
@app_commands.describe(user="User to remove timeout from")
async def remove_timeout(interaction: discord.Interaction, user: discord.Member):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return

    if not user.is_timed_out():
        await interaction.response.send_message(f"❌ {user.mention} is not currently timed out!", ephemeral=True)
        return

    try:
        await user.timeout(None, reason=f"Timeout removed by {interaction.user}")

        embed = discord.Embed(
            title="🔓 **Timeout Removed**",
            description=f"**User:** {user.mention}\n**Removed by:** {interaction.user.mention}\n**Action:** Timeout has been lifted early",
            color=0x43b581
        )
        embed.set_footer(text="🤖 ᴠᴀᴀʀᴀ Moderation", icon_url=bot.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild.id, "moderation", f"🔓 [TIMEOUT REMOVED] {user} timeout removed by {interaction.user}")

        # Notify user via DM
        try:
            dm_embed = discord.Embed(
                title="🔓 **Timeout Removed**",
                description=f"**Server:** {interaction.guild.name}\n**Removed by:** {interaction.user}\n**Status:** You can now participate normally in the server",
                color=0x43b581
            )
            dm_embed.set_footer(text="ᴠᴀᴀʀᴀ Moderation", icon_url=bot.user.display_avatar.url)
            await user.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled

    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to remove timeout: {str(e)}", ephemeral=True)

@bot.tree.command(name="timeout-stats", description="📊 View timeout statistics for a user")
@app_commands.describe(user="User to check timeout stats for")
async def timeout_stats(interaction: discord.Interaction, user: discord.Member = None):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return

    if user is None:
        user = interaction.user

    guild_id = str(interaction.guild.id)
    user_id = str(user.id)

    if guild_id in user_messages and user_id in user_messages[guild_id]:
        user_data = user_messages[guild_id][user_id]

        embed = discord.Embed(
            title=f"📊 **Timeout Stats for {user.display_name}**",
            color=0x3498db
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="🤬 Bad Words", value=f"`{user_data['bad_word_count']}` offenses", inline=True)
        embed.add_field(name="💨 Spam", value=f"`{user_data['spam_count']}` offenses", inline=True)
        embed.add_field(name="🔗 Links", value=f"`{user_data['link_count']}` offenses", inline=True)

        total_offenses = user_data['bad_word_count'] + user_data['spam_count'] + user_data['link_count']
        embed.add_field(name="📈 Total Offenses", value=f"`{total_offenses}`", inline=False)

        if user.is_timed_out():
            timeout_until = user.timed_out_until
            remaining = timeout_until - discord.utils.utcnow()
            minutes_left = int(remaining.total_seconds() / 60)
            embed.add_field(name="⏰ Current Status", value=f"🔴 Timed out ({minutes_left} minutes left)", inline=False)
        else:
            embed.add_field(name="⏰ Current Status", value="🟢 Active", inline=False)

        embed.set_footer(text="🤖 ᴠᴀᴀʀᴀ Auto-Moderation Stats", icon_url=bot.user.display_avatar.url)
    else:
        embed = discord.Embed(
            title=f"📊 **Timeout Stats for {user.display_name}**",
            description="✅ **Clean Record!**\nThis user has no timeout offenses.",
            color=0x43b581
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="🤖 ᴠᴀᴀʀᴀ Auto-Moderation Stats", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

# Hook into message events
@bot.event
async def on_message(message):
    # First run the existing on_message logic
    await bot.process_commands(message)

    # Then check for timeout triggers
    await on_message_timeout_check(message)