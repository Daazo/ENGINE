import discord
from discord.ext import commands
from discord import app_commands
import time
import random
from main import bot, db, has_permission, log_action, get_server_data

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

    # Check for level up (every 5 karma) - FIXED: Check if milestone reached
    old_milestone = (old_karma // 5) * 5
    new_milestone = (new_karma // 5) * 5

    if new_milestone > old_milestone and new_karma >= 5:
        await send_karma_levelup(interaction.guild, user, new_karma)

    await log_action(interaction.guild.id, "karma", f"✨ [KARMA] {interaction.user} gave +{karma_points} karma to {user}")

@bot.tree.command(name="karma", description="Check someone's karma points and server rank")
@app_commands.describe(user="User to check karma for (optional)")
async def check_karma(interaction: discord.Interaction, user: discord.Member = None):
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

    # Calculate progress to next milestone
    next_milestone = ((karma // 5) + 1) * 5
    progress = karma % 5
    progress_bar = "█" * progress + "░" * (5 - progress)

    embed = discord.Embed(
        title=f"✨ {target_user.display_name}'s Karma",
        color=0x3498db
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.add_field(name="🌟 Karma Points", value=f"**{karma}** points", inline=True)
    embed.add_field(name="🏆 Server Rank", value=f"#{rank}", inline=True)
    embed.add_field(name="📊 Progress to Next Milestone", value=f"`{progress_bar}` {progress}/5\n*Next milestone: {next_milestone} karma*", inline=False)
    embed.set_footer(text="🌟 Karma reflects positive contributions!", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mykarma", description="Check your own karma points quickly")
async def my_karma(interaction: discord.Interaction):
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

    # Calculate progress to next milestone
    next_milestone = ((karma // 5) + 1) * 5
    progress = karma % 5
    progress_bar = "█" * progress + "░" * (5 - progress)

    embed = discord.Embed(
        title=f"✨ {target_user.display_name}'s Karma",
        color=0x3498db
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.add_field(name="🌟 Karma Points", value=f"**{karma}** points", inline=True)
    embed.add_field(name="🏆 Server Rank", value=f"#{rank}", inline=True)
    embed.add_field(name="📊 Progress to Next Milestone", value=f"`{progress_bar}` {progress}/5\n*Next milestone: {next_milestone} karma*", inline=False)
    embed.set_footer(text="🌟 Karma reflects positive contributions!", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="karmaboard", description="Show server karma leaderboard with top 10 contributors")
async def karma_leaderboard(interaction: discord.Interaction):
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

            # Medal emojis for top 3
            if i == 0:
                medal = "🥇"
            elif i == 1:
                medal = "🥈"
            elif i == 2:
                medal = "🥉"
            else:
                medal = f"**{i+1}.**"

            leaderboard_text += f"{medal} **{user.display_name}** - {karma} karma ✨\n"

    embed = discord.Embed(
        title="🏆 **Community Karma Leaderboard** ✨",
        description=leaderboard_text,
        color=0xf39c12
    )
    embed.set_footer(text="🌟 These members are making our community amazing!", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setkarmachannel", description="Set karma announcement channel (Main Moderator only)")
@app_commands.describe(channel="Channel for karma level-up announcements")
async def set_karma_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    from main import update_server_data
    await update_server_data(interaction.guild.id, {'karma_channel': str(channel.id)})

    embed = discord.Embed(
        title="✅ Karma Channel Set",
        description=f"**Karma announcements will be sent to:** {channel.mention}",
        color=0x43b581
    )
    embed.set_footer(text="🌟 Karma system configured!", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

    await log_action(interaction.guild.id, "setup", f"✨ [KARMA SETUP] Karma channel set to {channel} by {interaction.user}")

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
    karma_channel_id = server_data.get('karma_channel')

    if karma_channel_id:
        karma_channel = bot.get_channel(int(karma_channel_id))
        if karma_channel:
            # Get random quote
            quote = random.choice(KARMA_QUOTES)

            # Calculate milestone
            milestone = (karma // 5) * 5
            next_milestone = milestone + 5

            # Create progress bar for next milestone
            progress = karma % 5
            progress_bar = "█" * progress + "░" * (5 - progress)

            # Select celebration GIF based on milestone level
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
                description=f"🌟 **{user.mention} just reached {karma} karma points!** 🚀\n\n💫 **Milestone:** {milestone} karma achieved!\n\n🎯 *{quote}*",
                color=0xf39c12
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(
                name="📊 Progress to Next Milestone",
                value=f"`{progress_bar}` {progress}/5\n🎯 *Next celebration at: {next_milestone} karma*",
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
            await karma_channel.send(f"🎉 **KARMA CELEBRATION TIME!** 🎊", embed=embed)

            print(f"✨ [KARMA MILESTONE] {user} reached {karma} karma in {guild.name}")
    else:
        print(f"⚠️ [KARMA] No karma channel set for {guild.name}")

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
        old_milestone = (old_karma // 5) * 5
        new_milestone = (new_karma // 5) * 5

        if new_milestone > old_milestone and new_karma >= 5:
            await send_karma_levelup(reaction.message.guild, reaction.message.author, new_karma)