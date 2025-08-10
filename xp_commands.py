
import discord
from discord.ext import commands
from discord import app_commands
from main import bot, db, create_rank_image, calculate_level, xp_for_level

@bot.tree.command(name="rank", description="Show your XP rank")
@app_commands.describe(user="User to check rank for (optional)")
async def rank(interaction: discord.Interaction, user: discord.Member = None):
    # Check if XP commands channel is set and restrict usage
    from main import get_server_data
    server_data = await get_server_data(interaction.guild.id)
    xp_commands_channel_id = server_data.get('xp_commands_channel')

    if xp_commands_channel_id and str(interaction.channel.id) != xp_commands_channel_id:
        xp_channel = bot.get_channel(int(xp_commands_channel_id))
        embed = discord.Embed(
            title="❌ Wrong Channel",
            description=f"XP commands can only be used in {xp_channel.mention}!",
            color=0xe74c3c
        )
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    target_user = user or interaction.user

    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return

    user_data = await db.users.find_one({'user_id': str(target_user.id), 'guild_id': str(interaction.guild.id)})

    if not user_data:
        embed = discord.Embed(
            title="📊 Rank Card",
            description=f"{target_user.display_name} has not gained any XP yet!",
            color=0xe74c3c
        )
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
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
    embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")

    if rank_image:
        file = discord.File(rank_image, filename="rank.png")
        embed.set_image(url="attachment://rank.png")
        await interaction.response.send_message(embed=embed, file=file)
    else:
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Show server XP leaderboard")
async def leaderboard(interaction: discord.Interaction):
    # Check if XP commands channel is set and restrict usage
    from main import get_server_data
    server_data = await get_server_data(interaction.guild.id)
    xp_commands_channel_id = server_data.get('xp_commands_channel')

    if xp_commands_channel_id and str(interaction.channel.id) != xp_commands_channel_id:
        xp_channel = bot.get_channel(int(xp_commands_channel_id))
        embed = discord.Embed(
            title="❌ Wrong Channel",
            description=f"XP commands can only be used in {xp_channel.mention}!",
            color=0xe74c3c
        )
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return

    users_sorted = await db.users.find({'guild_id': str(interaction.guild.id)}).sort('xp', -1).limit(10).to_list(None)

    if not users_sorted:
        embed = discord.Embed(
            title="📊 XP Leaderboard",
            description="No users have gained XP yet!",
            color=0xe74c3c
        )
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
        await interaction.response.send_message(embed=embed)
        return

    # Build leaderboard text
    leaderboard_text = ""
    for i, user_data in enumerate(users_sorted):
        user = bot.get_user(int(user_data['user_id']))
        if user:
            level = user_data.get('level', 1)
            xp = user_data.get('xp', 0)
            
            # Medal emojis for top 3
            if i == 0:
                medal = "🥇"
            elif i == 1:
                medal = "🥈"
            elif i == 2:
                medal = "🥉"
            else:
                medal = f"**{i+1}.**"
            
            leaderboard_text += f"{medal} **{user.display_name}** - Level {level} ({xp:,} XP)\n"

    embed = discord.Embed(
        title="📊 **Server Leaderboard** 🏆",
        description=leaderboard_text,
        color=0xf39c12
    )
    embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="resetxp", description="Reset XP data for user or server")
@app_commands.describe(
    scope="Reset scope",
    user="User to reset (if scope is user)"
)
@app_commands.choices(scope=[
    app_commands.Choice(name="user", value="user"),
    app_commands.Choice(name="server", value="server")
])
async def reset_xp(interaction: discord.Interaction, scope: str, user: discord.Member = None):
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
        
        result = await db.users.delete_one({'user_id': str(user.id), 'guild_id': str(interaction.guild.id)})
        
        if result.deleted_count > 0:
            embed = discord.Embed(
                title="✅ User XP Reset",
                description=f"**User:** {user.mention}\n**Action:** XP data has been reset\n**Reset by:** {interaction.user.mention}",
                color=0x43b581
            )
        else:
            embed = discord.Embed(
                title="❌ User Not Found",
                description=f"{user.mention} has no XP data to reset.",
                color=0xe74c3c
            )
        
    elif scope == "server":
        result = await db.users.delete_many({'guild_id': str(interaction.guild.id)})
        
        embed = discord.Embed(
            title="✅ Server XP Reset",
            description=f"**Action:** All XP data has been reset\n**Users affected:** {result.deleted_count}\n**Reset by:** {interaction.user.mention}",
            color=0x43b581
        )
    
    embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
    await interaction.response.send_message(embed=embed)
    
    from main import log_action
    await log_action(interaction.guild.id, "moderation", f"🔄 [XP RESET] {scope} reset by {interaction.user}")
