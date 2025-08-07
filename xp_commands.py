
import discord
from discord.ext import commands
from discord import app_commands
from main import bot, db, create_rank_image, calculate_level, xp_for_level

@bot.tree.command(name="rank", description="Show your XP rank")
@app_commands.describe(user="User to check rank for (optional)")
async def rank(interaction: discord.Interaction, user: discord.Member = None):
    target_user = user or interaction.user
    
    if not db:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return
    
    user_data = await db.users.find_one({'user_id': str(target_user.id), 'guild_id': str(interaction.guild.id)})
    
    if not user_data:
        embed = discord.Embed(
            title="📊 Rank Card",
            description=f"{target_user.display_name} has not gained any XP yet!",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed)
        return
    
    xp = user_data.get('xp', 0)
    level = user_data.get('level', 1)
    
    # Get user rank
    users_sorted = await db.users.find({'guild_id': str(interaction.guild.id)}).sort('xp', -1).to_list(None)
    rank = next((i + 1 for i, u in enumerate(users_sorted) if u['user_id'] == str(target_user.id)), None)
    
    # Create rank image
    rank_image = await create_rank_image(target_user, xp, level, rank)
    
    embed = discord.Embed(
        title=f"📊 {target_user.display_name}'s Rank",
        color=0x3498db
    )
    embed.add_field(name="Level", value=level, inline=True)
    embed.add_field(name="XP", value=f"{xp}/{xp_for_level(level + 1)}", inline=True)
    embed.add_field(name="Rank", value=f"#{rank}" if rank else "Unknown", inline=True)
    
    if rank_image:
        file = discord.File(rank_image, filename="rank.png")
        embed.set_image(url="attachment://rank.png")
        await interaction.response.send_message(embed=embed, file=file)
    else:
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Show server XP leaderboard")
async def leaderboard(interaction: discord.Interaction):
    if not db:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return
    
    users_sorted = await db.users.find({'guild_id': str(interaction.guild.id)}).sort('xp', -1).limit(10).to_list(None)
    
    if not users_sorted:
        embed = discord.Embed(
            title="📊 XP Leaderboard",
            description="No users have gained XP yet!",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="🏆 XP Leaderboard",
        description="Top 10 users by XP",
        color=0xf39c12
    )
    
    leaderboard_text = ""
    for i, user_data in enumerate(users_sorted, 1):
        try:
            user = bot.get_user(int(user_data['user_id']))
            if user:
                xp = user_data.get('xp', 0)
                level = user_data.get('level', 1)
                
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                leaderboard_text += f"{medal} **{user.display_name}** - Level {level} ({xp:,} XP)\n"
        except:
            continue
    
    embed.description = leaderboard_text or "No users found"
    await interaction.response.send_message(embed=embed)
