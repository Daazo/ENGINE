import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from main import bot, has_permission, log_action

@bot.tree.command(name="kick", description="👢 Kick a user from the server")
@app_commands.describe(user="User to kick", reason="Reason for kick")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ You cannot kick someone with equal or higher role!", ephemeral=True)
        return

    try:
        # Send DM to user before kicking
        try:
            dm_embed = discord.Embed(
                title=f"👢 You were kicked from {interaction.guild.name}",
                description=f"**Reason:** {reason}\n**Moderator:** {interaction.user}",
                color=0xf39c12
            )
            await user.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled

        await user.kick(reason=f"Kicked by {interaction.user}: {reason}")

        embed = discord.Embed(
            title="👢 User Kicked",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
            color=0xf39c12
        )
        await interaction.response.send_message(embed=embed)

        await log_action(interaction.guild.id, "moderation", f"👢 [KICK] {user} kicked by {interaction.user} - Reason: {reason}")

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to kick this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="ban", description="🔨 Ban a user from the server")
@app_commands.describe(user="User to ban", reason="Reason for ban")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ You cannot ban someone with equal or higher role!", ephemeral=True)
        return

    try:
        # Send DM to user before banning
        try:
            dm_embed = discord.Embed(
                title=f"🔨 You were banned from {interaction.guild.name}",
                description=f"**Reason:** {reason}\n**Moderator:** {interaction.user}",
                color=0xe74c3c
            )
            await user.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled

        await user.ban(reason=f"Banned by {interaction.user}: {reason}")

        embed = discord.Embed(
            title="🔨 User Banned",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed)

        await log_action(interaction.guild.id, "moderation", f"🔨 [BAN] {user} banned by {interaction.user} - Reason: {reason}")

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to ban this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="nuke", description="💥 Delete all messages in current channel")
async def nuke(interaction: discord.Interaction):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    # Confirmation embed
    embed = discord.Embed(
        title="⚠️ **DANGER: CHANNEL NUKE** ⚠️",
        description=f"**This will DELETE ALL messages in {interaction.channel.mention}!**\n\n**❌ This action CANNOT be undone!**\n**💀 All chat history will be permanently lost!**\n\n**Are you absolutely sure?**",
        color=0xe74c3c
    )

    view = NukeConfirmView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class NukeConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label='💥 CONFIRM NUKE', style=discord.ButtonStyle.danger, emoji='💥')
    async def confirm_nuke(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await has_permission(interaction, "main_moderator"):
            await interaction.response.send_message("❌ You need Main Moderator permissions!", ephemeral=True)
            return

        channel = interaction.channel
        channel_name = channel.name
        channel_topic = channel.topic
        channel_category = channel.category
        channel_overwrites = channel.overwrites

        await interaction.response.send_message("💥 **NUKING CHANNEL...** 💥", ephemeral=True)

        try:
            # Delete the channel
            await channel.delete(reason=f"Channel nuked by {interaction.user}")

            # Recreate the channel
            new_channel = await channel_category.create_text_channel(
                name=channel_name,
                topic=channel_topic,
                overwrites=channel_overwrites,
                reason=f"Channel recreated after nuke by {interaction.user}"
            )

            # Send confirmation in new channel
            embed = discord.Embed(
                title="💥 **Channel Nuked Successfully** 💥",
                description=f"**All messages have been deleted!**\n\n**Moderator:** {interaction.user.mention}\n**Time:** {discord.utils.format_dt(discord.utils.utcnow())}\n\n*This channel has been completely reset.*",
                color=0xe74c3c
            )
            embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ Moderation", icon_url=interaction.client.user.display_avatar.url)

            await new_channel.send(embed=embed)

            await log_action(interaction.guild.id, "moderation", f"💥 [NUKE] Channel #{channel_name} nuked by {interaction.user}")

        except Exception as e:
            print(f"Nuke error: {e}")

    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.secondary, emoji='❌')
    async def cancel_nuke(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✅ **Nuke Cancelled**",
            description="The channel nuke has been cancelled. No messages were deleted.",
            color=0x43b581
        )
        await interaction.response.edit_message(embed=embed, view=None)