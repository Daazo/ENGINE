import discord
from discord.ext import commands
from discord import app_commands
import time
import random
from main import bot, db, has_permission, log_action, get_server_data, update_server_data

# Karma cooldown tracking (user_id -> {target_user_id: last_time})
karma_cooldowns = {}

# Motivational quotes for level ups
KARMA_QUOTES = [
    "Kindness is a language which the deaf can hear and the blind can see! 💫",
    "Your positive energy is contagious! Keep spreading good vibes! ✨",
    "Great things happen when good people work together! 🌟",
    "You're making this community a better place, one act at a time! 🌈",
    "Your helpfulness doesn't go unnoticed - you're amazing! 🚀",
    "Community champions like you make all the difference! 🏆",
    "Your karma reflects your beautiful soul! Keep shining! ⭐",
    "Positive vibes attract positive lives - and you're proof! 🌻",
    "You're not just earning karma, you're earning hearts! 💕",
    "The world needs more people like you! Keep being awesome! 🌍"
]

# Define karma levels and their corresponding milestones, titles, and colors
KARMA_LEVELS = [
    {"milestone": 0, "title": "🌱 Community Sprout", "color": 0x8bc34a},
    {"milestone": 50, "title": "🌿 Sapling", "color": 0x6fbf7a},
    {"milestone": 100, "title": "🌳 Growing Tree", "color": 0x5cb85c},
    {"milestone": 200, "title": "🌟 Rising Star", "color": 0xffd700},
    {"milestone": 350, "title": "⭐ Shining Star", "color": 0xffe066},
    {"milestone": 500, "title": "💎 Community Gem", "color": 0x50c878},
    {"milestone": 750, "title": "✨ Respected Member", "color": 0x4CAF50},
    {"milestone": 1000, "title": "🎖️ Community Pillar", "color": 0x3e8e41},
    {"milestone": 1500, "title": "🏆 Community Hero", "color": 0x2e7d32},
    {"milestone": 2000, "title": "👑 Community Legend", "color": 0x1b5e20},
    {"milestone": 2500, "title": "🔮 Elder Sage", "color": 0x795548},
    {"milestone": 3000, "title": "🌌 Cosmic Contributor", "color": 0x673ab7},
    {"milestone": 3500, "title": "🚀 Galactic Guardian", "color": 0x3f51b5},
    {"milestone": 4000, "title": "🌠 Celestial Champion", "color": 0x2196f3},
    {"milestone": 4500, "title": "✨ Transcendent Master", "color": 0xff4081} # Max level
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
            color=0xe74c3c
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
            color=0xf39c12
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
        title="✨ Karma Given!",
        description=f"**{interaction.user.mention}** ({role_text}) gave **+{karma_points} karma** to **{user.mention}**{reason_text}!",
        color=0x43b581
    )
    embed.add_field(name="New Karma Total", value=f"{new_karma} points", inline=True)
    embed.set_footer(text="🌟 Keep spreading positivity!", icon_url=bot.user.display_avatar.url)

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
        progress_text = "🎆 **MAXIMUM LEVEL ACHIEVED!** 🎆\n*You are a Transcendent Master!*"

    # Use current level color or default
    embed_color = current_level["color"] if current_level else 0x95a5a6
    level_title = current_level["title"] if current_level else "🌱 New Member"

    embed = discord.Embed(
        title=f"✨ {target_user.display_name}'s Karma Profile",
        description=f"**Current Level:** {level_title}",
        color=embed_color
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.add_field(name="🌟 Karma Points", value=f"**{karma}** points", inline=True)
    embed.add_field(name="🏆 Server Rank", value=f"#{rank}", inline=True)

    if next_level:
        embed.add_field(name="📊 Progress to Next Level", value=progress_text, inline=False)
    else:
        embed.add_field(name="🎆 Status", value="**TRANSCENDENT MASTER** - Maximum Level!", inline=False)

    embed.set_footer(text="🌟 Karma reflects your positive impact on our community!", icon_url=bot.user.display_avatar.url)

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
        progress_text = "🎆 **MAXIMUM LEVEL ACHIEVED!** 🎆\n*You are a Transcendent Master!*"

    # Use current level color or default
    embed_color = current_level["color"] if current_level else 0x95a5a6
    level_title = current_level["title"] if current_level else "🌱 New Member"

    embed = discord.Embed(
        title=f"✨ {target_user.display_name}'s Karma Profile",
        description=f"**Current Level:** {level_title}",
        color=embed_color
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.add_field(name="🌟 Karma Points", value=f"**{karma}** points", inline=True)
    embed.add_field(name="🏆 Server Rank", value=f"#{rank}", inline=True)

    if next_level:
        embed.add_field(name="📊 Progress to Next Level", value=progress_text, inline=False)
    else:
        embed.add_field(name="🎆 Status", value="**TRANSCENDENT MASTER** - Maximum Level!", inline=False)

    embed.set_footer(text="🌟 Karma reflects your positive impact on our community!", icon_url=bot.user.display_avatar.url)

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
            color=0xe74c3c
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
        title="🏆 **Community Karma Leaderboard** ✨",
        description=leaderboard_text,
        color=0xf39c12
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
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
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
                title="✅ User Karma Reset",
                description=f"**User:** {user.mention}\n**Action:** Karma data has been reset\n**Reset by:** {interaction.user.mention}",
                color=0x43b581
            )
        else:
            embed = discord.Embed(
                title="❌ User Not Found",
                description=f"{user.mention} has no karma data to reset.",
                color=0xe74c3c
            )

    elif scope == "server":
        result = await db.karma.delete_many({'guild_id': str(interaction.guild.id)})

        embed = discord.Embed(
            title="✅ Server Karma Reset",
            description=f"**Action:** All karma data has been reset\n**Users affected:** {result.deleted_count}\n**Reset by:** {interaction.user.mention}",
            color=0x43b581
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
                title="🎉 **KARMA MILESTONE CELEBRATION!** ✨🎊",
                description=f"🌟 **{user.mention} just reached {karma} karma points!** 🚀\n\n💫 **Level:** {current_level['title']}!\n\n🎯 *{quote}*",
                color=current_level["color"] if current_level else 0xf39c12
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
            embed.set_footer(text="🌴 Spreading positivity in our Kerala-style community! 🌟", icon_url=bot.user.display_avatar.url)

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