
import discord
from discord.ext import commands
from discord import app_commands
from main import bot
from brand_config import create_permission_denied_embed, create_owner_only_embed,  BOT_FOOTER, BrandColors, create_success_embed, create_error_embed, create_info_embed, create_command_embed, create_warning_embed
from main import has_permission, log_action

@bot.tree.command(name="mute", description="🔇 Mute user in voice channel")
@app_commands.describe(user="User to mute")
async def mute(interaction: discord.Interaction, user: discord.Member):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not user.voice:
        await interaction.response.send_message("❌ User is not in a voice channel!", ephemeral=True)
        return

    try:
        await user.edit(mute=True)

        embed = discord.Embed(
            title="🔇 User Muted",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.WARNING
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🔇 [MUTE] {user} muted by {interaction.user}")

        # Log to global per-server channel
        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔇 Mute**\n**User:** {user}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to mute this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="unmute", description="🔊 Unmute user in voice channel")
@app_commands.describe(user="User to unmute")
async def unmute(interaction: discord.Interaction, user: discord.Member):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not user.voice:
        await interaction.response.send_message("❌ User is not in a voice channel!", ephemeral=True)
        return

    try:
        await user.edit(mute=False)

        embed = discord.Embed(
            title="🔊 User Unmuted",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.SUCCESS
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🔊 [UNMUTE] {user} unmuted by {interaction.user}")

        # Log to global per-server channel
        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔊 Unmute**\n**User:** {user}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to unmute this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="movevc", description="Move user to different voice channel")
@app_commands.describe(user="User to move", channel="Voice channel to move to")
async def movevc(interaction: discord.Interaction, user: discord.Member, channel: discord.VoiceChannel):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not user.voice:
        await interaction.response.send_message("❌ User is not in a voice channel!", ephemeral=True)
        return

    try:
        await user.move_to(channel)

        embed = discord.Embed(
            title="🔀 User Moved",
            description=f"**User:** {user.mention}\n**Moved to:** {channel.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.SUCCESS
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🛡 [MOVE VC] {user} moved to {channel.name} by {interaction.user}")

        # Log to global per-server channel
        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔀 Move VC**\n**User:** {user}\n**Moved to:** {channel.mention}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to move this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="vckick", description="Kick user from voice channel")
@app_commands.describe(user="User to kick from voice")
async def vckick(interaction: discord.Interaction, user: discord.Member):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not user.voice:
        await interaction.response.send_message("❌ User is not in a voice channel!", ephemeral=True)
        return

    try:
        await user.move_to(None)

        embed = discord.Embed(
            title="👢 User Kicked from VC",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.WARNING
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🛡 [VC KICK] {user} kicked from voice by {interaction.user}")

        # Log to global per-server channel
        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**👢 VC Kick**\n**User:** {user}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to disconnect this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="vclock", description="Lock current voice channel")
async def vclock(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not interaction.user.voice:
        await interaction.response.send_message("❌ You need to be in a voice channel to use this command!", ephemeral=True)
        return

    channel = interaction.user.voice.channel

    try:
        await channel.set_permissions(interaction.guild.default_role, connect=False)

        embed = discord.Embed(
            title="🔒 Voice Channel Locked",
            description=f"**Channel:** {channel.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.DANGER
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🛡 [VC LOCK] {channel.name} locked by {interaction.user}")

        # Log to global per-server channel
        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔒 VC Lock**\n**Channel:** {channel.mention}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to modify this channel!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="vcunlock", description="Unlock current voice channel")
async def vcunlock(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not interaction.user.voice:
        await interaction.response.send_message("❌ You need to be in a voice channel to use this command!", ephemeral=True)
        return

    channel = interaction.user.voice.channel

    try:
        await channel.set_permissions(interaction.guild.default_role, connect=None)

        embed = discord.Embed(
            title="🔓 Voice Channel Unlocked",
            description=f"**Channel:** {channel.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.SUCCESS
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🛡 [VC UNLOCK] {channel.name} unlocked by {interaction.user}")

        # Log to global per-server channel
        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔓 VC Unlock**\n**Channel:** {channel.mention}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to modify this channel!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="vclimit", description="Set voice channel user limit")
@app_commands.describe(limit="User limit (0-99, 0 = unlimited)")
async def vclimit(interaction: discord.Interaction, limit: int):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not interaction.user.voice:
        await interaction.response.send_message("❌ You need to be in a voice channel to use this command!", ephemeral=True)
        return

    if limit < 0 or limit > 99:
        await interaction.response.send_message("❌ Limit must be between 0-99 (0 = unlimited)!", ephemeral=True)
        return

    channel = interaction.user.voice.channel

    try:
        await channel.edit(user_limit=limit)

        limit_text = "Unlimited" if limit == 0 else str(limit)
        embed = discord.Embed(
            title="🔢 Voice Channel Limit Set",
            description=f"**Channel:** {channel.mention}\n**Limit:** {limit_text} users\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.INFO
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🛡 [VC LIMIT] {channel.name} limit set to {limit_text} by {interaction.user}")

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to modify this channel!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
