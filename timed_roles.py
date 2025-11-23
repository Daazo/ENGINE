import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import re
from main import bot
from brand_config import create_permission_denied_embed, create_owner_only_embed,  BOT_FOOTER, BrandColors
from main import has_permission, get_server_data, update_server_data, log_action, db

# Background task to check for expired roles
@tasks.loop(minutes=1)
async def check_expired_roles():
    """Check for expired timed roles every minute"""
    if db is None:
        return

    try:
        # Get all expired timed roles
        expired_roles = await db.timed_roles.find({
            'expires_at': {'$lte': datetime.utcnow()}
        }).to_list(length=None)

        for role_data in expired_roles:
            try:
                guild = bot.get_guild(int(role_data['guild_id']))
                if not guild:
                    # Remove from database if guild not found
                    await db.timed_roles.delete_one({'_id': role_data['_id']})
                    continue

                member = guild.get_member(int(role_data['user_id']))
                role = guild.get_role(int(role_data['role_id']))

                if member and role and role in member.roles:
                    await member.remove_roles(role, reason="Timed role expired")

                    # Send notification to user
                    try:
                        dm_content = f"Your **{role.name}** role in **{guild.name}** has expired and been removed."
                        embed = discord.Embed(
                            title="⏰ **Timed Role Expired**",
                            description=dm_content,
                            color=BrandColors.WARNING
                        )
                        embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
                        await member.send(embed=embed)
                        # Log DM sent
                        from advanced_logging import log_dm_sent
                        await log_dm_sent(member, dm_content, guild)
                    except:
                        pass  # User has DMs disabled

                    await log_action(guild.id, "timed_roles", f"⏰ [TIMED ROLE] {role.name} automatically removed from {member} (expired)")

                # Remove from database
                await db.timed_roles.delete_one({'_id': role_data['_id']})

            except Exception as e:
                print(f"Error processing expired role: {e}")
                # Remove problematic entry
                await db.timed_roles.delete_one({'_id': role_data['_id']})

    except Exception as e:
        print(f"Error in check_expired_roles: {e}")

def parse_duration(duration_str):
    """Parse duration string like '1h30m', '2d', '45s' into seconds"""
    duration_str = duration_str.lower().strip()

    # Regex to match patterns like 1d2h30m45s
    pattern = r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?'
    match = re.match(pattern, duration_str)

    if not match:
        return None

    days, hours, minutes, seconds = match.groups()

    total_seconds = 0
    if days:
        total_seconds += int(days) * 86400
    if hours:
        total_seconds += int(hours) * 3600
    if minutes:
        total_seconds += int(minutes) * 60
    if seconds:
        total_seconds += int(seconds)

    # Minimum 1 minute, maximum 30 days
    if total_seconds < 60:
        return None
    if total_seconds > 2592000:  # 30 days
        return None

    return total_seconds

def format_duration(seconds):
    """Format seconds into readable duration"""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        parts.append(f"{seconds}s")

    return "".join(parts) if parts else "0s"

@bot.tree.command(name="giverole", description="🎭 Give a role to a user (optionally for a specific duration)")
@app_commands.describe(
    user="User to give the role to",
    role="Role to assign",
    duration="Duration (e.g., 1h30m, 2d, 45m) - Max 30 days. Leave empty for permanent role"
)
async def give_timed_role(
    interaction: discord.Interaction,
    user: discord.Member,
    role: discord.Role,
    duration: str = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True)
        return

    # Parse duration (optional for permanent roles)
    is_permanent = duration is None
    if not is_permanent:
        duration_seconds = parse_duration(duration)
        if not duration_seconds:
            await interaction.response.send_message("❌ Invalid duration format! Use format like: `1h30m`, `2d`, `45m` (Min: 1m, Max: 30d)", ephemeral=True)
            return

    # Check if bot can assign this role
    if role >= interaction.guild.me.top_role:
        await interaction.response.send_message("❌ I cannot assign this role! Please make sure my role is higher than the target role.", ephemeral=True)
        return

    # Check if user already has the role
    if role in user.roles:
        await interaction.response.send_message(f"❌ {user.mention} already has the {role.mention} role!", ephemeral=True)
        return

    # Check if user can assign this role
    if role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ You cannot assign a role equal to or higher than your highest role!", ephemeral=True)
        return

    try:
        if is_permanent:
            # Assign permanent role
            await user.add_roles(role, reason=f"Permanent role assigned by {interaction.user}")

            # Send confirmation for permanent role
            embed = discord.Embed(
                title="✅ **Permanent Role Assigned**",
                description=f"**User:** {user.mention}\n**Role:** {role.mention}\n**Type:** `Permanent`\n**Assigned by:** {interaction.user.mention}\n\n*This role will remain until manually removed.*",
                color=BrandColors.SUCCESS
            )
            embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
            await interaction.response.send_message(embed=embed)

            # Send DM to user for permanent role
            try:
                dm_embed = discord.Embed(
                    title="🎭 **You've been given a permanent role!**",
                    description=f"**Server:** {interaction.guild.name}\n**Role:** {role.name}\n**Type:** Permanent\n\n*This role will remain until a moderator removes it.*",
                    color=BrandColors.SUCCESS
                )
                dm_embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
                await user.send(embed=dm_embed)
            except:
                pass  # User has DMs disabled

            await log_action(interaction.guild.id, "moderation", f"🎭 [PERMANENT ROLE] {role.name} assigned to {user} by {interaction.user}")

        else:
            # Calculate expiry time for timed role
            expires_at = datetime.utcnow() + timedelta(seconds=duration_seconds)

            # Assign the timed role
            await user.add_roles(role, reason=f"Timed role assigned by {interaction.user} for {format_duration(duration_seconds)}")

            # Store in database for timed roles only
            if db is not None:
                await db.timed_roles.insert_one({
                    'guild_id': str(interaction.guild.id),
                    'user_id': str(user.id),
                    'role_id': str(role.id),
                    'assigned_by': str(interaction.user.id),
                    'assigned_at': datetime.utcnow(),
                    'expires_at': expires_at,
                    'duration_seconds': duration_seconds
                })

            # Send confirmation for timed role
            embed = discord.Embed(
                title="✅ **Timed Role Assigned**",
                description=f"**User:** {user.mention}\n**Role:** {role.mention}\n**Duration:** `{format_duration(duration_seconds)}`\n**Expires:** {discord.utils.format_dt(expires_at, style='R')}\n**Assigned by:** {interaction.user.mention}",
                color=BrandColors.SUCCESS
            )
            embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
            await interaction.response.send_message(embed=embed)

            # Send DM to user for timed role
            try:
                dm_content = f"**Server:** {interaction.guild.name}\n**Role:** {role.name}\n**Duration:** `{format_duration(duration_seconds)}`\n**Expires:** {discord.utils.format_dt(expires_at, style='F')}\n\n*This role will be automatically removed when it expires.*"
                dm_embed = discord.Embed(
                    title="🎭 **You've been given a timed role!**",
                    description=dm_content,
                    color=BrandColors.SUCCESS
                )
                dm_embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
                await user.send(embed=dm_embed)
                # Log DM sent
                from advanced_logging import log_dm_sent
                await log_dm_sent(user, dm_content, interaction.guild)
            except:
                pass  # User has DMs disabled

            await log_action(interaction.guild.id, "timed_roles", f"🕰️ [TIMED ROLE] {role.name} given to {user} for {format_duration(duration_seconds)} by {interaction.user}")

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to assign this role!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="removerole", description="🗑️ Manually remove a role from a user")
@app_commands.describe(
    user="User to remove the role from",
    role="Role to remove"
)
async def remove_role(
    interaction: discord.Interaction,
    user: discord.Member,
    role: discord.Role
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True)
        return

    # Check if user has the role
    if role not in user.roles:
        await interaction.response.send_message(f"❌ {user.mention} doesn't have the {role.mention} role!", ephemeral=True)
        return

    # Check if user can remove this role
    if role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ You cannot remove a role equal to or higher than your highest role!", ephemeral=True)
        return

    try:
        # Remove the role
        await user.remove_roles(role, reason=f"Role manually removed by {interaction.user}")

        # Remove from timed roles database if it exists
        if db is not None:
            result = await db.timed_roles.delete_one({
                'guild_id': str(interaction.guild.id),
                'user_id': str(user.id),
                'role_id': str(role.id)
            })
            was_timed = result.deleted_count > 0
        else:
            was_timed = False

        # Send confirmation
        embed = discord.Embed(
            title="✅ **Role Removed**",
            description=f"**User:** {user.mention}\n**Role:** {role.mention}\n**Removed by:** {interaction.user.mention}" + (f"\n**Note:** This was a timed role that has been cancelled." if was_timed else ""),
            color=BrandColors.WARNING
        )
        embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

        # Send DM to user
        try:
            dm_content = f"Your **{role.name}** role has been removed from **{interaction.guild.name}**" + (f" (timed role cancelled)" if was_timed else "") + f".\n\n**Removed by:** {interaction.user}"
            dm_embed = discord.Embed(
                title="🗑️ **Role Removed**",
                description=dm_content,
                color=BrandColors.WARNING
            )
            dm_embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
            await user.send(embed=dm_embed)
            # Log DM sent
            from advanced_logging import log_dm_sent
            await log_dm_sent(user, dm_content, interaction.guild)
        except:
            pass  # User has DMs disabled

        action_text = "cancelled timed role" if was_timed else "removed role"
        await log_action(interaction.guild.id, "timed_roles", f"🕰️ [TIMED ROLE] {role.name} manually removed from {user} by {interaction.user}")

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to remove this role!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="timedroles", description="📋 View all active timed roles in the server")
async def view_timed_roles(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if db is None:
        await interaction.response.send_message("❌ Database not available!", ephemeral=True)
        return

    try:
        # Get all timed roles for this server
        timed_roles = await db.timed_roles.find({
            'guild_id': str(interaction.guild.id)
        }).sort('expires_at', 1).to_list(length=100)

        if not timed_roles:
            embed = discord.Embed(
                title="📋 **Active Timed Roles**",
                description="*No active timed roles found in this server.*",
                color=0x95a5a6
            )
            embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
            await interaction.response.send_message(embed=embed)
            return

        # Create embed with timed roles
        embed = discord.Embed(
            title="📋 **Active Timed Roles**",
            description=f"*Showing {len(timed_roles)} active timed role(s)*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=BrandColors.INFO
        )

        for i, role_data in enumerate(timed_roles[:10]):  # Show max 10 to avoid embed limits
            try:
                user = interaction.guild.get_member(int(role_data['user_id']))
                role = interaction.guild.get_role(int(role_data['role_id']))
                assigned_by = interaction.guild.get_member(int(role_data['assigned_by']))

                user_name = user.display_name if user else f"User ID: {role_data['user_id']}"
                role_name = role.name if role else f"Role ID: {role_data['role_id']}"
                assigned_by_name = assigned_by.display_name if assigned_by else f"User ID: {role_data['assigned_by']}"

                expires_at = role_data['expires_at']
                time_left = expires_at - datetime.utcnow()

                if time_left.total_seconds() > 0:
                    status = f"⏰ Expires {discord.utils.format_dt(expires_at, style='R')}"
                else:
                    status = "⚠️ Expired (processing removal)"

                embed.add_field(
                    name=f"#{i+1} {role_name}",
                    value=f"**User:** {user_name}\n**Assigned by:** {assigned_by_name}\n**Status:** {status}",
                    inline=True
                )

            except Exception as e:
                embed.add_field(
                    name=f"#{i+1} Error",
                    value=f"Failed to load role data",
                    inline=True
                )

        if len(timed_roles) > 10:
            embed.add_field(
                name="📊 **Additional Roles**",
                value=f"*{len(timed_roles) - 10} more roles not shown (use command again for updated list)*",
                inline=False
            )

        embed.set_footer(text=f"{BOT_FOOTER} • Roles are checked every minute", icon_url=bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

# Function to start timed roles task (called from main.py)
def start_timed_roles_task():
    if not check_expired_roles.is_running():
        check_expired_roles.start()
        print("✅ Timed roles background task started")

# Stop the task when the bot shuts down
@bot.event
async def on_disconnect():
    if check_expired_roles.is_running():
        check_expired_roles.stop()
        print("🛑 Timed roles background task stopped")