
import discord
from discord.ext import commands
from discord import app_commands
import time
import random
from datetime import datetime, timedelta
from main import bot, db, log_action, get_server_data

# Pet evolution names based on levels
PET_STAGES = {
    1: "Baby", 2: "Toddler", 3: "Young", 4: "Teen", 5: "Adult",
    6: "Mature", 7: "Elder", 8: "Ancient", 9: "Legendary", 10: "Mythical"
}

PET_MOODS = ["😭 Crying", "😢 Sad", "😐 Neutral", "😊 Happy", "😍 Ecstatic", "🤩 Overjoyed"]

DAILY_LOGIN_BONUS_XP = 50

@bot.tree.command(name="adoptpet", description="🐾 Adopt a virtual pet companion!")
@app_commands.describe(name="Name for your new pet (max 20 characters)")
async def adopt_pet(interaction: discord.Interaction, name: str):
    if len(name) > 20:
        await interaction.response.send_message("❌ Pet name must be 20 characters or less!", ephemeral=True)
        return
    
    # Check for inappropriate names
    bad_words = ["fuck", "shit", "damn", "hell", "ass", "bitch", "bastard"]
    if any(word in name.lower() for word in bad_words):
        await interaction.response.send_message("❌ Please choose a family-friendly name for your pet!", ephemeral=True)
        return
    
    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return
    
    # Check if user already has a pet
    existing_pet = await db.pets.find_one({
        'user_id': str(interaction.user.id),
        'guild_id': str(interaction.guild.id)
    })
    
    if existing_pet:
        await interaction.response.send_message(f"❌ You already have a pet named **{existing_pet['pet_name']}**! Use `/petinfo` to check on them.", ephemeral=True)
        return
    
    # Create new pet
    pet_data = {
        'user_id': str(interaction.user.id),
        'guild_id': str(interaction.guild.id),
        'pet_name': name,
        'pet_level': 1,
        'pet_xp': 0,
        'pet_mood': 3,  # Index for neutral mood
        'last_fed': datetime.utcnow() - timedelta(hours=25),  # Allow immediate feeding
        'last_played': datetime.utcnow() - timedelta(hours=25),  # Allow immediate playing
        'last_daily_login': datetime.utcnow() - timedelta(days=2),  # Allow immediate daily bonus
        'adoption_date': datetime.utcnow(),
        'messages_sent': 0
    }
    
    await db.pets.insert_one(pet_data)
    
    # Random pet type emoji
    pet_emojis = ["🐶", "🐱", "🐹", "🐰", "🦊", "🐼", "🐨", "🦁", "🐯", "🐷"]
    pet_emoji = random.choice(pet_emojis)
    
    embed = discord.Embed(
        title="🎉 Pet Adoption Successful!",
        description=f"**Congratulations!** {interaction.user.mention} just adopted **{name}**! {pet_emoji}\n\n🌟 **Level:** 1\n💫 **XP:** 0/100\n😊 **Mood:** Happy\n🎂 **Age:** Just born!\n\n*Your pet will gain XP from your messages and level up over time! Use `/feedpet` and `/playpet` to keep them happy!*",
        color=0x43b581
    )
    embed.set_footer(text="🐾 Welcome to the pet family! Use /petinfo to check on your pet anytime!")
    await interaction.response.send_message(embed=embed)
    
    await log_action(interaction.guild.id, "communication", f"🐾 [PET] {interaction.user} adopted pet '{name}'")

@bot.tree.command(name="petinfo", description="🐾 Check your pet's status and stats")
@app_commands.describe(user="Check another user's pet (optional)")
async def pet_info(interaction: discord.Interaction, user: discord.Member = None):
    target_user = user or interaction.user
    
    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return
    
    pet_data = await db.pets.find_one({
        'user_id': str(target_user.id),
        'guild_id': str(interaction.guild.id)
    })
    
    if not pet_data:
        if target_user == interaction.user:
            await interaction.response.send_message("❌ You don't have a pet yet! Use `/adoptpet <name>` to adopt one!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {target_user.mention} doesn't have a pet!", ephemeral=True)
        return
    
    # Calculate pet stats
    level = pet_data.get('pet_level', 1)
    xp = pet_data.get('pet_xp', 0)
    mood_index = pet_data.get('pet_mood', 3)
    pet_name = pet_data.get('pet_name', 'Unknown')
    adoption_date = pet_data.get('adoption_date', datetime.utcnow())
    messages_sent = pet_data.get('messages_sent', 0)
    
    # XP needed for next level (100 * level)
    xp_needed = 100 * level
    xp_progress = min(xp, xp_needed)
    
    # Mood
    mood = PET_MOODS[min(mood_index, len(PET_MOODS) - 1)]
    
    # Pet stage
    stage = PET_STAGES.get(level, "Transcendent")
    
    # Age calculation
    age_days = (datetime.utcnow() - adoption_date).days
    
    # Progress bar
    progress_percent = (xp_progress / xp_needed) * 20
    filled_bars = int(progress_percent)
    progress_bar = "█" * filled_bars + "░" * (20 - filled_bars)
    
    # Pet emoji based on level
    if level <= 2:
        pet_emoji = "🐣"
    elif level <= 4:
        pet_emoji = "🐾"
    elif level <= 6:
        pet_emoji = "🦁"
    elif level <= 8:
        pet_emoji = "🐉"
    else:
        pet_emoji = "✨"
    
    embed = discord.Embed(
        title=f"🐾 {pet_name} - {stage} {pet_emoji}",
        description=f"*{target_user.mention}'s beloved companion*",
        color=0x3498db
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    
    embed.add_field(name="📊 Level & XP", value=f"**Level:** {level}\n**XP:** {xp}/{xp_needed}\n`{progress_bar}` {xp_progress}/{xp_needed}", inline=True)
    embed.add_field(name="💭 Status", value=f"**Mood:** {mood}\n**Age:** {age_days} days\n**Messages:** {messages_sent:,}", inline=True)
    embed.add_field(name="🎮 Actions", value="🍖 `/feedpet` - Boost mood\n🎾 `/playpet` - Gain XP\n📅 Daily login bonus!", inline=True)
    
    # Check if actions are available
    last_fed = pet_data.get('last_fed', datetime.utcnow() - timedelta(days=1))
    last_played = pet_data.get('last_played', datetime.utcnow() - timedelta(days=1))
    last_daily = pet_data.get('last_daily_login', datetime.utcnow() - timedelta(days=2))
    
    can_feed = (datetime.utcnow() - last_fed).total_seconds() > 3600  # 1 hour cooldown
    can_play = (datetime.utcnow() - last_played).total_seconds() > 3600  # 1 hour cooldown  
    can_daily = (datetime.utcnow() - last_daily).total_seconds() > 86400  # 24 hour cooldown
    
    availability = []
    if can_feed:
        availability.append("🍖 Ready to feed!")
    if can_play:
        availability.append("🎾 Ready to play!")
    if can_daily:
        availability.append("📅 Daily bonus available!")
    
    if availability:
        embed.add_field(name="✅ Available Actions", value="\n".join(availability), inline=False)
    
    embed.set_footer(text=f"🌴 Adopted on {adoption_date.strftime('%B %d, %Y')}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="feedpet", description="🍖 Feed your pet to improve their mood!")
async def feed_pet(interaction: discord.Interaction):
    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return
    
    pet_data = await db.pets.find_one({
        'user_id': str(interaction.user.id),
        'guild_id': str(interaction.guild.id)
    })
    
    if not pet_data:
        await interaction.response.send_message("❌ You don't have a pet yet! Use `/adoptpet <name>` to adopt one!", ephemeral=True)
        return
    
    # Check cooldown (1 hour)
    last_fed = pet_data.get('last_fed', datetime.utcnow() - timedelta(days=1))
    cooldown = 3600  # 1 hour in seconds
    
    if (datetime.utcnow() - last_fed).total_seconds() < cooldown:
        remaining = cooldown - (datetime.utcnow() - last_fed).total_seconds()
        minutes = int(remaining // 60)
        await interaction.response.send_message(f"❌ {pet_data['pet_name']} is still full! You can feed them again in {minutes} minutes.", ephemeral=True)
        return
    
    # Improve mood
    current_mood = pet_data.get('pet_mood', 3)
    new_mood = min(current_mood + 1, len(PET_MOODS) - 1)
    xp_gain = random.randint(10, 25)
    
    # Update pet data
    new_xp = pet_data.get('pet_xp', 0) + xp_gain
    new_level = pet_data.get('pet_level', 1)
    
    # Check for level up
    xp_needed = 100 * new_level
    leveled_up = False
    if new_xp >= xp_needed:
        new_level += 1
        leveled_up = True
        # Give karma bonus for level up
        try:
            from xp_commands import db as karma_db
            if karma_db:
                karma_data = await karma_db.karma.find_one({
                    'user_id': str(interaction.user.id),
                    'guild_id': str(interaction.guild.id)
                }) or {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id), 'karma': 0}
                
                karma_data['karma'] += 1  # +1 karma for pet level up
                await karma_db.karma.update_one(
                    {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id)},
                    {'$set': karma_data},
                    upsert=True
                )
        except:
            pass
    
    await db.pets.update_one(
        {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id)},
        {'$set': {
            'pet_mood': new_mood,
            'pet_xp': new_xp,
            'pet_level': new_level,
            'last_fed': datetime.utcnow()
        }}
    )
    
    # Random food emojis
    foods = ["🥩", "🍖", "🐟", "🥛", "🍎", "🥕", "🦴", "🍪", "🎂"]
    food = random.choice(foods)
    
    mood_text = PET_MOODS[new_mood]
    
    description = f"**{pet_data['pet_name']}** enjoyed the {food}!\n\n💭 **Mood:** {mood_text}\n💫 **XP Gained:** +{xp_gain}"
    
    if leveled_up:
        stage = PET_STAGES.get(new_level, "Transcendent")
        description += f"\n\n🎉 **LEVEL UP!** Your pet is now a **Level {new_level} {stage}**!\n✨ **Karma Bonus:** +1 karma earned!"
    
    embed = discord.Embed(
        title="🍖 Pet Fed Successfully!",
        description=description,
        color=0x43b581
    )
    embed.set_footer(text="🐾 Your pet is happy! Come back in 1 hour to feed them again.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="playpet", description="🎾 Play with your pet to gain XP and improve mood!")
async def play_pet(interaction: discord.Interaction):
    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return
    
    pet_data = await db.pets.find_one({
        'user_id': str(interaction.user.id),
        'guild_id': str(interaction.guild.id)
    })
    
    if not pet_data:
        await interaction.response.send_message("❌ You don't have a pet yet! Use `/adoptpet <name>` to adopt one!", ephemeral=True)
        return
    
    # Check cooldown (1 hour)
    last_played = pet_data.get('last_played', datetime.utcnow() - timedelta(days=1))
    cooldown = 3600  # 1 hour in seconds
    
    if (datetime.utcnow() - last_played).total_seconds() < cooldown:
        remaining = cooldown - (datetime.utcnow() - last_played).total_seconds()
        minutes = int(remaining // 60)
        await interaction.response.send_message(f"❌ {pet_data['pet_name']} is tired! You can play with them again in {minutes} minutes.", ephemeral=True)
        return
    
    # Gain XP and improve mood
    current_mood = pet_data.get('pet_mood', 3)
    new_mood = min(current_mood + 1, len(PET_MOODS) - 1)
    xp_gain = random.randint(15, 35)
    
    # Update pet data
    new_xp = pet_data.get('pet_xp', 0) + xp_gain
    new_level = pet_data.get('pet_level', 1)
    
    # Check for level up
    xp_needed = 100 * new_level
    leveled_up = False
    if new_xp >= xp_needed:
        new_level += 1
        leveled_up = True
        # Give karma bonus for level up
        try:
            from xp_commands import db as karma_db
            if karma_db:
                karma_data = await karma_db.karma.find_one({
                    'user_id': str(interaction.user.id),
                    'guild_id': str(interaction.guild.id)
                }) or {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id), 'karma': 0}
                
                karma_data['karma'] += 1  # +1 karma for pet level up
                await karma_db.karma.update_one(
                    {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id)},
                    {'$set': karma_data},
                    upsert=True
                )
        except:
            pass
    
    await db.pets.update_one(
        {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id)},
        {'$set': {
            'pet_mood': new_mood,
            'pet_xp': new_xp,
            'pet_level': new_level,
            'last_played': datetime.utcnow()
        }}
    )
    
    # Random play activities
    activities = [
        "played fetch", "chased their tail", "did tricks", "went for a walk",
        "played hide and seek", "rolled around", "danced", "played with toys"
    ]
    activity = random.choice(activities)
    
    mood_text = PET_MOODS[new_mood]
    
    description = f"**{pet_data['pet_name']}** {activity} with you!\n\n💭 **Mood:** {mood_text}\n💫 **XP Gained:** +{xp_gain}"
    
    if leveled_up:
        stage = PET_STAGES.get(new_level, "Transcendent")
        description += f"\n\n🎉 **LEVEL UP!** Your pet is now a **Level {new_level} {stage}**!\n✨ **Karma Bonus:** +1 karma earned!"
    
    embed = discord.Embed(
        title="🎾 Playtime Success!",
        description=description,
        color=0x43b581
    )
    embed.set_footer(text="🐾 Your pet had fun! Come back in 1 hour to play again.")
    await interaction.response.send_message(embed=embed)

# Event to give pets XP from messages
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    
    if db is None:
        return
    
    # Give pet XP from messages (small amount)
    pet_data = await db.pets.find_one({
        'user_id': str(message.author.id),
        'guild_id': str(message.guild.id)
    })
    
    if pet_data:
        # Small XP gain from chatting (1-3 XP per message, max once per minute per user)
        current_time = time.time()
        last_message_xp = pet_data.get('last_message_xp', 0)
        
        if current_time - last_message_xp >= 60:  # 1 minute cooldown
            xp_gain = random.randint(1, 3)
            new_xp = pet_data.get('pet_xp', 0) + xp_gain
            new_level = pet_data.get('pet_level', 1)
            messages_sent = pet_data.get('messages_sent', 0) + 1
            
            # Check for level up
            xp_needed = 100 * new_level
            leveled_up = False
            if new_xp >= xp_needed:
                new_level += 1
                leveled_up = True
                
                # Send level up message
                stage = PET_STAGES.get(new_level, "Transcendent")
                embed = discord.Embed(
                    title="🎉 Pet Level Up!",
                    description=f"**{pet_data['pet_name']}** grew from your conversations!\n\n🆙 **New Level:** {new_level} ({stage})\n✨ **Bonus:** +1 karma earned!",
                    color=0xf39c12
                )
                try:
                    await message.channel.send(embed=embed, delete_after=10)
                except:
                    pass
                
                # Give karma bonus
                try:
                    from xp_commands import db as karma_db
                    if karma_db:
                        karma_data = await karma_db.karma.find_one({
                            'user_id': str(message.author.id),
                            'guild_id': str(message.guild.id)
                        }) or {'user_id': str(message.author.id), 'guild_id': str(message.guild.id), 'karma': 0}
                        
                        karma_data['karma'] += 1
                        await karma_db.karma.update_one(
                            {'user_id': str(message.author.id), 'guild_id': str(message.guild.id)},
                            {'$set': karma_data},
                            upsert=True
                        )
                except:
                    pass
            
            await db.pets.update_one(
                {'user_id': str(message.author.id), 'guild_id': str(message.guild.id)},
                {'$set': {
                    'pet_xp': new_xp,
                    'pet_level': new_level,
                    'messages_sent': messages_sent,
                    'last_message_xp': current_time
                }}
            )

@bot.tree.command(name="dailypet", description="📅 Get daily login bonus for your pet!")
async def daily_pet_bonus(interaction: discord.Interaction):
    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return
    
    pet_data = await db.pets.find_one({
        'user_id': str(interaction.user.id),
        'guild_id': str(interaction.guild.id)
    })
    
    if not pet_data:
        await interaction.response.send_message("❌ You don't have a pet yet! Use `/adoptpet <name>` to adopt one!", ephemeral=True)
        return
    
    # Check daily cooldown (24 hours)
    last_daily = pet_data.get('last_daily_login', datetime.utcnow() - timedelta(days=2))
    cooldown = 86400  # 24 hours in seconds
    
    if (datetime.utcnow() - last_daily).total_seconds() < cooldown:
        remaining = cooldown - (datetime.utcnow() - last_daily).total_seconds()
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await interaction.response.send_message(f"❌ Daily bonus already claimed! Come back in {hours}h {minutes}m.", ephemeral=True)
        return
    
    # Give daily bonus
    xp_gain = DAILY_LOGIN_BONUS_XP
    mood_boost = 1
    
    current_mood = pet_data.get('pet_mood', 3)
    new_mood = min(current_mood + mood_boost, len(PET_MOODS) - 1)
    
    new_xp = pet_data.get('pet_xp', 0) + xp_gain
    new_level = pet_data.get('pet_level', 1)
    
    # Check for level up
    xp_needed = 100 * new_level
    leveled_up = False
    if new_xp >= xp_needed:
        new_level += 1
        leveled_up = True
        # Give karma bonus for level up
        try:
            from xp_commands import db as karma_db
            if karma_db:
                karma_data = await karma_db.karma.find_one({
                    'user_id': str(interaction.user.id),
                    'guild_id': str(interaction.guild.id)
                }) or {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id), 'karma': 0}
                
                karma_data['karma'] += 2  # +2 karma for daily login level up
                await karma_db.karma.update_one(
                    {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id)},
                    {'$set': karma_data},
                    upsert=True
                )
        except:
            pass
    
    await db.pets.update_one(
        {'user_id': str(interaction.user.id), 'guild_id': str(interaction.guild.id)},
        {'$set': {
            'pet_mood': new_mood,
            'pet_xp': new_xp,
            'pet_level': new_level,
            'last_daily_login': datetime.utcnow()
        }}
    )
    
    mood_text = PET_MOODS[new_mood]
    
    description = f"**{pet_data['pet_name']}** is excited to see you again!\n\n💫 **Daily XP Bonus:** +{xp_gain}\n💭 **Mood:** {mood_text}"
    
    if leveled_up:
        stage = PET_STAGES.get(new_level, "Transcendent")
        description += f"\n\n🎉 **LEVEL UP!** Your pet is now a **Level {new_level} {stage}**!\n✨ **Karma Bonus:** +2 karma earned!"
    
    embed = discord.Embed(
        title="📅 Daily Pet Bonus!",
        description=description,
        color=0x43b581
    )
    embed.set_footer(text="🐾 Come back tomorrow for another daily bonus!")
    await interaction.response.send_message(embed=embed)
