import discord
from discord.ext import commands
from discord import app_commands
import random
import time
import asyncio
from datetime import datetime, timedelta
from main import bot, db, has_permission, get_server_data, update_server_data, log_action

# Economy constants
DAILY_REWARD_BASE = 50
WEEKLY_REWARD_BASE = 300
WORK_COOLDOWN = 3600  # 1 hour
DAILY_COOLDOWN = 86400  # 24 hours
WEEKLY_COOLDOWN = 604800  # 7 days
KARMA_TO_COINS_RATE = 10  # 1 karma = 10 coins

# Job messages with Kerala/banana theme
WORK_JOBS = [
    {"name": "harvested bananas", "min": 20, "max": 60},
    {"name": "sold banana pancakes", "min": 30, "max": 50},
    {"name": "delivered coconuts", "min": 25, "max": 45},
    {"name": "caught fish in backwaters", "min": 35, "max": 65},
    {"name": "picked mangoes", "min": 15, "max": 40},
    {"name": "guided tourists in Munnar", "min": 40, "max": 80},
    {"name": "sold banana chips", "min": 20, "max": 50},
    {"name": "worked in spice plantation", "min": 45, "max": 75},
    {"name": "ferried passengers in houseboat", "min": 50, "max": 90},
    {"name": "performed Kathakali dance", "min": 60, "max": 100}
]

# Special messages for earning/losing coins
EARNING_MESSAGES = [
    "🍌 You found a golden banana worth {} 🪙!",
    "🐒 A friendly monkey gave you {} 🪙!",
    "🌴 Coconuts fell from a tree and you sold them for {} 🪙!",
    "⛵ You found treasure washed up from the backwaters worth {} 🪙!",
    "🎭 Your Kathakali performance earned {} 🪙!",
    "🏝️ A tourist tipped you {} 🪙 for directions!"
]

LOSING_MESSAGES = [
    "🐒 A naughty monkey stole {} 🪙 from your stash!",
    "🍌 You slipped on a banana peel and dropped {} 🪙!",
    "🌊 A wave washed away {} 🪙 from your pocket!",
    "🐘 An elephant stepped on your coins, crushing {} 🪙!",
    "🌴 You got distracted by beautiful Kerala scenery and lost {} 🪙!"
]

# Trivia questions about Kerala/India
TRIVIA_QUESTIONS = [
    {"question": "What is Kerala known as?", "answer": "god's own country", "reward": 30},
    {"question": "Which is the capital of Kerala?", "answer": "thiruvananthapuram", "reward": 25},
    {"question": "What are the famous backwaters in Kerala called?", "answer": "alappuzha", "reward": 35},
    {"question": "Which spice is Kerala famous for?", "answer": "cardamom", "reward": 20},
    {"question": "What is the traditional dance of Kerala?", "answer": "kathakali", "reward": 40},
    {"question": "Which festival involves boat races in Kerala?", "answer": "onam", "reward": 35},
    {"question": "What is the local language of Kerala?", "answer": "malayalam", "reward": 25}
]

async def get_user_economy(user_id, guild_id):
    """Get user's economy data"""
    if db is None:
        return None

    user_data = await db.economy.find_one({'user_id': str(user_id), 'guild_id': str(guild_id)})
    if not user_data:
        # Create new user with default values
        user_data = {
            'user_id': str(user_id),
            'guild_id': str(guild_id),
            'coins': 100,  # Starting coins
            'bank': 0,
            'last_daily': 0,
            'last_weekly': 0,
            'last_work': 0,
            'daily_streak': 0,
            'total_earned': 100,
            'total_spent': 0
        }
        await db.economy.insert_one(user_data)

    return user_data

async def update_user_economy(user_id, guild_id, data):
    """Update user's economy data"""
    if db is None:
        return

    await db.economy.update_one(
        {'user_id': str(user_id), 'guild_id': str(guild_id)},
        {'$set': data},
        upsert=True
    )

@bot.tree.command(name="balance", description="🪙 Check your Vaazha Coins balance")
@app_commands.describe(user="User to check balance for (optional)")
async def balance(interaction: discord.Interaction, user: discord.Member = None):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    economy_channels = server_data.get('economy_channels', {})
    balance_channel_id = economy_channels.get('balance_channel')

    if balance_channel_id and str(interaction.channel.id) != balance_channel_id:
        balance_channel = bot.get_channel(int(balance_channel_id))
        channel_mention = balance_channel.mention if balance_channel else "#coin-vault"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    target_user = user or interaction.user
    user_data = await get_user_economy(target_user.id, interaction.guild.id)

    if not user_data:
        await interaction.response.send_message("❌ Economy system error!", ephemeral=True)
        return

    coins = user_data.get('coins', 0)
    bank = user_data.get('bank', 0)
    total = coins + bank

    embed = discord.Embed(
        title=f"🪙 {target_user.display_name}'s Vaazha Wallet",
        description=f"*Banking in God's Own Country* 🌴",
        color=0xf1c40f
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.add_field(name="💰 Wallet", value=f"{coins:,} 🪙", inline=True)
    embed.add_field(name="🏦 Bank", value=f"{bank:,} 🪙", inline=True)
    embed.add_field(name="💎 Total Worth", value=f"{total:,} 🪙", inline=True)

    # Add streak info
    streak = user_data.get('daily_streak', 0)
    if streak > 0:
        embed.add_field(name="🔥 Daily Streak", value=f"{streak} days", inline=True)

    embed.set_footer(text="🍌 Vaazha Economy • Use /daily and /weekly for rewards!", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="🌅 Claim your daily Vaazha Coins reward")
async def daily(interaction: discord.Interaction):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    economy_channels = server_data.get('economy_channels', {})
    balance_channel_id = economy_channels.get('balance_channel')

    if balance_channel_id and str(interaction.channel.id) != balance_channel_id:
        balance_channel = bot.get_channel(int(balance_channel_id))
        channel_mention = balance_channel.mention if balance_channel else "#coin-vault"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    user_data = await get_user_economy(interaction.user.id, interaction.guild.id)
    current_time = time.time()
    last_daily = user_data.get('last_daily', 0)

    if current_time - last_daily < DAILY_COOLDOWN:
        remaining = int(DAILY_COOLDOWN - (current_time - last_daily))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60

        embed = discord.Embed(
            title="⏰ Daily Reward Cooldown",
            description=f"Come back in **{hours}h {minutes}m** for your next banana harvest! 🍌",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Calculate streak
    streak = user_data.get('daily_streak', 0)
    if current_time - last_daily <= DAILY_COOLDOWN * 1.5:  # Grace period
        streak += 1
    else:
        streak = 1

    # Calculate reward with streak bonus
    base_reward = DAILY_REWARD_BASE
    streak_bonus = min(streak * 5, 100)  # Max 100 bonus
    total_reward = base_reward + streak_bonus

    # Random bonus chance
    if random.randint(1, 10) == 1:  # 10% chance
        bonus = random.randint(20, 50)
        total_reward += bonus
        bonus_text = f"\n🎊 **Bonus:** +{bonus} 🪙 (Lucky day!)"
    else:
        bonus_text = ""

    # Update user data
    new_coins = user_data.get('coins', 0) + total_reward
    await update_user_economy(interaction.user.id, interaction.guild.id, {
        'coins': new_coins,
        'last_daily': current_time,
        'daily_streak': streak,
        'total_earned': user_data.get('total_earned', 0) + total_reward
    })

    embed = discord.Embed(
        title="🌅 Daily Banana Harvest Complete!",
        description=f"🍌 **Base Reward:** {base_reward} 🪙\n🔥 **Streak Bonus:** +{streak_bonus} 🪙 ({streak} days){bonus_text}\n\n💰 **Total Earned:** {total_reward} 🪙",
        color=0x43b581
    )
    embed.add_field(name="💼 New Balance", value=f"{new_coins:,} 🪙", inline=True)
    embed.add_field(name="🔥 Streak", value=f"{streak} days", inline=True)
    embed.set_footer(text="🌴 Come back tomorrow for more bananas!", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "economy", f"🪙 [DAILY] {interaction.user} claimed {total_reward} coins")

@bot.tree.command(name="weekly", description="🗓️ Claim your weekly Vaazha Coins jackpot")
async def weekly(interaction: discord.Interaction):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    economy_channels = server_data.get('economy_channels', {})
    balance_channel_id = economy_channels.get('balance_channel')

    if balance_channel_id and str(interaction.channel.id) != balance_channel_id:
        balance_channel = bot.get_channel(int(balance_channel_id))
        channel_mention = balance_channel.mention if balance_channel else "#coin-vault"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    user_data = await get_user_economy(interaction.user.id, interaction.guild.id)
    current_time = time.time()
    last_weekly = user_data.get('last_weekly', 0)

    if current_time - last_weekly < WEEKLY_COOLDOWN:
        remaining = int(WEEKLY_COOLDOWN - (current_time - last_weekly))
        days = remaining // 86400
        hours = (remaining % 86400) // 3600

        embed = discord.Embed(
            title="⏰ Weekly Jackpot Cooldown",
            description=f"Next banana festival in **{days}d {hours}h**! 🎭",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Calculate weekly reward
    base_reward = WEEKLY_REWARD_BASE
    streak = user_data.get('daily_streak', 0)
    streak_bonus = min(streak * 10, 200)  # Max 200 bonus

    # Big random bonus for weekly
    if random.randint(1, 5) == 1:  # 20% chance
        mega_bonus = random.randint(100, 300)
        total_reward = base_reward + streak_bonus + mega_bonus
        bonus_text = f"\n🎆 **MEGA BONUS:** +{mega_bonus} 🪙 (Festival special!)"
    else:
        total_reward = base_reward + streak_bonus
        bonus_text = ""

    # Update user data
    new_coins = user_data.get('coins', 0) + total_reward
    await update_user_economy(interaction.user.id, interaction.guild.id, {
        'coins': new_coins,
        'last_weekly': current_time,
        'total_earned': user_data.get('total_earned', 0) + total_reward
    })

    embed = discord.Embed(
        title="🎭 Weekly Banana Festival Jackpot!",
        description=f"🍌 **Festival Reward:** {base_reward} 🪙\n🔥 **Streak Bonus:** +{streak_bonus} 🪙{bonus_text}\n\n💰 **Total Jackpot:** {total_reward} 🪙",
        color=0xf39c12
    )
    embed.add_field(name="💼 New Balance", value=f"{new_coins:,} 🪙", inline=True)
    embed.set_footer(text="🌴 Weekly festivals are the best! See you next week!", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "economy", f"🪙 [WEEKLY] {interaction.user} claimed {total_reward} coins")

@bot.tree.command(name="work", description="💼 Work a Kerala-themed job for Vaazha Coins")
async def work(interaction: discord.Interaction):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    economy_channels = server_data.get('economy_channels', {})
    work_channel_id = economy_channels.get('work_channel')

    if work_channel_id and str(interaction.channel.id) != work_channel_id:
        work_channel = bot.get_channel(int(work_channel_id))
        channel_mention = work_channel.mention if work_channel else "#banana-jobs"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    user_data = await get_user_economy(interaction.user.id, interaction.guild.id)
    current_time = time.time()
    last_work = user_data.get('last_work', 0)

    if current_time - last_work < WORK_COOLDOWN:
        remaining = int(WORK_COOLDOWN - (current_time - last_work))
        minutes = remaining // 60

        embed = discord.Embed(
            title="😴 You're Tired!",
            description=f"Rest for **{minutes} minutes** before working again! 💤",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Select random job
    job = random.choice(WORK_JOBS)
    earnings = random.randint(job["min"], job["max"])

    # Update user data
    new_coins = user_data.get('coins', 0) + earnings
    await update_user_economy(interaction.user.id, interaction.guild.id, {
        'coins': new_coins,
        'last_work': current_time,
        'total_earned': user_data.get('total_earned', 0) + earnings
    })

    embed = discord.Embed(
        title="💼 Work Complete!",
        description=f"🌴 You **{job['name']}** and earned **{earnings} 🪙**!",
        color=0x43b581
    )
    embed.add_field(name="💼 New Balance", value=f"{new_coins:,} 🪙", inline=True)
    embed.set_footer(text="🍌 Hard work pays off in Kerala style!", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buykarma", description="✨ Buy karma points with Vaazha Coins")
@app_commands.describe(amount="Amount of karma to buy (1 karma = 10 coins)")
async def buy_karma(interaction: discord.Interaction, amount: int):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    economy_channels = server_data.get('economy_channels', {})
    store_channel_id = economy_channels.get('store_channel')

    if store_channel_id and str(interaction.channel.id) != store_channel_id:
        store_channel = bot.get_channel(int(store_channel_id))
        channel_mention = store_channel.mention if store_channel else "#vaazha-store"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    if amount <= 0 or amount > 100:
        await interaction.response.send_message("❌ You can buy 1-100 karma points at a time!", ephemeral=True)
        return

    cost = amount * KARMA_TO_COINS_RATE
    user_data = await get_user_economy(interaction.user.id, interaction.guild.id)
    current_coins = user_data.get('coins', 0)

    if current_coins < cost:
        embed = discord.Embed(
            title="💸 Not Enough Coins!",
            description=f"You need **{cost:,} 🪙** to buy **{amount} karma points**.\nYou have **{current_coins:,} 🪙**.",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Update coins
    new_coins = current_coins - cost
    await update_user_economy(interaction.user.id, interaction.guild.id, {
        'coins': new_coins,
        'total_spent': user_data.get('total_spent', 0) + cost
    })

    # Add karma using existing karma system
    if db is None:
        await interaction.response.send_message("❌ Database error!", ephemeral=True)
        return

    karma_data = await db.karma.find_one({'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id)})
    if not karma_data:
        karma_data = {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id), 'karma': 0}

    old_karma = karma_data.get('karma', 0)
    new_karma = old_karma + amount
    karma_data['karma'] = new_karma

    await db.karma.update_one(
        {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id)},
        {'$set': karma_data},
        upsert=True
    )

    embed = discord.Embed(
        title="✨ Karma Purchase Complete!",
        description=f"💰 **Spent:** {cost:,} 🪙\n⭐ **Gained:** {amount} karma points\n🪙 **Remaining:** {new_coins:,} coins",
        color=0x43b581
    )
    embed.add_field(name="New Karma Total", value=f"{new_karma} points", inline=True)
    embed.set_footer(text="🌟 Karma purchased successfully!", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "economy", f"🪙 [KARMA BUY] {interaction.user} bought {amount} karma for {cost} coins")

@bot.tree.command(name="slots", description="🎰 Play the banana-themed slot machine")
@app_commands.describe(bet="Amount to bet (10-500 coins)")
async def slots(interaction: discord.Interaction, bet: int):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    game_channels = server_data.get('game_channels', {})
    slots_channel_id = game_channels.get('slots_channel')

    if slots_channel_id and str(interaction.channel.id) != slots_channel_id:
        slots_channel = bot.get_channel(int(slots_channel_id))
        channel_mention = slots_channel.mention if slots_channel else "#banana-slots"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    if bet < 10 or bet > 500:
        await interaction.response.send_message("❌ You can bet between 10-500 🪙!", ephemeral=True)
        return

    user_data = await get_user_economy(interaction.user.id, interaction.guild.id)
    current_coins = user_data.get('coins', 0)

    if current_coins < bet:
        await interaction.response.send_message(f"❌ You need {bet} 🪙 to play! You have {current_coins} 🪙.", ephemeral=True)
        return

    # Slot symbols with Kerala theme
    symbols = ['🍌', '🥥', '🌴', '🐒', '⛵', '🎭', '💎', '👑']
    weights = [30, 25, 20, 15, 5, 3, 1, 1]  # Higher chance for common symbols

    # Spin the slots
    slot1 = random.choices(symbols, weights=weights)[0]
    slot2 = random.choices(symbols, weights=weights)[0]
    slot3 = random.choices(symbols, weights=weights)[0]

    # Calculate winnings
    winnings = 0
    if slot1 == slot2 == slot3:
        if slot1 == '👑':
            winnings = bet * 10  # Royal jackpot
        elif slot1 == '💎':
            winnings = bet * 8
        elif slot1 == '🎭':
            winnings = bet * 6
        elif slot1 == '⛵':
            winnings = bet * 5
        elif slot1 == '🐒':
            winnings = bet * 4
        elif slot1 == '🌴':
            winnings = bet * 3
        elif slot1 == '🥥':
            winnings = bet * 2
        elif slot1 == '🍌':
            winnings = bet * 2
    elif slot1 == slot2 or slot2 == slot3 or slot1 == slot3:
        winnings = int(bet * 0.5)  # Small win for two matching

    # Update coins
    new_coins = current_coins - bet + winnings
    await update_user_economy(interaction.user.id, interaction.guild.id, {
        'coins': new_coins,
        'total_spent': user_data.get('total_spent', 0) + bet,
        'total_earned': user_data.get('total_earned', 0) + winnings
    })

    # Create result message
    if winnings > bet:
        color = 0x43b581
        result_text = f"🎉 **BIG WIN!** You won {winnings:,} 🪙!"
    elif winnings > 0:
        color = 0xf39c12
        result_text = f"🎊 **Small win!** You won {winnings:,} 🪙!"
    else:
        color = 0xe74c3c
        result_text = f"💸 Better luck next time! You lost {bet:,} 🪙."

    embed = discord.Embed(
        title="🎰 Vaazha Slots Casino",
        description=f"**[ {slot1} | {slot2} | {slot3} ]**\n\n{result_text}\n\n💰 **New Balance:** {new_coins:,} 🪙",
        color=color
    )
    embed.set_footer(text="🍌 Try your luck again! Gambling responsibly!", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="trivia", description="🧠 Answer Kerala trivia questions for rewards")
async def trivia(interaction: discord.Interaction):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    game_channels = server_data.get('game_channels', {})
    trivia_channel_id = game_channels.get('trivia_channel')

    if trivia_channel_id and str(interaction.channel.id) != trivia_channel_id:
        trivia_channel = bot.get_channel(int(trivia_channel_id))
        channel_mention = trivia_channel.mention if trivia_channel else "#kerala-trivia"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    question_data = random.choice(TRIVIA_QUESTIONS)

    embed = discord.Embed(
        title="🧠 Kerala Trivia Challenge",
        description=f"**Question:** {question_data['question']}\n\n**Reward:** {question_data['reward']} 🪙\n\n*Type your answer in chat!*",
        color=0x3498db
    )
    embed.set_footer(text="🌴 You have 30 seconds to answer!", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

    def check(message):
        return (message.author == interaction.user and
                message.channel == interaction.channel and
                message.content.lower().strip() == question_data['answer'])

    try:
        answer_message = await bot.wait_for('message', timeout=30.0, check=check)

        # Correct answer - give reward
        user_data = await get_user_economy(interaction.user.id, interaction.guild.id)
        new_coins = user_data.get('coins', 0) + question_data['reward']
        await update_user_economy(interaction.user.id, interaction.guild.id, {
            'coins': new_coins,
            'total_earned': user_data.get('total_earned', 0) + question_data['reward']
        })

        embed = discord.Embed(
            title="🎉 Correct Answer!",
            description=f"✅ **Answer:** {question_data['answer'].title()}\n💰 **Reward:** {question_data['reward']} 🪙\n🪙 **New Balance:** {new_coins:,} coins",
            color=0x43b581
        )
        await interaction.followup.send(embed=embed)

    except asyncio.TimeoutError:
        embed = discord.Embed(
            title="⏰ Time's Up!",
            description=f"❌ **Correct Answer:** {question_data['answer'].title()}\n\nBetter luck next time! Try `/trivia` again.",
            color=0xe74c3c
        )
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="richest", description="🏆 Show the richest members leaderboard")
async def richest(interaction: discord.Interaction):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    economy_channels = server_data.get('economy_channels', {})
    richest_channel_id = economy_channels.get('richest_channel')

    if richest_channel_id and str(interaction.channel.id) != richest_channel_id:
        richest_channel = bot.get_channel(int(richest_channel_id))
        channel_mention = richest_channel.mention if richest_channel else "#rich-leaderboard"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return

    # Get top 10 richest users
    users_sorted = await db.economy.find({'guild_id': str(interaction.guild.id)}).sort([('coins', -1), ('bank', -1)]).limit(10).to_list(None)

    if not users_sorted:
        embed = discord.Embed(
            title="🏆 Richest Vaazha Holders",
            description="No one has earned coins yet! Start with `/daily` or `/work`!",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed)
        return

    leaderboard_text = ""
    for i, user_data in enumerate(users_sorted):
        user = bot.get_user(int(user_data['user_id']))
        if user:
            total_wealth = user_data.get('coins', 0) + user_data.get('bank', 0)

            if i == 0:
                medal = "🥇"
            elif i == 1:
                medal = "🥈"
            elif i == 2:
                medal = "🥉"
            else:
                medal = f"**{i+1}.**"

            leaderboard_text += f"{medal} **{user.display_name}** - {total_wealth:,} 🪙\n"

    embed = discord.Embed(
        title="🏆 **Richest Vaazha Coin Holders** 🪙",
        description=leaderboard_text,
        color=0xf1c40f
    )
    embed.set_footer(text="🍌 These members rule the Vaazha economy!", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="deposit", description="🏦 Deposit coins into your bank account")
@app_commands.describe(amount="Amount to deposit")
async def deposit(interaction: discord.Interaction, amount: str):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    bank_channels = server_data.get('bank_channels', {})
    deposit_channel_id = bank_channels.get('deposit_channel')

    if deposit_channel_id and str(interaction.channel.id) != deposit_channel_id:
        deposit_channel = bot.get_channel(int(deposit_channel_id))
        channel_mention = deposit_channel.mention if deposit_channel else "#coin-deposits"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    user_data = await get_user_economy(interaction.user.id, interaction.guild.id)
    current_coins = user_data.get('coins', 0)

    if amount.lower() == 'all':
        deposit_amount = current_coins
    else:
        try:
            deposit_amount = int(amount)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number or 'all'!", ephemeral=True)
            return

    if deposit_amount <= 0:
        await interaction.response.send_message("❌ You need to deposit at least 1 🪙!", ephemeral=True)
        return

    if deposit_amount > current_coins:
        await interaction.response.send_message(f"❌ You only have {current_coins:,} 🪙 in your wallet!", ephemeral=True)
        return

    # Update balances
    new_coins = current_coins - deposit_amount
    new_bank = user_data.get('bank', 0) + deposit_amount

    await update_user_economy(interaction.user.id, interaction.guild.id, {
        'coins': new_coins,
        'bank': new_bank
    })

    embed = discord.Embed(
        title="🏦 Bank Deposit Successful",
        description=f"💰 **Deposited:** {deposit_amount:,} 🪙\n\n🪙 **Wallet:** {new_coins:,} coins\n🏦 **Bank:** {new_bank:,} coins\n💎 **Total:** {new_coins + new_bank:,} coins",
        color=0x43b581
    )
    embed.set_footer(text="🌴 Your coins are safe in the Kerala Central Bank!", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="withdraw", description="💸 Withdraw coins from your bank account")
@app_commands.describe(amount="Amount to withdraw")
async def withdraw(interaction: discord.Interaction, amount: str):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    bank_channels = server_data.get('bank_channels', {})
    withdraw_channel_id = bank_channels.get('withdraw_channel')

    if withdraw_channel_id and str(interaction.channel.id) != withdraw_channel_id:
        withdraw_channel = bot.get_channel(int(withdraw_channel_id))
        channel_mention = withdraw_channel.mention if withdraw_channel else "#coin-withdrawals"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    user_data = await get_user_economy(interaction.user.id, interaction.guild.id)
    current_bank = user_data.get('bank', 0)

    if amount.lower() == 'all':
        withdraw_amount = current_bank
    else:
        try:
            withdraw_amount = int(amount)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number or 'all'!", ephemeral=True)
            return

    if withdraw_amount <= 0:
        await interaction.response.send_message("❌ You need to withdraw at least 1 🪙!", ephemeral=True)
        return

    if withdraw_amount > current_bank:
        await interaction.response.send_message(f"❌ You only have {current_bank:,} 🪙 in your bank!", ephemeral=True)
        return

    # Update balances
    new_bank = current_bank - withdraw_amount
    new_coins = user_data.get('coins', 0) + withdraw_amount

    await update_user_economy(interaction.user.id, interaction.guild.id, {
        'coins': new_coins,
        'bank': new_bank
    })

    embed = discord.Embed(
        title="🏦 Bank Withdrawal Successful",
        description=f"💸 **Withdrew:** {withdraw_amount:,} 🪙\n\n🪙 **Wallet:** {new_coins:,} coins\n🏦 **Bank:** {new_bank:,} coins\n💎 **Total:** {new_coins + new_bank:,} coins",
        color=0x43b581
    )
    embed.set_footer(text="🌴 Enjoy spending your Kerala coins!", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="trade", description="🤝 Send coins to another user")
@app_commands.describe(user="User to send coins to", amount="Amount to send")
async def trade(interaction: discord.Interaction, user: discord.Member, amount: int):
    # Check if command is used in correct channel
    server_data = await get_server_data(interaction.guild.id)
    bank_channels = server_data.get('bank_channels', {})
    trade_channel_id = bank_channels.get('trade_channel')

    if trade_channel_id and str(interaction.channel.id) != trade_channel_id:
        trade_channel = bot.get_channel(int(trade_channel_id))
        channel_mention = trade_channel.mention if trade_channel else "#coin-trading"
        await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}!", ephemeral=True)
        return

    if user.bot:
        await interaction.response.send_message("❌ You can't send coins to bots!", ephemeral=True)
        return

    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ You can't send coins to yourself!", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ You need to send at least 1 🪙!", ephemeral=True)
        return

    # Get sender data
    sender_data = await get_user_economy(interaction.user.id, interaction.guild.id)
    sender_coins = sender_data.get('coins', 0)

    if amount > sender_coins:
        await interaction.response.send_message(f"❌ You only have {sender_coins:,} 🪙 in your wallet!", ephemeral=True)
        return

    # Get receiver data
    receiver_data = await get_user_economy(user.id, interaction.guild.id)

    # Calculate tax (2% for trades over 100 coins)
    tax = int(amount * 0.02) if amount > 100 else 0
    final_amount = amount - tax

    # Update both users
    await update_user_economy(interaction.user.id, interaction.guild.id, {
        'coins': sender_coins - amount,
        'total_spent': sender_data.get('total_spent', 0) + amount
    })

    await update_user_economy(user.id, interaction.guild.id, {
        'coins': receiver_data.get('coins', 0) + final_amount,
        'total_earned': receiver_data.get('total_earned', 0) + final_amount
    })

    tax_text = f"\n🏛️ **Transaction Tax:** {tax} 🪙" if tax > 0 else ""

    embed = discord.Embed(
        title="💸 Coin Transfer Successful",
        description=f"**From:** {interaction.user.mention}\n**To:** {user.mention}\n💰 **Amount Sent:** {amount:,} 🪙\n💎 **Amount Received:** {final_amount:,} 🪙{tax_text}",
        color=0x43b581
    )
    embed.set_footer(text="🌴 Kerala banking at its finest!", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "economy", f"🪙 [TRADE] {interaction.user} sent {amount} coins to {user}")

# Economy admin commands
@bot.tree.command(name="addcoins", description="💰 Add coins to a user (Main Moderator only)")
@app_commands.describe(user="User to give coins to", amount="Amount of coins to add")
async def add_coins(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    if amount <= 0 or amount > 10000:
        await interaction.response.send_message("❌ You can add 1-10,000 coins at a time!", ephemeral=True)
        return

    user_data = await get_user_economy(user.id, interaction.guild.id)
    new_coins = user_data.get('coins', 0) + amount

    await update_user_economy(user.id, interaction.guild.id, {
        'coins': new_coins,
        'total_earned': user_data.get('total_earned', 0) + amount
    })

    embed = discord.Embed(
        title="💰 Coins Added Successfully",
        description=f"**User:** {user.mention}\n**Amount Added:** {amount:,} 🪙\n**New Balance:** {new_coins:,} 🪙\n**Added by:** {interaction.user.mention}",
        color=0x43b581
    )
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "economy", f"🪙 [ADMIN ADD] {interaction.user} added {amount} coins to {user}")

@bot.tree.command(name="removecoins", description="💸 Remove coins from a user (Main Moderator only)")
@app_commands.describe(user="User to remove coins from", amount="Amount of coins to remove")
async def remove_coins(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ You need to remove at least 1 coin!", ephemeral=True)
        return

    user_data = await get_user_economy(user.id, interaction.guild.id)
    current_coins = user_data.get('coins', 0)
    new_coins = max(0, current_coins - amount)
    actual_removed = current_coins - new_coins

    await update_user_economy(user.id, interaction.guild.id, {
        'coins': new_coins
    })

    embed = discord.Embed(
        title="💸 Coins Removed Successfully",
        description=f"**User:** {user.mention}\n**Amount Removed:** {actual_removed:,} 🪙\n**New Balance:** {new_coins:,} 🪙\n**Removed by:** {interaction.user.mention}",
        color=0xe74c3c
    )
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "economy", f"🪙 [ADMIN REMOVE] {interaction.user} removed {actual_removed} coins from {user}")

# Category and Channel Setup Commands

@bot.tree.command(name="seteconomycatogary", description="sets the economy category")
@app_commands.describe(catogary="economy category")
async def set_economy_catogary(interaction: discord.Interaction, catogary: discord.CategoryChannel):
    if not await has_permission(interaction, "administrator"):
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    if 'economy_channels' not in server_data:
        server_data['economy_channels'] = {}

    server_data['economy_channels']['category'] = catogary.id
    await update_server_data(interaction.guild.id, server_data)

    await interaction.response.send_message(f"✅ Economy category set to {catogary.name}!")

@bot.tree.command(name="setgamecatogary", description="sets the game category")
@app_commands.describe(catogary="game category")
async def set_game_catogary(interaction: discord.Interaction, catogary: discord.CategoryChannel):
    if not await has_permission(interaction, "administrator"):
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    if 'game_channels' not in server_data:
        server_data['game_channels'] = {}

    server_data['game_channels']['category'] = catogary.id
    await update_server_data(interaction.guild.id, server_data)

    await interaction.response.send_message(f"✅ Game category set to {catogary.name}!")

@bot.tree.command(name="setbankcatogary", description="sets the bank category")
@app_commands.describe(catogary="bank category")
async def set_bank_catogary(interaction: discord.Interaction, catogary: discord.CategoryChannel):
    if not await has_permission(interaction, "administrator"):
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    if 'bank_channels' not in server_data:
        server_data['bank_channels'] = {}

    server_data['bank_channels']['category'] = catogary.id
    await update_server_data(interaction.guild.id, server_data)

    await interaction.response.send_message(f"✅ Bank category set to {catogary.name}!")

@bot.tree.command(name="createeconomychannels", description="creates economy channels")
async def create_economy_channels(interaction: discord.Interaction):
    if not await has_permission(interaction, "administrator"):
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    economy_category_id = server_data.get('economy_channels', {}).get('category')

    if not economy_category_id:
        await interaction.response.send_message("❌ Economy category not set. Please use `/seteconomycatogary` first.", ephemeral=True)
        return

    economy_category = discord.utils.get(interaction.guild.categories, id=int(economy_category_id))
    if not economy_category:
        await interaction.response.send_message("❌ Economy category not found. Please check the category ID.", ephemeral=True)
        return

    # Create channels if they don't exist
    channel_names = {
        "balance_channel": "📊・balance",
        "work_channel": "💼・work",
        "store_channel": "🛍️・vaazha-store",
        "richest_channel": "🏆・rich-leaderboard"
    }
    created_channels = []

    for key, name in channel_names.items():
        channel_base_name = name.split('・')[1]
        existing_channel = discord.utils.get(economy_category.text_channels, name=channel_base_name)
        if not existing_channel:
            try:
                new_channel = await interaction.guild.create_text_channel(
                    name=channel_base_name,
                    category=economy_category,
                    topic="Economy related commands",
                    position=len(economy_category.text_channels) # Add to the end
                )
                # Set channel permissions to follow category
                await new_channel.set_permissions(interaction.guild.default_role, send_messages=False, read_messages=True) # Default to read only
                # Give bot and admins permissions to send messages
                bot_role = discord.utils.get(interaction.guild.roles, name="VaazhaBot") # Assuming a role named VaazhaBot
                admin_role = discord.utils.get(interaction.guild.roles, name="Admin") # Example admin role name, adjust if needed

                if bot_role:
                    await new_channel.set_permissions(bot_role, send_messages=True)
                if admin_role:
                    await new_channel.set_permissions(admin_role, send_messages=True)

                server_data['economy_channels'][key] = new_channel.id
                created_channels.append(new_channel.mention)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error creating channel {name}: {e}", ephemeral=True)
                return
        else:
            server_data['economy_channels'][key] = existing_channel.id
            created_channels.append(existing_channel.mention)

    await update_server_data(interaction.guild.id, server_data)
    await interaction.response.send_message(f"✅ Economy channels created/found: {', '.join(created_channels)}")


@bot.tree.command(name="create_game_channels", description="creates game channels")
async def create_game_channels(interaction: discord.Interaction):
    if not await has_permission(interaction, "administrator"):
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    game_category_id = server_data.get('game_channels', {}).get('category')

    if not game_category_id:
        await interaction.response.send_message("❌ Game category not set. Please use `/setgamecatogary` first.", ephemeral=True)
        return

    game_category = discord.utils.get(interaction.guild.categories, id=int(game_category_id))
    if not game_category:
        await interaction.response.send_message("❌ Game category not found. Please check the category ID.", ephemeral=True)
        return

    channel_names = {
        "slots_channel": "🎰・slots",
        "trivia_channel": "🧠・kerala-trivia"
    }
    created_channels = []

    for key, name in channel_names.items():
        channel_base_name = name.split('・')[1]
        existing_channel = discord.utils.get(game_category.text_channels, name=channel_base_name)
        if not existing_channel:
            try:
                new_channel = await interaction.guild.create_text_channel(
                    name=channel_base_name,
                    category=game_category,
                    topic="Game related commands",
                    position=len(game_category.text_channels)
                )
                await new_channel.set_permissions(interaction.guild.default_role, send_messages=False, read_messages=True)
                bot_role = discord.utils.get(interaction.guild.roles, name="VaazhaBot")
                admin_role = discord.utils.get(interaction.guild.roles, name="Admin")
                if bot_role:
                    await new_channel.set_permissions(bot_role, send_messages=True)
                if admin_role:
                    await new_channel.set_permissions(admin_role, send_messages=True)
                server_data['game_channels'][key] = new_channel.id
                created_channels.append(new_channel.mention)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error creating channel {name}: {e}", ephemeral=True)
                return
        else:
            server_data['game_channels'][key] = existing_channel.id
            created_channels.append(existing_channel.mention)

    await update_server_data(interaction.guild.id, server_data)
    await interaction.response.send_message(f"✅ Game channels created/found: {', '.join(created_channels)}")

@bot.tree.command(name="create_bank_channels", description="creates bank channels")
async def create_bank_channels(interaction: discord.Interaction):
    if not await has_permission(interaction, "administrator"):
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    bank_category_id = server_data.get('bank_channels', {}).get('category')

    if not bank_category_id:
        await interaction.response.send_message("❌ Bank category not set. Please use `/setbankcatogary` first.", ephemeral=True)
        return

    bank_category = discord.utils.get(interaction.guild.categories, id=int(bank_category_id))
    if not bank_category:
        await interaction.response.send_message("❌ Bank category not found. Please check the category ID.", ephemeral=True)
        return

    channel_names = {
        "deposit_channel": "🏦・coin-deposits",
        "withdraw_channel": "💸・coin-withdrawals",
        "trade_channel": "🤝・coin-trading"
    }
    created_channels = []

    for key, name in channel_names.items():
        channel_base_name = name.split('・')[1]
        existing_channel = discord.utils.get(bank_category.text_channels, name=channel_base_name)
        if not existing_channel:
            try:
                new_channel = await interaction.guild.create_text_channel(
                    name=channel_base_name,
                    category=bank_category,
                    topic="Bank related commands",
                    position=len(bank_category.text_channels)
                )
                await new_channel.set_permissions(interaction.guild.default_role, send_messages=False, read_messages=True)
                bot_role = discord.utils.get(interaction.guild.roles, name="VaazhaBot")
                admin_role = discord.utils.get(interaction.guild.roles, name="Admin")
                if bot_role:
                    await new_channel.set_permissions(bot_role, send_messages=True)
                if admin_role:
                    await new_channel.set_permissions(admin_role, send_messages=True)
                server_data['bank_channels'][key] = new_channel.id
                created_channels.append(new_channel.mention)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error creating channel {name}: {e}", ephemeral=True)
                return
        else:
            server_data['bank_channels'][key] = existing_channel.id
            created_channels.append(existing_channel.mention)

    await update_server_data(interaction.guild.id, server_data)
    await interaction.response.send_message(f"✅ Bank channels created/found: {', '.join(created_channels)}")