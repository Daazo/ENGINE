import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
from datetime import datetime, timedelta
from main import bot
from brand_config import BOT_FOOTER, BrandColors
from main import has_permission, get_server_data, update_server_data, log_action, has_permission_user
import re

# Enhanced security tracking data
enhanced_security_data = {
    'user_roles': {},  # Store user roles before timeout {guild_id: {user_id: [role_ids]}}
    'timeout_roles': {},  # Store timeout role IDs {guild_id: role_id}
    'whitelists': {},  # Store whitelists per feature {guild_id: {feature: [user_ids]}}
    'mention_tracking': {},  # Track @everyone/@here mentions
}

# ═══════════════════════════════════════════════════════════════════════════
# ENHANCED TIMEOUT ROLE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def get_or_create_timeout_role(guild):
    """Get or create the timeout role with proper permissions"""
    guild_id = str(guild.id)
    
    # Check if timeout role already exists in our cache
    if guild_id in enhanced_security_data['timeout_roles']:
        role_id = enhanced_security_data['timeout_roles'][guild_id]
        role = guild.get_role(int(role_id))
        if role:
            return role  # Return existing role without modifying permissions
    
    # Check database for saved timeout role
    server_data = await get_server_data(guild.id)
    security_settings = server_data.get('security_settings', {})
    timeout_role_id = security_settings.get('timeout_role_id')
    
    if timeout_role_id:
        role = guild.get_role(int(timeout_role_id))
        if role:
            enhanced_security_data['timeout_roles'][guild_id] = timeout_role_id
            return role  # Return existing role without modifying permissions
    
    # Create new timeout role (only runs if role doesn't exist)
    try:
        role = await guild.create_role(
            name="⏰ Timed Out",
            color=discord.Color(BrandColors.DANGER),
            reason="RXT ENGINE Enhanced Timeout System - Auto-created",
            mentionable=False
        )
        
        # Save to database and cache
        security_settings['timeout_role_id'] = str(role.id)
        await update_server_data(guild.id, {'security_settings': security_settings})
        enhanced_security_data['timeout_roles'][guild_id] = str(role.id)
        
        # Get timeout channel from settings
        timeout_settings = server_data.get('timeout_settings', {})
        timeout_channel_id = timeout_settings.get('timeout_channel')
        
        # ONLY set permissions if timeout channel is configured
        # This avoids overwriting all channel permissions
        if timeout_channel_id:
            timeout_channel = guild.get_channel(int(timeout_channel_id))
            if timeout_channel:
                try:
                    # Allow access to timeout channel only
                    await timeout_channel.set_permissions(
                        role,
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        reason="Timeout role - access to timeout channel"
                    )
                    print(f"✅ [TIMEOUT ROLE] Set permissions for timeout channel: {timeout_channel.name}")
                except Exception as e:
                    print(f"⚠️ [TIMEOUT ROLE] Could not set permissions for timeout channel: {e}")
        
        await log_action(guild.id, "security", f"⚡ [TIMEOUT ROLE] Created timeout role: {role.name}")
        print(f"✅ [TIMEOUT ROLE] Created new timeout role in {guild.name}")
        return role
        
    except discord.Forbidden:
        print(f"❌ [TIMEOUT ROLE] No permission to create role in {guild.name}")
        return None
    except Exception as e:
        print(f"❌ [TIMEOUT ROLE] Error creating timeout role: {e}")
        return None

async def save_user_roles(guild, member):
    """Save user's current roles before timeout"""
    guild_id = str(guild.id)
    user_id = str(member.id)
    
    if guild_id not in enhanced_security_data['user_roles']:
        enhanced_security_data['user_roles'][guild_id] = {}
    
    # Save all roles except @everyone
    role_ids = [str(role.id) for role in member.roles if role.id != guild.id]
    enhanced_security_data['user_roles'][guild_id][user_id] = role_ids
    
    # Save to database for persistence (store per user, not nested by guild)
    server_data = await get_server_data(guild.id)
    saved_roles = server_data.get('saved_user_roles', {})
    saved_roles[user_id] = {
        'roles': role_ids,
        'saved_at': datetime.now().isoformat()
    }
    await update_server_data(guild.id, {'saved_user_roles': saved_roles})

async def restore_user_roles(guild, member):
    """Restore user's roles after timeout ends"""
    guild_id = str(guild.id)
    user_id = str(member.id)
    
    # Try to get from cache first
    roles_to_restore = []
    if guild_id in enhanced_security_data['user_roles']:
        if user_id in enhanced_security_data['user_roles'][guild_id]:
            role_ids = enhanced_security_data['user_roles'][guild_id][user_id]
            roles_to_restore = [guild.get_role(int(rid)) for rid in role_ids]
            roles_to_restore = [r for r in roles_to_restore if r is not None]
    
    # If not in cache, try database (stored per user, not nested by guild)
    if not roles_to_restore:
        server_data = await get_server_data(guild.id)
        saved_roles = server_data.get('saved_user_roles', {})
        if user_id in saved_roles:
            role_ids = saved_roles[user_id].get('roles', [])
            roles_to_restore = [guild.get_role(int(rid)) for rid in role_ids]
            roles_to_restore = [r for r in roles_to_restore if r is not None]
    
    # Restore roles
    if roles_to_restore:
        try:
            await member.add_roles(*roles_to_restore, reason="Timeout ended - restoring previous roles")
            print(f"✅ [ROLE RESTORE] Restored {len(roles_to_restore)} roles for {member}")
        except Exception as e:
            print(f"❌ [ROLE RESTORE] Failed to restore roles for {member}: {e}")
    else:
        print(f"⚠️ [ROLE RESTORE] No saved roles found for {member}")
    
    # Clean up saved data from cache and database
    if guild_id in enhanced_security_data['user_roles']:
        if user_id in enhanced_security_data['user_roles'][guild_id]:
            del enhanced_security_data['user_roles'][guild_id][user_id]
    
    # Clean up from database
    server_data = await get_server_data(guild.id)
    saved_roles = server_data.get('saved_user_roles', {})
    if user_id in saved_roles:
        del saved_roles[user_id]
        await update_server_data(guild.id, {'saved_user_roles': saved_roles})

async def apply_enhanced_timeout(guild, member, duration_minutes, reason, triggered_by=None):
    """Apply enhanced timeout with role saving and timeout role application"""
    try:
        # 1. Get server data for timeout settings
        server_data = await get_server_data(guild.id)
        
        # 2. Save current roles FIRST before any modifications
        await save_user_roles(guild, member)
        print(f"✅ [ENHANCED TIMEOUT] Saved {len(member.roles)-1} roles for {member}")
        
        # 3. Get or create timeout role
        timeout_role = await get_or_create_timeout_role(guild)
        if not timeout_role:
            print(f"❌ [ENHANCED TIMEOUT] Could not get/create timeout role")
            await log_action(guild.id, "security", f"❌ [ENHANCED TIMEOUT ERROR] Failed to create timeout role for {member.mention}")
            return False
        
        # 4. Remove all current roles (except @everyone)
        roles_to_remove = [role for role in member.roles if role.id != guild.id and role != timeout_role]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason=f"Timeout applied: {reason}")
                print(f"✅ [ENHANCED TIMEOUT] Removed {len(roles_to_remove)} roles from {member}")
            except Exception as e:
                print(f"⚠️ [ENHANCED TIMEOUT] Could not remove some roles: {e}")
                await log_action(guild.id, "security", f"⚠️ [ENHANCED TIMEOUT WARNING] Could not remove all roles from {member.mention}")
        
        # 5. Add timeout role
        await member.add_roles(timeout_role, reason=f"Timeout applied: {reason}")
        print(f"✅ [ENHANCED TIMEOUT] Added timeout role to {member}")
        
        # 5. Apply per-member channel restrictions (deny all channels except timeout channel)
        timeout_settings = server_data.get('timeout_settings', {})
        timeout_channel_id = timeout_settings.get('timeout_channel')
        
        for channel in guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
                try:
                    if timeout_channel_id and channel.id == int(timeout_channel_id):
                        # Allow access to timeout channel only
                        await channel.set_permissions(
                            member,
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True,
                            reason=f"Timeout isolation: {reason}"
                        )
                    else:
                        # Deny access to all other channels
                        await channel.set_permissions(
                            member,
                            view_channel=False,
                            send_messages=False,
                            reason=f"Timeout isolation: {reason}"
                        )
                except Exception as e:
                    print(f"⚠️ [ENHANCED TIMEOUT] Could not set channel permissions for {channel.name}: {e}")
        
        print(f"✅ [ENHANCED TIMEOUT] Applied channel restrictions for {member}")
        
        # 6. Apply Discord timeout
        duration = timedelta(minutes=duration_minutes)
        await member.timeout(duration, reason=reason)
        
        # 7. Log action to security channel
        await log_action(guild.id, "security", f"⏰ [ENHANCED TIMEOUT] {member.mention} timed out for {duration_minutes}m | Reason: {reason} | By: {triggered_by or 'Auto-System'}")
        
        # 8. Send DM to user
        try:
            dm_embed = discord.Embed(
                title="⚡ **Quantum Security Timeout**",
                description=f"**◆ You have been timed out**\n\n**Server:** {guild.name}\n**Duration:** {duration_minutes} minutes\n**Reason:** {reason}\n\n💠 Your roles have been temporarily removed and will be restored when the timeout ends.",
                color=BrandColors.DANGER
            )
            if guild.me:
                dm_embed.set_footer(text=BOT_FOOTER, icon_url=guild.me.display_avatar.url)
            else:
                dm_embed.set_footer(text=BOT_FOOTER)
            await member.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled
        
        print(f"⏰ [ENHANCED TIMEOUT] Applied to {member} for {duration_minutes}m - {reason}")
        return True
        
    except discord.Forbidden:
        print(f"❌ [ENHANCED TIMEOUT] No permission to timeout {member}")
        return False
    except Exception as e:
        print(f"❌ [ENHANCED TIMEOUT] Error applying timeout: {e}")
        return False

async def remove_enhanced_timeout(guild, member, removed_by=None):
    """Remove enhanced timeout and restore user's roles"""
    try:
        # 1. Get timeout role
        timeout_role = await get_or_create_timeout_role(guild)
        
        # 2. Remove Discord timeout
        await member.timeout(None, reason="Timeout manually removed")
        print(f"✅ [TIMEOUT REMOVE] Removed Discord timeout from {member}")
        
        # 3. Remove timeout role
        if timeout_role and timeout_role in member.roles:
            await member.remove_roles(timeout_role, reason="Timeout removed")
            print(f"✅ [TIMEOUT REMOVE] Removed timeout role from {member}")
        
        # 4. Remove per-member channel restrictions
        for channel in guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
                try:
                    # Remove member-specific overwrites (restore to default/role permissions)
                    await channel.set_permissions(member, overwrite=None, reason="Timeout ended - removing restrictions")
                except Exception as e:
                    print(f"⚠️ [TIMEOUT REMOVE] Could not remove channel permissions for {channel.name}: {e}")
        
        print(f"✅ [TIMEOUT REMOVE] Removed channel restrictions for {member}")
        
        # 5. Restore previous roles
        await restore_user_roles(guild, member)
        print(f"✅ [TIMEOUT REMOVE] Restored roles for {member}")
        
        # 7. Log action to security channel
        await log_action(guild.id, "security", f"✅ [TIMEOUT REMOVED] {member.mention} timeout removed and roles restored | By: {removed_by or 'Auto-System'}")
        
        # 8. Send DM to user
        try:
            dm_embed = discord.Embed(
                title="⚡ **Timeout Removed**",
                description=f"**◆ Your timeout has ended**\n\n**Server:** {guild.name}\n\n✅ Your previous roles have been restored\n💠 You now have full server access",
                color=BrandColors.SUCCESS
            )
            if guild.me:
                dm_embed.set_footer(text=BOT_FOOTER, icon_url=guild.me.display_avatar.url)
            else:
                dm_embed.set_footer(text=BOT_FOOTER)
            await member.send(embed=dm_embed)
        except:
            pass
        
        print(f"✅ [TIMEOUT REMOVED] {member} timeout removed and roles restored")
        return True
        
    except Exception as e:
        print(f"❌ [TIMEOUT REMOVE] Error removing timeout: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════
# WHITELIST SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def is_whitelisted(guild_id, user_id, feature):
    """Check if user is whitelisted for a specific security feature"""
    guild_id = str(guild_id)
    user_id = str(user_id)
    
    # Get from database
    server_data = await get_server_data(guild_id)
    security_whitelists = server_data.get('security_whitelists', {})
    feature_whitelist = security_whitelists.get(feature, [])
    
    return user_id in feature_whitelist

async def add_to_whitelist(guild_id, user_id, feature):
    """Add user to whitelist for a specific feature"""
    guild_id = str(guild_id)
    user_id = str(user_id)
    
    server_data = await get_server_data(guild_id)
    security_whitelists = server_data.get('security_whitelists', {})
    
    if feature not in security_whitelists:
        security_whitelists[feature] = []
    
    if user_id not in security_whitelists[feature]:
        security_whitelists[feature].append(user_id)
        await update_server_data(guild_id, {'security_whitelists': security_whitelists})
        return True
    return False

async def remove_from_whitelist(guild_id, user_id, feature):
    """Remove user from whitelist for a specific feature"""
    guild_id = str(guild_id)
    user_id = str(user_id)
    
    server_data = await get_server_data(guild_id)
    security_whitelists = server_data.get('security_whitelists', {})
    
    if feature in security_whitelists and user_id in security_whitelists[feature]:
        security_whitelists[feature].remove(user_id)
        await update_server_data(guild_id, {'security_whitelists': security_whitelists})
        return True
    return False

# ═══════════════════════════════════════════════════════════════════════════
# AUTO-TIMEOUT FOR @EVERYONE/@HERE MENTIONS
# ═══════════════════════════════════════════════════════════════════════════

async def on_message_mention_check(message):
    """Check for @everyone/@here mentions and auto-timeout (called from main.py on_message event)"""
    if message.author.bot or not message.guild:
        return
    
    # Skip if user has moderator permissions
    if await has_permission_user(message.author, message.guild, "junior_moderator"):
        return
    
    # Check if user is whitelisted for mention bypass
    if await is_whitelisted(message.guild.id, message.author.id, 'mention_everyone'):
        return
    
    # Get security settings
    server_data = await get_server_data(message.guild.id)
    security_settings = server_data.get('security_settings', {})
    auto_timeout_mentions = security_settings.get('auto_timeout_mentions', {})
    
    if not auto_timeout_mentions.get('enabled', False):
        return
    
    # Check for @everyone or @here mentions
    if message.mention_everyone:
        # Delete the message
        try:
            await message.delete()
        except:
            pass
        
        # Get timeout duration from settings (default 30 minutes)
        duration = auto_timeout_mentions.get('duration_minutes', 30)
        
        # Apply enhanced timeout
        await apply_enhanced_timeout(
            message.guild,
            message.author,
            duration,
            "Unauthorized @everyone/@here mention",
            triggered_by="Auto-Security System"
        )
        
        # Send notification in channel
        try:
            embed = discord.Embed(
                title="⚡ **Auto-Timeout Applied**",
                description=f"**{message.author.mention} has been timed out**\n\n**◆ Reason:** Unauthorized @everyone/@here mention\n**◆ Duration:** {duration} minutes\n\n💠 Message deleted by Quantum Security",
                color=BrandColors.DANGER
            )
            if message.guild and message.guild.me:
                embed.set_footer(text=BOT_FOOTER, icon_url=message.guild.me.display_avatar.url)
            else:
                embed.set_footer(text=BOT_FOOTER)
            await message.channel.send(embed=embed, delete_after=10)
        except:
            pass

# ═══════════════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="remove-timeout", description="⏰ Remove timeout from a user and restore their roles")
@app_commands.describe(member="The member to remove timeout from")
async def remove_timeout_command(interaction: discord.Interaction, member: discord.Member):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    success = await remove_enhanced_timeout(interaction.guild, member, removed_by=interaction.user)
    
    if success:
        embed = discord.Embed(
            title="⚡ **Timeout Removed**",
            description=f"**◆ User:** {member.mention}\n**◆ Status:** Timeout removed\n**◆ Roles:** Restored\n\n✅ User has full server access",
            color=BrandColors.SUCCESS
        )
    else:
        embed = discord.Embed(
            title="❌ **Error**",
            description=f"Could not remove timeout from {member.mention}",
            color=BrandColors.DANGER
        )
    
    embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="security-whitelist", description="🔐 Manage security feature whitelists")
@app_commands.describe(
    action="Add, remove, or list whitelist",
    feature="Security feature to whitelist for",
    user="User to whitelist (required for add/remove)"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="list", value="list")
    ],
    feature=[
        app_commands.Choice(name="Mention @everyone/@here", value="mention_everyone"),
        app_commands.Choice(name="Post Links", value="post_links"),
        app_commands.Choice(name="Discord Invites", value="discord_invites"),
        app_commands.Choice(name="All Security", value="all_security")
    ]
)
async def security_whitelist_command(
    interaction: discord.Interaction,
    action: str,
    feature: str,
    user: discord.Member = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
    
    server_data = await get_server_data(interaction.guild.id)
    security_whitelists = server_data.get('security_whitelists', {})
    
    if action == "list":
        # Show all whitelisted users for this feature
        feature_whitelist = security_whitelists.get(feature, [])
        
        if not feature_whitelist:
            user_list = "*No users whitelisted*"
        else:
            users = []
            for user_id in feature_whitelist:
                member = interaction.guild.get_member(int(user_id))
                if member:
                    users.append(f"• {member.mention} ({member})")
                else:
                    users.append(f"• Unknown User (ID: {user_id})")
            user_list = "\n".join(users)
        
        feature_names = {
            'mention_everyone': '📣 Mention @everyone/@here',
            'post_links': '🔗 Post Links',
            'discord_invites': '💬 Discord Invites',
            'all_security': '🛡️ All Security Features'
        }
        
        embed = discord.Embed(
            title="⚡ **Security Whitelist**",
            description=f"**◆ Feature:** {feature_names.get(feature, feature)}\n\n**Whitelisted Users:**\n{user_list}",
            color=BrandColors.PRIMARY
        )
        embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
        return
    
    if not user:
        await interaction.response.send_message("❌ You must specify a user for add/remove actions!", ephemeral=True)
        return
    
    # Initialize embed variable
    embed = None
    
    if action == "add":
        success = await add_to_whitelist(interaction.guild.id, user.id, feature)
        if success:
            embed = discord.Embed(
                title="⚡ **Added to Whitelist**",
                description=f"**◆ User:** {user.mention}\n**◆ Feature:** {feature.replace('_', ' ').title()}\n\n✅ User can now bypass this security feature",
                color=BrandColors.SUCCESS
            )
            await log_action(interaction.guild.id, "security", f"🔐 [WHITELIST] {user.mention} added to {feature} whitelist by {interaction.user}")
        else:
            embed = discord.Embed(
                title="⚠️ **Already Whitelisted**",
                description=f"{user.mention} is already whitelisted for {feature}",
                color=BrandColors.WARNING
            )
    
    elif action == "remove":
        success = await remove_from_whitelist(interaction.guild.id, user.id, feature)
        if success:
            embed = discord.Embed(
                title="⚡ **Removed from Whitelist**",
                description=f"**◆ User:** {user.mention}\n**◆ Feature:** {feature.replace('_', ' ').title()}\n\n✅ User no longer bypasses this security feature",
                color=BrandColors.SUCCESS
            )
            await log_action(interaction.guild.id, "security", f"🔐 [WHITELIST] {user.mention} removed from {feature} whitelist by {interaction.user}")
        else:
            embed = discord.Embed(
                title="⚠️ **Not Whitelisted**",
                description=f"{user.mention} is not whitelisted for {feature}",
                color=BrandColors.WARNING
            )
    
    if embed:
        embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="security-config", description="⚙️ Configure auto-timeout security features")
@app_commands.describe(
    feature="Security feature to configure",
    enabled="Enable or disable the feature",
    duration="Timeout duration in minutes (where applicable)"
)
@app_commands.choices(feature=[
    app_commands.Choice(name="Auto-Timeout @everyone/@here", value="auto_timeout_mentions"),
])
async def security_config_command(
    interaction: discord.Interaction,
    feature: str,
    enabled: bool,
    duration: int = 30
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
    
    server_data = await get_server_data(interaction.guild.id)
    security_settings = server_data.get('security_settings', {})
    
    if feature == "auto_timeout_mentions":
        security_settings['auto_timeout_mentions'] = {
            'enabled': enabled,
            'duration_minutes': duration
        }
    
    await update_server_data(interaction.guild.id, {'security_settings': security_settings})
    
    status = "✅ Enabled" if enabled else "❌ Disabled"
    feature_names = {
        'auto_timeout_mentions': '📣 Auto-Timeout @everyone/@here Mentions'
    }
    
    embed = discord.Embed(
        title="⚡ **Security Configuration Updated**",
        description=f"**◆ Feature:** {feature_names.get(feature, feature)}\n**◆ Status:** {status}\n**◆ Duration:** {duration} minutes",
        color=BrandColors.PRIMARY if enabled else BrandColors.DANGER
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "security", f"⚙️ [SECURITY CONFIG] {feature_names.get(feature, feature)} {status} | Duration: {duration}m | By: {interaction.user}")

print("✅ [ENHANCED SECURITY] Phase 1 systems loaded - Enhanced Timeout, Whitelist Framework, Auto-Timeout")
