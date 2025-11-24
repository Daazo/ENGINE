import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from main import bot
from brand_config import create_permission_denied_embed, create_owner_only_embed,  BOT_FOOTER, BrandColors, create_success_embed, create_error_embed, create_info_embed, create_command_embed, create_warning_embed
from main import has_permission, log_action

@bot.tree.command(name="kick", description="⚔️ Kick a user from the server")
@app_commands.describe(user="User to kick", reason="Reason for kick")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True)
        return

    if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message(embed=create_error_embed("You cannot kick someone with equal or higher role!"), ephemeral=True)
        return

    try:
        # Send DM to user before kicking
        try:
            dm_embed = discord.Embed(
                title=f"⚔️ You were kicked from {interaction.guild.name}",
                description=f"**Reason:** {reason}\n**Moderator:** {interaction.user}",
                color=BrandColors.WARNING
            )
            dm_embed.set_footer(text=BOT_FOOTER)
            await user.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled

        await user.kick(reason=f"Kicked by {interaction.user}: {reason}")

        embed = discord.Embed(
            title="⚔️ User Kicked",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
            color=BrandColors.WARNING
        )
        embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

        await log_action(interaction.guild.id, "moderation", f"⚔️ [KICK] {user} kicked by {interaction.user} - Reason: {reason}")

        # Log to global per-server channel
        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**⚔️ Kick**\n**User:** {user}\n**Moderator:** {interaction.user}\n**Reason:** {reason}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message(embed=create_error_embed("I don't have permission to kick this user!"), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="ban", description="🔨 Ban a user from the server")
@app_commands.describe(user="User to ban", reason="Reason for ban")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True)
        return

    if user.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message(embed=create_error_embed("You cannot ban someone with equal or higher role!"), ephemeral=True)
        return

    try:
        # Send DM to user before banning
        try:
            dm_embed = discord.Embed(
                title=f"🔨 You were banned from {interaction.guild.name}",
                description=f"**Reason:** {reason}\n**Moderator:** {interaction.user}",
                color=BrandColors.DANGER
            )
            await user.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled

        await user.ban(reason=f"Banned by {interaction.user}: {reason}")

        embed = discord.Embed(
            title="🔨 User Banned",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
            color=BrandColors.DANGER
        )
        await interaction.response.send_message(embed=embed)

        await log_action(interaction.guild.id, "moderation", f"🔨 [BAN] {user} banned by {interaction.user} - Reason: {reason}")

        # Log to global per-server channel
        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔨 Ban**\n**User:** {user}\n**Moderator:** {interaction.user}\n**Reason:** {reason}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message(embed=create_error_embed("I don't have permission to ban this user!"), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="nuke", description="💥 Delete all messages in current channel")
async def nuke(interaction: discord.Interaction):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True)
        return

    # Confirmation embed
    embed = discord.Embed(
        title="⚠️ **DANGER: CHANNEL NUKE** ⚠️",
        description=f"**This will DELETE ALL messages in {interaction.channel.mention}!**\n**❌ This action CANNOT be undone!**\n**💀 All chat history will be permanently lost!**\n\n**Are you absolutely sure?**",
        color=BrandColors.DANGER
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
                description=f"**All messages have been deleted!**\n**Moderator:** {interaction.user.mention}\n**Time:** {discord.utils.format_dt(discord.utils.utcnow())}\n\n*This channel has been completely reset.*",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)

            await new_channel.send(embed=embed)

            await log_action(interaction.guild.id, "moderation", f"💥 [NUKE] Channel #{channel_name} nuked by {interaction.user}")

            # Log to global per-server channel
            try:
                from advanced_logging import send_global_log
                await send_global_log("moderation", f"**💥 Channel Nuke**\n**Channel:** #{channel_name}\n**Moderator:** {interaction.user}", interaction.guild)
            except:
                pass

        except Exception as e:
            print(f"Nuke error: {e}")

    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.secondary, emoji='❌')
    async def cancel_nuke(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✅ **Nuke Cancelled**",
            description="The channel nuke has been cancelled. No messages were deleted.",
            color=BrandColors.SUCCESS
        )
        await interaction.response.edit_message(embed=embed, view=None)