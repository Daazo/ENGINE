import discord
from discord.ext import commands
from discord import app_commands
import time
import random
from main import bot
from brand_config import create_permission_denied_embed, create_owner_only_embed,  BOT_FOOTER, BrandColors
from main import db, has_permission, log_action, get_server_data, update_server_data

# Karma cooldown tracking (user_id -> {target_user_id: last_time})
karma_cooldowns = {}

# Quantum system messages for level advancement
KARMA_QUOTES = [
    "Quantum signature amplified — neural network recognizes your contribution ⚡",
    "Holographic matrix updated — positive energy indexed to core database 💠",
    "System protocol activated — collaborative patterns detected and logged ◆",
    "Core enhancement detected — community optimization protocols engaged ⬡",
    "Neural pathway strengthened — assistance subroutines successfully executed ▲",
    "Quantum achievement registered — leadership algorithms acknowledged 🟣",
    "Holographic imprint established — contribution permanently archived ✦",
    "Matrix resonance detected — positive influence propagated across network ◇",
    "System elevation confirmed — karma matrix synchronization complete ⚡",
    "Neural core expansion — advanced contributor status recognized 💠"
]

# Define karma levels with quantum purple gradient theme - using BrandColors
from brand_config import create_permission_denied_embed, create_owner_only_embed,  BrandColors

KARMA_LEVELS = [
    {"milestone": 0, "title": "◇ Quantum Initiate", "color": BrandColors.GRADIENT_1},
    {"milestone": 50, "title": "⬡ Data Node", "color": BrandColors.GRADIENT_2},
    {"milestone": 100, "title": "◆ Circuit Runner", "color": BrandColors.GRADIENT_3},
    {"milestone": 200, "title": "⚡ Voltage Keeper", "color": BrandColors.GRADIENT_4},
    {"milestone": 350, "title": "💠 Core Fragment", "color": BrandColors.GRADIENT_5},
    {"milestone": 500, "title": "🟣 Neon Sentinel", "color": BrandColors.GRADIENT_6},
    {"milestone": 750, "title": "✦ Hologram Architect", "color": BrandColors.GRADIENT_7},
    {"milestone": 1000, "title": "▲ System Pillar", "color": BrandColors.GRADIENT_5},
    {"milestone": 1500, "title": "◆ Quantum Guardian", "color": BrandColors.GRADIENT_3},
    {"milestone": 2000, "title": "⬢ Neural Legend", "color": BrandColors.GRADIENT_1},
    {"milestone": 2500, "title": "💎 Matrix Sage", "color": BrandColors.GRADIENT_8},
    {"milestone": 3000, "title": "🌌 Cosmic Operator", "color": BrandColors.GRADIENT_9},
    {"milestone": 3500, "title": "⚡ Plasma Champion", "color": BrandColors.GRADIENT_2},
    {"milestone": 4000, "title": "💠 Quantum Sovereign", "color": BrandColors.GRADIENT_5},
    {"milestone": 4500, "title": "✨ Holographic Master", "color": BrandColors.GRADIENT_7}
]

def get_karma_level_info(karma):
    """Determines the current and next karma level based on karma points."""
    current_level = None
    next_level = None

    # Sort levels by milestone in descending order to find the current level first
    sorted_levels = sorted(KARMA_LEVELS, key=lambda x: x['milestone'], reverse=True)

    for i, level in enumerate(sorted_levels):
        if karma >= level["milestone"]:
            current_level = level
            # If there's a next level in the sorted list (meaning a higher milestone), assign it
            if i > 0:
                next_level = sorted_levels[i-1]
            break # Found the highest applicable level

    # If no level found (karma is 0 or less), default to the lowest level
    if current_level is None:
        current_level = KARMA_LEVELS[0]
        next_level = KARMA_LEVELS[1] if len(KARMA_LEVELS) > 1 else None
    elif next_level is None and current_level["title"] == "✨ Transcendent Master":
        # If the current level is the max, there is no next level
        pass

    return current_level, next_level


@bot.tree.command(name="givekarma", description="Give karma points to another user for their positive contribution")
@app_commands.describe(
    user="User to give karma to",
    amount="Amount of karma to give (Server Owner: unlimited, Main Mod: 1-2, Junior Mod: can't give)",
    reason="Reason for giving karma (optional but recommended)"
)
async def give_karma(interaction: discord.Interaction, user: discord.Member, amount: int = None, reason: str = None):
    # Prevent self-karma
    if user.id == interaction.user.id:
        embed = discord.Embed(
            title="❌ Cannot Give Self-Karma",
            description="You cannot give karma to yourself! Ask others to appreciate your contributions instead.",
            color=BrandColors.DANGER
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Check permissions and set karma limits
    is_owner = interaction.user.id == interaction.guild.owner_id
    is_main_mod = await has_permission(interaction, "main_moderator")
    is_junior_mod = await has_permission(interaction, "junior_moderator")

    # Determine karma amount based on role
    if is_owner:
        # Server owner can give unlimited karma (if amount not specified, give 1-2)
        if amount is None:
            karma_points = random.randint(1, 2)
        else:
            if amount < 1 or amount > 100:  # Reasonable limit even for owner
                await interaction.response.send_message("❌ Please specify karma amount between 1-100!", ephemeral=True)
                return
            karma_points = amount
    elif is_main_mod:
        # Main moderators can give 1-2 karma only
        if amount is not None and amount not in [1, 2]:
            await interaction.response.send_message("❌ Main Moderators can only give 1-2 karma points!", ephemeral=True)
            return
        karma_points = amount if amount in [1, 2] else random.randint(1, 2)
    else:
        # Regular members (including junior mods) can give 1-2 karma only
        if amount is not None and amount not in [1, 2]:
            await interaction.response.send_message("❌ You can only give 1-2 karma points!", ephemeral=True)
            return
        karma_points = amount if amount in [1, 2] else random.randint(1, 2)

    # Check cooldown (1 minute for main mods, 3 minutes for others)
    current_time = time.time()
    giver_id = interaction.user.id
    receiver_id = user.id

    if giver_id not in karma_cooldowns:
        karma_cooldowns[giver_id] = {}

    last_given = karma_cooldowns[giver_id].get(receiver_id, 0)
    cooldown_time = 60 if is_main_mod else 180  # 1 minute for main mods, 3 minutes for others

    # Server owner has no cooldown
    if not is_owner and current_time - last_given < cooldown_time:
        remaining = int(cooldown_time - (current_time - last_given))
        minutes = remaining // 60
        seconds = remaining % 60

        embed = discord.Embed(
            title="⏰ Karma Cooldown",
            description=f"You can give karma to {user.mention} again in **{minutes}m {seconds}s**",
            color=BrandColors.WARNING
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Update cooldown (except for owner)
    if not is_owner:
        karma_cooldowns[giver_id][receiver_id] = current_time

    # Add karma to database
    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return

    # Get or create user karma data
    user_data = await db.karma.find_one({'user_id': str(receiver_id), 'guild_id': str(interaction.guild.id)})
    if not user_data:
        user_data = {'user_id': str(receiver_id), 'guild_id': str(interaction.guild.id), 'karma': 0}

    old_karma = user_data.get('karma', 0)
    new_karma = old_karma + karma_points
    user_data['karma'] = new_karma

    await db.karma.update_one(
        {'user_id': str(receiver_id), 'guild_id': str(interaction.guild.id)},
        {'$set': user_data},
        upsert=True
    )

    # Create response embed
    reason_text = f" for **{reason}**" if reason else ""
    role_text = "👑 Server Owner" if is_owner else "🔴 Main Moderator" if is_main_mod else "🟡 Junior Moderator" if is_junior_mod else "🟢 Member"

    embed = discord.Embed(
        title="⚡ **Quantum Karma Transferred**",
        description=f"**{interaction.user.mention}** ({role_text}) transmitted **+{karma_points} karma** to **{user.mention}**{reason_text}\n\n*◆ Neural network updated*",
        color=BrandColors.PRIMARY
    )
    embed.add_field(name="◆ New Karma Index", value=f"{new_karma} points", inline=True)
    embed.set_footer(text="💠 Quantum recognition protocol active", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

    # Check for level up (milestones are now defined in KARMA_LEVELS)
    old_level_info, _ = get_karma_level_info(old_karma)
    new_level_info, _ = get_karma_level_info(new_karma)

    if new_level_info and old_level_info and new_level_info["milestone"] > old_level_info["milestone"]:
        await send_karma_levelup(interaction.guild, user, new_karma)

    await log_action(interaction.guild.id, "karma", f"✨ [KARMA] {interaction.user} gave +{karma_points} karma to {user}")

@bot.tree.command(name="karma", description="Check someone's karma points and server rank")
@app_commands.describe(user="User to check karma for (optional)")
async def check_karma(interaction: discord.Interaction, user: discord.Member = None):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    karma_channels = server_data.get('karma_channels', {})
    karma_zone_channel_id = karma_channels.get('karma_zone_channel')
    
    if karma_zone_channel_id and str(interaction.channel.id) != karma_zone_channel_id:
        karma_zone_channel = bot.get_channel(int(karma_zone_channel_id))
        channel_mention = karma_zone_channel.mention if karma_zone_channel else "#karma-zone"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return
    
    target_user = user or interaction.user

    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return

    user_data = await db.karma.find_one({'user_id': str(target_user.id), 'guild_id': str(interaction.guild.id)})

    if not user_data:
        karma = 0
    else:
        karma = user_data.get('karma', 0)

    # Get user rank
    users_sorted = await db.karma.find({'guild_id': str(interaction.guild.id)}).sort('karma', -1).to_list(None)
    rank = next((i + 1 for i, u in enumerate(users_sorted) if u['user_id'] == str(target_user.id)), len(users_sorted) + 1)

    # Get current and next level info
    current_level, next_level = get_karma_level_info(karma)

    # Calculate progress to next level
    if next_level:
        next_milestone = next_level["milestone"]
        if current_level:
            progress = karma - current_level["milestone"]
            max_progress = next_milestone - current_level["milestone"]
        else:
            progress = karma
            max_progress = next_milestone

        progress_segments = 15  # More detailed progress bar
        filled_segments = min(progress_segments, int((progress / max_progress) * progress_segments))
        progress_bar = "█" * filled_segments + "░" * (progress_segments - filled_segments)
        progress_text = f"`{progress_bar}` {progress}/{max_progress}\n*Next level: {next_level['title']} at {next_milestone} karma*"
    else:
        progress_text = "⚡ **QUANTUM MAXIMUM ACHIEVED** ⚡\n*Holographic Master — peak neural resonance!*"

    # Use current level color or default
    embed_color = current_level["color"] if current_level else BrandColors.NEUTRAL
    level_title = current_level["title"] if current_level else "◇ Quantum Initiate"

    embed = discord.Embed(
        title=f"💠 {target_user.display_name}'s Quantum Profile",
        description=f"**Neural Rank:** {level_title}",
        color=embed_color
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.add_field(name="⚡ Karma Index", value=f"**{karma}** points", inline=True)
    embed.add_field(name="🏆 Server Position", value=f"#{rank}", inline=True)

    if next_level:
        embed.add_field(name="◆ Quantum Advancement", value=progress_text, inline=False)
    else:
        embed.add_field(name="⚡ Status", value="**HOLOGRAPHIC MASTER** — Maximum quantum level achieved!", inline=False)

    embed.set_footer(text="💠 Karma matrix reflects your quantum contribution index", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mykarma", description="Check your own karma points quickly")
async def my_karma(interaction: discord.Interaction):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    karma_channels = server_data.get('karma_channels', {})
    karma_zone_channel_id = karma_channels.get('karma_zone_channel')
    
    if karma_zone_channel_id and str(interaction.channel.id) != karma_zone_channel_id:
        karma_zone_channel = bot.get_channel(int(karma_zone_channel_id))
        channel_mention = karma_zone_channel.mention if karma_zone_channel else "#karma-zone"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return
    
    target_user = interaction.user

    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return

    user_data = await db.karma.find_one({'user_id': str(target_user.id), 'guild_id': str(interaction.guild.id)})

    if not user_data:
        karma = 0
    else:
        karma = user_data.get('karma', 0)

    # Get user rank
    users_sorted = await db.karma.find({'guild_id': str(interaction.guild.id)}).sort('karma', -1).to_list(None)
    rank = next((i + 1 for i, u in enumerate(users_sorted) if u['user_id'] == str(target_user.id)), len(users_sorted) + 1)

    # Get current and next level info
    current_level, next_level = get_karma_level_info(karma)

    # Calculate progress to next level
    if next_level:
        next_milestone = next_level["milestone"]
        if current_level:
            progress = karma - current_level["milestone"]
            max_progress = next_milestone - current_level["milestone"]
        else:
            progress = karma
            max_progress = next_milestone

        progress_segments = 15  # More detailed progress bar
        filled_segments = min(progress_segments, int((progress / max_progress) * progress_segments))
        progress_bar = "█" * filled_segments + "░" * (progress_segments - filled_segments)
        progress_text = f"`{progress_bar}` {progress}/{max_progress}\n*Next level: {next_level['title']} at {next_milestone} karma*"
    else:
        progress_text = "⚡ **QUANTUM MAXIMUM ACHIEVED** ⚡\n*Holographic Master — peak neural resonance!*"

    # Use current level color or default
    embed_color = current_level["color"] if current_level else BrandColors.NEUTRAL
    level_title = current_level["title"] if current_level else "◇ Quantum Initiate"

    embed = discord.Embed(
        title=f"💠 {target_user.display_name}'s Quantum Profile",
        description=f"**Neural Rank:** {level_title}",
        color=embed_color
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.add_field(name="⚡ Karma Index", value=f"**{karma}** points", inline=True)
    embed.add_field(name="🏆 Server Position", value=f"#{rank}", inline=True)

    if next_level:
        embed.add_field(name="◆ Quantum Advancement", value=progress_text, inline=False)
    else:
        embed.add_field(name="⚡ Status", value="**HOLOGRAPHIC MASTER** — Maximum quantum level achieved!", inline=False)

    embed.set_footer(text="💠 Karma matrix reflects your quantum contribution index", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="karmaboard", description="Show server karma leaderboard with top 10 contributors")
async def karma_leaderboard(interaction: discord.Interaction):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    karma_channels = server_data.get('karma_channels', {})
    karma_zone_channel_id = karma_channels.get('karma_zone_channel')
    
    if karma_zone_channel_id and str(interaction.channel.id) != karma_zone_channel_id:
        karma_zone_channel = bot.get_channel(int(karma_zone_channel_id))
        channel_mention = karma_zone_channel.mention if karma_zone_channel else "#karma-zone"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return
    
    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return

    users_sorted = await db.karma.find({'guild_id': str(interaction.guild.id)}).sort('karma', -1).limit(10).to_list(None)

    if not users_sorted:
        embed = discord.Embed(
            title="🏆 Karma Leaderboard",
            description="No karma has been given yet! Start appreciating community members!",
            color=BrandColors.DANGER
        )
        embed.set_footer(text="🌟 Be the first to spread positivity!", icon_url=bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
        return

    # Build leaderboard text
    leaderboard_text = ""
    for i, user_data in enumerate(users_sorted):
        user = bot.get_user(int(user_data['user_id']))
        if user:
            karma = user_data.get('karma', 0)

            # Get level info for the user
            current_level, _ = get_karma_level_info(karma)
            level_title = current_level["title"] if current_level else "🌱 New Member"

            # Medal emojis for top 3
            if i == 0:
                medal = "🥇"
            elif i == 1:
                medal = "🥈"
            elif i == 2:
                medal = "🥉"
            else:
                medal = f"**{i+1}.**"

            leaderboard_text += f"{medal} **{user.display_name}** ({level_title}) - {karma} karma ✨\n"

    embed = discord.Embed(
        title="💠 **Community Karma Leaderboard**",
        description=leaderboard_text,
        color=BrandColors.PRIMARY
    )
    embed.set_footer(text="🌟 These members are making our community amazing!", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)




@bot.tree.command(name="resetkarma", description="Reset karma data for user or entire server (Main Moderator only)")
@app_commands.describe(
    scope="Reset scope",
    user="User to reset (if scope is user)"
)
@app_commands.choices(scope=[
    app_commands.Choice(name="user", value="user"),
    app_commands.Choice(name="server", value="server")
])
async def reset_karma(interaction: discord.Interaction, scope: str, user: discord.Member = None):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True, ephemeral=True)
        return

    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return

    if scope == "user":
        if not user:
            await interaction.response.send_message("❌ Please specify a user to reset!", ephemeral=True)
            return

        result = await db.karma.delete_one({'user_id': str(user.id), 'guild_id': str(interaction.guild.id)})

        if result.deleted_count > 0:
            embed = discord.Embed(
                title="⚡ **User Karma Reset**",
                description=f"**◆ User:** {user.mention}\n**◆ Action:** Karma data has been reset\n**◆ Reset by:** {interaction.user.mention}",
                color=BrandColors.PRIMARY
            )
        else:
            embed = discord.Embed(
                title="❌ User Not Found",
                description=f"{user.mention} has no karma data to reset.",
                color=BrandColors.DANGER
            )

    elif scope == "server":
        result = await db.karma.delete_many({'guild_id': str(interaction.guild.id)})

        embed = discord.Embed(
            title="⚡ **Server Karma Reset**",
            description=f"**◆ Action:** All karma data has been reset\n**◆ Users affected:** {result.deleted_count}\n**◆ Reset by:** {interaction.user.mention}",
            color=BrandColors.PRIMARY
        )

    embed.set_footer(text="🌟 Fresh start for karma system!", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

    await log_action(interaction.guild.id, "moderation", f"🔄 [KARMA RESET] {scope} reset by {interaction.user}")

async def send_karma_levelup(guild, user, karma):
    """Send karma level-up announcement with animated GIF and motivational quotes"""
    server_data = await get_server_data(guild.id)
    karma_channels = server_data.get('karma_channels', {})
    levelup_channel_id = karma_channels.get('levelup_channel')

    if levelup_channel_id:
        levelup_channel = bot.get_channel(int(levelup_channel_id))
        if levelup_channel:
            # Get random quote
            quote = random.choice(KARMA_QUOTES)

            # Get current and next level info
            current_level, next_level = get_karma_level_info(karma)

            # Create progress bar for next milestone
            if next_level:
                next_milestone = next_level["milestone"]
                if current_level:
                    progress = karma - current_level["milestone"]
                    max_progress = next_milestone - current_level["milestone"]
                else:
                    progress = karma
                    max_progress = next_milestone

                progress_segments = 15
                filled_segments = min(progress_segments, int((progress / max_progress) * progress_segments))
                progress_bar = "█" * filled_segments + "░" * (progress_segments - filled_segments)
                progress_text = f"`{progress_bar}` {progress}/{max_progress}\n*Next level: {next_level['title']} at {next_milestone} karma*"
            else:
                progress_text = "🎆 **MAXIMUM LEVEL ACHIEVED!** 🎆\n*You are a Transcendent Master!*"

            # Select celebration GIF based on milestone level (can be expanded)
            celebration_gifs = [
                "https://media.giphy.com/media/3oz8xAFtqoOUUrsh7W/giphy.gif",  # Confetti
                "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",  # Party
                "https://media.giphy.com/media/g9582DNuQppxC/giphy.gif",      # Celebration
                "https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif",  # Fireworks
                "https://media.giphy.com/media/3o6fJ1BM7R2EBRDnxK/giphy.gif", # Victory
                "https://media.giphy.com/media/l0HlNQ03J5JxX6lva/giphy.gif",  # Achievement
                "https://media.giphy.com/media/3o7absbD7PbTFQa0c8/giphy.gif", # Success
                "https://media.giphy.com/media/3o6ZtaO9BZHcOjmErm/giphy.gif"  # Celebration dance
            ]

            selected_gif = random.choice(celebration_gifs)

            embed = discord.Embed(
                title="⚡ **QUANTUM MILESTONE ACHIEVED!** 💠",
                description=f"**{user.mention} neural index elevated to {karma} karma points!**\n\n**◆ Neural Rank:** {current_level['title']}\n\n*{quote}*",
                color=current_level["color"] if current_level else BrandColors.WARNING
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(
                name="📊 Progress to Next Level",
                value=progress_text,
                inline=False
            )
            embed.add_field(
                name="🏆 Community Impact",
                value=f"✨ This member is making our community amazing!\n🌟 Keep up the positive vibes!",
                inline=False
            )
            embed.set_image(url=selected_gif)
            from brand_config import create_permission_denied_embed, create_owner_only_embed,  BOT_FOOTER
            embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)

            # Send announcement
            await levelup_channel.send(f"🎉 **KARMA CELEBRATION TIME!** 🎊", embed=embed)

            print(f"✨ [KARMA MILESTONE] {user} reached {karma} karma in {guild.name}")
    else:
        print(f"⚠️ [KARMA] No karma level-up channel set for {guild.name}")

# Reaction-based karma system
@bot.event
async def on_reaction_add(reaction, user):
    # Don't give karma for bot reactions or self-reactions
    if user.bot or user.id == reaction.message.author.id:
        return

    # Process both positive and negative karma emojis
    positive_emojis = ['👍', '⭐', '❤️', '🔥', '💯', '✨', '🌟', '💖', '👏', '🙌', '🎉', '🥳', '😍', '🥰', '🏆', '🚀', '🌈', '💎', '👑']
    negative_emojis = ['👎', '💀', '😴', '🤮', '🗿', '😤', '😠', '😡', '🤬', '💔', '🖕', '😵', '🤢', '❌', '⛔', '🚫', '💩', '🤡']

    emoji_str = str(reaction.emoji)
    karma_change = 0

    if emoji_str in positive_emojis:
        karma_change = 1
    elif emoji_str in negative_emojis:
        karma_change = -1
    else:
        return  # Not a karma emoji

    # Don't give karma in DMs
    if not reaction.message.guild:
        return

    # Check cooldown (3 minutes)
    current_time = time.time()
    giver_id = user.id
    receiver_id = reaction.message.author.id

    if giver_id not in karma_cooldowns:
        karma_cooldowns[giver_id] = {}

    last_given = karma_cooldowns[giver_id].get(receiver_id, 0)
    cooldown_time = 180  # 3 minutes

    if current_time - last_given < cooldown_time:
        return

    # Update cooldown
    karma_cooldowns[giver_id][receiver_id] = current_time

    # Update karma
    if db is None:
        return

    user_data = await db.karma.find_one({'user_id': str(receiver_id), 'guild_id': str(reaction.message.guild.id)})
    if not user_data:
        user_data = {'user_id': str(receiver_id), 'guild_id': str(reaction.message.guild.id), 'karma': 0}

    old_karma = user_data.get('karma', 0)
    new_karma = max(0, old_karma + karma_change)  # Don't allow negative karma
    user_data['karma'] = new_karma

    await db.karma.update_one(
        {'user_id': str(receiver_id), 'guild_id': str(reaction.message.guild.id)},
        {'$set': user_data},
        upsert=True
    )

    # Check for level up only on positive karma
    if karma_change > 0:
        old_level_info, _ = get_karma_level_info(old_karma)
        new_level_info, _ = get_karma_level_info(new_karma)

        if new_level_info and old_level_info and new_level_info["milestone"] > old_level_info["milestone"]:
            await send_karma_levelup(reaction.message.guild, reaction.message.author, new_karma)