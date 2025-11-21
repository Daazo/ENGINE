import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import re
from collections import defaultdict
from brand_config import BrandColors, VisualElements, BOT_FOOTER

user_message_timestamps = defaultdict(lambda: defaultdict(list))
user_join_timestamps = defaultdict(list)

_bot_instance = None
_get_server_data = None
_update_server_data = None
_log_action = None
_has_permission = None
_setup_complete = False

async def get_security_config(guild_id: int) -> Dict:
    server_data = await _get_server_data(guild_id)
    default_config = {
        'security_enabled': False,
        'antiraid_enabled': False,
        'antinuke_enabled': False,
        'antilink_enabled': False,
        'antispam_enabled': False,
        'massmention_enabled': False,
        'webhookguard_enabled': False,
        'antirole_enabled': False,
        
        'timeout_role_id': None,
        'timeout_channel_id': None,
        
        'whitelist_users': [],
        'whitelist_roles': [],
        'whitelist_bots': [],
        
        'raid_join_threshold': 10,
        'raid_time_window': 10,
        'raid_account_age_days': 7,
        
        'spam_message_threshold': 5,
        'spam_time_window': 5,
        
        'allowed_domains': [],
        'blocked_domains': ['discord.gg', 'bit.ly', 't.co'],
        
        'timeout_durations': {}
    }
    
    security_config = server_data.get('security_config', {})
    default_config.update(security_config)
    return default_config

async def update_security_config(guild_id: int, config_data: Dict):
    await _update_server_data(guild_id, {'security_config': config_data})

async def is_whitelisted(guild_id: int, user: discord.Member) -> bool:
    if user.guild.owner_id == user.id:
        return True
    
    config = await get_security_config(guild_id)
    
    if user.id in config.get('whitelist_users', []):
        return True
    
    if user.bot and user.id in config.get('whitelist_bots', []):
        return True
    
    user_role_ids = [role.id for role in user.roles]
    whitelist_roles = config.get('whitelist_roles', [])
    if any(role_id in whitelist_roles for role_id in user_role_ids):
        return True
    
    return False

async def get_or_create_timeout_role(guild: discord.Guild, config: Dict) -> discord.Role:
    timeout_role_id = config.get('timeout_role_id')
    
    if timeout_role_id:
        timeout_role = guild.get_role(int(timeout_role_id))
        if timeout_role:
            return timeout_role
    
    timeout_role = await guild.create_role(
        name="🔒 RXT Timeout",
        color=BrandColors.DANGER,
        reason="RXT Security System - Auto-created timeout role"
    )
    
    for channel in guild.channels:
        try:
            await channel.set_permissions(timeout_role, 
                                         send_messages=False,
                                         add_reactions=False,
                                         speak=False,
                                         connect=False,
                                         send_messages_in_threads=False,
                                         create_public_threads=False,
                                         create_private_threads=False)
        except:
            pass
    
    config['timeout_role_id'] = timeout_role.id
    await update_security_config(guild.id, config)
    
    return timeout_role

async def get_or_create_timeout_channel(guild: discord.Guild, config: Dict, timeout_role: discord.Role) -> discord.TextChannel:
    timeout_channel_id = config.get('timeout_channel_id')
    
    if timeout_channel_id:
        timeout_channel = guild.get_channel(int(timeout_channel_id))
        if timeout_channel and isinstance(timeout_channel, discord.TextChannel):
            return timeout_channel
    
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        timeout_role: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            read_message_history=True,
            add_reactions=False,
            attach_files=False,
            embed_links=False
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            manage_messages=True
        )
    }
    
    timeout_channel = await guild.create_text_channel(
        name="🔒-rxt-timeout",
        overwrites=overwrites,
        reason="RXT Security System - Auto-created timeout channel"
    )
    
    embed = discord.Embed(
        title="🔒 **RXT SECURITY TIMEOUT NOTIFICATIONS**",
        description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                   f"⚠️ **This channel logs RXT Security timeout events.**\n\n"
                   f"**Purpose:** Security timeout notifications and logging\n"
                   f"**Note:** Users in Discord timeout cannot send messages anywhere\n\n"
                   f"When a user is timed out by the security system:\n"
                   f"• They cannot send messages, react, or join voice channels\n"
                   f"• The timeout duration is set via Discord's native timeout\n"
                   f"• Notifications will be posted here for moderator awareness\n\n"
                   f"{VisualElements.CIRCUIT_LINE}",
        color=BrandColors.DANGER
    )
    embed.set_footer(text=BOT_FOOTER)
    await timeout_channel.send(embed=embed)
    
    config['timeout_channel_id'] = timeout_channel.id
    await update_security_config(guild.id, config)
    
    return timeout_channel

async def apply_timeout(member: discord.Member, reason: str, duration_seconds: Optional[int] = None):
    if duration_seconds is None:
        duration_seconds = 3600
    
    timeout_duration = timedelta(seconds=min(duration_seconds, 2419200))
    
    try:
        await member.timeout(timeout_duration, reason=f"RXT Security: {reason}")
    except discord.Forbidden:
        await _log_action(member.guild.id, "security", 
                        f"⚠️ [SECURITY TIMEOUT FAILED] Cannot timeout {member} - Missing permissions")
        return
    except discord.HTTPException as e:
        await _log_action(member.guild.id, "security", 
                        f"⚠️ [SECURITY TIMEOUT FAILED] {member} - HTTP Error: {e}")
        return
    except Exception as e:
        await _log_action(member.guild.id, "security", 
                        f"⚠️ [SECURITY TIMEOUT FAILED] {member} - Error: {e}")
        return
    
    config = await get_security_config(member.guild.id)
    timeout_channel_id = config.get('timeout_channel_id')
    
    if timeout_channel_id:
        timeout_channel = member.guild.get_channel(int(timeout_channel_id))
        if timeout_channel:
            embed = discord.Embed(
                title="🔒 **SECURITY TIMEOUT APPLIED**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**User:** {member.mention} (`{member.id}`)\n"
                           f"**Reason:** {reason}\n"
                           f"**Duration:** {duration_seconds // 60} minutes\n"
                           f"**Status:** User timed out via Discord native timeout\n\n"
                           f"User cannot send messages, react, join voice, or start threads until timeout expires.\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.DANGER,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=BOT_FOOTER)
            try:
                await timeout_channel.send(embed=embed)
            except:
                pass
    
    await _log_action(member.guild.id, "security", 
                    f"🔒 [SECURITY TIMEOUT] {member} ({member.id}) - Reason: {reason} - Duration: {duration_seconds}s")


async def remove_timeout(member: discord.Member):
    if member.timed_out_until is None:
        return False
    
    try:
        await member.timeout(None, reason="RXT Security - Timeout removed manually")
    except discord.Forbidden:
        await _log_action(member.guild.id, "security", 
                        f"⚠️ [TIMEOUT REMOVAL FAILED] Cannot remove timeout from {member} - Missing permissions")
        return False
    except Exception as e:
        await _log_action(member.guild.id, "security", 
                        f"⚠️ [TIMEOUT REMOVAL FAILED] {member} - Error: {e}")
        return False
    
    await _log_action(member.guild.id, "security", 
                    f"✅ [TIMEOUT REMOVED] {member} ({member.id}) - Timeout removed manually")
    
    return True


def setup(bot: commands.Bot, get_server_data_func, update_server_data_func, log_action_func, has_permission_func):
    global _bot_instance, _get_server_data, _update_server_data, _log_action, _has_permission, _setup_complete
    
    if _setup_complete:
        print("⚠️ RXT Security System already initialized, skipping duplicate setup")
        return
    
    _bot_instance = bot
    _get_server_data = get_server_data_func
    _update_server_data = update_server_data_func
    _log_action = log_action_func
    _has_permission = has_permission_func
    _setup_complete = True
    
    @bot.listen('on_message')
    async def security_on_message(message):
        if message.author.bot:
            return
        
        if not message.guild:
            return
        
        config = await get_security_config(message.guild.id)
        
        if not config.get('security_enabled'):
            return
        
        if await is_whitelisted(message.guild.id, message.author):
            return
        
        if config.get('massmention_enabled'):
            if '@everyone' in message.content or '@here' in message.content:
                if not message.author.guild_permissions.mention_everyone:
                    try:
                        await message.delete()
                    except:
                        pass
                    
                    await apply_timeout(message.author, "Unauthorized @everyone/@here mention", 3600)
                    
                    await _log_action(message.guild.id, "security", 
                                   f"🚫 [MASS MENTION BLOCKED] {message.author} attempted @everyone/@here")
                    return
        
        if config.get('antispam_enabled'):
            user_id = message.author.id
            guild_id = message.guild.id
            current_time = time.time()
            
            user_message_timestamps[guild_id][user_id].append(current_time)
            
            user_message_timestamps[guild_id][user_id] = [
                ts for ts in user_message_timestamps[guild_id][user_id]
                if current_time - ts < config.get('spam_time_window', 5)
            ]
            
            if len(user_message_timestamps[guild_id][user_id]) > config.get('spam_message_threshold', 5):
                try:
                    await message.delete()
                except:
                    pass
                
                await apply_timeout(message.author, "Spam/Flood detected", 1800)
                
                await _log_action(message.guild.id, "security", 
                               f"🚫 [ANTI-SPAM] {message.author} was timed out for spam/flood")
                
                user_message_timestamps[guild_id][user_id].clear()
                return
        
        if config.get('antilink_enabled'):
            url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'
            urls = re.findall(url_pattern, message.content)
            
            if urls:
                allowed_domains = config.get('allowed_domains', [])
                blocked_domains = config.get('blocked_domains', [])
                
                for url in urls:
                    is_blocked = False
                    
                    for blocked_domain in blocked_domains:
                        if blocked_domain in url:
                            is_blocked = True
                            break
                    
                    if is_blocked and not any(allowed_domain in url for allowed_domain in allowed_domains):
                        try:
                            await message.delete()
                        except:
                            pass
                        
                        await apply_timeout(message.author, f"Posted blocked link: {url}", 1800)
                        
                        await _log_action(message.guild.id, "security", 
                                       f"🚫 [ANTI-LINK] {message.author} posted blocked link")
                        return
    
    @bot.listen('on_member_join')
    async def security_on_member_join(member):
        if member.bot:
            return
        
        config = await get_security_config(member.guild.id)
        
        if not config.get('security_enabled') or not config.get('antiraid_enabled'):
            return
        
        if await is_whitelisted(member.guild.id, member):
            return
        
        current_time = time.time()
        guild_id = member.guild.id
        
        user_join_timestamps[guild_id].append(current_time)
        
        user_join_timestamps[guild_id] = [
            ts for ts in user_join_timestamps[guild_id]
            if current_time - ts < config.get('raid_time_window', 10)
        ]
        
        if len(user_join_timestamps[guild_id]) > config.get('raid_join_threshold', 10):
            try:
                await member.kick(reason="RXT Security - Raid detected")
                await _log_action(member.guild.id, "security", 
                               f"🚫 [ANTI-RAID] {member} kicked - Raid detected ({len(user_join_timestamps[guild_id])} joins)")
            except:
                pass
            return
        
        account_age = (datetime.utcnow() - member.created_at).days
        min_age = config.get('raid_account_age_days', 7)
        
        if account_age < min_age:
            try:
                await member.kick(reason=f"RXT Security - Account too new ({account_age} days)")
                await _log_action(member.guild.id, "security", 
                               f"🚫 [ANTI-RAID] {member} kicked - Account age {account_age} days (min: {min_age})")
            except:
                pass
            return
        
        suspicious_patterns = ['discord.gg', 'nitro', 'gift', 'http', 'www']
        username_lower = member.name.lower()
        if any(pattern in username_lower for pattern in suspicious_patterns):
            try:
                await member.kick(reason="RXT Security - Suspicious username")
                await _log_action(member.guild.id, "security", 
                               f"🚫 [ANTI-RAID] {member} kicked - Suspicious username pattern")
            except:
                pass
            return
    
    @bot.listen('on_guild_channel_delete')
    async def security_on_guild_channel_delete(channel):
        await asyncio.sleep(1)
        
        config = await get_security_config(channel.guild.id)
        
        if not config.get('security_enabled') or not config.get('antinuke_enabled'):
            return
        
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    executor = entry.user
                    
                    if await is_whitelisted(channel.guild.id, executor):
                        return
                    
                    recent_deletes = 0
                    async for e in channel.guild.audit_logs(limit=10, action=discord.AuditLogAction.channel_delete):
                        if e.user.id == executor.id and (datetime.utcnow() - e.created_at).seconds < 60:
                            recent_deletes += 1
                    
                    if recent_deletes >= 3:
                        try:
                            executor_member = channel.guild.get_member(executor.id)
                            if executor_member:
                                await apply_timeout(executor_member, "Anti-Nuke: Mass channel deletion", 7200)
                                await _log_action(channel.guild.id, "security", 
                                               f"🚫 [ANTI-NUKE] {executor} timed out - Mass channel deletion ({recent_deletes} channels)")
                        except:
                            pass
                    break
        except:
            pass
    
    @bot.listen('on_guild_role_delete')
    async def security_on_guild_role_delete(role):
        await asyncio.sleep(1)
        
        config = await get_security_config(role.guild.id)
        
        if not config.get('security_enabled') or not config.get('antinuke_enabled'):
            return
        
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    executor = entry.user
                    
                    if await is_whitelisted(role.guild.id, executor):
                        return
                    
                    recent_deletes = 0
                    async for e in role.guild.audit_logs(limit=10, action=discord.AuditLogAction.role_delete):
                        if e.user.id == executor.id and (datetime.utcnow() - e.created_at).seconds < 60:
                            recent_deletes += 1
                    
                    if recent_deletes >= 3:
                        try:
                            executor_member = role.guild.get_member(executor.id)
                            if executor_member:
                                await apply_timeout(executor_member, "Anti-Nuke: Mass role deletion", 7200)
                                await _log_action(role.guild.id, "security", 
                                               f"🚫 [ANTI-NUKE] {executor} timed out - Mass role deletion ({recent_deletes} roles)")
                        except:
                            pass
                    break
        except:
            pass
    
    @bot.listen('on_member_ban')
    async def security_on_member_ban(guild, user):
        await asyncio.sleep(1)
        
        config = await get_security_config(guild.id)
        
        if not config.get('security_enabled') or not config.get('antinuke_enabled'):
            return
        
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    executor = entry.user
                    
                    if await is_whitelisted(guild.id, executor):
                        return
                    
                    recent_bans = 0
                    async for e in guild.audit_logs(limit=10, action=discord.AuditLogAction.ban):
                        if e.user.id == executor.id and (datetime.utcnow() - e.created_at).seconds < 60:
                            recent_bans += 1
                    
                    if recent_bans >= 5:
                        try:
                            executor_member = guild.get_member(executor.id)
                            if executor_member:
                                await apply_timeout(executor_member, "Anti-Nuke: Mass ban", 7200)
                                await _log_action(guild.id, "security", 
                                               f"🚫 [ANTI-NUKE] {executor} timed out - Mass ban ({recent_bans} bans)")
                        except:
                            pass
                    break
        except:
            pass
    
    @bot.listen('on_webhooks_update')
    async def security_on_webhooks_update(channel):
        config = await get_security_config(channel.guild.id)
        
        if not config.get('security_enabled') or not config.get('webhookguard_enabled'):
            return
        
        try:
            webhooks = await channel.webhooks()
            
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
                executor = entry.user
                
                if await is_whitelisted(channel.guild.id, executor):
                    return
                
                for webhook in webhooks:
                    if webhook.user and webhook.user.id == executor.id:
                        try:
                            await webhook.delete(reason="RXT Security - Webhook guard")
                            await _log_action(channel.guild.id, "security", 
                                           f"🚫 [WEBHOOK GUARD] Webhook created by {executor} was deleted")
                        except:
                            pass
                        
                        try:
                            executor_member = channel.guild.get_member(executor.id)
                            if executor_member:
                                await apply_timeout(executor_member, "Anti-Webhook: Unauthorized webhook creation", 3600)
                        except:
                            pass
                break
        except:
            pass
    
    @bot.listen('on_guild_role_create')
    async def security_on_guild_role_create(role):
        await asyncio.sleep(1)
        
        config = await get_security_config(role.guild.id)
        
        if not config.get('security_enabled') or not config.get('antirole_enabled'):
            return
        
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    executor = entry.user
                    
                    if await is_whitelisted(role.guild.id, executor):
                        return
                    
                    dangerous_perms = [
                        'administrator',
                        'manage_guild',
                        'manage_roles',
                        'manage_channels',
                        'kick_members',
                        'ban_members',
                        'manage_webhooks'
                    ]
                    
                    role_perms = role.permissions
                    has_dangerous_perm = any(getattr(role_perms, perm, False) for perm in dangerous_perms)
                    
                    if has_dangerous_perm:
                        try:
                            await role.delete(reason="RXT Security - High-permission role created without authorization")
                            await _log_action(role.guild.id, "security", 
                                           f"🚫 [ANTI-ROLE] Role created by {executor} was deleted - Dangerous permissions")
                        except:
                            pass
                        
                        try:
                            executor_member = role.guild.get_member(executor.id)
                            if executor_member:
                                await apply_timeout(executor_member, "Anti-Role: Created high-permission role", 3600)
                        except:
                            pass
                    break
        except:
            pass
    
    @bot.tree.command(name="security", description="🔐 Configure RXT Security System")
    @app_commands.describe(
        action="Action to perform",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="enable - Turn on security system", value="enable"),
        app_commands.Choice(name="disable - Turn off security system", value="disable"),
        app_commands.Choice(name="status - View security status", value="status"),
        app_commands.Choice(name="config - View configuration", value="config")
    ])
    async def security_command(interaction: discord.Interaction, action: str):
        if not await _has_permission(interaction, "main_moderator"):
            embed = discord.Embed(
                title="❌ **ACCESS DENIED**",
                description="**Permission Required:** 🔴 Main Moderator\n\nYou don't have permission to manage security settings.",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        config = await get_security_config(interaction.guild.id)
        
        if action == "enable":
            config['security_enabled'] = True
            await update_security_config(interaction.guild.id, config)
            
            embed = discord.Embed(
                title="🔐 **RXT SECURITY SYSTEM ENABLED**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"✅ **Security system is now ACTIVE**\n\n"
                           f"**Protection Status:**\n"
                           f"🔹 Anti-Raid: {'✅ Enabled' if config.get('antiraid_enabled') else '❌ Disabled'}\n"
                           f"🔹 Anti-Nuke: {'✅ Enabled' if config.get('antinuke_enabled') else '❌ Disabled'}\n"
                           f"🔹 Anti-Link: {'✅ Enabled' if config.get('antilink_enabled') else '❌ Disabled'}\n"
                           f"🔹 Anti-Spam: {'✅ Enabled' if config.get('antispam_enabled') else '❌ Disabled'}\n"
                           f"🔹 Mass Mention: {'✅ Enabled' if config.get('massmention_enabled') else '❌ Disabled'}\n"
                           f"🔹 Webhook Guard: {'✅ Enabled' if config.get('webhookguard_enabled') else '❌ Disabled'}\n"
                           f"🔹 Anti-Role: {'✅ Enabled' if config.get('antirole_enabled') else '❌ Disabled'}\n\n"
                           f"Use `/antiraid`, `/antinuke`, etc. to enable individual protections.\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.SUCCESS
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
            await _log_action(interaction.guild.id, "security", 
                            f"🔐 [SECURITY ENABLED] RXT Security System enabled by {interaction.user}")
            
        elif action == "disable":
            config['security_enabled'] = False
            await update_security_config(interaction.guild.id, config)
            
            embed = discord.Embed(
                title="🔐 **RXT SECURITY SYSTEM DISABLED**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"⚠️ **Security system is now INACTIVE**\n\n"
                           f"All protection features have been disabled.\n"
                           f"Your server is no longer protected by RXT Security.\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.WARNING
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
            await _log_action(interaction.guild.id, "security", 
                            f"🔐 [SECURITY DISABLED] RXT Security System disabled by {interaction.user}")
            
        elif action == "status":
            status_emoji = "🟢" if config.get('security_enabled') else "🔴"
            status_text = "ACTIVE" if config.get('security_enabled') else "INACTIVE"
            
            embed = discord.Embed(
                title="🔐 **RXT SECURITY SYSTEM STATUS**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**System Status:** {status_emoji} {status_text}\n\n"
                           f"**Protection Modules:**\n"
                           f"{'🟢' if config.get('antiraid_enabled') else '🔴'} Anti-Raid System\n"
                           f"{'🟢' if config.get('antinuke_enabled') else '🔴'} Anti-Nuke System\n"
                           f"{'🟢' if config.get('antilink_enabled') else '🔴'} Anti-Link Protection\n"
                           f"{'🟢' if config.get('antispam_enabled') else '🔴'} Anti-Spam & Flood\n"
                           f"{'🟢' if config.get('massmention_enabled') else '🔴'} Mass Mention Guard\n"
                           f"{'🟢' if config.get('webhookguard_enabled') else '🔴'} Webhook Guard\n"
                           f"{'🟢' if config.get('antirole_enabled') else '🔴'} Anti-Role Abuse\n\n"
                           f"**Whitelist:**\n"
                           f"👤 Users: {len(config.get('whitelist_users', []))}\n"
                           f"🎭 Roles: {len(config.get('whitelist_roles', []))}\n"
                           f"🤖 Bots: {len(config.get('whitelist_bots', []))}\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.PRIMARY
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
            
        elif action == "config":
            embed = discord.Embed(
                title="⚙️ **RXT SECURITY CONFIGURATION**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**Anti-Raid Settings:**\n"
                           f"• Join Threshold: {config.get('raid_join_threshold', 10)} joins\n"
                           f"• Time Window: {config.get('raid_time_window', 10)} seconds\n"
                           f"• Min Account Age: {config.get('raid_account_age_days', 7)} days\n\n"
                           f"**Anti-Spam Settings:**\n"
                           f"• Message Threshold: {config.get('spam_message_threshold', 5)} messages\n"
                           f"• Time Window: {config.get('spam_time_window', 5)} seconds\n\n"
                           f"**Anti-Link Settings:**\n"
                           f"• Blocked Domains: {len(config.get('blocked_domains', []))}\n"
                           f"• Allowed Domains: {len(config.get('allowed_domains', []))}\n\n"
                           f"**Timeout Settings:**\n"
                           f"• Timeout Role: {'✅ Configured' if config.get('timeout_role_id') else '❌ Not set'}\n"
                           f"• Timeout Channel: {'✅ Configured' if config.get('timeout_channel_id') else '❌ Not set'}\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.INFO
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
    
    def create_protection_toggle_command(name: str, title: str, protection_key: str, features: list):
        @bot.tree.command(name=name, description=f"{title} Toggle {title} protection")
        @app_commands.describe(state="Enable or disable")
        @app_commands.choices(state=[
            app_commands.Choice(name="on - Enable protection", value="on"),
            app_commands.Choice(name="off - Disable protection", value="off")
        ])
        async def toggle_command(interaction: discord.Interaction, state: str):
            if not await _has_permission(interaction, "main_moderator"):
                embed = discord.Embed(
                    title="❌ **ACCESS DENIED**",
                    description="**Permission Required:** 🔴 Main Moderator",
                    color=BrandColors.DANGER
                )
                embed.set_footer(text=BOT_FOOTER)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            config = await get_security_config(interaction.guild.id)
            config[protection_key] = (state == "on")
            await update_security_config(interaction.guild.id, config)
            
            status = "ENABLED" if state == "on" else "DISABLED"
            emoji = "🟢" if state == "on" else "🔴"
            color = BrandColors.SUCCESS if state == "on" else BrandColors.WARNING
            
            features_text = "\n".join([f"• {feature}" for feature in features])
            
            embed = discord.Embed(
                title=f"{title} **{name.upper()} {status}**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**Status:** {emoji} {title} protection is now {status}\n\n"
                           f"**Protection includes:**\n"
                           f"{features_text}\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=color
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
            await _log_action(interaction.guild.id, "security", 
                            f"{title} [{name.upper()}] {status} by {interaction.user}")
        
        return toggle_command
    
    create_protection_toggle_command("antiraid", "🛡️", "antiraid_enabled", ["Join rate monitoring", "Account age verification", "Suspicious username detection"])
    create_protection_toggle_command("antinuke", "💣", "antinuke_enabled", ["Mass channel deletion", "Mass role deletion", "Mass ban/kick prevention"])
    create_protection_toggle_command("antilink", "🔗", "antilink_enabled", ["Malicious link detection", "Phishing domain blocking", "Domain whitelist support"])
    create_protection_toggle_command("antispam", "💬", "antispam_enabled", ["Message rate limiting", "Spam flood detection", "Auto timeout for violators"])
    create_protection_toggle_command("massmention", "📢", "massmention_enabled", ["@everyone mention blocking", "@here mention blocking", "Auto timeout for violators"])
    create_protection_toggle_command("webhookguard", "🪝", "webhookguard_enabled", ["Unknown webhook detection", "Auto webhook deletion", "Timeout for webhook creators"])
    create_protection_toggle_command("antirole", "🎭", "antirole_enabled", ["High-permission role detection", "Permission escalation prevention", "Auto role deletion"])
    
    @bot.tree.command(name="timeout", description="⏱️ Manually timeout a user")
    @app_commands.describe(
        user="User to timeout",
        duration="Duration in minutes",
        reason="Reason for timeout"
    )
    async def timeout_add_command(interaction: discord.Interaction, user: discord.Member, duration: int, reason: str = "Manual timeout"):
        if not await _has_permission(interaction, "junior_moderator"):
            embed = discord.Embed(
                title="❌ **ACCESS DENIED**",
                description="**Permission Required:** 🔵 Junior Moderator+",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if user.guild_permissions.administrator:
            embed = discord.Embed(
                title="❌ **CANNOT TIMEOUT ADMIN**",
                description="Cannot timeout users with administrator permissions.",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await apply_timeout(user, reason, duration * 60)
        
        embed = discord.Embed(
            title="⏱️ **TIMEOUT APPLIED**",
            description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                       f"**User:** {user.mention}\n"
                       f"**Duration:** {duration} minutes\n"
                       f"**Reason:** {reason}\n"
                       f"**Applied by:** {interaction.user.mention}\n\n"
                       f"User cannot send messages, react, join voice channels, or start threads.\n\n"
                       f"{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.WARNING
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="untimeout", description="✅ Remove timeout from a user")
    @app_commands.describe(user="User to remove timeout from")
    async def timeout_remove_command(interaction: discord.Interaction, user: discord.Member):
        if not await _has_permission(interaction, "junior_moderator"):
            embed = discord.Embed(
                title="❌ **ACCESS DENIED**",
                description="**Permission Required:** 🔵 Junior Moderator+",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        success = await remove_timeout(user)
        
        if success:
            embed = discord.Embed(
                title="✅ **TIMEOUT REMOVED**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**User:** {user.mention}\n"
                           f"**Action:** Timeout removed, user can now interact normally\n"
                           f"**Removed by:** {interaction.user.mention}\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.SUCCESS
            )
        else:
            embed = discord.Embed(
                title="❌ **NOT IN TIMEOUT**",
                description=f"{user.mention} is not currently in timeout.",
                color=BrandColors.DANGER
            )
        
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="whitelist", description="🟩 Manage security whitelist")
    @app_commands.describe(
        action="Action to perform",
        target_type="Type of target",
        target="User, role, or bot to whitelist"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="add - Add to whitelist", value="add"),
            app_commands.Choice(name="remove - Remove from whitelist", value="remove"),
            app_commands.Choice(name="list - View whitelist", value="list")
        ],
        target_type=[
            app_commands.Choice(name="user", value="user"),
            app_commands.Choice(name="role", value="role"),
            app_commands.Choice(name="bot", value="bot")
        ]
    )
    async def whitelist_command(interaction: discord.Interaction, action: str, target_type: str = None, target: str = None):
        if not await _has_permission(interaction, "main_moderator"):
            embed = discord.Embed(
                title="❌ **ACCESS DENIED**",
                description="**Permission Required:** 🔴 Main Moderator",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        config = await get_security_config(interaction.guild.id)
        
        if action == "list":
            whitelist_users = config.get('whitelist_users', [])
            whitelist_roles = config.get('whitelist_roles', [])
            whitelist_bots = config.get('whitelist_bots', [])
            
            users_text = "\n".join([f"<@{uid}>" for uid in whitelist_users[:10]]) if whitelist_users else "None"
            roles_text = "\n".join([f"<@&{rid}>" for rid in whitelist_roles[:10]]) if whitelist_roles else "None"
            bots_text = "\n".join([f"<@{bid}>" for bid in whitelist_bots[:10]]) if whitelist_bots else "None"
            
            embed = discord.Embed(
                title="🟩 **SECURITY WHITELIST**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**Whitelisted Users ({len(whitelist_users)}):**\n{users_text}\n\n"
                           f"**Whitelisted Roles ({len(whitelist_roles)}):**\n{roles_text}\n\n"
                           f"**Whitelisted Bots ({len(whitelist_bots)}):**\n{bots_text}\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.SUCCESS
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
            return
        
        if not target:
            embed = discord.Embed(
                title="❌ **MISSING TARGET**",
                description="Please provide a target (user, role, or bot mention/ID).",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        target_id = int(re.sub(r'[<@&!>]', '', target))
        
        embed = discord.Embed(title="⚠️ **ERROR**", description="An error occurred.", color=BrandColors.DANGER)
        
        if action == "add":
            if target_type == "user":
                if target_id not in config.get('whitelist_users', []):
                    if 'whitelist_users' not in config:
                        config['whitelist_users'] = []
                    config['whitelist_users'].append(target_id)
                    await update_security_config(interaction.guild.id, config)
                    
                    embed = discord.Embed(
                        title="✅ **WHITELIST UPDATED**",
                        description=f"Added <@{target_id}> to user whitelist.\n\nThey will bypass all security protections.",
                        color=BrandColors.SUCCESS
                    )
                    await _log_action(interaction.guild.id, "security", 
                                   f"🟩 [WHITELIST] User <@{target_id}> added by {interaction.user}")
                else:
                    embed = discord.Embed(
                        title="⚠️ **ALREADY WHITELISTED**",
                        description=f"<@{target_id}> is already in the user whitelist.",
                        color=BrandColors.WARNING
                    )
            
            elif target_type == "role":
                if target_id not in config.get('whitelist_roles', []):
                    if 'whitelist_roles' not in config:
                        config['whitelist_roles'] = []
                    config['whitelist_roles'].append(target_id)
                    await update_security_config(interaction.guild.id, config)
                    
                    embed = discord.Embed(
                        title="✅ **WHITELIST UPDATED**",
                        description=f"Added <@&{target_id}> to role whitelist.\n\nUsers with this role will bypass all security protections.",
                        color=BrandColors.SUCCESS
                    )
                    await _log_action(interaction.guild.id, "security", 
                                   f"🟩 [WHITELIST] Role <@&{target_id}> added by {interaction.user}")
                else:
                    embed = discord.Embed(
                        title="⚠️ **ALREADY WHITELISTED**",
                        description=f"<@&{target_id}> is already in the role whitelist.",
                        color=BrandColors.WARNING
                    )
            
            elif target_type == "bot":
                if target_id not in config.get('whitelist_bots', []):
                    if 'whitelist_bots' not in config:
                        config['whitelist_bots'] = []
                    config['whitelist_bots'].append(target_id)
                    await update_security_config(interaction.guild.id, config)
                    
                    embed = discord.Embed(
                        title="✅ **WHITELIST UPDATED**",
                        description=f"Added <@{target_id}> to bot whitelist.\n\nThis bot will bypass all security protections.",
                        color=BrandColors.SUCCESS
                    )
                    await _log_action(interaction.guild.id, "security", 
                                   f"🟩 [WHITELIST] Bot <@{target_id}> added by {interaction.user}")
                else:
                    embed = discord.Embed(
                        title="⚠️ **ALREADY WHITELISTED**",
                        description=f"<@{target_id}> is already in the bot whitelist.",
                        color=BrandColors.WARNING
                    )
        
        elif action == "remove":
            if target_type == "user":
                if target_id in config.get('whitelist_users', []):
                    config['whitelist_users'].remove(target_id)
                    await update_security_config(interaction.guild.id, config)
                    
                    embed = discord.Embed(
                        title="✅ **WHITELIST UPDATED**",
                        description=f"Removed <@{target_id}> from user whitelist.\n\nThey are now subject to security protections.",
                        color=BrandColors.SUCCESS
                    )
                    await _log_action(interaction.guild.id, "security", 
                                   f"🟩 [WHITELIST] User <@{target_id}> removed by {interaction.user}")
                else:
                    embed = discord.Embed(
                        title="⚠️ **NOT WHITELISTED**",
                        description=f"<@{target_id}> is not in the user whitelist.",
                        color=BrandColors.WARNING
                    )
            
            elif target_type == "role":
                if target_id in config.get('whitelist_roles', []):
                    config['whitelist_roles'].remove(target_id)
                    await update_security_config(interaction.guild.id, config)
                    
                    embed = discord.Embed(
                        title="✅ **WHITELIST UPDATED**",
                        description=f"Removed <@&{target_id}> from role whitelist.\n\nUsers with this role are now subject to security protections.",
                        color=BrandColors.SUCCESS
                    )
                    await _log_action(interaction.guild.id, "security", 
                                   f"🟩 [WHITELIST] Role <@&{target_id}> removed by {interaction.user}")
                else:
                    embed = discord.Embed(
                        title="⚠️ **NOT WHITELISTED**",
                        description=f"<@&{target_id}> is not in the role whitelist.",
                        color=BrandColors.WARNING
                    )
            
            elif target_type == "bot":
                if target_id in config.get('whitelist_bots', []):
                    config['whitelist_bots'].remove(target_id)
                    await update_security_config(interaction.guild.id, config)
                    
                    embed = discord.Embed(
                        title="✅ **WHITELIST UPDATED**",
                        description=f"Removed <@{target_id}> from bot whitelist.\n\nThis bot is now subject to security protections.",
                        color=BrandColors.SUCCESS
                    )
                    await _log_action(interaction.guild.id, "security", 
                                   f"🟩 [WHITELIST] Bot <@{target_id}> removed by {interaction.user}")
                else:
                    embed = discord.Embed(
                        title="⚠️ **NOT WHITELISTED**",
                        description=f"<@{target_id}> is not in the bot whitelist.",
                        color=BrandColors.WARNING
                    )
        
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)
    
    print("✅ RXT Security System setup complete - event listeners and commands registered")
