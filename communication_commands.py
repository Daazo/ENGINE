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
    embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
    await interaction.response.send_message(embed=embed, ephemeral=True)

    await log_action(interaction.guild.id, "communication", f"💬 [SAY] Message sent to {target_channel.name} by {interaction.user}")

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
    embed.set_footer(text="ᴠᴀᴀᴢʜᴀ", icon_url=bot.user.display_avatar.url)

    await target_channel.send(embed=embed)

    response_embed = discord.Embed(
        title="✅ Embed Sent",
        description=f"Embed sent to {target_channel.mention}",
        color=0x43b581
    )
    response_embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
    await interaction.response.send_message(embed=response_embed, ephemeral=True)

    await log_action(interaction.guild.id, "communication", f"📝 [EMBED] Embed sent to {target_channel.name} by {interaction.user}")

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
        title="📢 **Server Announcement** 📢",
        description=message,
        color=0xf39c12
    )
    embed.set_footer(text="ᴠᴀᴀᴢʜᴀ", icon_url=bot.user.display_avatar.url)

    await channel.send(announcement_content, embed=embed)

    response_embed = discord.Embed(
        title="✅ Announcement Sent",
        description=f"Announcement sent to {channel.mention}",
        color=0x43b581
    )
    response_embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
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
    embed.set_footer(text="ᴠᴀᴀᴢʜᴀ", icon_url=bot.user.display_avatar.url)

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
    embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # Set reminder
    await asyncio.sleep(total_seconds)

    reminder_embed = discord.Embed(
        title="⏰ Reminder",
        description=f"**{message}**",
        color=0xf39c12
    )
    reminder_embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")

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
            title=f"📩 Message from {interaction.guild.name}",
            description=message,
            color=0x3498db
        )
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")

        await user.send(embed=embed)

        response_embed = discord.Embed(
            title="✅ DM Sent",
            description=f"DM sent to {user.mention}",
            color=0x43b581
        )
        response_embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
        await interaction.response.send_message(embed=response_embed, ephemeral=True)

        await log_action(interaction.guild.id, "communication", f"📨 [DM] DM sent to {user} by {interaction.user}")

    except discord.Forbidden:
        await interaction.response.send_message("❌ Cannot send DM to this user (DMs might be disabled)", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

# Help and contact commands are handled in main.py to avoid duplicates

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Reaction Role Setup Command
    if message.content.startswith("reaction role setup"):
        if not await has_permission(message, "main_moderator"):
            await message.channel.send("❌ You need Main Moderator permissions to use this command!")
            return

        await message.channel.send("Please provide the message, emoji, role, and channel for the reaction role.")
        await message.channel.send("Optional: Specify if 'remove role' should be enabled and the role to remove.")

        def check(m):
            return m.author == message.author and m.channel == message.channel

        try:
            # Get message
            msg_prompt = await bot.wait_for("message", check=check, timeout=60)
            message_content = msg_prompt.content
            message_to_react = await bot.get_channel(message.channel.id).fetch_message(int(message_content.split(' ')[0])) # Assuming message ID is first

            # Get emoji
            emoji_prompt = await bot.wait_for("message", check=check, timeout=60)
            emoji_str = emoji_prompt.content

            # Get role
            role_prompt = await bot.wait_for("message", check=check, timeout=60)
            role_name = role_prompt.content
            guild = message.guild
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                await message.channel.send(f"❌ Role '{role_name}' not found.")
                return

            # Get channel
            channel_prompt = await bot.wait_for("message", check=check, timeout=60)
            channel_name = channel_prompt.content
            target_channel = discord.utils.get(guild.text_channels, name=channel_name)
            if not target_channel:
                await message.channel.send(f"❌ Channel '{channel_name}' not found.")
                return

            # Get remove role option
            remove_role_prompt = await bot.wait_for("message", check=check, timeout=60)
            remove_role_enabled = remove_role_prompt.content.lower() == 'yes'
            role_to_remove = None

            if remove_role_enabled:
                remove_role_prompt_2 = await bot.wait_for("message", check=check, timeout=60)
                role_to_remove_name = remove_role_prompt_2.content
                role_to_remove = discord.utils.get(guild.roles, name=role_to_remove_name)
                if not role_to_remove:
                    await message.channel.send(f"❌ Role to remove '{role_to_remove_name}' not found.")
                    return

            # Add reaction to the message
            try:
                await message_to_react.add_reaction(emoji_str)
            except discord.HTTPException:
                await message.channel.send("❌ Invalid emoji provided.")
                return

            # Store reaction role data (you'll need a persistent storage for this)
            # For now, we'll just log it
            log_data = {
                "message_id": message_to_react.id,
                "emoji": emoji_str,
                "role_id": role.id,
                "channel_id": target_channel.id,
                "remove_role_enabled": remove_role_enabled,
                "role_to_remove_id": role_to_remove.id if role_to_remove else None
            }
            print(f"Reaction role setup: {log_data}") # Replace with actual storage

            await message.channel.send("Reaction role setup complete!")

        except asyncio.TimeoutError:
            await message.channel.send("❌ Timeout. Please try the command again.")
        except Exception as e:
            await message.channel.send(f"❌ An error occurred: {e}")

    # Forward bot DMs to contact info if it's a DM to the bot
    if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
        await contact_command(message) # Call the contact command to send info


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return

    # Retrieve reaction role data (replace with your actual storage retrieval)
    # Example: reaction_roles = get_reaction_roles_from_storage()
    reaction_roles = {
        # message_id: {"emoji": emoji_str, "role_id": role_id, "channel_id": channel_id, "remove_role_enabled": bool, "role_to_remove_id": role_to_remove_id}
    }
    # Dummy data for testing, replace with actual storage
    # This needs to be populated when the reaction role setup command is used
    # For example:
    # reaction_roles[123456789012345678] = {"emoji": "👍", "role_id": 987654321098765432, "channel_id": 112233445566778899, "remove_role_enabled": False, "role_to_remove_id": None}
    # reaction_roles[876543210987654321] = {"emoji": "⭐", "role_id": 123456789012345678, "channel_id": 112233445566778899, "remove_role_enabled": True, "role_to_remove_id": 101010101010101010}


    if payload.message_id in reaction_roles:
        role_data = reaction_roles[payload.message_id]
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        emoji = str(payload.emoji)

        if emoji == role_data["emoji"]:
            role_to_assign = guild.get_role(role_data["role_id"])
            if not role_to_assign:
                return

            if role_data["remove_role_enabled"]:
                role_to_remove = guild.get_role(role_data["role_to_remove_id"])
                if role_to_remove and role_to_remove in member.roles:
                    await member.remove_roles(role_to_remove)

            if role_to_assign not in member.roles:
                await member.add_roles(role_to_assign)
                print(f"Assigned role {role_to_assign.name} to {member.display_name}") # Logging

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return

    # Retrieve reaction role data (replace with your actual storage retrieval)
    reaction_roles = {
        # message_id: {"emoji": emoji_str, "role_id": role_id, "channel_id": channel_id, "remove_role_enabled": bool, "role_to_remove_id": role_to_remove_id}
    }
    # Dummy data for testing, replace with actual storage

    if payload.message_id in reaction_roles:
        role_data = reaction_roles[payload.message_id]
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        emoji = str(payload.emoji)

        if emoji == role_data["emoji"]:
            role_to_assign = guild.get_role(role_data["role_id"])
            if not role_to_assign:
                return

            if role_to_assign in member.roles:
                await member.remove_roles(role_to_assign)
                print(f"Removed role {role_to_assign.name} from {member.display_name}") # Logging

            if role_data["remove_role_enabled"]:
                role_to_remove = guild.get_role(role_data["role_to_remove_id"])
                if role_to_remove and role_to_remove in member.roles:
                    await member.remove_roles(role_to_remove)
                    print(f"Removed role {role_to_remove.name} from {member.display_name}") # Logging