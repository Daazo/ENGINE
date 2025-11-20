import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
from datetime import datetime, timedelta
from main import bot
from brand_config import BOT_FOOTER, BrandColors
from main import has_permission, get_server_data, update_server_data, log_action, has_permission_user
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
    "f*ck", "f@ck", "fuck", "f*kin", "f**kin", "f*cked", "fcked", "fcuk",
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

async def on_message_timeout_check(message):
    """Check messages for timeout triggers (called from main.py on_message event)"""
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

async def restore_timeout_permissions(guild, member):
    """Restore previous channel permissions after timeout ends"""
    guild_id = str(guild.id)
    user_id = str(member.id)
    
    # Check if we have timeout data for this user
    if guild_id in user_messages and user_id in user_messages[guild_id]:
        timeout_data = user_messages[guild_id][user_id].get('timeout_data')
        
        if timeout_data and 'overrides' in timeout_data:
            overrides = timeout_data['overrides']
            
            # Restore permissions for each channel
            for channel_id_str, override_data in overrides.items():
                channel = guild.get_channel(int(channel_id_str))
                if channel:
                    try:
                        if override_data['had_override']:
                            # Restore previous overwrite using allow/deny values
                            allow = discord.Permissions(override_data['allow'])
                            deny = discord.Permissions(override_data['deny'])
                            overwrite = discord.PermissionOverwrite.from_pair(allow, deny)
                            await channel.set_permissions(member, overwrite=overwrite, reason="Timeout ended - restoring previous permissions")
                        else:
                            # No previous overwrite, so remove the timeout overwrite
                            await channel.set_permissions(member, overwrite=None, reason="Timeout ended - removing restrictions")
                    except Exception as e:
                        print(f"⚠️ [TIMEOUT RESTORE] Could not restore permissions for {channel.name}: {e}")
            
            # Clear timeout data
            user_messages[guild_id][user_id]['timeout_data'] = None
            print(f"✅ [TIMEOUT RESTORE] Restored permissions for {member} in {guild.name}")

async def timeout_user(member, guild, timeout_duration, offense_type, message_content, offense_count):
    """Timeout a user and send notifications"""
    # Get log channel
    server_data = await get_server_data(guild.id)
    log_channels = server_data.get('log_channels', {})
    timeout_settings = server_data.get('timeout_settings', {})
    timeout_channel_id = timeout_settings.get('timeout_channel')
    
    log_channel = None

    if 'moderation' in log_channels:
        log_channel = bot.get_channel(int(log_channels['moderation']))
    elif 'all' in log_channels:
        log_channel = bot.get_channel(int(log_channels['all']))
    
    # This is for the new setup command, will be refactored later
    # Use generic 'timeout' log type if specific one is not found
    log_type = 'timeout' 
    if log_channel is None:
        if 'all' in log_channels:
            log_channel = bot.get_channel(int(log_channels['all']))
            log_type = 'all' # If 'all' is the fallback, log it there

    try:
        # Check if bot has timeout permissions
        if not guild.me.guild_permissions.moderate_members:
            print(f"❌ [TIMEOUT ERROR] Bot lacks 'Moderate Members' permission in {guild.name}")
            return False

        # Check if target member can be timed out
        if member.top_role >= guild.me.top_role:
            print(f"❌ [TIMEOUT ERROR] Cannot timeout {member} - role hierarchy")
            return False

        # Apply Discord timeout
        duration = timedelta(minutes=timeout_duration)
        await member.timeout(duration, reason=f"Auto-timeout: {offense_type.title()} violation")
        
        # Apply timeout channel restrictions if configured
        if timeout_channel_id:
            timeout_channel = guild.get_channel(int(timeout_channel_id))
            if timeout_channel:
                # Track channels modified for this timeout and save previous overrides
                timeout_overrides = {}
                
                # Set channel-specific permissions for the timed-out user
                # They can ONLY see and send messages in the timeout channel
                for channel in guild.channels:
                    # Only apply to text channels, voice channels, and categories
                    if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
                        try:
                            # Save previous overwrite using pair() method to get allow/deny values
                            previous_overwrite = channel.overwrites_for(member)
                            allow, deny = previous_overwrite.pair() if previous_overwrite else (discord.Permissions.none(), discord.Permissions.none())
                            
                            if channel.id == timeout_channel.id:
                                # Allow viewing and sending in timeout channel only
                                overwrite = discord.PermissionOverwrite(
                                    view_channel=True,
                                    send_messages=True,
                                    read_message_history=True
                                )
                                await channel.set_permissions(
                                    member,
                                    overwrite=overwrite,
                                    reason=f"Timeout channel access - {offense_type}"
                                )
                            else:
                                # Deny access to all other channels
                                overwrite = discord.PermissionOverwrite(
                                    view_channel=False
                                )
                                await channel.set_permissions(
                                    member,
                                    overwrite=overwrite,
                                    reason=f"Timeout restriction - {offense_type}"
                                )
                            
                            # Store channel ID and previous overwrite for restoration
                            # Save allow/deny permission values for reconstruction
                            timeout_overrides[str(channel.id)] = {
                                'had_override': previous_overwrite is not None and not previous_overwrite.is_empty(),
                                'allow': allow.value,
                                'deny': deny.value
                            }
                            
                        except Exception as e:
                            print(f"⚠️ [TIMEOUT] Could not set permissions for {channel.name}: {e}")
                
                # Store timeout data with expiry time for cleanup
                user_id = str(member.id)
                guild_id = str(guild.id)
                if guild_id not in user_messages:
                    user_messages[guild_id] = {}
                if user_id not in user_messages[guild_id]:
                    user_messages[guild_id][user_id] = {
                        'messages': [],
                        'bad_word_count': 0,
                        'spam_count': 0,
                        'link_count': 0
                    }
                
                # Store timeout info with expiry and previous overrides
                user_messages[guild_id][user_id]['timeout_data'] = {
                    'overrides': timeout_overrides,
                    'expires_at': (datetime.now() + timedelta(minutes=timeout_duration)).timestamp()
                }

        # Send DM to user
        try:
            dm_embed = discord.Embed(
                title="⏰ You've been timed out",
                description=f"**Server:** {guild.name}\n**Reason:** {offense_type.title()} violation\n**Duration:** {timeout_duration} minutes",
                color=BrandColors.WARNING
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
                color=BrandColors.WARNING
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
        color=BrandColors.SUCCESS if enabled else 0xe74c3c
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "setup", f"⚙️ [TIMEOUT SETTINGS] {feature_names.get(feature, feature)} {status.lower()} by {interaction.user}")

# NOTE: /remove-timeout command has been moved to enhanced_security.py (Phase 1)
# The enhanced version includes role restoration in addition to channel permission restoration

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
            color=BrandColors.INFO
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

        embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
    else:
        embed = discord.Embed(
            title=f"📊 **Timeout Stats for {user.display_name}**",
            description="✅ **Clean Record!**\nThis user has no timeout offenses.",
            color=BrandColors.SUCCESS
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="timeout-channel", description="🔒 Configure timeout channel for isolated communication")
@app_commands.describe(
    channel="Channel where timed-out members can chat (set to None to disable)"
)
async def timeout_channel_config(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    timeout_settings = server_data.get('timeout_settings', {})
    
    if channel:
        timeout_settings['timeout_channel'] = str(channel.id)
        status_msg = f"✅ Timeout channel set to {channel.mention}"
        description = f"**Timeout Channel:** {channel.mention}\n**Status:** Active\n\n⚡ **How it works:**\nWhen a member is timed out, they will:\n• Lose access to all server channels\n• Only see and chat in {channel.mention}\n• Have restrictions removed when timeout ends\n\nThis provides 100% isolation for timed-out members while allowing communication."
        color = BrandColors.SUCCESS
    else:
        timeout_settings.pop('timeout_channel', None)
        status_msg = "❌ Timeout channel disabled"
        description = "**Status:** Disabled\n\nTimed-out members will use Discord's default timeout system only."
        color = BrandColors.WARNING
    
    await update_server_data(interaction.guild.id, {'timeout_settings': timeout_settings})
    
    embed = discord.Embed(
        title="🔒 **Timeout Channel Configuration**",
        description=description,
        color=color
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "setup", f"🔒 [TIMEOUT CHANNEL] {status_msg} by {interaction.user}")

async def timeout_cleanup_task():
    """Background task to check and clean up expired timeouts"""
    await bot.wait_until_ready()
    print("✅ [TIMEOUT] Auto-cleanup task started")
    
    while not bot.is_closed():
        try:
            current_time = time.time()
            
            # Check all guilds for expired timeouts
            for guild_id_str, guild_data in list(user_messages.items()):
                guild = bot.get_guild(int(guild_id_str))
                if not guild:
                    continue
                
                for user_id_str, user_data in list(guild_data.items()):
                    timeout_data = user_data.get('timeout_data')
                    
                    if timeout_data and 'expires_at' in timeout_data:
                        expires_at = timeout_data['expires_at']
                        
                        # Check if timeout has expired
                        if current_time >= expires_at:
                            member = guild.get_member(int(user_id_str))
                            
                            if member and not member.is_timed_out():
                                # Timeout expired naturally, restore permissions
                                await restore_timeout_permissions(guild, member)
                                print(f"🔄 [AUTO-CLEANUP] Restored permissions for {member} after timeout expiry")
            
        except Exception as e:
            print(f"❌ [TIMEOUT CLEANUP ERROR] {e}")
        
        # Run every 60 seconds
        await asyncio.sleep(60)

# Hook into message events
@bot.event
async def on_message(message):
    # First run the existing on_message logic
    await bot.process_commands(message)

    # Then check for timeout triggers
    await on_message_timeout_check(message)