
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from main import bot, has_permission, log_action

@bot.tree.command(name="say", description="Make the bot say something")
@app_commands.describe(message="Message to say", channel="Channel to send to (optional)")
async def say(interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    target_channel = channel or interaction.channel
    
    await target_channel.send(message)
    
    embed = discord.Embed(
        title="✅ Message Sent",
        description=f"Message sent to {target_channel.mention}",
        color=0x43b581
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    await log_action(interaction.guild.id, "communication", f"📢 [SAY] Message sent to {target_channel.name} by {interaction.user}")

@bot.tree.command(name="embed", description="Send a rich embed message")
@app_commands.describe(
    title="Embed title",
    description="Embed description", 
    color="Embed color (hex or name)",
    channel="Channel to send to (optional)"
)
async def embed_command(
    interaction: discord.Interaction, 
    title: str = None,
    description: str = None,
    color: str = "blue",
    channel: discord.TextChannel = None
):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    target_channel = channel or interaction.channel
    
    # Parse color
    color_map = {
        "red": 0xe74c3c,
        "green": 0x43b581,
        "blue": 0x3498db,
        "yellow": 0xf1c40f,
        "purple": 0x9b59b6,
        "orange": 0xe67e22
    }
    
    if color.lower() in color_map:
        embed_color = color_map[color.lower()]
    elif color.startswith("#"):
        try:
            embed_color = int(color[1:], 16)
        except:
            embed_color = 0x3498db
    else:
        embed_color = 0x3498db
    
    embed = discord.Embed(color=embed_color)
    
    if title:
        embed.title = title
    if description:
        embed.description = description
    
    await target_channel.send(embed=embed)
    
    response_embed = discord.Embed(
        title="✅ Embed Sent",
        description=f"Embed sent to {target_channel.mention}",
        color=0x43b581
    )
    await interaction.response.send_message(embed=response_embed, ephemeral=True)
    
    await log_action(interaction.guild.id, "communication", f"📢 [EMBED] Embed sent to {target_channel.name} by {interaction.user}")

@bot.tree.command(name="announce", description="Send an announcement")
@app_commands.describe(
    channel="Channel to announce in",
    message="Announcement message",
    mention="Role or @everyone to mention (optional)"
)
async def announce(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
    mention: str = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    announcement_content = ""
    
    if mention:
        if mention.lower() == "@everyone":
            announcement_content = "@everyone\n"
        else:
            # Try to find role by name
            role = discord.utils.get(interaction.guild.roles, name=mention)
            if role:
                announcement_content = f"{role.mention}\n"
    
    embed = discord.Embed(
        title="📢 Announcement",
        description=message,
        color=0xf39c12
    )
    embed.set_footer(text=f"Announced by {interaction.user.display_name}")
    
    await channel.send(announcement_content, embed=embed)
    
    response_embed = discord.Embed(
        title="✅ Announcement Sent",
        description=f"Announcement sent to {channel.mention}",
        color=0x43b581
    )
    await interaction.response.send_message(embed=response_embed, ephemeral=True)
    
    await log_action(interaction.guild.id, "communication", f"📢 [ANNOUNCEMENT] Announcement sent to {channel.name} by {interaction.user}")

@bot.tree.command(name="poll", description="Create a poll")
@app_commands.describe(
    question="Poll question",
    option1="First option",
    option2="Second option",
    option3="Third option (optional)",
    option4="Fourth option (optional)"
)
async def poll(
    interaction: discord.Interaction,
    question: str,
    option1: str,
    option2: str,
    option3: str = None,
    option4: str = None
):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    options = [option1, option2]
    if option3:
        options.append(option3)
    if option4:
        options.append(option4)
    
    embed = discord.Embed(
        title="📊 Poll",
        description=f"**{question}**\n\n" + "\n".join([f"{chr(0x1f1e6 + i)} {option}" for i, option in enumerate(options)]),
        color=0x3498db
    )
    embed.set_footer(text=f"Poll created by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    
    # Add reactions
    for i in range(len(options)):
        await message.add_reaction(chr(0x1f1e6 + i))
    
    await log_action(interaction.guild.id, "communication", f"📊 [POLL] Poll created by {interaction.user}: {question}")

@bot.tree.command(name="reminder", description="Set a reminder")
@app_commands.describe(
    message="Reminder message",
    time="Time (e.g., 1h30m, 45s, 2h)"
)
async def reminder(interaction: discord.Interaction, message: str, time: str):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    # Parse time
    import re
    time_regex = re.compile(r'(\d+)([smhd])')
    matches = time_regex.findall(time.lower())
    
    if not matches:
        await interaction.response.send_message("❌ Invalid time format! Use format like: 1h30m, 45s, 2h", ephemeral=True)
        return
    
    total_seconds = 0
    for amount, unit in matches:
        amount = int(amount)
        if unit == 's':
            total_seconds += amount
        elif unit == 'm':
            total_seconds += amount * 60
        elif unit == 'h':
            total_seconds += amount * 3600
        elif unit == 'd':
            total_seconds += amount * 86400
    
    if total_seconds > 86400 * 7:  # Max 7 days
        await interaction.response.send_message("❌ Maximum reminder time is 7 days!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="⏰ Reminder Set",
        description=f"I'll remind you about: **{message}**\nIn: **{time}**",
        color=0x43b581
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Set reminder
    await asyncio.sleep(total_seconds)
    
    reminder_embed = discord.Embed(
        title="⏰ Reminder",
        description=f"**{message}**",
        color=0xf39c12
    )
    
    try:
        await interaction.user.send(embed=reminder_embed)
    except:
        # If DM fails, try to send in channel
        try:
            await interaction.followup.send(f"{interaction.user.mention}", embed=reminder_embed)
        except:
            pass

@bot.tree.command(name="dm", description="Send a DM to a user")
@app_commands.describe(user="User to send DM to", message="Message to send")
async def dm_command(interaction: discord.Interaction, user: discord.Member, message: str):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    try:
        embed = discord.Embed(
            title=f"📨 Message from {interaction.guild.name}",
            description=message,
            color=0x3498db
        )
        embed.set_footer(text=f"Sent by {interaction.user.display_name}")
        
        await user.send(embed=embed)
        
        response_embed = discord.Embed(
            title="✅ DM Sent",
            description=f"DM sent to {user.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=response_embed, ephemeral=True)
        
        await log_action(interaction.guild.id, "communication", f"📨 [DM] DM sent to {user} by {interaction.user}")
    
    except discord.Forbidden:
        await interaction.response.send_message("❌ Cannot send DM to this user (DMs might be disabled)", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
