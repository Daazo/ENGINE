
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
from main import bot, has_permission, get_server_data, update_server_data, log_action, db

# Start the background task when the module loads
@tasks.loop(minutes=1)
async def check_expired_roles():
    """Background task to check and remove expired roles"""
    if db is None:
        return
    
    current_time = datetime.utcnow()
    
    # Find all expired role assignments
    expired_assignments = await db.timed_roles.find({
        'expires_at': {'$lt': current_time}
    }).to_list(None)
    
    for assignment in expired_assignments:
        try:
            guild = bot.get_guild(int(assignment['guild_id']))
            if not guild:
                continue
            
            member = guild.get_member(int(assignment['user_id']))
            role = guild.get_role(int(assignment['role_id']))
            
            if member and role and role in member.roles:
                await member.remove_roles(role, reason="Timed role expired")
                
                # Log the removal
                await log_action(guild.id, "moderation", f"⏰ [TIMED ROLE] {role.name} automatically removed from {member} (expired)")
                
                # Try to DM user about role expiration
                try:
                    embed = discord.Embed(
                        title="⏰ Timed Role Expired",
                        description=f"Your **{role.name}** role in **{guild.name}** has expired and been removed.",
                        color=0xf39c12
                    )
                    await member.send(embed=embed)
                except:
                    pass  # User has DMs disabled
            
            # Remove from database
            await db.timed_roles.delete_one({'_id': assignment['_id']})
            
        except Exception as e:
            print(f"Error removing expired role: {e}")

@bot.event
async def on_ready():
    """Start the timed roles check task when bot is ready"""
    if not check_expired_roles.is_running():
        check_expired_roles.start()

@bot.tree.command(name="giverole", description="⏰ Give a role to user for a specific duration")
@app_commands.describe(
    user="User to give role to",
    role="Role to assign",
    duration="Duration (e.g., 1d, 5h, 30m, 2w)"
)
async def give_timed_role(interaction: discord.Interaction, user: discord.Member, role: discord.Role, duration: str):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    # Check if bot can manage the role
    if role >= interaction.guild.me.top_role:
        await interaction.response.send_message("❌ I cannot assign this role! Make sure my role is higher than the target role.", ephemeral=True)
        return
    
    # Parse duration
    try:
        duration_seconds = parse_duration(duration)
        expires_at = datetime.utcnow() + timedelta(seconds=duration_seconds)
    except ValueError as e:
        await interaction.response.send_message(f"❌ Invalid duration format! Use format like: 1d, 5h, 30m, 2w\nError: {e}", ephemeral=True)
        return
    
    # Check if user already has the role
    if role in user.roles:
        await interaction.response.send_message(f"❌ {user.mention} already has the {role.mention} role!", ephemeral=True)
        return
    
    try:
        # Assign the role
        await user.add_roles(role, reason=f"Timed role by {interaction.user} for {duration}")
        
        # Store in database
        if db is not None:
            timed_role_data = {
                'guild_id': str(interaction.guild.id),
                'user_id': str(user.id),
                'role_id': str(role.id),
                'assigned_by': str(interaction.user.id),
                'assigned_at': datetime.utcnow(),
                'expires_at': expires_at,
                'duration_text': duration
            }
            await db.timed_roles.insert_one(timed_role_data)
        
        # Create response embed
        embed = discord.Embed(
            title="⏰ Timed Role Assigned",
            description=f"**Role:** {role.mention}\n**User:** {user.mention}\n**Duration:** {duration}\n**Expires:** {discord.utils.format_dt(expires_at, style='F')}\n**Assigned by:** {interaction.user.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        
        # DM user about role assignment
        try:
            dm_embed = discord.Embed(
                title="⏰ You received a timed role!",
                description=f"**Server:** {interaction.guild.name}\n**Role:** {role.name}\n**Duration:** {duration}\n**Expires:** {discord.utils.format_dt(expires_at, style='F')}",
                color=0x43b581
            )
            await user.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled
        
        await log_action(interaction.guild.id, "moderation", f"⏰ [TIMED ROLE] {role.name} assigned to {user} by {interaction.user} for {duration}")
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to assign this role!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="removerole", description="🗑️ Manually remove a role from user")
@app_commands.describe(
    user="User to remove role from",
    role="Role to remove"
)
async def remove_role_command(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    if role not in user.roles:
        await interaction.response.send_message(f"❌ {user.mention} doesn't have the {role.mention} role!", ephemeral=True)
        return
    
    try:
        # Remove the role
        await user.remove_roles(role, reason=f"Manually removed by {interaction.user}")
        
        # Remove from timed roles database if it exists there
        if db is not None:
            await db.timed_roles.delete_one({
                'guild_id': str(interaction.guild.id),
                'user_id': str(user.id),
                'role_id': str(role.id)
            })
        
        embed = discord.Embed(
            title="🗑️ Role Removed",
            description=f"**Role:** {role.mention}\n**User:** {user.mention}\n**Removed by:** {interaction.user.mention}",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🗑️ [ROLE REMOVE] {role.name} removed from {user} by {interaction.user}")
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to remove this role!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="timedroles", description="📋 Show all active timed roles in the server")
async def list_timed_roles(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    if db is None:
        await interaction.response.send_message("❌ Database not connected!", ephemeral=True)
        return
    
    # Get all active timed roles for this server
    active_roles = await db.timed_roles.find({
        'guild_id': str(interaction.guild.id)
    }).sort('expires_at', 1).to_list(None)
    
    if not active_roles:
        embed = discord.Embed(
            title="📋 Active Timed Roles",
            description="No active timed roles in this server!",
            color=0x3498db
        )
        await interaction.response.send_message(embed=embed)
        return
    
    # Build list of timed roles
    role_list = []
    for i, role_data in enumerate(active_roles[:10]):  # Limit to 10 to avoid embed limits
        try:
            member = interaction.guild.get_member(int(role_data['user_id']))
            role = interaction.guild.get_role(int(role_data['role_id']))
            
            if member and role:
                expires_in = role_data['expires_at'] - datetime.utcnow()
                if expires_in.total_seconds() > 0:
                    hours, remainder = divmod(int(expires_in.total_seconds()), 3600)
                    minutes = remainder // 60
                    time_left = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                    
                    role_list.append(f"**{i+1}.** {member.mention} → {role.mention}\n*Expires in: {time_left}*")
                else:
                    role_list.append(f"**{i+1}.** {member.mention} → {role.mention}\n*⚠️ Expired (will be removed soon)*")
        except:
            continue
    
    if not role_list:
        description = "No valid timed roles found!"
    else:
        description = "\n\n".join(role_list)
        if len(active_roles) > 10:
            description += f"\n\n*... and {len(active_roles) - 10} more*"
    
    embed = discord.Embed(
        title="📋 Active Timed Roles",
        description=description,
        color=0x3498db
    )
    embed.set_footer(text="🌴 Roles are automatically removed when they expire")
    await interaction.response.send_message(embed=embed)

def parse_duration(duration_str):
    """Parse duration string like '1d', '5h', '30m', '2w' into seconds"""
    duration_str = duration_str.lower().strip()
    
    # Extract number and unit
    import re
    match = re.match(r'^(\d+)([smhdw])$', duration_str)
    if not match:
        raise ValueError("Duration must be in format like: 5m, 2h, 1d, 3w")
    
    amount = int(match.group(1))
    unit = match.group(2)
    
    multipliers = {
        's': 1,           # seconds
        'm': 60,          # minutes
        'h': 3600,        # hours
        'd': 86400,       # days
        'w': 604800       # weeks
    }
    
    if unit not in multipliers:
        raise ValueError("Unit must be s (seconds), m (minutes), h (hours), d (days), or w (weeks)")
    
    total_seconds = amount * multipliers[unit]
    
    # Limit maximum duration to 30 days
    if total_seconds > 30 * 86400:
        raise ValueError("Maximum duration is 30 days (30d)")
    
    # Minimum duration is 1 minute
    if total_seconds < 60:
        raise ValueError("Minimum duration is 1 minute (1m)")
    
    return total_seconds
