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
    'quarantine_roles': {},  # Store quarantine role IDs {guild_id: role_id}
    'whitelists': {},  # Store whitelists per feature {guild_id: {feature: [user_ids]}}
    'mention_tracking': {},  # Track @everyone/@here mentions
    'spam_tracking': {},  # Track message spam {guild_id: {user_id: {'messages': [], 'last_message': '', 'repeat_count': 0}}}
    'raid_tracking': {},  # Track member joins {guild_id: {'joins': [], 'raid_mode': False}}
    'warnings': {},  # Track user warnings {guild_id: {user_id: [warning_data]}}
    'nuke_tracking': {  # Track nuke actions (Phase 3)
        'bans': {},  # {guild_id: [(timestamp, (user_id, moderator_id))]}
        'kicks': {},  # {guild_id: [(timestamp, (user_id, moderator_id))]}
        'role_deletes': {},  # {guild_id: [(timestamp, (role_data, moderator_id))]}
        'channel_deletes': {},  # {guild_id: [(timestamp, (channel_data, moderator_id))]}
    }
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
    
    print(f"🔍 [@MENTION CHECK] Checking message from {message.author} in {message.guild.name}")
    
    # Skip if user has moderator permissions
    if await has_permission_user(message.author, message.guild, "junior_moderator"):
        print(f"✅ [@MENTION CHECK] User {message.author} is moderator - skipping")
        return
    
    # Check if user is whitelisted for mention bypass
    if await is_whitelisted(message.guild.id, message.author.id, 'mention_everyone'):
        print(f"✅ [@MENTION CHECK] User {message.author} is whitelisted - skipping")
        return
    
    # Get security settings
    server_data = await get_server_data(message.guild.id)
    security_settings = server_data.get('security_settings', {})
    auto_timeout_mentions = security_settings.get('auto_timeout_mentions', {})
    
    print(f"📊 [@MENTION CHECK] auto_timeout_mentions settings: {auto_timeout_mentions}")
    
    if not auto_timeout_mentions.get('enabled', False):
        print(f"⚠️ [@MENTION CHECK] @everyone/@here protection NOT ENABLED for {message.guild.name}")
        return
    
    # Check for @everyone or @here mentions (both actual mentions AND text attempts)
    has_mention = message.mention_everyone  # Actual Discord mention that pings
    
    # Check for text attempts using regex to avoid false positives (e.g., email@here.com)
    # Negative lookbehind (?<!\S) ensures @ is not preceded by non-whitespace
    has_text_mention = bool(re.search(r'(?<!\S)@(?:everyone|here)\b', message.content, re.IGNORECASE))
    
    print(f"📊 [@MENTION CHECK] has_mention={has_mention}, has_text_mention={has_text_mention}, content='{message.content}'")
    
    if has_mention or has_text_mention:
        print(f"🚨 [@MENTION CHECK] VIOLATION DETECTED! Applying timeout...")

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
        app_commands.Choice(name="Anti-Alt Protection", value="anti_alt"),
        app_commands.Choice(name="Bot-Block (for bots)", value="bot_block"),
        app_commands.Choice(name="Malware Filter", value="malware_filter"),
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
            'anti_alt': '🚫 Anti-Alt Protection',
            'bot_block': '🤖 Bot-Block',
            'malware_filter': '🛡️ Malware Filter',
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

@bot.tree.command(name="security-config", description="⚙️ Configure security features - Main security control panel")
@app_commands.describe(
    feature="Security feature to configure",
    enabled="Enable or disable the feature",
    duration="Timeout duration in minutes (where applicable)",
    ban_threshold="Ban threshold for anti-nuke (default: 5)",
    kick_threshold="Kick threshold for anti-nuke (default: 5)",
    role_threshold="Role delete threshold for anti-nuke (default: 3)",
    channel_threshold="Channel delete threshold for anti-nuke (default: 3)",
    min_age_days="Minimum account age in days for anti-alt (default: 7)",
    strike_1="Warning count for Strike 1 - 1h timeout (default: 3)",
    strike_2="Warning count for Strike 2 - 24h timeout (default: 5)",
    strike_3="Warning count for Strike 3 - ban (default: 7)"
)
@app_commands.choices(feature=[
    app_commands.Choice(name="Auto-Timeout @everyone/@here", value="auto_timeout_mentions"),
    app_commands.Choice(name="Link Filter", value="link_filter"),
    app_commands.Choice(name="Anti-Invite", value="anti_invite"),
    app_commands.Choice(name="Anti-Spam", value="anti_spam"),
    app_commands.Choice(name="Anti-Raid", value="anti_raid"),
    app_commands.Choice(name="Anti-Nuke (Mass Bans/Kicks/Deletes)", value="anti_nuke"),
    app_commands.Choice(name="Permission Shield", value="permission_shield"),
    app_commands.Choice(name="Webhook Protection", value="webhook_protection"),
    app_commands.Choice(name="Anti-Alt (Quarantine New Accounts)", value="anti_alt"),
    app_commands.Choice(name="Auto Bot-Block", value="bot_block"),
    app_commands.Choice(name="Malware/File Filter", value="malware_filter"),
    app_commands.Choice(name="Auto Warning System", value="warning_system"),
    app_commands.Choice(name="Timeout: Bad Words Detection", value="timeout_bad_words"),
    app_commands.Choice(name="Timeout: Spam Detection", value="timeout_spam"),
    app_commands.Choice(name="Timeout: Link Detection", value="timeout_links"),
])
async def security_config_command(
    interaction: discord.Interaction,
    feature: str,
    enabled: bool,
    duration: int = 30,
    ban_threshold: int = 5,
    kick_threshold: int = 5,
    role_threshold: int = 3,
    channel_threshold: int = 3,
    min_age_days: int = 7,
    strike_1: int = 3,
    strike_2: int = 5,
    strike_3: int = 7
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
    elif feature == "link_filter":
        security_settings['link_filter'] = {
            'enabled': enabled
        }
    elif feature == "anti_invite":
        security_settings['anti_invite'] = {
            'enabled': enabled,
            'allowed_channels': []
        }
    elif feature == "anti_spam":
        security_settings['anti_spam'] = {
            'enabled': enabled,
            'timeout_duration': duration
        }
    elif feature == "anti_raid":
        security_settings['anti_raid'] = {
            'enabled': enabled,
            'threshold_seconds': 10,
            'join_threshold': 5
        }
    elif feature == "anti_nuke":
        security_settings['anti_nuke'] = {
            'enabled': enabled,
            'ban_threshold': ban_threshold,
            'kick_threshold': kick_threshold,
            'role_delete_threshold': role_threshold,
            'channel_delete_threshold': channel_threshold,
            'auto_rollback': True  # Enable automatic rollback
        }
    elif feature == "permission_shield":
        security_settings['permission_shield'] = {
            'enabled': enabled
        }
    elif feature == "webhook_protection":
        security_settings['webhook_protection'] = {
            'enabled': enabled
        }
    elif feature == "anti_alt":
        security_settings['anti_alt'] = {
            'enabled': enabled,
            'min_age_days': min_age_days
        }
    elif feature == "bot_block":
        security_settings['bot_block'] = {
            'enabled': enabled
        }
    elif feature == "malware_filter":
        security_settings['malware_filter'] = {
            'enabled': enabled
        }
    elif feature == "warning_system":
        security_settings['warning_system'] = {
            'enabled': enabled,
            'strike_1_warnings': strike_1,
            'strike_2_warnings': strike_2,
            'strike_3_warnings': strike_3
        }
    elif feature == "timeout_bad_words":
        timeout_settings = server_data.get('timeout_settings', {})
        timeout_settings['bad_words'] = enabled
        await update_server_data(interaction.guild.id, {'timeout_settings': timeout_settings})
    elif feature == "timeout_spam":
        timeout_settings = server_data.get('timeout_settings', {})
        timeout_settings['spam'] = enabled
        await update_server_data(interaction.guild.id, {'timeout_settings': timeout_settings})
    elif feature == "timeout_links":
        timeout_settings = server_data.get('timeout_settings', {})
        timeout_settings['links'] = enabled
        await update_server_data(interaction.guild.id, {'timeout_settings': timeout_settings})
    
    await update_server_data(interaction.guild.id, {'security_settings': security_settings})
    
    status = "✅ Enabled" if enabled else "❌ Disabled"
    feature_names = {
        'auto_timeout_mentions': '📣 Auto-Timeout @everyone/@here Mentions',
        'link_filter': '🔗 Link Filter',
        'anti_invite': '💬 Anti-Invite (Discord Invites)',
        'anti_spam': '💨 Anti-Spam',
        'anti_raid': '🚨 Anti-Raid (Mass Joins)',
        'anti_nuke': '🚫 Anti-Nuke (Mass Bans/Kicks/Deletes)',
        'permission_shield': '🛡️ Permission Shield',
        'webhook_protection': '🔗 Webhook Protection',
        'anti_alt': '🚫 Anti-Alt (Quarantine New Accounts)',
        'bot_block': '🤖 Auto Bot-Block',
        'malware_filter': '🛡️ Malware/File Filter',
        'warning_system': '⚠️ Auto Warning System',
        'timeout_bad_words': '🤬 Timeout: Bad Words Detection',
        'timeout_spam': '💨 Timeout: Spam Detection',
        'timeout_links': '🔗 Timeout: Link Detection'
    }
    
    # Build description based on feature type
    description_parts = [
        f"**◆ Feature:** {feature_names.get(feature, feature)}",
        f"**◆ Status:** {status}"
    ]
    
    if feature in ['auto_timeout_mentions', 'anti_spam']:
        description_parts.append(f"**◆ Duration:** {duration} minutes")
    
    if feature == 'anti_nuke':
        description_parts.append(f"**◆ Ban Threshold:** {ban_threshold}/min")
        description_parts.append(f"**◆ Kick Threshold:** {kick_threshold}/min")
        description_parts.append(f"**◆ Role Delete Threshold:** {role_threshold}/min")
        description_parts.append(f"**◆ Channel Delete Threshold:** {channel_threshold}/min")
        description_parts.append(f"**◆ Auto-Rollback:** Enabled")
    
    if feature == 'anti_alt':
        description_parts.append(f"**◆ Minimum Account Age:** {min_age_days} days")
    
    if feature == 'warning_system':
        description_parts.append(f"**◆ Strike 1 (1h timeout):** {strike_1} warnings")
        description_parts.append(f"**◆ Strike 2 (24h timeout):** {strike_2} warnings")
        description_parts.append(f"**◆ Strike 3 (ban):** {strike_3} warnings")
    
    embed = discord.Embed(
        title="⚡ **Security Configuration Updated**",
        description="\n".join(description_parts),
        color=BrandColors.PRIMARY if enabled else BrandColors.DANGER
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "security", f"⚙️ [SECURITY CONFIG] {feature_names.get(feature, feature)} {status} | By: {interaction.user}")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: LINK FILTER SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def check_link_filter(message):
    """Check for external links and delete if not whitelisted"""
    if message.author.bot or not message.guild:
        return
    
    print(f"🔍 [LINK FILTER] Checking message from {message.author} in {message.guild.name}")
    
    # Skip if user has moderator permissions
    if await has_permission_user(message.author, message.guild, "junior_moderator"):
        print(f"✅ [LINK FILTER] User {message.author} is moderator - skipping")
        return
    
    # Check if user is whitelisted for posting links
    if await is_whitelisted(message.guild.id, message.author.id, 'post_links'):
        print(f"✅ [LINK FILTER] User {message.author} is whitelisted - skipping")
        return
    
    # Get security settings
    server_data = await get_server_data(message.guild.id)
    security_settings = server_data.get('security_settings', {})
    link_filter = security_settings.get('link_filter', {})
    
    print(f"📊 [LINK FILTER] link_filter settings: {link_filter}")
    
    if not link_filter.get('enabled', False):
        print(f"⚠️ [LINK FILTER] Link filter NOT ENABLED for {message.guild.name}")
        return
    
    # Check for links (http://, https://, www.)
    link_pattern = r'(https?://|www\.)\S+'
    if re.search(link_pattern, message.content, re.IGNORECASE):
        # Delete the message
        try:
            await message.delete()
        except:
            pass
        
        # Send notification
        try:
            embed = discord.Embed(
                title="⚡ **Link Blocked**",
                description=f"**{message.author.mention}, external links are not allowed**\n\n💠 Message deleted by Quantum Security",
                color=BrandColors.DANGER
            )
            if message.guild and message.guild.me:
                embed.set_footer(text=BOT_FOOTER, icon_url=message.guild.me.display_avatar.url)
            else:
                embed.set_footer(text=BOT_FOOTER)
            await message.channel.send(embed=embed, delete_after=5)
        except:
            pass
        
        # Log action
        await log_action(message.guild.id, "security", f"🔗 [LINK FILTER] Blocked link from {message.author.mention} in {message.channel.mention}")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: ANTI-INVITE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def check_discord_invites(message):
    """Check for Discord invite links and delete if not in allowed channels"""
    if message.author.bot or not message.guild:
        return
    
    print(f"🔍 [ANTI-INVITE] Checking message from {message.author} in {message.guild.name}")
    
    # Skip if user has moderator permissions
    if await has_permission_user(message.author, message.guild, "junior_moderator"):
        print(f"✅ [ANTI-INVITE] User {message.author} is moderator - skipping")
        return
    
    # Check if user is whitelisted for posting invites
    if await is_whitelisted(message.guild.id, message.author.id, 'discord_invites'):
        print(f"✅ [ANTI-INVITE] User {message.author} is whitelisted - skipping")
        return
    
    # Get security settings
    server_data = await get_server_data(message.guild.id)
    security_settings = server_data.get('security_settings', {})
    anti_invite = security_settings.get('anti_invite', {})
    
    print(f"📊 [ANTI-INVITE] anti_invite settings: {anti_invite}")
    
    if not anti_invite.get('enabled', False):
        print(f"⚠️ [ANTI-INVITE] Anti-invite NOT ENABLED for {message.guild.name}")
        return
    
    # Check if channel is allowed
    allowed_channels = anti_invite.get('allowed_channels', [])
    if str(message.channel.id) in allowed_channels:
        return
    
    # Check for Discord invite links
    invite_pattern = r'(discord\.gg/|discord\.com/invite/|discordapp\.com/invite/)\S+'
    if re.search(invite_pattern, message.content, re.IGNORECASE):
        # Delete the message
        try:
            await message.delete()
        except:
            pass
        
        # Send notification
        try:
            embed = discord.Embed(
                title="⚡ **Discord Invite Blocked**",
                description=f"**{message.author.mention}, Discord invites are not allowed here**\n\n💠 Message deleted by Quantum Security",
                color=BrandColors.DANGER
            )
            if message.guild and message.guild.me:
                embed.set_footer(text=BOT_FOOTER, icon_url=message.guild.me.display_avatar.url)
            else:
                embed.set_footer(text=BOT_FOOTER)
            await message.channel.send(embed=embed, delete_after=5)
        except:
            pass
        
        # Log action
        await log_action(message.guild.id, "security", f"💬 [ANTI-INVITE] Blocked Discord invite from {message.author.mention} in {message.channel.mention}")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: ANTI-SPAM SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def check_spam(message):
    """Check for message spam and repeated content"""
    if message.author.bot or not message.guild:
        return
    
    print(f"🔍 [SPAM CHECK] Checking message from {message.author} in {message.guild.name}")
    
    # Skip if user has moderator permissions
    if await has_permission_user(message.author, message.guild, "junior_moderator"):
        print(f"✅ [SPAM CHECK] User {message.author} is moderator - skipping")
        return
    
    # Get security settings
    server_data = await get_server_data(message.guild.id)
    security_settings = server_data.get('security_settings', {})
    anti_spam = security_settings.get('anti_spam', {})
    
    print(f"📊 [SPAM CHECK] anti_spam settings: {anti_spam}")
    
    if not anti_spam.get('enabled', False):
        print(f"⚠️ [SPAM CHECK] Anti-spam NOT ENABLED for {message.guild.name}")
        return
    
    guild_id = str(message.guild.id)
    user_id = str(message.author.id)
    
    # Initialize tracking
    if guild_id not in enhanced_security_data['spam_tracking']:
        enhanced_security_data['spam_tracking'][guild_id] = {}
    
    if user_id not in enhanced_security_data['spam_tracking'][guild_id]:
        enhanced_security_data['spam_tracking'][guild_id][user_id] = {
            'messages': [],
            'last_message': '',
            'repeat_count': 0
        }
    
    user_spam_data = enhanced_security_data['spam_tracking'][guild_id][user_id]
    current_time = time.time()
    
    # Check for repeated messages
    if message.content == user_spam_data['last_message']:
        user_spam_data['repeat_count'] += 1
        
        # If repeated 3+ times, timeout user
        if user_spam_data['repeat_count'] >= 3:
            try:
                await message.delete()
            except:
                pass
            
            duration = anti_spam.get('timeout_duration', 10)
            await apply_enhanced_timeout(
                message.guild,
                message.author,
                duration,
                "Spam: Repeated messages",
                triggered_by="Anti-Spam System"
            )
            
            # Send notification
            try:
                embed = discord.Embed(
                    title="⚡ **Anti-Spam: User Timed Out**",
                    description=f"**{message.author.mention} has been timed out**\n\n**◆ Reason:** Repeated messages (spam)\n**◆ Duration:** {duration} minutes\n\n💠 Message deleted by Quantum Security",
                    color=BrandColors.DANGER
                )
                if message.guild and message.guild.me:
                    embed.set_footer(text=BOT_FOOTER, icon_url=message.guild.me.display_avatar.url)
                else:
                    embed.set_footer(text=BOT_FOOTER)
                await message.channel.send(embed=embed, delete_after=10)
            except:
                pass
            
            # Reset tracking
            user_spam_data['repeat_count'] = 0
            user_spam_data['messages'] = []
            return
    else:
        user_spam_data['repeat_count'] = 0
        user_spam_data['last_message'] = message.content
    
    # Check for message flood (5+ messages in 5 seconds)
    user_spam_data['messages'].append(current_time)
    user_spam_data['messages'] = [t for t in user_spam_data['messages'] if current_time - t < 5]
    
    if len(user_spam_data['messages']) >= 5:
        # Delete recent messages and timeout
        try:
            await message.delete()
        except:
            pass
        
        duration = anti_spam.get('timeout_duration', 10)
        await apply_enhanced_timeout(
            message.guild,
            message.author,
            duration,
            "Spam: Message flooding",
            triggered_by="Anti-Spam System"
        )
        
        # Send notification
        try:
            embed = discord.Embed(
                title="⚡ **Anti-Spam: User Timed Out**",
                description=f"**{message.author.mention} has been timed out**\n\n**◆ Reason:** Message flooding (5+ messages in 5s)\n**◆ Duration:** {duration} minutes\n\n💠 Quantum Security active",
                color=BrandColors.DANGER
            )
            if message.guild and message.guild.me:
                embed.set_footer(text=BOT_FOOTER, icon_url=message.guild.me.display_avatar.url)
            else:
                embed.set_footer(text=BOT_FOOTER)
            await message.channel.send(embed=embed, delete_after=10)
        except:
            pass
        
        # Reset tracking
        user_spam_data['messages'] = []

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: ANTI-RAID SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def check_raid_on_join(member):
    """Check for raid (mass joins) and enable raid mode"""
    guild = member.guild
    guild_id = str(guild.id)
    
    # Get security settings
    server_data = await get_server_data(guild.id)
    security_settings = server_data.get('security_settings', {})
    anti_raid = security_settings.get('anti_raid', {})
    
    if not anti_raid.get('enabled', False):
        return
    
    # Initialize tracking
    if guild_id not in enhanced_security_data['raid_tracking']:
        enhanced_security_data['raid_tracking'][guild_id] = {
            'joins': [],
            'raid_mode': False
        }
    
    raid_data = enhanced_security_data['raid_tracking'][guild_id]
    current_time = time.time()
    
    # Add this join to tracking
    raid_data['joins'].append(current_time)
    
    # Clean old joins (older than threshold seconds)
    threshold_seconds = anti_raid.get('threshold_seconds', 10)
    raid_data['joins'] = [t for t in raid_data['joins'] if current_time - t < threshold_seconds]
    
    # Check if raid threshold exceeded
    join_threshold = anti_raid.get('join_threshold', 5)
    
    if len(raid_data['joins']) >= join_threshold and not raid_data['raid_mode']:
        # Enable raid mode
        raid_data['raid_mode'] = True
        
        # Log raid detected
        await log_action(guild.id, "security", f"🚨 [ANTI-RAID] Raid detected! {len(raid_data['joins'])} joins in {threshold_seconds}s - RAID MODE ENABLED")
        
        # Send alert to security channel
        server_data = await get_server_data(guild.id)
        organized_logs = server_data.get('organized_log_channels', {})
        
        if organized_logs and 'security' in organized_logs:
            channel = bot.get_channel(int(organized_logs['security']))
            if channel:
                embed = discord.Embed(
                    title="🚨 **RAID ALERT - RAID MODE ACTIVATED**",
                    description=f"**◆ Detection:** {len(raid_data['joins'])} members joined in {threshold_seconds} seconds\n**◆ Status:** RAID MODE ENABLED\n**◆ Action:** New members will be kicked automatically\n\n💠 Use `/security-config` to disable raid mode",
                    color=BrandColors.DANGER
                )
                if guild.me:
                    embed.set_footer(text=BOT_FOOTER, icon_url=guild.me.display_avatar.url)
                else:
                    embed.set_footer(text=BOT_FOOTER)
                await channel.send(embed=embed)
    
    # If raid mode active, kick new members
    if raid_data['raid_mode']:
        try:
            await member.kick(reason="Auto-kicked during raid mode - RXT ENGINE Security")
            await log_action(guild.id, "security", f"🚨 [ANTI-RAID] Auto-kicked {member} ({member.id}) - Raid mode active")
        except Exception as e:
            print(f"⚠️ [ANTI-RAID] Could not kick {member}: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: UNIFIED MESSAGE CHECK HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def on_message_security_checks(message):
    """Run all Phase 2 security checks on messages (called from main.py)"""
    if message.author.bot or not message.guild:
        return
    
    print(f"🔍 [PHASE 2] Running all Phase 2 security checks for {message.author} in {message.guild.name}")
    
    # Run all checks (order matters - most strict first)
    await check_spam(message)  # Check spam first (can timeout user)
    await check_discord_invites(message)  # Check Discord invites
    await check_link_filter(message)  # Check external links

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: RAID MODE MANAGEMENT COMMAND
# ═══════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="raid-mode", description="🚨 Manually enable/disable raid mode")
@app_commands.describe(enabled="Enable or disable raid mode")
async def raid_mode_command(interaction: discord.Interaction, enabled: bool):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    
    # Initialize tracking
    if guild_id not in enhanced_security_data['raid_tracking']:
        enhanced_security_data['raid_tracking'][guild_id] = {
            'joins': [],
            'raid_mode': False
        }
    
    enhanced_security_data['raid_tracking'][guild_id]['raid_mode'] = enabled
    
    status = "🚨 ENABLED" if enabled else "✅ DISABLED"
    color = BrandColors.DANGER if enabled else BrandColors.SUCCESS
    
    embed = discord.Embed(
        title="⚡ **Raid Mode Updated**",
        description=f"**◆ Status:** {status}\n\n{'💠 New members will be automatically kicked' if enabled else '💠 Normal member joins resumed'}",
        color=color
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "security", f"🚨 [RAID MODE] {'Enabled' if enabled else 'Disabled'} by {interaction.user}")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: ANTI-NUKE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

# Add Phase 3 tracking to enhanced_security_data
enhanced_security_data['nuke_tracking'] = {
    'bans': {},  # {guild_id: [(timestamp, user_id, moderator_id)]}
    'kicks': {},  # {guild_id: [(timestamp, user_id, moderator_id)]}
    'role_deletes': {},  # {guild_id: [(timestamp, role_data, moderator_id)]}
    'channel_deletes': {},  # {guild_id: [(timestamp, channel_data, moderator_id)]}
}
enhanced_security_data['permission_backup'] = {}  # Backup of role permissions {guild_id: {role_id: permissions}}
enhanced_security_data['webhook_tracking'] = {}  # Track webhook actions {guild_id: [webhooks]}

async def check_nuke_threshold(guild_id, action_type, threshold, time_window=60):
    """Check if nuke threshold has been exceeded"""
    guild_id = str(guild_id)
    current_time = time.time()
    
    if guild_id not in enhanced_security_data['nuke_tracking'][action_type]:
        enhanced_security_data['nuke_tracking'][action_type][guild_id] = []
    
    # Clean old actions (older than time_window seconds)
    enhanced_security_data['nuke_tracking'][action_type][guild_id] = [
        action for action in enhanced_security_data['nuke_tracking'][action_type][guild_id]
        if current_time - action[0] < time_window
    ]
    
    # Check if threshold exceeded
    action_count = len(enhanced_security_data['nuke_tracking'][action_type][guild_id])
    return action_count >= threshold

async def track_nuke_action(guild_id, action_type, data):
    """Track a nuke action (ban/kick/delete)"""
    guild_id = str(guild_id)
    current_time = time.time()
    
    if guild_id not in enhanced_security_data['nuke_tracking'][action_type]:
        enhanced_security_data['nuke_tracking'][action_type][guild_id] = []
    
    enhanced_security_data['nuke_tracking'][action_type][guild_id].append((current_time, data))

async def handle_anti_nuke_alert(guild, action_type, count, moderator=None):
    """Send alert when nuke is detected"""
    action_names = {
        'bans': 'Mass Bans',
        'kicks': 'Mass Kicks',
        'role_deletes': 'Mass Role Deletions',
        'channel_deletes': 'Mass Channel Deletions'
    }
    
    action_name = action_names.get(action_type, 'Mass Actions')
    
    # Log to security channel
    await log_action(guild.id, "security", f"🚨 [ANTI-NUKE] {action_name} detected! {count} actions in 60 seconds - NUKE PROTECTION ACTIVATED")
    
    # Send critical alert to security channel
    server_data = await get_server_data(guild.id)
    organized_logs = server_data.get('organized_log_channels', {})
    
    if organized_logs and 'security' in organized_logs:
        channel = bot.get_channel(int(organized_logs['security']))
        if channel:
            mod_mention = moderator.mention if moderator else "Unknown"
            embed = discord.Embed(
                title="🚨 **ANTI-NUKE ALERT - PROTECTION ACTIVATED**",
                description=f"**◆ Detection:** {action_name}\n**◆ Count:** {count} actions in 60 seconds\n**◆ Moderator:** {mod_mention}\n**◆ Status:** NUKE PROTECTION ACTIVE\n\n💠 Future actions will be blocked automatically\n⚡ Server owner has been notified",
                color=BrandColors.DANGER
            )
            if guild.me:
                embed.set_footer(text=BOT_FOOTER, icon_url=guild.me.display_avatar.url)
            else:
                embed.set_footer(text=BOT_FOOTER)
            await channel.send(embed=embed)
    
    # Try to DM the server owner
    try:
        owner = guild.owner
        if owner:
            dm_embed = discord.Embed(
                title="🚨 **CRITICAL: Anti-Nuke Protection Activated**",
                description=f"**Server:** {guild.name}\n\n**◆ Alert:** {action_name} detected\n**◆ Count:** {count} actions in 60 seconds\n**◆ Moderator:** {moderator if moderator else 'Unknown'}\n\n⚡ RXT ENGINE Anti-Nuke system has activated and is blocking further destructive actions.\n\n💠 Review your server's security settings and moderator permissions immediately.",
                color=BrandColors.DANGER
            )
            if guild.me:
                dm_embed.set_footer(text=BOT_FOOTER, icon_url=guild.me.display_avatar.url)
            else:
                dm_embed.set_footer(text=BOT_FOOTER)
            await owner.send(embed=dm_embed)
            print(f"✅ [ANTI-NUKE] Sent owner DM for {guild.name}")
    except Exception as e:
        print(f"⚠️ [ANTI-NUKE] Could not DM owner: {e}")

async def on_member_ban_check(guild, user, moderator=None):
    """Check for mass bans (Anti-Nuke) with automatic rollback"""
    if not guild:
        return
    
    # Get security settings
    server_data = await get_server_data(guild.id)
    security_settings = server_data.get('security_settings', {})
    anti_nuke = security_settings.get('anti_nuke', {})
    
    if not anti_nuke.get('enabled', False):
        return
    
    # Track this ban
    await track_nuke_action(guild.id, 'bans', (user.id, moderator.id if moderator else None))
    
    # Check threshold (default: 5 bans in 60 seconds)
    threshold = anti_nuke.get('ban_threshold', 5)
    
    if await check_nuke_threshold(guild.id, 'bans', threshold):
        await handle_anti_nuke_alert(guild, 'bans', threshold, moderator)
        
        # AUTO-ROLLBACK: Unban all recently banned users
        if anti_nuke.get('auto_rollback', True):
            guild_id = str(guild.id)
            banned_users = enhanced_security_data.get('nuke_tracking', {}).get('bans', {}).get(guild_id, [])
            
            if not banned_users:
                print(f"⚠️ [ANTI-NUKE ROLLBACK] No banned users tracked for rollback")
                return True
            
            unbanned_count = 0
            for timestamp, (banned_user_id, ban_moderator_id) in banned_users:
                try:
                    # Unban the user
                    banned_user = await bot.fetch_user(int(banned_user_id))
                    await guild.unban(banned_user, reason="RXT ENGINE Anti-Nuke: Mass ban rollback")
                    unbanned_count += 1
                    print(f"✅ [ANTI-NUKE ROLLBACK] Unbanned {banned_user} (ID: {banned_user_id})")
                except Exception as e:
                    print(f"⚠️ [ANTI-NUKE ROLLBACK] Could not unban user {banned_user_id}: {e}")
            
            # Log rollback action
            await log_action(guild.id, "security", f"🔄 [ANTI-NUKE ROLLBACK] Automatically unbanned {unbanned_count} users after mass ban detection")
            
            # Clear the tracked bans
            enhanced_security_data['nuke_tracking']['bans'][guild_id] = []
            
            print(f"🔄 [ANTI-NUKE ROLLBACK] Unbanned {unbanned_count}/{len(banned_users)} users")
        
        return True  # Nuke detected
    
    return False

async def on_member_kick_check(guild, user, moderator=None):
    """Check for mass kicks (Anti-Nuke) with automatic re-invite via DM"""
    if not guild:
        return
    
    # Get security settings
    server_data = await get_server_data(guild.id)
    security_settings = server_data.get('security_settings', {})
    anti_nuke = security_settings.get('anti_nuke', {})
    
    if not anti_nuke.get('enabled', False):
        return
    
    # Track this kick
    await track_nuke_action(guild.id, 'kicks', (user.id, moderator.id if moderator else None))
    
    # Check threshold (default: 5 kicks in 60 seconds)
    threshold = anti_nuke.get('kick_threshold', 5)
    
    if await check_nuke_threshold(guild.id, 'kicks', threshold):
        await handle_anti_nuke_alert(guild, 'kicks', threshold, moderator)
        
        # AUTO-ROLLBACK: Send re-invite links to kicked users
        if anti_nuke.get('auto_rollback', True):
            guild_id = str(guild.id)
            kicked_users = enhanced_security_data.get('nuke_tracking', {}).get('kicks', {}).get(guild_id, [])
            
            if not kicked_users:
                print(f"⚠️ [ANTI-NUKE ROLLBACK] No kicked users tracked for rollback")
                return True
            
            # Create an invite link (valid for 1 day, 100 uses)
            try:
                # Find a suitable channel to create invite from (prefer system channel or first text channel)
                invite_channel = guild.system_channel or next((c for c in guild.text_channels if c.permissions_for(guild.me).create_instant_invite), None)
                
                if not invite_channel:
                    await log_action(guild.id, "security", f"⚠️ [ANTI-NUKE] Cannot create invite link - no suitable channel found")
                    return True
                
                invite = await invite_channel.create_invite(
                    max_age=86400,  # 1 day
                    max_uses=100,
                    reason="RXT ENGINE Anti-Nuke: Mass kick rollback - re-inviting kicked users"
                )
                
                reinvited_count = 0
                failed_count = 0
                
                for timestamp, (kicked_user_id, kick_moderator_id) in kicked_users:
                    try:
                        kicked_user = await bot.fetch_user(int(kicked_user_id))
                        
                        # DM the kicked user with re-invite link
                        embed = discord.Embed(
                            title="🚨 **RXT ENGINE Security Alert**",
                            description=f"**You were kicked from {guild.name} during a mass kick attack.**\n\nOur anti-nuke system detected this as a server raid. You can rejoin immediately using the link below:\n\n**[Click here to rejoin {guild.name}]({invite.url})**\n\nThis was not a legitimate kick. Our security system has alerted the server owner.",
                            color=BrandColors.WARNING
                        )
                        embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
                        
                        await kicked_user.send(embed=embed)
                        reinvited_count += 1
                        print(f"✅ [ANTI-NUKE ROLLBACK] Sent re-invite to {kicked_user} (ID: {kicked_user_id})")
                    except discord.Forbidden:
                        failed_count += 1
                        print(f"⚠️ [ANTI-NUKE ROLLBACK] Cannot DM user {kicked_user_id} - DMs disabled")
                    except Exception as e:
                        failed_count += 1
                        print(f"⚠️ [ANTI-NUKE ROLLBACK] Could not send re-invite to user {kicked_user_id}: {e}")
                
                # Log rollback action
                await log_action(guild.id, "security", f"🔄 [ANTI-NUKE ROLLBACK] Sent re-invite links to {reinvited_count}/{len(kicked_users)} kicked users (Failed: {failed_count} - DMs disabled)")
                
                # Clear the tracked kicks
                enhanced_security_data['nuke_tracking']['kicks'][guild_id] = []
                
                print(f"🔄 [ANTI-NUKE ROLLBACK] Sent re-invite to {reinvited_count}/{len(kicked_users)} users, {failed_count} failed")
                
            except Exception as e:
                await log_action(guild.id, "security", f"⚠️ [ANTI-NUKE] Could not create invite link: {e}")
                print(f"⚠️ [ANTI-NUKE ROLLBACK] Invite creation failed: {e}")
        
        return True  # Nuke detected
    
    return False

async def on_role_delete_check(guild, role, moderator=None):
    """Check for mass role deletions (Anti-Nuke) with automatic rollback"""
    if not guild:
        return
    
    # Get security settings
    server_data = await get_server_data(guild.id)
    security_settings = server_data.get('security_settings', {})
    anti_nuke = security_settings.get('anti_nuke', {})
    
    if not anti_nuke.get('enabled', False):
        return
    
    # Save role data for potential rollback
    role_data = {
        'id': role.id,
        'name': role.name,
        'color': role.color.value,
        'hoist': role.hoist,
        'mentionable': role.mentionable,
        'permissions': role.permissions.value,
        'position': role.position
    }
    
    # Track this role deletion
    await track_nuke_action(guild.id, 'role_deletes', (role_data, moderator.id if moderator else None))
    
    # Check threshold (default: 3 role deletions in 60 seconds)
    threshold = anti_nuke.get('role_delete_threshold', 3)
    
    if await check_nuke_threshold(guild.id, 'role_deletes', threshold):
        await handle_anti_nuke_alert(guild, 'role_deletes', threshold, moderator)
        
        # AUTO-ROLLBACK: Recreate deleted roles
        if anti_nuke.get('auto_rollback', True):
            guild_id = str(guild.id)
            deleted_roles = enhanced_security_data.get('nuke_tracking', {}).get('role_deletes', {}).get(guild_id, [])
            
            if not deleted_roles:
                print(f"⚠️ [ANTI-NUKE ROLLBACK] No deleted roles tracked for rollback")
                return True
            
            recreated_count = 0
            for timestamp, (deleted_role_data, delete_moderator_id) in deleted_roles:
                try:
                    # Recreate the role
                    new_role = await guild.create_role(
                        name=deleted_role_data['name'],
                        permissions=discord.Permissions(deleted_role_data['permissions']),
                        color=discord.Color(deleted_role_data['color']),
                        hoist=deleted_role_data['hoist'],
                        mentionable=deleted_role_data['mentionable'],
                        reason="RXT ENGINE Anti-Nuke: Mass role deletion rollback"
                    )
                    recreated_count += 1
                    print(f"✅ [ANTI-NUKE ROLLBACK] Recreated role: {deleted_role_data['name']}")
                except Exception as e:
                    print(f"⚠️ [ANTI-NUKE ROLLBACK] Could not recreate role {deleted_role_data['name']}: {e}")
            
            # Log rollback action
            await log_action(guild.id, "security", f"🔄 [ANTI-NUKE ROLLBACK] Automatically recreated {recreated_count} roles after mass deletion detection")
            
            # Clear the tracked role deletions
            enhanced_security_data['nuke_tracking']['role_deletes'][guild_id] = []
            
            print(f"🔄 [ANTI-NUKE ROLLBACK] Recreated {recreated_count}/{len(deleted_roles)} roles")
        
        return True  # Nuke detected
    
    return False

async def on_channel_delete_check(guild, channel, moderator=None):
    """Check for mass channel deletions (Anti-Nuke) with automatic rollback"""
    if not guild:
        return
    
    # Get security settings
    server_data = await get_server_data(guild.id)
    security_settings = server_data.get('security_settings', {})
    anti_nuke = security_settings.get('anti_nuke', {})
    
    if not anti_nuke.get('enabled', False):
        return
    
    # Save channel data for potential rollback
    channel_data = {
        'id': channel.id,
        'name': channel.name,
        'type': str(channel.type),
        'category': channel.category.name if channel.category else None,
        'category_id': channel.category.id if channel.category else None,
        'position': channel.position if hasattr(channel, 'position') else 0
    }
    
    # Add text channel specific data
    if isinstance(channel, discord.TextChannel):
        channel_data['topic'] = channel.topic
        channel_data['slowmode_delay'] = channel.slowmode_delay
        channel_data['nsfw'] = channel.nsfw
    
    # Track this channel deletion
    await track_nuke_action(guild.id, 'channel_deletes', (channel_data, moderator.id if moderator else None))
    
    # Check threshold (default: 3 channel deletions in 60 seconds)
    threshold = anti_nuke.get('channel_delete_threshold', 3)
    
    if await check_nuke_threshold(guild.id, 'channel_deletes', threshold):
        await handle_anti_nuke_alert(guild, 'channel_deletes', threshold, moderator)
        
        # AUTO-ROLLBACK: Recreate deleted channels
        if anti_nuke.get('auto_rollback', True):
            guild_id = str(guild.id)
            deleted_channels = enhanced_security_data.get('nuke_tracking', {}).get('channel_deletes', {}).get(guild_id, [])
            
            if not deleted_channels:
                print(f"⚠️ [ANTI-NUKE ROLLBACK] No deleted channels tracked for rollback")
                return True
            
            recreated_count = 0
            for timestamp, (deleted_channel_data, delete_moderator_id) in deleted_channels:
                try:
                    # Get category if it exists
                    category = None
                    if deleted_channel_data.get('category_id'):
                        category = guild.get_channel(int(deleted_channel_data['category_id']))
                    
                    # Recreate the channel (basic structure)
                    if 'text' in deleted_channel_data['type'].lower():
                        new_channel = await guild.create_text_channel(
                            name=deleted_channel_data['name'],
                            topic=deleted_channel_data.get('topic'),
                            slowmode_delay=deleted_channel_data.get('slowmode_delay', 0),
                            nsfw=deleted_channel_data.get('nsfw', False),
                            category=category,
                            reason="RXT ENGINE Anti-Nuke: Mass channel deletion rollback"
                        )
                    elif 'voice' in deleted_channel_data['type'].lower():
                        new_channel = await guild.create_voice_channel(
                            name=deleted_channel_data['name'],
                            category=category,
                            reason="RXT ENGINE Anti-Nuke: Mass channel deletion rollback"
                        )
                    else:
                        # Unknown channel type, skip
                        continue
                    
                    recreated_count += 1
                    print(f"✅ [ANTI-NUKE ROLLBACK] Recreated channel: {deleted_channel_data['name']}")
                except Exception as e:
                    print(f"⚠️ [ANTI-NUKE ROLLBACK] Could not recreate channel {deleted_channel_data['name']}: {e}")
            
            # Log rollback action
            await log_action(guild.id, "security", f"🔄 [ANTI-NUKE ROLLBACK] Automatically recreated {recreated_count} channels after mass deletion detection")
            
            # Clear the tracked channel deletions
            enhanced_security_data['nuke_tracking']['channel_deletes'][guild_id] = []
            
            print(f"🔄 [ANTI-NUKE ROLLBACK] Recreated {recreated_count}/{len(deleted_channels)} channels")
        
        return True  # Nuke detected
    
    return False

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: PERMISSION SHIELD SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def backup_role_permissions(guild):
    """Backup all role permissions for the guild"""
    guild_id = str(guild.id)
    
    if guild_id not in enhanced_security_data['permission_backup']:
        enhanced_security_data['permission_backup'][guild_id] = {}
    
    for role in guild.roles:
        enhanced_security_data['permission_backup'][guild_id][str(role.id)] = {
            'permissions': role.permissions.value,
            'name': role.name,
            'is_admin': role.permissions.administrator,
            'dangerous_perms': {
                'administrator': role.permissions.administrator,
                'manage_guild': role.permissions.manage_guild,
                'manage_channels': role.permissions.manage_channels,
                'manage_roles': role.permissions.manage_roles,
                'ban_members': role.permissions.ban_members,
                'kick_members': role.permissions.kick_members,
                'manage_webhooks': role.permissions.manage_webhooks
            }
        }

async def on_role_permission_change(before_role, after_role, moderator=None):
    """Detect and revert dangerous permission changes (Permission Shield)"""
    if not after_role.guild:
        return
    
    # Get security settings
    server_data = await get_server_data(after_role.guild.id)
    security_settings = server_data.get('security_settings', {})
    permission_shield = security_settings.get('permission_shield', {})
    
    if not permission_shield.get('enabled', False):
        return
    
    # Check for moderator whitelist
    if moderator:
        if await has_permission_user(moderator, after_role.guild, "main_moderator"):
            return  # Allow main moderators to change permissions
    
    # Dangerous permissions to monitor
    dangerous_perms = ['administrator', 'manage_guild', 'manage_channels', 'manage_roles', 'ban_members', 'kick_members', 'manage_webhooks']
    
    # Check if dangerous permissions were added
    permissions_added = []
    for perm in dangerous_perms:
        before_val = getattr(before_role.permissions, perm, False)
        after_val = getattr(after_role.permissions, perm, False)
        
        if not before_val and after_val:
            permissions_added.append(perm)
    
    # If dangerous permissions were added, revert
    if permissions_added:
        try:
            # Revert to previous permissions
            await after_role.edit(permissions=before_role.permissions, reason="RXT ENGINE Permission Shield - Reverting unauthorized permission changes")
            
            # Log action
            await log_action(after_role.guild.id, "security", f"🛡️ [PERMISSION SHIELD] Reverted unauthorized permission changes to {after_role.name} | Added permissions: {', '.join(permissions_added)} | By: {moderator if moderator else 'Unknown'}")
            
            # Send alert to security channel
            server_data = await get_server_data(after_role.guild.id)
            organized_logs = server_data.get('organized_log_channels', {})
            
            if organized_logs and 'security' in organized_logs:
                channel = bot.get_channel(int(organized_logs['security']))
                if channel:
                    mod_mention = moderator.mention if moderator else "Unknown"
                    embed = discord.Embed(
                        title="🛡️ **PERMISSION SHIELD ACTIVATED**",
                        description=f"**◆ Role:** {after_role.mention}\n**◆ Moderator:** {mod_mention}\n**◆ Blocked Permissions:** {', '.join(permissions_added)}\n\n⚡ Unauthorized permission changes have been automatically reverted\n💠 RXT ENGINE Permission Shield Active",
                        color=BrandColors.WARNING
                    )
                    if after_role.guild.me:
                        embed.set_footer(text=BOT_FOOTER, icon_url=after_role.guild.me.display_avatar.url)
                    else:
                        embed.set_footer(text=BOT_FOOTER)
                    await channel.send(embed=embed)
            
            print(f"🛡️ [PERMISSION SHIELD] Reverted permissions on {after_role.name}: {', '.join(permissions_added)}")
            return True  # Permissions reverted
            
        except Exception as e:
            print(f"❌ [PERMISSION SHIELD] Failed to revert permissions: {e}")
            await log_action(after_role.guild.id, "security", f"❌ [PERMISSION SHIELD ERROR] Could not revert permissions on {after_role.name}: {e}")
    
    return False

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: WEBHOOK PROTECTION SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def on_webhook_create_check(webhook, moderator=None):
    """Prevent unauthorized webhook creation"""
    if not webhook.guild:
        return
    
    # Get security settings
    server_data = await get_server_data(webhook.guild.id)
    security_settings = server_data.get('security_settings', {})
    webhook_protection = security_settings.get('webhook_protection', {})
    
    if not webhook_protection.get('enabled', False):
        return
    
    # Check for moderator whitelist
    if moderator:
        if await has_permission_user(moderator, webhook.guild, "main_moderator"):
            await log_action(webhook.guild.id, "security", f"🔗 [WEBHOOK] Created by authorized moderator: {webhook.name} in #{webhook.channel.name}")
            return False  # Allow authorized creation
    
    # Unauthorized webhook creation detected
    try:
        # Delete the webhook
        await webhook.delete(reason="RXT ENGINE Webhook Protection - Unauthorized webhook creation")
        
        # Log action
        await log_action(webhook.guild.id, "security", f"🔗 [WEBHOOK PROTECTION] Blocked unauthorized webhook creation: {webhook.name} in #{webhook.channel.name} | By: {moderator if moderator else 'Unknown'}")
        
        # Send alert to security channel
        server_data = await get_server_data(webhook.guild.id)
        organized_logs = server_data.get('organized_log_channels', {})
        
        if organized_logs and 'security' in organized_logs:
            channel = bot.get_channel(int(organized_logs['security']))
            if channel:
                mod_mention = moderator.mention if moderator else "Unknown"
                embed = discord.Embed(
                    title="🔗 **WEBHOOK PROTECTION ACTIVATED**",
                    description=f"**◆ Webhook Name:** {webhook.name}\n**◆ Channel:** #{webhook.channel.name}\n**◆ Moderator:** {mod_mention}\n\n⚡ Unauthorized webhook has been deleted\n💠 RXT ENGINE Webhook Protection Active",
                    color=BrandColors.WARNING
                )
                if webhook.guild.me:
                    embed.set_footer(text=BOT_FOOTER, icon_url=webhook.guild.me.display_avatar.url)
                else:
                    embed.set_footer(text=BOT_FOOTER)
                await channel.send(embed=embed)
        
        print(f"🔗 [WEBHOOK PROTECTION] Deleted unauthorized webhook: {webhook.name}")
        return True  # Webhook deleted
        
    except Exception as e:
        print(f"❌ [WEBHOOK PROTECTION] Failed to delete webhook: {e}")
        await log_action(webhook.guild.id, "security", f"❌ [WEBHOOK PROTECTION ERROR] Could not delete webhook {webhook.name}: {e}")
    
    return False

async def on_webhook_delete_check(webhook, moderator=None):
    """Log webhook deletions"""
    if not webhook.guild:
        return
    
    # Get security settings
    server_data = await get_server_data(webhook.guild.id)
    security_settings = server_data.get('security_settings', {})
    webhook_protection = security_settings.get('webhook_protection', {})
    
    if not webhook_protection.get('enabled', False):
        return
    
    # Log webhook deletion
    await log_action(webhook.guild.id, "security", f"🔗 [WEBHOOK] Deleted: {webhook.name} from #{webhook.channel.name if webhook.channel else 'Unknown'} | By: {moderator if moderator else 'Unknown'}")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: ANTI-ALT SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

enhanced_security_data['quarantine_roles'] = {}  # Store quarantine role IDs {guild_id: role_id}

async def get_or_create_quarantine_role(guild):
    """Get or create the quarantine role for alt accounts"""
    guild_id = str(guild.id)
    
    # Check cache
    if guild_id in enhanced_security_data['quarantine_roles']:
        role_id = enhanced_security_data['quarantine_roles'][guild_id]
        role = guild.get_role(int(role_id))
        if role:
            return role
    
    # Check database
    server_data = await get_server_data(guild.id)
    security_settings = server_data.get('security_settings', {})
    quarantine_role_id = security_settings.get('quarantine_role_id')
    
    if quarantine_role_id:
        role = guild.get_role(int(quarantine_role_id))
        if role:
            enhanced_security_data['quarantine_roles'][guild_id] = quarantine_role_id
            return role
    
    # Create new quarantine role
    try:
        role = await guild.create_role(
            name="🚫 Quarantine",
            color=discord.Color(BrandColors.WARNING),
            reason="RXT ENGINE Anti-Alt System - Auto-created",
            mentionable=False
        )
        
        # Save to database
        security_settings['quarantine_role_id'] = str(role.id)
        await update_server_data(guild.id, {'security_settings': security_settings})
        enhanced_security_data['quarantine_roles'][guild_id] = str(role.id)
        
        # Set permissions - deny most actions
        for channel in guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                try:
                    await channel.set_permissions(
                        role,
                        view_channel=True,
                        send_messages=False,
                        connect=False,
                        speak=False,
                        reason="Quarantine role - restricted access"
                    )
                except Exception as e:
                    print(f"⚠️ [ANTI-ALT] Could not set permissions for {channel.name}: {e}")
        
        await log_action(guild.id, "security", f"⚡ [ANTI-ALT] Created quarantine role: {role.name}")
        print(f"✅ [ANTI-ALT] Created quarantine role in {guild.name}")
        return role
        
    except Exception as e:
        print(f"❌ [ANTI-ALT] Error creating quarantine role: {e}")
        return None

async def check_anti_alt(member):
    """Check if member is an alt account and quarantine if necessary"""
    if not member.guild:
        return
    
    # Get security settings
    server_data = await get_server_data(member.guild.id)
    security_settings = server_data.get('security_settings', {})
    anti_alt = security_settings.get('anti_alt', {})
    
    if not anti_alt.get('enabled', False):
        return
    
    # Check if user is whitelisted
    if await is_whitelisted(member.guild.id, member.id, 'anti_alt'):
        return
    
    # Calculate account age in days
    account_age = (datetime.now() - member.created_at.replace(tzinfo=None)).days
    min_age_days = anti_alt.get('min_age_days', 7)
    
    if account_age < min_age_days:
        # Account is too new - quarantine
        quarantine_role = await get_or_create_quarantine_role(member.guild)
        if not quarantine_role:
            await log_action(member.guild.id, "security", f"❌ [ANTI-ALT ERROR] Could not create quarantine role for {member}")
            return
        
        try:
            # Add quarantine role
            await member.add_roles(quarantine_role, reason=f"RXT ENGINE Anti-Alt: Account age {account_age} days (minimum: {min_age_days} days)")
            
            # Log action
            await log_action(member.guild.id, "security", f"🚫 [ANTI-ALT] Quarantined {member.mention} | Account age: {account_age} days (Min: {min_age_days} days)")
            
            # Send alert to security channel
            organized_logs = server_data.get('organized_log_channels', {})
            if organized_logs and 'security' in organized_logs:
                channel = bot.get_channel(int(organized_logs['security']))
                if channel:
                    embed = discord.Embed(
                        title="🚫 **ANTI-ALT PROTECTION ACTIVATED**",
                        description=f"**◆ User:** {member.mention}\n**◆ Account Age:** {account_age} days\n**◆ Required Age:** {min_age_days} days\n**◆ Account Created:** <t:{int(member.created_at.timestamp())}:R>\n\n⚡ User has been quarantined\n💠 Review manually to release",
                        color=BrandColors.WARNING
                    )
                    if member.guild.me:
                        embed.set_footer(text=BOT_FOOTER, icon_url=member.guild.me.display_avatar.url)
                    else:
                        embed.set_footer(text=BOT_FOOTER)
                    await channel.send(embed=embed)
            
            # Send DM to user
            try:
                dm_embed = discord.Embed(
                    title="🚫 **Account Quarantined**",
                    description=f"**Welcome to {member.guild.name}!**\n\n**Your account has been temporarily quarantined because it's too new.**\n\n**◆ Your Account Age:** {account_age} days\n**◆ Required Age:** {min_age_days} days\n\n💠 This is an automated security measure to prevent alt accounts and raids.\n⚡ A moderator will review your account shortly.",
                    color=BrandColors.WARNING
                )
                dm_embed.set_footer(text=BOT_FOOTER)
                await member.send(embed=dm_embed)
            except:
                pass
            
            print(f"🚫 [ANTI-ALT] Quarantined {member} - Account age: {account_age} days")
            
        except Exception as e:
            print(f"❌ [ANTI-ALT] Error quarantining {member}: {e}")
            await log_action(member.guild.id, "security", f"❌ [ANTI-ALT ERROR] Could not quarantine {member.mention}: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: AUTO BOT-BLOCK SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def check_bot_block(member):
    """Block unauthorized bot joins"""
    if not member.bot or not member.guild:
        return
    
    # Get security settings
    server_data = await get_server_data(member.guild.id)
    security_settings = server_data.get('security_settings', {})
    bot_block = security_settings.get('bot_block', {})
    
    if not bot_block.get('enabled', False):
        return
    
    # Check if bot is whitelisted
    if await is_whitelisted(member.guild.id, member.id, 'bot_block'):
        await log_action(member.guild.id, "security", f"✅ [BOT-BLOCK] Allowed whitelisted bot: {member} ({member.id})")
        return
    
    # Bot is not whitelisted - kick it
    try:
        # Log action first
        await log_action(member.guild.id, "security", f"🤖 [BOT-BLOCK] Blocked unauthorized bot: {member} ({member.id})")
        
        # Send alert to security channel
        organized_logs = server_data.get('organized_log_channels', {})
        if organized_logs and 'security' in organized_logs:
            channel = bot.get_channel(int(organized_logs['security']))
            if channel:
                embed = discord.Embed(
                    title="🤖 **AUTO BOT-BLOCK ACTIVATED**",
                    description=f"**◆ Bot:** {member.mention}\n**◆ Bot Name:** {member.name}\n**◆ Bot ID:** {member.id}\n\n⚡ Unauthorized bot has been blocked\n💠 Use `/security-whitelist add bot_block @bot` to approve bots",
                    color=BrandColors.DANGER
                )
                if member.guild.me:
                    embed.set_footer(text=BOT_FOOTER, icon_url=member.guild.me.display_avatar.url)
                else:
                    embed.set_footer(text=BOT_FOOTER)
                await channel.send(embed=embed)
        
        # Kick the bot
        await member.kick(reason="RXT ENGINE Auto Bot-Block - Unauthorized bot join")
        print(f"🤖 [BOT-BLOCK] Kicked unauthorized bot: {member.name}")
        
    except Exception as e:
        print(f"❌ [BOT-BLOCK] Error kicking bot {member}: {e}")
        await log_action(member.guild.id, "security", f"❌ [BOT-BLOCK ERROR] Could not kick bot {member.mention}: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: FILE/MALWARE FILTER SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

# List of known malicious/suspicious file extensions and domains
BLOCKED_FILE_EXTENSIONS = [
    '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', '.jar',
    '.msi', '.app', '.deb', '.rpm', '.dmg', '.pkg', '.apk', '.ipa',
    '.dll', '.sys', '.drv', '.ocx', '.cpl', '.inf', '.ins', '.isp',
    '.reg', '.scf', '.lnk', '.hta', '.chm', '.gadget', '.msc', '.ps1',
    '.psm1', '.psc1', '.psd1', '.pssc', '.pl', '.py', '.rb', '.sh'
]

SUSPICIOUS_DOMAINS = [
    'grabify', 'iplogger', 'blasze', 'linkify', 'streamable', 'bit.ly',
    'tinyurl', 'discord.gg', 'discordapp', 'discord.com/api/webhooks',
    'steamcommunity.com/openid', 'steemcommunity', 'discordnitro',
    'steam-wallet', 'discrod', 'dlscord', 'free-nitro', 'steamcommunnity'
]

async def check_malware_filter(message):
    """Check message for malicious files and links"""
    if message.author.bot or not message.guild:
        return
    
    print(f"🔍 [MALWARE FILTER] Checking message from {message.author} in {message.guild.name}")
    
    # Get security settings
    server_data = await get_server_data(message.guild.id)
    security_settings = server_data.get('security_settings', {})
    malware_filter = security_settings.get('malware_filter', {})
    
    print(f"📊 [MALWARE FILTER] malware_filter settings: {malware_filter}")
    
    if not malware_filter.get('enabled', False):
        print(f"⚠️ [MALWARE FILTER] Malware filter NOT ENABLED for {message.guild.name}")
        return
    
    # Check if user has moderator permissions (exempt)
    if await has_permission_user(message.author, message.guild, "junior_moderator"):
        print(f"✅ [MALWARE FILTER] User {message.author} is moderator - skipping")
        return
    
    # Check if user is whitelisted
    if await is_whitelisted(message.guild.id, message.author.id, 'malware_filter'):
        print(f"✅ [MALWARE FILTER] User {message.author} is whitelisted - skipping")
        return
    
    is_dangerous = False
    danger_reason = ""
    
    # Check attachments for dangerous file extensions
    for attachment in message.attachments:
        file_ext = attachment.filename[attachment.filename.rfind('.'):].lower() if '.' in attachment.filename else ''
        if file_ext in BLOCKED_FILE_EXTENSIONS:
            is_dangerous = True
            danger_reason = f"Blocked file type: {file_ext}"
            break
    
    # Check message content for suspicious links
    if not is_dangerous and message.content:
        content_lower = message.content.lower()
        for domain in SUSPICIOUS_DOMAINS:
            if domain in content_lower:
                is_dangerous = True
                danger_reason = f"Suspicious domain detected: {domain}"
                break
    
    if is_dangerous:
        # Delete the message
        try:
            await message.delete()
        except:
            pass
        
        # Log action
        await log_action(message.guild.id, "security", f"🛡️ [MALWARE FILTER] Blocked dangerous content from {message.author.mention} | Reason: {danger_reason}")
        
        # Apply warning (if warning system is enabled)
        await add_warning(message.guild, message.author, "Auto-Warning: Posted malicious/dangerous content", triggered_by="Auto-Security System")
        
        # Send notification in channel
        try:
            embed = discord.Embed(
                title="🛡️ **Malware Filter Activated**",
                description=f"**{message.author.mention}, your message was deleted**\n\n**◆ Reason:** {danger_reason}\n**◆ Action:** Auto-warning applied\n\n💠 Do not share malicious files or suspicious links",
                color=BrandColors.DANGER
            )
            if message.guild and message.guild.me:
                embed.set_footer(text=BOT_FOOTER, icon_url=message.guild.me.display_avatar.url)
            else:
                embed.set_footer(text=BOT_FOOTER)
            await message.channel.send(embed=embed, delete_after=10)
        except:
            pass
        
        # Send alert to security channel
        organized_logs = server_data.get('organized_log_channels', {})
        if organized_logs and 'security' in organized_logs:
            channel = bot.get_channel(int(organized_logs['security']))
            if channel:
                embed = discord.Embed(
                    title="🛡️ **MALWARE FILTER ALERT**",
                    description=f"**◆ User:** {message.author.mention}\n**◆ Channel:** {message.channel.mention}\n**◆ Reason:** {danger_reason}\n**◆ Message:** {message.content[:200] if message.content else 'File attachment'}\n\n⚡ Content deleted and warning applied",
                    color=BrandColors.DANGER
                )
                if message.guild.me:
                    embed.set_footer(text=BOT_FOOTER, icon_url=message.guild.me.display_avatar.url)
                else:
                    embed.set_footer(text=BOT_FOOTER)
                await channel.send(embed=embed)
        
        print(f"🛡️ [MALWARE FILTER] Blocked content from {message.author} - {danger_reason}")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: AUTO WARNING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

enhanced_security_data['warnings'] = {}  # Store user warnings {guild_id: {user_id: [warnings]}}

async def add_warning(guild, member, reason, triggered_by="System"):
    """Add a warning to a user and apply escalating punishments"""
    guild_id = str(guild.id)
    user_id = str(member.id)
    
    # Initialize tracking
    if guild_id not in enhanced_security_data['warnings']:
        enhanced_security_data['warnings'][guild_id] = {}
    
    if user_id not in enhanced_security_data['warnings'][guild_id]:
        enhanced_security_data['warnings'][guild_id][user_id] = []
    
    # Add warning with timestamp
    warning_data = {
        'reason': reason,
        'timestamp': datetime.now().isoformat(),
        'triggered_by': triggered_by
    }
    enhanced_security_data['warnings'][guild_id][user_id].append(warning_data)
    
    # Save to database
    server_data = await get_server_data(guild.id)
    saved_warnings = server_data.get('user_warnings', {})
    saved_warnings[user_id] = enhanced_security_data['warnings'][guild_id][user_id]
    await update_server_data(guild.id, {'user_warnings': saved_warnings})
    
    # Get warning count
    warning_count = len(enhanced_security_data['warnings'][guild_id][user_id])
    
    # Get warning system settings
    security_settings = server_data.get('security_settings', {})
    warning_system = security_settings.get('warning_system', {})
    
    if not warning_system.get('enabled', False):
        return
    
    # Apply escalating punishments based on strike levels
    strike_1 = warning_system.get('strike_1_warnings', 3)
    strike_2 = warning_system.get('strike_2_warnings', 5)
    strike_3 = warning_system.get('strike_3_warnings', 7)
    
    action_taken = None
    
    if warning_count >= strike_3:
        # Strike 3: Ban
        try:
            await member.ban(reason=f"RXT ENGINE Auto-Warning: {warning_count} warnings - Strike 3")
            action_taken = f"🔨 BANNED (Strike 3 - {warning_count} warnings)"
            print(f"🔨 [WARNING SYSTEM] Banned {member} - {warning_count} warnings")
        except Exception as e:
            print(f"❌ [WARNING SYSTEM] Could not ban {member}: {e}")
    
    elif warning_count >= strike_2:
        # Strike 2: Timeout (24 hours)
        try:
            await apply_enhanced_timeout(guild, member, 1440, f"Auto-Warning Strike 2: {warning_count} warnings", triggered_by="Auto-Warning System")
            action_taken = f"⏰ TIMEOUT 24H (Strike 2 - {warning_count} warnings)"
            print(f"⏰ [WARNING SYSTEM] Timed out {member} for 24h - {warning_count} warnings")
        except Exception as e:
            print(f"❌ [WARNING SYSTEM] Could not timeout {member}: {e}")
    
    elif warning_count >= strike_1:
        # Strike 1: Timeout (1 hour)
        try:
            await apply_enhanced_timeout(guild, member, 60, f"Auto-Warning Strike 1: {warning_count} warnings", triggered_by="Auto-Warning System")
            action_taken = f"⏰ TIMEOUT 1H (Strike 1 - {warning_count} warnings)"
            print(f"⏰ [WARNING SYSTEM] Timed out {member} for 1h - {warning_count} warnings")
        except Exception as e:
            print(f"❌ [WARNING SYSTEM] Could not timeout {member}: {e}")
    else:
        action_taken = f"⚠️ WARNING #{warning_count}"
    
    # Log action
    await log_action(guild.id, "security", f"⚠️ [AUTO-WARNING] {member.mention} | Warning #{warning_count} | Reason: {reason} | Action: {action_taken}")
    
    # Send DM to user
    try:
        dm_embed = discord.Embed(
            title="⚠️ **Auto-Warning Issued**",
            description=f"**You have received a warning in {guild.name}**\n\n**◆ Reason:** {reason}\n**◆ Warning Count:** {warning_count}\n**◆ Action:** {action_taken}\n\n💠 Further violations may result in timeout or ban",
            color=BrandColors.WARNING if warning_count < strike_1 else BrandColors.DANGER
        )
        dm_embed.set_footer(text=BOT_FOOTER)
        await member.send(embed=dm_embed)
    except:
        pass
    
    return warning_count

async def clear_warnings(guild, member):
    """Clear all warnings for a user"""
    guild_id = str(guild.id)
    user_id = str(member.id)
    
    # Clear from memory
    if guild_id in enhanced_security_data['warnings']:
        if user_id in enhanced_security_data['warnings'][guild_id]:
            del enhanced_security_data['warnings'][guild_id][user_id]
    
    # Clear from database
    server_data = await get_server_data(guild.id)
    saved_warnings = server_data.get('user_warnings', {})
    if user_id in saved_warnings:
        del saved_warnings[user_id]
        await update_server_data(guild.id, {'user_warnings': saved_warnings})
    
    await log_action(guild.id, "security", f"✅ [WARNING SYSTEM] Cleared all warnings for {member.mention}")

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: UNIFIED MEMBER JOIN HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def on_member_join_phase4_checks(member):
    """Run all Phase 4 security checks on member join (called from main.py)"""
    if not member.guild:
        return
    
    # Run all Phase 4 checks
    await check_anti_alt(member)  # Check for alt accounts
    await check_bot_block(member)  # Check for unauthorized bots

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: UNIFIED MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def on_message_phase4_checks(message):
    """Run all Phase 4 security checks on messages (called from main.py)"""
    if message.author.bot or not message.guild:
        return
    
    # Run Phase 4 checks
    await check_malware_filter(message)  # Check for malicious files/links

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: WARNING SYSTEM COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="warn", description="⚠️ Issue a manual warning to a user")
@app_commands.describe(
    member="User to warn",
    reason="Reason for the warning"
)
async def warn_command(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
    
    # Add warning
    warning_count = await add_warning(interaction.guild, member, reason, triggered_by=str(interaction.user))
    
    embed = discord.Embed(
        title="⚠️ **Warning Issued**",
        description=f"**◆ User:** {member.mention}\n**◆ Reason:** {reason}\n**◆ Total Warnings:** {warning_count}\n\n✅ Warning has been recorded",
        color=BrandColors.WARNING
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="warnings", description="📋 View a user's warning history")
@app_commands.describe(member="User to check warnings for")
async def warnings_command(interaction: discord.Interaction, member: discord.Member):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    user_id = str(member.id)
    
    # Get warnings from memory or database
    warnings = []
    if guild_id in enhanced_security_data['warnings'] and user_id in enhanced_security_data['warnings'][guild_id]:
        warnings = enhanced_security_data['warnings'][guild_id][user_id]
    else:
        # Try database
        server_data = await get_server_data(interaction.guild.id)
        saved_warnings = server_data.get('user_warnings', {})
        if user_id in saved_warnings:
            warnings = saved_warnings[user_id]
    
    if not warnings:
        embed = discord.Embed(
            title="📋 **Warning History**",
            description=f"**◆ User:** {member.mention}\n**◆ Total Warnings:** 0\n\n✅ No warnings on record",
            color=BrandColors.SUCCESS
        )
    else:
        warning_list = []
        for i, warning in enumerate(warnings[-10:], 1):  # Show last 10 warnings
            timestamp = warning.get('timestamp', 'Unknown')
            reason = warning.get('reason', 'No reason provided')
            by = warning.get('triggered_by', 'System')
            warning_list.append(f"**{i}.** {reason}\n*By: {by} | {timestamp[:10]}*")
        
        embed = discord.Embed(
            title="📋 **Warning History**",
            description=f"**◆ User:** {member.mention}\n**◆ Total Warnings:** {len(warnings)}\n\n" + "\n\n".join(warning_list),
            color=BrandColors.WARNING
        )
    
    embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clearwarnings", description="🗑️ Clear all warnings for a user")
@app_commands.describe(member="User to clear warnings for")
async def clearwarnings_command(interaction: discord.Interaction, member: discord.Member):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
    
    await clear_warnings(interaction.guild, member)
    
    embed = discord.Embed(
        title="✅ **Warnings Cleared**",
        description=f"**◆ User:** {member.mention}\n\n✅ All warnings have been cleared",
        color=BrandColors.SUCCESS
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="security-timeout-channel", description="🔒 Configure timeout channel for isolated communication")
@app_commands.describe(
    channel="Channel where timed-out members can chat (leave empty to disable)"
)
async def security_timeout_channel_config(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    server_data = await get_server_data(interaction.guild.id)
    timeout_settings = server_data.get('timeout_settings', {})
    
    if channel:
        timeout_settings['timeout_channel'] = str(channel.id)
        status_msg = f"✅ Timeout channel set to {channel.mention}"
        description = f"**Timeout Channel:** {channel.mention}\n**Status:** Active\n\n⚡ **How it works:**\nWhen a member is timed out, they will:\n• Lose access to all server channels\n• Only see and chat in {channel.mention}\n• Have restrictions removed when timeout ends\n\n💠 This provides 100% isolation for timed-out members"
        color = BrandColors.SUCCESS
    else:
        timeout_settings.pop('timeout_channel', None)
        status_msg = "❌ Timeout channel disabled"
        description = "**Status:** Disabled\n\nTimed-out members will use Discord's default timeout system only."
        color = BrandColors.WARNING
    
    await update_server_data(interaction.guild.id, {'timeout_settings': timeout_settings})
    
    embed = discord.Embed(
        title="🔒 **Timeout Channel Configuration**",
        description=description,
        color=color
    )
    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "security", f"🔒 [TIMEOUT CHANNEL] {status_msg} by {interaction.user}")

@bot.tree.command(name="security-status", description="📊 View all security settings for this server")
async def security_status_command(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return
    
    server_data = await get_server_data(interaction.guild.id)
    security_settings = server_data.get('security_settings', {})
    timeout_settings = server_data.get('timeout_settings', {})
    
    def get_status_emoji(setting_dict):
        return "✅" if setting_dict.get('enabled', False) else "❌"
    
    def get_timeout_status(setting_key):
        return "✅" if timeout_settings.get(setting_key, True) else "❌"
    
    embed = discord.Embed(
        title="🛡️ **Security System Status**",
        description=f"**Server:** {interaction.guild.name}\n\n**Complete security overview for this server**",
        color=BrandColors.PRIMARY
    )
    
    auto_security = f"{get_status_emoji(security_settings.get('auto_timeout_mentions', {}))} @everyone/@here Protection\n"
    auto_security += f"{get_status_emoji(security_settings.get('anti_spam', {}))} Anti-Spam\n"
    auto_security += f"{get_status_emoji(security_settings.get('anti_raid', {}))} Anti-Raid\n"
    auto_security += f"{get_status_emoji(security_settings.get('anti_nuke', {}))} Anti-Nuke"
    
    content_filters = f"{get_status_emoji(security_settings.get('link_filter', {}))} Link Filter\n"
    content_filters += f"{get_status_emoji(security_settings.get('anti_invite', {}))} Anti-Invite\n"
    content_filters += f"{get_status_emoji(security_settings.get('malware_filter', {}))} Malware Filter"
    
    member_protection = f"{get_status_emoji(security_settings.get('anti_alt', {}))} Anti-Alt Accounts\n"
    member_protection += f"{get_status_emoji(security_settings.get('bot_block', {}))} Auto Bot-Block\n"
    member_protection += f"{get_status_emoji(security_settings.get('warning_system', {}))} Auto Warning System"
    
    timeout_system = f"{get_timeout_status('bad_words')} Bad Words Detection\n"
    timeout_system += f"{get_timeout_status('spam')} Spam Detection\n"
    timeout_system += f"{get_timeout_status('links')} Link Detection"
    
    embed.add_field(name="🚨 Auto Security", value=auto_security, inline=True)
    embed.add_field(name="🔗 Content Filters", value=content_filters, inline=True)
    embed.add_field(name="👥 Member Protection", value=member_protection, inline=True)
    embed.add_field(name="⏰ Timeout System", value=timeout_system, inline=False)
    
    timeout_channel_id = timeout_settings.get('timeout_channel')
    if timeout_channel_id:
        timeout_channel = interaction.guild.get_channel(int(timeout_channel_id))
        if timeout_channel:
            embed.add_field(name="🔒 Timeout Channel", value=f"{timeout_channel.mention}", inline=False)
    
    embed.set_footer(text=f"{BOT_FOOTER} • Use /security-config to modify settings", icon_url=bot.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

print("✅ [ENHANCED SECURITY] Phase 1, 2, 3 & 4 systems loaded - Full Security Suite Active")
