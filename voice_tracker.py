import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Dict
import asyncio

from brand_config import (
    BOT_FOOTER, BrandColors, VisualElements,
    create_success_embed, create_error_embed, create_info_embed,
    create_permission_denied_embed
)

bot = None
db = None
has_permission = None
log_action = None

voice_sessions: Dict[str, Dict[str, datetime]] = {}

MILESTONES_HOURS = [24, 50, 100, 150, 200]
MILESTONE_INCREMENT = 50

def format_duration(total_seconds: int) -> str:
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def get_next_milestone(current_hours: float) -> int:
    for milestone in MILESTONES_HOURS:
        if current_hours < milestone:
            return milestone
    
    last_milestone = MILESTONES_HOURS[-1]
    while current_hours >= last_milestone:
        last_milestone += MILESTONE_INCREMENT
    return last_milestone

def get_all_milestones_up_to(hours: float) -> list:
    milestones = []
    for m in MILESTONES_HOURS:
        if hours >= m:
            milestones.append(m)
    
    if hours >= MILESTONES_HOURS[-1]:
        extra = MILESTONES_HOURS[-1] + MILESTONE_INCREMENT
        while hours >= extra:
            milestones.append(extra)
            extra += MILESTONE_INCREMENT
    
    return milestones

async def is_voice_tracker_enabled(guild_id: str) -> bool:
    if db is None:
        return False
    server_data = await db.servers.find_one({'guild_id': guild_id}) or {}
    return server_data.get('voice_tracker_enabled', False)

async def get_voice_data(guild_id: str, user_id: str) -> dict:
    if db is None:
        return {'guild_id': guild_id, 'user_id': user_id, 'total_seconds': 0, 'last_milestone': 0}
    
    data = await db.voice_tracker.find_one({'guild_id': guild_id, 'user_id': user_id})
    if not data:
        return {'guild_id': guild_id, 'user_id': user_id, 'total_seconds': 0, 'last_milestone': 0}
    return data

async def update_voice_data(guild_id: str, user_id: str, total_seconds: int, last_milestone: int):
    if db is None:
        return
    
    await db.voice_tracker.update_one(
        {'guild_id': guild_id, 'user_id': user_id},
        {'$set': {
            'total_seconds': total_seconds,
            'last_milestone': last_milestone
        }},
        upsert=True
    )

def start_session(guild_id: str, user_id: str):
    key = f"{guild_id}_{user_id}"
    voice_sessions[key] = datetime.utcnow()

def end_session(guild_id: str, user_id: str) -> int:
    key = f"{guild_id}_{user_id}"
    if key not in voice_sessions:
        return 0
    
    start_time = voice_sessions.pop(key)
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    return int(elapsed)

def get_session_key(guild_id: str, user_id: str) -> str:
    return f"{guild_id}_{user_id}"

async def send_milestone_message(guild: discord.Guild, member: discord.Member, milestone_hours: int):
    server_data = await db.servers.find_one({'guild_id': str(guild.id)}) or {}
    
    embed = discord.Embed(
        title="🎧 **VOICE MILESTONE UNLOCKED**",
        description=f"{VisualElements.CIRCUIT_LINE}",
        color=BrandColors.PRIMARY,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="◆ Milestone Achieved",
        value=f"**{milestone_hours} Hours** in Voice Channels!",
        inline=False
    )
    embed.add_field(
        name="◆ User",
        value=f"{member.mention} (`{member.display_name}`)",
        inline=True
    )
    embed.add_field(
        name="◆ Server",
        value=f"{guild.name}",
        inline=True
    )
    
    next_milestone = get_next_milestone(milestone_hours)
    embed.add_field(
        name="◆ Next Milestone",
        value=f"**{next_milestone} Hours**",
        inline=False
    )
    
    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
    embed.set_footer(text=f"⚡ RXT ENGINE • Voice Tracker", icon_url=bot.user.display_avatar.url)
    
    log_channel_id = server_data.get('log_channel')
    if log_channel_id:
        channel = guild.get_channel(int(log_channel_id))
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass
    
    try:
        await log_action(guild.id, "voice", f"🎧 [MILESTONE] {member} reached **{milestone_hours}h** voice time!")
    except:
        pass

async def handle_voice_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if db is None:
        return
    
    guild_id = str(member.guild.id)
    user_id = str(member.id)
    session_key = get_session_key(guild_id, user_id)
    
    if not await is_voice_tracker_enabled(guild_id):
        return
    
    afk_channel = member.guild.afk_channel
    
    def is_afk(channel):
        return afk_channel and channel and channel.id == afk_channel.id
    
    was_in_vc = before.channel is not None
    now_in_vc = after.channel is not None
    was_in_afk = is_afk(before.channel)
    now_in_afk = is_afk(after.channel)
    
    was_tracking = was_in_vc and not was_in_afk
    should_track = now_in_vc and not now_in_afk
    
    if was_tracking and not should_track:
        elapsed = end_session(guild_id, user_id)
        if elapsed > 0:
            await process_time_update(member, guild_id, user_id, elapsed)
    
    elif not was_tracking and should_track:
        if session_key not in voice_sessions:
            start_session(guild_id, user_id)

async def process_time_update(member: discord.Member, guild_id: str, user_id: str, elapsed_seconds: int):
    voice_data = await get_voice_data(guild_id, user_id)
    
    old_total = voice_data.get('total_seconds', 0)
    new_total = old_total + elapsed_seconds
    last_milestone = voice_data.get('last_milestone', 0)
    
    old_hours = old_total / 3600
    new_hours = new_total / 3600
    
    new_milestones = []
    for milestone in MILESTONES_HOURS:
        if old_hours < milestone <= new_hours and milestone > last_milestone:
            new_milestones.append(milestone)
    
    if new_hours >= MILESTONES_HOURS[-1]:
        extra = MILESTONES_HOURS[-1] + MILESTONE_INCREMENT
        while extra <= new_hours:
            if old_hours < extra and extra > last_milestone:
                new_milestones.append(extra)
            extra += MILESTONE_INCREMENT
    
    highest_milestone = last_milestone
    for milestone in new_milestones:
        if milestone > highest_milestone:
            highest_milestone = milestone
        try:
            await send_milestone_message(member.guild, member, milestone)
        except Exception as e:
            print(f"Error sending milestone message: {e}")
    
    await update_voice_data(guild_id, user_id, new_total, highest_milestone)

@app_commands.command(name="voicetracker", description="🎧 Enable or disable voice channel time tracking")
@app_commands.describe(action="Turn voice tracking on or off")
@app_commands.choices(action=[
    app_commands.Choice(name="on", value="on"),
    app_commands.Choice(name="off", value="off")
])
async def voicetracker_cmd(interaction: discord.Interaction, action: str):
    if not await has_permission(interaction, "main_moderator"):
        is_owner = interaction.user.id == interaction.guild.owner_id
        if not is_owner:
            await interaction.response.send_message(
                embed=create_permission_denied_embed("Owner / Main Moderator"),
                ephemeral=True
            )
            return
    
    if db is None:
        await interaction.response.send_message(
            embed=create_error_embed("Database Error", "Database not connected!"),
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    enabled = action == "on"
    
    await db.servers.update_one(
        {'guild_id': guild_id},
        {'$set': {'voice_tracker_enabled': enabled}},
        upsert=True
    )
    
    if enabled:
        embed = discord.Embed(
            title="🎧 **VOICE TRACKER ENABLED**",
            description=f"{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.SUCCESS,
            timestamp=datetime.now()
        )
        embed.add_field(
            name="◆ Status",
            value="Voice time tracking is now **ACTIVE**",
            inline=False
        )
        embed.add_field(
            name="◆ Features",
            value="• Track total voice time per user\n• Milestone achievements (24h, 50h, 100h+)\n• Leaderboards with `/voicetime leaderboard`",
            inline=False
        )
        status_text = "enabled"
    else:
        embed = discord.Embed(
            title="🎧 **VOICE TRACKER DISABLED**",
            description=f"{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.WARNING,
            timestamp=datetime.now()
        )
        embed.add_field(
            name="◆ Status",
            value="Voice time tracking is now **PAUSED**",
            inline=False
        )
        embed.add_field(
            name="◆ Note",
            value="All existing data is preserved. Re-enable anytime with `/voicetracker on`",
            inline=False
        )
        status_text = "disabled"
    
    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)
    
    await log_action(interaction.guild.id, "voice", f"🎧 [VOICE TRACKER] {status_text.upper()} by {interaction.user}")

@app_commands.command(name="voicetime", description="🎧 Check voice channel time stats")
@app_commands.describe(
    action="What to view",
    user="User to check (for 'user' action)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="me", value="me"),
    app_commands.Choice(name="user", value="user"),
    app_commands.Choice(name="leaderboard", value="leaderboard")
])
async def voicetime_cmd(interaction: discord.Interaction, action: str = "me", user: discord.Member = None):
    if db is None:
        await interaction.response.send_message(
            embed=create_error_embed("Database Error", "Database not connected!"),
            ephemeral=True
        )
        return
    
    guild_id = str(interaction.guild.id)
    
    if not await is_voice_tracker_enabled(guild_id):
        await interaction.response.send_message(
            embed=create_error_embed("Voice Tracker Disabled", "Voice tracking is not enabled on this server.\nAsk an admin to enable it with `/voicetracker on`"),
            ephemeral=True
        )
        return
    
    if action == "me":
        target = interaction.user
    elif action == "user":
        if user is None:
            await interaction.response.send_message(
                embed=create_error_embed("Missing User", "Please specify a user with the `user` parameter."),
                ephemeral=True
            )
            return
        target = user
    elif action == "leaderboard":
        await show_leaderboard(interaction)
        return
    else:
        target = interaction.user
    
    voice_data = await get_voice_data(guild_id, str(target.id))
    total_seconds = voice_data.get('total_seconds', 0)
    last_milestone = voice_data.get('last_milestone', 0)
    
    session_key = get_session_key(guild_id, str(target.id))
    current_session = 0
    if session_key in voice_sessions:
        current_session = int((datetime.utcnow() - voice_sessions[session_key]).total_seconds())
    
    display_total = total_seconds + current_session
    total_hours = display_total / 3600
    
    next_milestone = get_next_milestone(total_hours)
    hours_to_next = next_milestone - total_hours
    progress_percent = min(100, (total_hours / next_milestone) * 100) if next_milestone > 0 else 100
    
    progress_bar_length = 20
    filled = int((progress_percent / 100) * progress_bar_length)
    progress_bar = "█" * filled + "░" * (progress_bar_length - filled)
    
    all_users_raw = await db.voice_tracker.find({'guild_id': guild_id}).to_list(None)
    ranked_users = []
    for u in all_users_raw:
        u_total = u.get('total_seconds', 0)
        u_session_key = get_session_key(guild_id, u['user_id'])
        if u_session_key in voice_sessions:
            u_total += int((datetime.utcnow() - voice_sessions[u_session_key]).total_seconds())
        ranked_users.append({'user_id': u['user_id'], 'total': u_total})
    ranked_users.sort(key=lambda x: x['total'], reverse=True)
    
    rank = 1
    for i, u in enumerate(ranked_users):
        if u['user_id'] == str(target.id):
            rank = i + 1
            break
    
    embed = discord.Embed(
        title=f"🎧 **VOICE TIME STATS**",
        description=f"{VisualElements.CIRCUIT_LINE}",
        color=BrandColors.PRIMARY,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="◆ User",
        value=f"{target.mention}",
        inline=True
    )
    embed.add_field(
        name="◆ Server Rank",
        value=f"#{rank}",
        inline=True
    )
    embed.add_field(
        name="◆ Total Voice Time",
        value=f"**{format_duration(display_total)}**",
        inline=False
    )
    
    if current_session > 0:
        embed.add_field(
            name="◆ Current Session",
            value=f"{format_duration(current_session)} (live)",
            inline=True
        )
    
    embed.add_field(
        name=f"◆ Progress to {next_milestone}h",
        value=f"`{progress_bar}` {progress_percent:.1f}%\n{hours_to_next:.1f}h remaining",
        inline=False
    )
    
    if last_milestone > 0:
        embed.add_field(
            name="◆ Last Milestone",
            value=f"**{last_milestone}h** achieved",
            inline=True
        )
    
    embed.set_thumbnail(url=target.display_avatar.url if target.display_avatar else None)
    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

async def show_leaderboard(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    all_users_raw = await db.voice_tracker.find({'guild_id': guild_id}).to_list(None)
    
    if not all_users_raw:
        await interaction.response.send_message(
            embed=create_info_embed("Voice Leaderboard", "No voice time data yet! Start chatting in voice channels."),
            ephemeral=True
        )
        return
    
    leaderboard_data = []
    for user_data in all_users_raw:
        user_id = user_data['user_id']
        total_seconds = user_data.get('total_seconds', 0)
        
        session_key = get_session_key(guild_id, user_id)
        if session_key in voice_sessions:
            current = int((datetime.utcnow() - voice_sessions[session_key]).total_seconds())
            total_seconds += current
        
        leaderboard_data.append({
            'user_id': user_id,
            'total_seconds': total_seconds
        })
    
    leaderboard_data.sort(key=lambda x: x['total_seconds'], reverse=True)
    
    embed = discord.Embed(
        title="🎧 **VOICE TIME LEADERBOARD**",
        description=f"Top 10 users by voice channel time\n{VisualElements.CIRCUIT_LINE}",
        color=BrandColors.PRIMARY,
        timestamp=datetime.now()
    )
    
    medals = ["🥇", "🥈", "🥉"]
    leaderboard_text = ""
    
    for i, entry in enumerate(leaderboard_data[:10]):
        user_id = entry['user_id']
        total_seconds = entry['total_seconds']
        
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        
        if i < 3:
            rank_display = medals[i]
        else:
            rank_display = f"`#{i+1}`"
        
        leaderboard_text += f"{rank_display} **{name}** — {format_duration(total_seconds)}\n"
    
    embed.add_field(name="◆ Rankings", value=leaderboard_text, inline=False)
    
    user_id = str(interaction.user.id)
    user_total = 0
    user_rank = len(leaderboard_data) + 1
    
    for i, entry in enumerate(leaderboard_data):
        if entry['user_id'] == user_id:
            user_rank = i + 1
            user_total = entry['total_seconds']
            break
    
    embed.add_field(
        name="◆ Your Position",
        value=f"Rank **#{user_rank}** with **{format_duration(user_total)}**",
        inline=False
    )
    
    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

_setup_done = False

def setup(bot_instance, db_instance, has_permission_func, log_action_func):
    global bot, db, has_permission, log_action, _setup_done
    
    if _setup_done:
        return
    
    bot = bot_instance
    db = db_instance
    has_permission = has_permission_func
    log_action = log_action_func
    
    existing_commands = [cmd.name for cmd in bot.tree.get_commands()]
    
    if "voicetracker" not in existing_commands:
        bot.tree.add_command(voicetracker_cmd)
    if "voicetime" not in existing_commands:
        bot.tree.add_command(voicetime_cmd)
    
    _setup_done = True
    print("✅ Voice Tracker module loaded")
