import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from main import bot
from brand_config import create_permission_denied_embed, create_owner_only_embed,  BOT_FOOTER, BrandColors, create_success_embed, create_error_embed, create_info_embed, create_command_embed, create_warning_embed
from main import has_permission, log_action
import os
from datetime import datetime, timedelta
import time

@bot.tree.command(name="say", description="Make the bot say something")
@app_commands.describe(
    message="Message to say",
    channel="Channel to send to (optional)",
    image="Image URL to attach (optional)",
    heading="Custom heading/title for the message (optional)"
)
async def say(interaction: discord.Interaction, message: str, channel: discord.TextChannel = None, image: str = None, heading: str = None):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    target_channel = channel or interaction.channel

    # If heading or image is provided, send as embed
    if heading or image:
        embed = discord.Embed(
            title=heading if heading else None,
            description=message,
            color=BrandColors.INFO
        )
        if image:
            # Basic URL validation
            if image.startswith(('http://', 'https://')) and any(ext in image.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                embed.set_image(url=image)
            else:
                await interaction.response.send_message(embed=create_error_embed("Invalid image URL! Please provide a valid image URL."), ephemeral=True)
                return

        embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
        await target_channel.send(embed=embed)
    else:
        await target_channel.send(message)

    embed = discord.Embed(
        title="✅ Message Sent",
        description=f"Message sent to {target_channel.mention}",
        color=BrandColors.SUCCESS
    )
    embed.set_footer(text=BOT_FOOTER)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    await log_action(interaction.guild.id, "communication", f"💬 [SAY] Message sent to {target_channel.name} by {interaction.user}")

@bot.tree.command(name="embed", description="Send a rich embed message")
@app_commands.describe(
    title="Embed title",
    description="Embed description",
    color="Embed color (hex or name)",
    channel="Channel to send to (optional)",
    image="Image URL to attach (optional)"
)
async def embed_command(
    interaction: discord.Interaction,
    title: str = None,
    description: str = None,
    color: str = "blue",
    channel: discord.TextChannel = None,
    image: str = None
):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
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
    
    if image:
        # Basic URL validation
        if image.startswith(('http://', 'https://')) and any(ext in image.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
            embed.set_image(url=image)
        else:
            await interaction.response.send_message(embed=create_error_embed("Invalid image URL! Please provide a valid image URL."), ephemeral=True)
            return

    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)

    await target_channel.send(embed=embed)

    response_embed = discord.Embed(
        title="✅ Embed Sent",
        description=f"Embed sent to {target_channel.mention}",
        color=BrandColors.SUCCESS
    )
    response_embed.set_footer(text=BOT_FOOTER)
    await interaction.response.send_message(embed=response_embed, ephemeral=True)

    await log_action(interaction.guild.id, "communication", f"📝 [EMBED] Embed sent to {target_channel.name} by {interaction.user}")

@bot.tree.command(name="announce", description="Send an announcement")
@app_commands.describe(
    channel="Channel to announce in",
    message="Announcement message",
    mention="Role or @everyone to mention (optional)",
    image="Image URL to attach (optional)",
    heading="Custom announcement heading (default: Server Announcement)"
)
async def announce(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
    mention: str = None,
    image: str = None,
    heading: str = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True)
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

    # Use custom heading or default
    announcement_title = heading if heading else "📢 **Server Announcement** 📢"
    
    embed = discord.Embed(
        title=announcement_title,
        description=message,
        color=BrandColors.WARNING
    )
    
    if image:
        # Basic URL validation
        if image.startswith(('http://', 'https://')) and any(ext in image.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
            embed.set_image(url=image)
        else:
            await interaction.response.send_message(embed=create_error_embed("Invalid image URL! Please provide a valid image URL."), ephemeral=True)
            return

    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)

    await channel.send(announcement_content, embed=embed)

    response_embed = discord.Embed(
        title="✅ Announcement Sent",
        description=f"Announcement sent to {channel.mention}",
        color=BrandColors.SUCCESS
    )
    response_embed.set_footer(text=BOT_FOOTER)
    await interaction.response.send_message(embed=response_embed, ephemeral=True)

    await log_action(interaction.guild.id, "communication", f"📢 [ANNOUNCEMENT] Announcement sent to {channel.name} by {interaction.user}")

# ═══════════════════════════════════════════════════════════════════════════
# INTERACTIVE POLL SYSTEM WITH BUTTONS
# ═══════════════════════════════════════════════════════════════════════════

class PollView(discord.ui.View):
    def __init__(self, question, options, allow_multiple, creator):
        super().__init__(timeout=None)  # Poll never times out
        self.question = question
        self.options = options
        self.allow_multiple = allow_multiple
        self.creator = creator
        self.votes = {i: set() for i in range(len(options))}  # Track voters for each option
        
        # Add buttons for each option
        button_styles = [
            discord.ButtonStyle.primary,   # Purple
            discord.ButtonStyle.primary,   # Purple
            discord.ButtonStyle.secondary, # Gray
            discord.ButtonStyle.secondary, # Gray
            discord.ButtonStyle.success,   # Green
            discord.ButtonStyle.success,   # Green
            discord.ButtonStyle.danger     # Red
        ]
        
        button_emojis = ["🟣", "💠", "⚡", "◆", "✦", "🔮", "⬡"]
        
        for i, option in enumerate(options):
            button = discord.ui.Button(
                label=f"Option {i+1}",
                style=button_styles[i],
                emoji=button_emojis[i],
                custom_id=f"poll_vote_{i}"
            )
            button.callback = self.create_vote_callback(i)
            self.add_item(button)
        
        # Add "View Results" button
        results_button = discord.ui.Button(
            label="View Results",
            style=discord.ButtonStyle.success,
            emoji="📊",
            custom_id="poll_results"
        )
        results_button.callback = self.view_results
        self.add_item(results_button)
    
    def create_vote_callback(self, option_index):
        async def vote_callback(interaction: discord.Interaction):
            user_id = interaction.user.id
            
            # Check if user is trying to vote multiple times
            if not self.allow_multiple:
                # Remove user's vote from all other options
                for i in range(len(self.options)):
                    if user_id in self.votes[i]:
                        self.votes[i].discard(user_id)
            
            # Toggle vote
            if user_id in self.votes[option_index]:
                self.votes[option_index].discard(user_id)
                action = "removed"
            else:
                self.votes[option_index].add(user_id)
                action = "added"
            
            # Update the poll embed
            await self.update_poll_embed(interaction.message)
            
            # Send ephemeral response
            option_text = self.options[option_index]
            emoji = ["🟣", "💠", "⚡", "◆", "✦", "🔮", "⬡"][option_index]
            
            if action == "added":
                response = discord.Embed(
                    title="✅ Vote Recorded",
                    description=f"**You voted for:**\n{emoji} {option_text}",
                    color=BrandColors.SUCCESS
                )
            else:
                response = discord.Embed(
                    title="🔄 Vote Removed",
                    description=f"**You removed your vote from:**\n{emoji} {option_text}",
                    color=BrandColors.WARNING
                )
            
            response.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=response, ephemeral=True)
        
        return vote_callback
    
    async def view_results(self, interaction: discord.Interaction):
        """Show detailed poll results"""
        total_votes = sum(len(voters) for voters in self.votes.values())
        
        results_embed = discord.Embed(
            title="📊 **Detailed Poll Results**",
            description=f"**❓ {self.question}**\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=BrandColors.PRIMARY
        )
        
        # Show results for each option
        for i, option in enumerate(self.options):
            vote_count = len(self.votes[i])
            percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
            
            # Create progress bar
            bar_length = 15
            filled = int(bar_length * percentage / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            emoji = ["🟣", "💠", "⚡", "◆", "✦", "🔮", "⬡"][i]
            
            results_embed.add_field(
                name=f"{emoji} **Option {i+1}:** {option}",
                value=f"`{bar}` {vote_count} votes ({percentage:.1f}%)",
                inline=False
            )
        
        # Add total votes
        vote_mode = "🔄 Multiple votes allowed" if self.allow_multiple else "⚡ Single vote only"
        results_embed.add_field(
            name="📈 Statistics",
            value=f"**Total Votes:** {total_votes}\n**Mode:** {vote_mode}\n**Created by:** {self.creator.mention}",
            inline=False
        )
        
        results_embed.set_footer(text=BOT_FOOTER, icon_url=interaction.user.display_avatar.url)
        
        await interaction.response.send_message(embed=results_embed, ephemeral=True)
    
    async def update_poll_embed(self, message):
        """Update the poll embed with current results"""
        total_votes = sum(len(voters) for voters in self.votes.values())
        
        # Create updated embed
        embed = discord.Embed(
            title="⚡ **Quantum Poll Active**",
            description=f"**❓ {self.question}**\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=BrandColors.PRIMARY
        )
        
        # Add options
        options_text = ""
        for i, option in enumerate(self.options):
            emoji = ["🟣", "💠", "⚡", "◆", "✦", "🔮", "⬡"][i]
            options_text += f"{emoji} **Option {i+1}:** {option}\n"
        
        embed.add_field(
            name="📋 Vote Options",
            value=options_text,
            inline=False
        )
        
        # Add voting mode
        vote_mode = "🔄 **Multiple votes allowed**" if self.allow_multiple else "⚡ **Single vote only**"
        embed.add_field(
            name="🎯 Voting Mode",
            value=vote_mode,
            inline=False
        )
        
        # Add results preview
        if total_votes == 0:
            results_text = "*No votes yet - Click buttons below to vote!*"
        else:
            results_text = ""
            for i, option in enumerate(self.options):
                vote_count = len(self.votes[i])
                percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
                bar_length = 10
                filled = int(bar_length * percentage / 100)
                bar = "█" * filled + "░" * (bar_length - filled)
                emoji = ["🟣", "💠", "⚡", "◆", "✦", "🔮", "⬡"][i]
                results_text += f"{emoji} `{bar}` {vote_count} ({percentage:.0f}%)\n"
            
            results_text += f"\n**💠 Total Votes:** {total_votes}"
        
        embed.add_field(
            name="📊 Results",
            value=results_text,
            inline=False
        )
        
        embed.set_footer(text=f"{BOT_FOOTER} • Poll by {self.creator.display_name}", icon_url=self.creator.display_avatar.url)
        
        await message.edit(embed=embed, view=self)

@bot.tree.command(name="poll", description="⚡ Create an interactive poll with buttons")
@app_commands.describe(
    question="Poll question",
    option1="First option",
    option2="Second option",
    option3="Third option (optional)",
    option4="Fourth option (optional)",
    option5="Fifth option (optional)",
    option6="Sixth option (optional)",
    option7="Seventh option (optional)",
    multiple_votes="Allow users to vote for multiple options (default: No)"
)
@app_commands.choices(multiple_votes=[
    app_commands.Choice(name="Yes - Allow multiple votes", value="yes"),
    app_commands.Choice(name="No - One vote only", value="no")
])
async def poll(
    interaction: discord.Interaction,
    question: str,
    option1: str,
    option2: str,
    option3: str = None,
    option4: str = None,
    option5: str = None,
    option6: str = None,
    option7: str = None,
    multiple_votes: str = "no"
):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    # Collect options
    options = [option1, option2]
    if option3:
        options.append(option3)
    if option4:
        options.append(option4)
    if option5:
        options.append(option5)
    if option6:
        options.append(option6)
    if option7:
        options.append(option7)

    # Create poll view
    allow_multiple = (multiple_votes == "yes")
    poll_view = PollView(question, options, allow_multiple, interaction.user)

    # Create quantum-themed poll embed
    embed = discord.Embed(
        title="⚡ **Quantum Poll Active**",
        description=f"**❓ {question}**\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        color=BrandColors.PRIMARY
    )

    # Add options with quantum styling
    options_text = ""
    for i, option in enumerate(options):
        emoji = ["🟣", "💠", "⚡", "◆", "✦", "🔮", "⬡"][i]
        options_text += f"{emoji} **Option {i+1}:** {option}\n"
    
    embed.add_field(
        name="📋 Vote Options",
        value=options_text,
        inline=False
    )

    # Add voting rules
    vote_mode = "🔄 **Multiple votes allowed**" if allow_multiple else "⚡ **Single vote only**"
    embed.add_field(
        name="🎯 Voting Mode",
        value=vote_mode,
        inline=False
    )

    embed.add_field(
        name="📊 Results",
        value="*No votes yet - Click buttons below to vote!*",
        inline=False
    )

    embed.set_footer(text=f"{BOT_FOOTER} • Poll by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

    await interaction.response.send_message(embed=embed, view=poll_view)
    
    await log_action(interaction.guild.id, "communication", f"📊 [POLL] Interactive poll created by {interaction.user}: {question}")

@bot.tree.command(name="reminder", description="Set a reminder")
@app_commands.describe(
    message="Reminder message",
    time="Time (e.g., 1h30m, 45s, 2h)"
)
async def reminder(interaction: discord.Interaction, message: str, time: str):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    # Parse time
    import re
    time_regex = re.compile(r'(\d+)([smhd])')
    matches = time_regex.findall(time.lower())

    if not matches:
        await interaction.response.send_message(embed=create_error_embed("Invalid time format! Use format like: 1h30m, 45s, 2h"), ephemeral=True)
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
        await interaction.response.send_message(embed=create_error_embed("Maximum reminder time is 7 days!"), ephemeral=True)
        return

    embed = discord.Embed(
        title="⏰ Reminder Set",
        description=f"I'll remind you about: **{message}**\nIn: **{time}**",
        color=BrandColors.SUCCESS
    )
    embed.set_footer(text=BOT_FOOTER)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # Set reminder
    await asyncio.sleep(total_seconds)

    reminder_content = f"**{message}**"
    reminder_embed = discord.Embed(
        title="⏰ Reminder",
        description=reminder_content,
        color=BrandColors.WARNING
    )
    reminder_embed.set_footer(text=BOT_FOOTER)

    try:
        await interaction.user.send(embed=reminder_embed)
        # Log DM sent
        from advanced_logging import log_dm_sent
        await log_dm_sent(interaction.user, reminder_content, interaction.guild)
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
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True)
        return

    try:
        embed = discord.Embed(
            title=f"📩 Message from {interaction.guild.name}",
            description=message,
            color=BrandColors.INFO
        )
        embed.set_footer(text=BOT_FOOTER)

        await user.send(embed=embed)
        # Log DM sent
        from advanced_logging import log_dm_sent
        await log_dm_sent(user, message, interaction.guild)

        response_embed = discord.Embed(
            title="✅ DM Sent",
            description=f"DM sent to {user.mention}",
            color=BrandColors.SUCCESS
        )
        response_embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=response_embed, ephemeral=True)

        await log_action(interaction.guild.id, "communication", f"📨 [DM] DM sent to {user} by {interaction.user}")

    except discord.Forbidden:
        await interaction.response.send_message(embed=create_error_embed("Cannot send DM to this user (DMs might be disabled)"), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

# Help and contact commands are handled in main.py to avoid duplicates

# IMPORTANT: This on_message handler was OVERRIDING the main one in main.py
# causing the bot to ignore all messages except "reaction role setup"
# Commented out to fix AI chat and all other message handling

# @bot.event
# async def on_message(message):
#     if message.author == bot.user:
#         return
#
#     # Reaction Role Setup Command
#     if message.content.startswith("reaction role setup"):
#         if not await has_permission(message, "main_moderator"):
#             await message.channel.send("Main Moderator")
#             return
#
#         await message.channel.send("Please provide the message, emoji, role, and channel for the reaction role.")
#         await message.channel.send("Optional: Specify if 'remove role' should be enabled and the role to remove.")
#
#         def check(m):
#             return m.author == message.author and m.channel == message.channel
#
#         try:
#             # Get message
#             msg_prompt = await bot.wait_for("message", check=check, timeout=60)
#             message_content = msg_prompt.content
#             message_to_react = await bot.get_channel(message.channel.id).fetch_message(int(message_content.split(' ')[0])) # Assuming message ID is first
#
#             # Get emoji
#             emoji_prompt = await bot.wait_for("message", check=check, timeout=60)
#             emoji_str = emoji_prompt.content
#
#             # Get role
#             role_prompt = await bot.wait_for("message", check=check, timeout=60)
#             role_name = role_prompt.content
#             guild = message.guild
#             role = discord.utils.get(guild.roles, name=role_name)
#             if not role:
#                 await message.channel.send(f"❌ Role '{role_name}' not found.")
#                 return
#
#             # Get channel
#             channel_prompt = await bot.wait_for("message", check=check, timeout=60)
#             channel_name = channel_prompt.content
#             target_channel = discord.utils.get(guild.text_channels, name=channel_name)
#             if not target_channel:
#                 await message.channel.send(f"❌ Channel '{channel_name}' not found.")
#                 return
#
#             # Get remove role option
#             remove_role_prompt = await bot.wait_for("message", check=check, timeout=60)
#             remove_role_enabled = remove_role_prompt.content.lower() == 'yes'
#             role_to_remove = None
#
#             if remove_role_enabled:
#                 remove_role_prompt_2 = await bot.wait_for("message", check=check, timeout=60)
#                 role_to_remove_name = remove_role_prompt_2.content
#                 role_to_remove = discord.utils.get(guild.roles, name=role_to_remove_name)
#                 if not role_to_remove:
#                     await message.channel.send(f"❌ Role to remove '{role_to_remove_name}' not found.")
#                     return
#
#             # Add reaction to the message
#             try:
#                 await message_to_react.add_reaction(emoji_str)
#             except discord.HTTPException:
#                 await message.channel.send("❌ Invalid emoji provided.")
#                 return
#
#             # Store reaction role data (you'll need a persistent storage for this)
#             # For now, we'll just log it
#             log_data = {
#                 "message_id": message_to_react.id,
#                 "emoji": emoji_str,
#                 "role_id": role.id,
#                 "channel_id": target_channel.id,
#                 "remove_role_enabled": remove_role_enabled,
#                 "role_to_remove_id": role_to_remove.id if role_to_remove else None
#             }
#             print(f"Reaction role setup: {log_data}") # Replace with actual storage
#
#             await message.channel.send("Reaction role setup complete!")
#
#         except asyncio.TimeoutError:
#             await message.channel.send("❌ Timeout. Please try the command again.")
#         except Exception as e:
#             await message.channel.send(f"❌ An error occurred: {e}")



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
                    print(f"Assigned role {role_to_assign.name} to {member.display_name}") # Logging

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

# Contact command is handled in main.py to avoid duplicates

@bot.tree.command(name="print-channel", description="📄 Export channel messages to file and send via DM")
@app_commands.describe(
    format="Export format (txt or pdf)"
)
async def print_channel(interaction: discord.Interaction, format: str = "txt"):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Server Owner or Main Moderator"), ephemeral=True)
        return
    
    if format.lower() not in ["txt", "pdf"]:
        await interaction.response.send_message(embed=create_error_embed("Invalid format! Use: txt or pdf"), ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user
        from datetime import datetime
        
        messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
        
        if not messages:
            await interaction.followup.send(embed=create_warning_embed("No messages found in this channel"), ephemeral=True)
            return
        
        import io
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"RXT ENGINE — Channel Transcript\n\nServer: {guild.name}\nChannel: #{channel.name}\nGenerated By: {user.name}\nDate: {timestamp}\n\n{'='*60}\n\n"
        
        content = header
        for msg in messages:
            time_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author_name = msg.author.name
            if msg.author.bot:
                author_name = f"🤖 {author_name}"
            content += f"[{time_str}] {author_name}: {msg.content}\n"
            
            if msg.embeds:
                for embed in msg.embeds:
                    content += "  📋 [EMBED]\n"
                    if embed.title:
                        content += f"    Title: {embed.title}\n"
                    if embed.description:
                        content += f"    Description: {embed.description}\n"
                    if embed.fields:
                        for field in embed.fields:
                            content += f"    {field.name}: {field.value}\n"
            
            if msg.attachments:
                for att in msg.attachments:
                    content += f"  📎 Attachment: {att.url}\n"
            content += "\n"
        
        filename = f"{guild.name}_{channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        
        if format.lower() == "pdf":
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas
                
                buffer = io.BytesIO()
                c = canvas.Canvas(buffer, pagesize=letter)
                c.setFont("Helvetica", 10)
                
                y = 750
                for line in content.split('\n'):
                    if y < 50:
                        c.showPage()
                        y = 750
                    c.drawString(50, y, line[:90])
                    y -= 12
                
                c.save()
                buffer.seek(0)
                file_obj = discord.File(buffer, filename=filename)
            except Exception as e:
                await interaction.followup.send(embed=create_warning_embed(f"PDF export failed, using TXT instead"), ephemeral=True)
                file_obj = discord.File(io.BytesIO(content.encode()), filename=filename.replace(".pdf", ".txt"))
        else:
            file_obj = discord.File(io.BytesIO(content.encode()), filename=filename)
        
        try:
            await user.send(f"📄 **{guild.name}** - **#{channel.name}** transcript ({len(messages)} messages)", file=file_obj)
            await interaction.followup.send(embed=create_success_embed(f"✅ Transcript sent to your DMs!"), ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(embed=create_warning_embed("❌ Cannot send DM - your DMs are closed."), ephemeral=True)
        
        await log_action(guild.id, "communication", f"📄 [PRINT-CHANNEL] {user.name} exported #{channel.name} ({len(messages)} messages, format: {format})")
        
    except Exception as e:
        await interaction.followup.send(embed=create_error_embed(f"Export failed: {str(e)}"), ephemeral=True)
        print(f"❌ [PRINT-CHANNEL ERROR] {e}")
