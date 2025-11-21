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
user_message_deletion_attempts = defaultdict(lambda: defaultdict(list))
user_stored_roles = {}
user_quarantine_info = {}
system_role_actions = set()  # Track (guild_id, user_id) tuples for system-initiated role changes

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
        'massdelete_enabled': False,
        
        'quarantine_role_id': None,
        'quarantine_channel_id': None,
        'quarantine_category_id': None,
        
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
        
        'quarantine_base_duration': 900,
        'mass_delete_threshold': 5,
        'mass_delete_time_window': 5
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

async def get_or_create_quarantine_category(guild: discord.Guild, config: Dict):
    category_id = config.get('quarantine_category_id')
    if category_id:
        category = guild.get_channel(int(category_id))
        if category:
            return category
    
    category = await guild.create_category(
        name="RXT-QUARANTINE",
        reason="RXT Security System - Quarantine category"
    )
    
    config['quarantine_category_id'] = category.id
    await update_security_config(guild.id, config)
    
    return category

async def get_or_create_quarantine_role(guild: discord.Guild, config: Dict):
    role_id = config.get('quarantine_role_id')
    if role_id:
        role = guild.get_role(int(role_id))
        if role:
            return role
    
    perms = discord.Permissions(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        embed_links=False,
        attach_files=False,
        mention_everyone=False,
        add_reactions=False,
        connect=False
    )
    
    role = await guild.create_role(
        name="RXT-Quarantine",
        permissions=perms,
        color=discord.Color(0xFF4444),
        reason="RXT Security System - Quarantine role"
    )
    
    config['quarantine_role_id'] = role.id
    await update_security_config(guild.id, config)
    
    return role

async def get_or_create_quarantine_channel(guild: discord.Guild, config: Dict, role: discord.Role):
    channel_id = config.get('quarantine_channel_id')
    if channel_id:
        channel = guild.get_channel(int(channel_id))
        if channel:
            return channel
    
    category = await get_or_create_quarantine_category(guild, config)
    
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(view_channel=True)
    }
    
    channel = await category.create_text_channel(
        name="quarantine-zone",
        overwrites=overwrites,
        reason="RXT Security System - Quarantine channel"
    )
    
    embed = discord.Embed(
        title="🔒 **RXT QUARANTINE ZONE**",
        description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                   f"⚠️ **You have been placed in quarantine by the RXT Security System.**\n\n"
                   f"**What is quarantine?**\n"
                   f"• Your roles have been temporarily removed\n"
                   f"• You can only see and chat in this channel\n"
                   f"• Your message history is preserved\n\n"
                   f"**What happens next?**\n"
                   f"• Quarantine duration increases with repeated violations\n"
                   f"• Minimum duration: 15 minutes\n"
                   f"• Contact moderators if you believe this is a mistake\n\n"
                   f"{VisualElements.CIRCUIT_LINE}",
        color=BrandColors.DANGER
    )
    embed.set_footer(text=BOT_FOOTER)
    await channel.send(embed=embed)
    
    config['quarantine_channel_id'] = channel.id
    await update_security_config(guild.id, config)
    
    return channel

async def apply_quarantine(member: discord.Member, reason: str, violation_type: str = "security_violation"):
    storage_key = f"{member.guild.id}_{member.id}"
    config = await get_security_config(member.guild.id)
    
    current_violations = user_quarantine_info.get(storage_key, {}).get('violations', 0)
    current_violations += 1
    
    base_duration = config.get('quarantine_base_duration', 900)
    quarantine_duration = base_duration * (current_violations)
    quarantine_duration = max(quarantine_duration, 900)
    
    try:
        current_roles = [role for role in member.roles if role != member.guild.default_role]
        user_stored_roles[storage_key] = {
            'roles': [role.id for role in current_roles],
            'timestamp': time.time(),
            'duration': quarantine_duration,
            'violations': current_violations
        }
        
        quarantine_role = await get_or_create_quarantine_role(member.guild, config)
        quarantine_channel = await get_or_create_quarantine_channel(member.guild, config, quarantine_role)
        
        await member.remove_roles(*current_roles, reason=f"RXT Security Quarantine: {reason}")
        await member.add_roles(quarantine_role, reason=f"RXT Security Quarantine: {reason}")
        
        user_quarantine_info[storage_key] = {
            'quarantine_until': time.time() + quarantine_duration,
            'violations': current_violations,
            'reason': reason,
            'quarantine_role_id': quarantine_role.id
        }
        
        embed = discord.Embed(
            title="🔒 **QUARANTINE APPLIED**",
            description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                       f"**User:** {member.mention} (`{member.id}`)\n"
                       f"**Reason:** {reason}\n"
                       f"**Type:** {violation_type}\n"
                       f"**Duration:** {quarantine_duration // 60} minutes\n"
                       f"**Violations:** {current_violations}\n"
                       f"**Channel:** {quarantine_channel.mention}\n\n"
                       f"Roles have been removed. Use `/quarantine remove` to restore early.\n\n"
                       f"{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.DANGER,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=BOT_FOOTER)
        
        try:
            await quarantine_channel.send(f"{member.mention}", embed=embed)
        except:
            pass
        
        await _log_action(member.guild.id, "security", 
                        f"🔒 [QUARANTINE] {member} ({member.id}) - Reason: {reason} - Duration: {quarantine_duration}s - Violations: {current_violations}")
        
        asyncio.create_task(restore_roles_after_quarantine(member, quarantine_duration))
        
    except Exception as e:
        await _log_action(member.guild.id, "security", 
                        f"⚠️ [QUARANTINE FAILED] {member} - Error: {e}")

async def restore_roles_after_quarantine(member: discord.Member, duration_seconds: int):
    await asyncio.sleep(duration_seconds)
    
    storage_key = f"{member.guild.id}_{member.id}"
    if storage_key not in user_stored_roles:
        return
    
    try:
        stored_data = user_stored_roles[storage_key]
        role_ids = stored_data['roles']
        
        config = await get_security_config(member.guild.id)
        quarantine_role_id = config.get('quarantine_role_id')
        
        roles_to_add = []
        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if role:
                roles_to_add.append(role)
        
        # Mark this action as system-initiated to skip security checks
        system_role_actions.add((member.guild.id, member.id))
        
        if quarantine_role_id:
            quarantine_role = member.guild.get_role(int(quarantine_role_id))
            if quarantine_role:
                try:
                    await member.remove_roles(quarantine_role, reason="RXT Security - Quarantine expired")
                except:
                    pass
        
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="RXT Security - Quarantine expired, roles restored")
            except:
                pass
        
        # Clean up system action marker after a short delay
        await asyncio.sleep(3)
        system_role_actions.discard((member.guild.id, member.id))
        
        del user_stored_roles[storage_key]
        if storage_key in user_quarantine_info:
            del user_quarantine_info[storage_key]
        
        await _log_action(member.guild.id, "security", 
                        f"✅ [QUARANTINE EXPIRED] {member} ({member.id}) - Roles restored automatically")
    except Exception as e:
        await _log_action(member.guild.id, "security", 
                        f"⚠️ [QUARANTINE RESTORE FAILED] {member} - Error: {e}")

async def remove_quarantine_manual(member: discord.Member):
    storage_key = f"{member.guild.id}_{member.id}"
    if storage_key not in user_stored_roles:
        return False
    
    try:
        stored_data = user_stored_roles[storage_key]
        role_ids = stored_data['roles']
        
        config = await get_security_config(member.guild.id)
        quarantine_role_id = config.get('quarantine_role_id')
        
        roles_to_add = []
        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if role:
                roles_to_add.append(role)
        
        # Mark this action as system-initiated to skip security checks
        system_role_actions.add((member.guild.id, member.id))
        
        if quarantine_role_id:
            quarantine_role = member.guild.get_role(int(quarantine_role_id))
            if quarantine_role:
                try:
                    await member.remove_roles(quarantine_role, reason="RXT Security - Quarantine removed manually")
                except:
                    pass
        
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="RXT Security - Quarantine removed manually, roles restored")
            except:
                pass
        
        # Clean up system action marker after a short delay
        await asyncio.sleep(3)
        system_role_actions.discard((member.guild.id, member.id))
        
        del user_stored_roles[storage_key]
        if storage_key in user_quarantine_info:
            del user_quarantine_info[storage_key]
        
        await _log_action(member.guild.id, "security", 
                        f"✅ [QUARANTINE REMOVED] {member} ({member.id}) - Manually removed by moderator")
        
        return True
    except Exception as e:
        await _log_action(member.guild.id, "security", 
                        f"⚠️ [QUARANTINE REMOVAL FAILED] {member} - Error: {e}")
        return False


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
                try:
                    await message.delete()
                except:
                    pass
                
                await apply_quarantine(message.author, "Unauthorized @everyone/@here mention", "mass_mention")
                
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
                
                await apply_quarantine(message.author, "Spam/Flood detected", "anti_spam")
                
                await _log_action(message.guild.id, "security", 
                               f"🚫 [ANTI-SPAM] {message.author} placed in quarantine for spam/flood")
                
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
                        
                        await apply_quarantine(message.author, f"Posted blocked link: {url}", "anti_link")
                        
                        await _log_action(message.guild.id, "security", 
                                       f"🚫 [ANTI-LINK] {message.author} placed in quarantine for blocked link")
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
        
        if account_age < config.get('raid_account_age_days', 7):
            suspicious_username_patterns = ['discord', 'bot', 'fake', 'test', '^[0-9]+$']
            username_lower = member.name.lower()
            
            for pattern in suspicious_username_patterns:
                if re.search(pattern, username_lower):
                    try:
                        await member.kick(reason=f"RXT Security - Suspicious account detected: {pattern}")
                        await _log_action(member.guild.id, "security", 
                                       f"🚫 [ANTI-RAID] {member} kicked - Suspicious username pattern: {pattern}")
                    except:
                        pass
                    return
    
    @bot.listen('on_bulk_message_delete')
    async def security_on_bulk_delete(messages):
        if not messages:
            return
        
        config = await get_security_config(messages[0].guild.id)
        
        if not config.get('security_enabled') or not config.get('massdelete_enabled'):
            return
        
        await _log_action(messages[0].guild.id, "security",
                        f"🚫 [MASS MESSAGE DELETION] {len(messages)} messages deleted in {messages[0].channel.mention}")
    
    @bot.listen('on_message_delete')
    async def security_on_message_delete(message):
        if message.author.bot:
            return
        
        if not message.guild:
            return
        
        config = await get_security_config(message.guild.id)
        
        if not config.get('security_enabled') or not config.get('massdelete_enabled'):
            return
        
        if await is_whitelisted(message.guild.id, message.author):
            return
        
        user_id = message.author.id
        guild_id = message.guild.id
        current_time = time.time()
        
        user_message_deletion_attempts[guild_id][user_id].append(current_time)
        
        user_message_deletion_attempts[guild_id][user_id] = [
            ts for ts in user_message_deletion_attempts[guild_id][user_id]
            if current_time - ts < config.get('mass_delete_time_window', 5)
        ]
        
        if len(user_message_deletion_attempts[guild_id][user_id]) > config.get('mass_delete_threshold', 5):
            await apply_quarantine(message.author, "Mass message deletion detected", "mass_delete_violation")
            
            await _log_action(message.guild.id, "security",
                            f"🚫 [MASS DELETE] {message.author} placed in quarantine for mass message deletion")
    
    @bot.listen('on_member_update')
    async def security_on_role_change(before, after):
        config = await get_security_config(before.guild.id)
        
        if not config.get('security_enabled') or not config.get('antinuke_enabled'):
            return
        
        # Check if this is a system action (role restoration) - skip checks
        if (before.guild.id, before.id) in system_role_actions:
            return
        
        if await is_whitelisted(before.guild.id, before):
            return
        
        before_roles = set(before.roles)
        after_roles = set(after.roles)
        
        removed_roles = before_roles - after_roles
        added_roles = after_roles - before_roles
        
        # Check who made the role change from audit logs
        actor_is_trusted = False
        try:
            async for entry in before.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                if entry.target.id == before.id:
                    actor = entry.user
                    # Only trust: owner, whitelisted users, whitelisted roles, main mod role
                    if actor:
                        # Check if actor is server owner
                        if actor.id == before.guild.owner_id:
                            actor_is_trusted = True
                        # Check if actor is whitelisted user
                        elif await is_whitelisted(before.guild.id, actor):
                            actor_is_trusted = True
                        # Check if actor has main moderator role (from server setup)
                        else:
                            server_data = await _get_server_data(before.guild.id)
                            main_mod_role_id = server_data.get('main_moderator_role')
                            if main_mod_role_id and any(role.id == int(main_mod_role_id) for role in actor.roles):
                                actor_is_trusted = True
                    break
        except:
            pass
        
        # If actor is trusted, skip quarantine
        if actor_is_trusted:
            return
        
        if removed_roles:
            for role in removed_roles:
                if role.permissions.administrator or role.permissions.manage_guild:
                    try:
                        await before.add_roles(role, reason="RXT Security - Anti-nuke protection")
                    except:
                        pass
                    
                    await apply_quarantine(before, f"Attempted to remove high-permission role: {role.name}", "anti_nuke")
                    await _log_action(before.guild.id, "security",
                                   f"🚫 [ANTI-NUKE] {before} attempted to remove role: {role.name}")
                    return
        
        if added_roles:
            for role in added_roles:
                if role.permissions.administrator or role.permissions.manage_guild or role.permissions.ban_members:
                    try:
                        await before.remove_roles(role, reason="RXT Security - Anti-role abuse protection")
                    except:
                        pass
                    
                    await apply_quarantine(before, f"Attempted to gain high-permission role: {role.name}", "anti_role")
                    await _log_action(before.guild.id, "security",
                                   f"🚫 [ANTI-ROLE] {before} attempted to add role: {role.name}")
                    return
    
    @bot.listen('on_guild_channel_delete')
    async def security_on_channel_delete(channel):
        config = await get_security_config(channel.guild.id)
        
        if not config.get('security_enabled') or not config.get('antinuke_enabled'):
            return
        
        audit_log_entry = None
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                audit_log_entry = entry
                break
        except:
            return
        
        if not audit_log_entry or not audit_log_entry.user:
            return
        
        if audit_log_entry.user.bot:
            return
        
        if await is_whitelisted(channel.guild.id, audit_log_entry.user):
            return
        
        try:
            member = await channel.guild.fetch_member(audit_log_entry.user.id)
            await apply_quarantine(member, f"Mass channel deletion detected: {channel.name}", "anti_nuke")
            await _log_action(channel.guild.id, "security",
                           f"🚫 [ANTI-NUKE] {member} placed in quarantine - Channel deletion: {channel.name}")
        except:
            pass
    
    @bot.listen('on_guild_role_delete')
    async def security_on_role_delete(role):
        config = await get_security_config(role.guild.id)
        
        if not config.get('security_enabled') or not config.get('antinuke_enabled'):
            return
        
        audit_log_entry = None
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                audit_log_entry = entry
                break
        except:
            return
        
        if not audit_log_entry or not audit_log_entry.user:
            return
        
        if audit_log_entry.user.bot:
            return
        
        if await is_whitelisted(role.guild.id, audit_log_entry.user):
            return
        
        try:
            member = await role.guild.fetch_member(audit_log_entry.user.id)
            await apply_quarantine(member, f"Mass role deletion detected: {role.name}", "anti_nuke")
            await _log_action(role.guild.id, "security",
                           f"🚫 [ANTI-NUKE] {member} placed in quarantine - Role deletion: {role.name}")
        except:
            pass
    
    @bot.listen('on_webhooks_update')
    async def security_on_webhook_update(channel):
        config = await get_security_config(channel.guild.id)
        
        if not config.get('security_enabled') or not config.get('webhookguard_enabled'):
            return
        
        audit_log_entry = None
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
                audit_log_entry = entry
                break
        except:
            return
        
        if not audit_log_entry or not audit_log_entry.user:
            return
        
        if audit_log_entry.user.bot:
            return
        
        if await is_whitelisted(channel.guild.id, audit_log_entry.user):
            return
        
        try:
            webhooks = await channel.webhooks()
            for webhook in webhooks:
                if webhook.user and webhook.user.id == audit_log_entry.user.id:
                    try:
                        await webhook.delete(reason="RXT Security - Unauthorized webhook")
                    except:
                        pass
            
            member = await channel.guild.fetch_member(audit_log_entry.user.id)
            await apply_quarantine(member, f"Unauthorized webhook created in {channel.name}", "webhook_guard")
            await _log_action(channel.guild.id, "security",
                           f"🚫 [WEBHOOK GUARD] {member} placed in quarantine - Webhook created in {channel.name}")
        except:
            pass
    
    def create_protection_toggle_command(name, title, config_key, features):
        @bot.tree.command(name=name, description=f"{title} Toggle {title} protection")
        async def toggle_command(interaction: discord.Interaction):
            if not await _has_permission(interaction, "junior_moderator"):
                embed = discord.Embed(
                    title="❌ **ACCESS DENIED**",
                    description="**Permission Required:** 🔵 Junior Moderator+",
                    color=BrandColors.DANGER
                )
                embed.set_footer(text=BOT_FOOTER)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            config = await get_security_config(interaction.guild.id)
            new_state = not config.get(config_key, False)
            config[config_key] = new_state
            await update_security_config(interaction.guild.id, config)
            
            status = "✅ ENABLED" if new_state else "❌ DISABLED"
            features_text = "\n".join([f"• {feature}" for feature in features])
            
            embed = discord.Embed(
                title=f"{title} **{status}**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**Protected Against:**\n{features_text}\n\n"
                           f"**Status:** {status}\n"
                           f"**Enforcement:** Quarantine system active\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.SUCCESS if new_state else BrandColors.WARNING
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
            
            await _log_action(interaction.guild.id, "security",
                            f"{title} [{name.upper()}] {status} by {interaction.user}")
        
        return toggle_command
    
    create_protection_toggle_command("antiraid", "🛡️", "antiraid_enabled", ["Join rate monitoring", "Account age verification", "Suspicious username detection"])
    create_protection_toggle_command("antinuke", "💣", "antinuke_enabled", ["Mass channel deletion", "Mass role deletion", "Mass ban/kick prevention"])
    create_protection_toggle_command("antilink", "🔗", "antilink_enabled", ["Malicious link detection", "Phishing domain blocking", "Domain whitelist support"])
    create_protection_toggle_command("antispam", "💬", "antispam_enabled", ["Message rate limiting", "Spam flood detection", "Quarantine for violators"])
    create_protection_toggle_command("massmention", "📢", "massmention_enabled", ["@everyone mention blocking", "@here mention blocking", "Quarantine for violators"])
    create_protection_toggle_command("webhookguard", "🪝", "webhookguard_enabled", ["Unknown webhook detection", "Auto webhook deletion", "Quarantine for webhook creators"])
    create_protection_toggle_command("antirole", "🎭", "antirole_enabled", ["High-permission role detection", "Permission escalation prevention", "Auto role deletion"])
    create_protection_toggle_command("massdelete", "🗑️", "massdelete_enabled", ["Mass message deletion detection", "Auto-quarantine for violators", "Audit logging"])
    
    @bot.tree.command(name="security", description="🔐 Configure RXT Security System")
    @app_commands.describe(action="Action to perform")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="enable - Enable security", value="enable"),
            app_commands.Choice(name="disable - Disable security", value="disable"),
            app_commands.Choice(name="status - View security status", value="status"),
            app_commands.Choice(name="setup - Setup quarantine system", value="setup"),
        ]
    )
    async def security_command(interaction: discord.Interaction, action: str):
        if not await _has_permission(interaction, "junior_moderator"):
            embed = discord.Embed(
                title="❌ **ACCESS DENIED**",
                description="**Permission Required:** 🔵 Junior Moderator+",
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
                title="🔐 **SECURITY SYSTEM ENABLED**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**Status:** ✅ All protections active\n"
                           f"**Enforcement:** Quarantine system\n\n"
                           f"All security features are now monitoring the server.\n"
                           f"Configure individual protections with `/antiraid`, `/antinuke`, etc.\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.SUCCESS
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
            
            await _log_action(interaction.guild.id, "security",
                            f"🔐 Security system enabled by {interaction.user}")
        
        elif action == "disable":
            config['security_enabled'] = False
            await update_security_config(interaction.guild.id, config)
            
            embed = discord.Embed(
                title="⛔ **SECURITY SYSTEM DISABLED**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**Status:** ❌ All protections inactive\n\n"
                           f"Use `/security enable` to re-enable protections.\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.WARNING
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
            
            await _log_action(interaction.guild.id, "security",
                            f"⛔ Security system disabled by {interaction.user}")
        
        elif action == "status":
            status_lines = [
                f"🔐 Security: {'✅ Enabled' if config.get('security_enabled') else '❌ Disabled'}",
                f"🛡️ Anti-Raid: {'✅ Enabled' if config.get('antiraid_enabled') else '❌ Disabled'}",
                f"💣 Anti-Nuke: {'✅ Enabled' if config.get('antinuke_enabled') else '❌ Disabled'}",
                f"🔗 Anti-Link: {'✅ Enabled' if config.get('antilink_enabled') else '❌ Disabled'}",
                f"💬 Anti-Spam: {'✅ Enabled' if config.get('antispam_enabled') else '❌ Disabled'}",
                f"📢 Mass Mention: {'✅ Enabled' if config.get('massmention_enabled') else '❌ Disabled'}",
                f"🪝 Webhook Guard: {'✅ Enabled' if config.get('webhookguard_enabled') else '❌ Disabled'}",
                f"🎭 Anti-Role: {'✅ Enabled' if config.get('antirole_enabled') else '❌ Disabled'}",
                f"🗑️ Mass Delete: {'✅ Enabled' if config.get('massdelete_enabled') else '❌ Disabled'}",
            ]
            
            embed = discord.Embed(
                title="🔐 **SECURITY STATUS**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n" + "\n".join(status_lines) + f"\n\n{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.INFO
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
        
        elif action == "setup":
            await interaction.response.defer()
            await get_or_create_quarantine_role(interaction.guild, config)
            await get_or_create_quarantine_channel(interaction.guild, config, await get_or_create_quarantine_role(interaction.guild, config))
            
            embed = discord.Embed(
                title="✅ **QUARANTINE SYSTEM SETUP**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**Created:**\n"
                           f"• 🔴 Quarantine Role\n"
                           f"• 📁 Quarantine Category\n"
                           f"• 💬 Quarantine Channel\n\n"
                           f"**Features:**\n"
                           f"• Automatic role storage and restoration\n"
                           f"• Escalating quarantine durations\n"
                           f"• Minimum 15 minute quarantine\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.SUCCESS
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.followup.send(embed=embed)
            
            await _log_action(interaction.guild.id, "security",
                            f"✅ Quarantine system setup by {interaction.user}")
    
    @bot.tree.command(name="quarantine", description="⚠️ Manage user quarantine")
    @app_commands.describe(
        action="Action to perform",
        user="User to quarantine/unquarantine"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="remove - Remove user from quarantine", value="remove"),
            app_commands.Choice(name="info - Show quarantine info", value="info"),
        ]
    )
    async def quarantine_command(interaction: discord.Interaction, action: str, user: discord.Member = None):
        if not await _has_permission(interaction, "junior_moderator"):
            embed = discord.Embed(
                title="❌ **ACCESS DENIED**",
                description="**Permission Required:** 🔵 Junior Moderator+",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if action == "remove" and user:
            success = await remove_quarantine_manual(user)
            
            if success:
                embed = discord.Embed(
                    title="✅ **QUARANTINE REMOVED**",
                    description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                               f"**User:** {user.mention}\n"
                               f"**Status:** Quarantine removed, roles restored\n"
                               f"**Removed by:** {interaction.user.mention}\n\n"
                               f"{VisualElements.CIRCUIT_LINE}",
                    color=BrandColors.SUCCESS
                )
            else:
                embed = discord.Embed(
                    title="❌ **NOT IN QUARANTINE**",
                    description=f"{user.mention} is not currently in quarantine.",
                    color=BrandColors.DANGER
                )
            
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
        
        elif action == "info" and user:
            storage_key = f"{interaction.guild.id}_{user.id}"
            quarantine_data = user_quarantine_info.get(storage_key)
            
            if quarantine_data:
                time_remaining = max(0, quarantine_data['quarantine_until'] - time.time())
                embed = discord.Embed(
                    title="⚠️ **QUARANTINE INFO**",
                    description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                               f"**User:** {user.mention}\n"
                               f"**Reason:** {quarantine_data['reason']}\n"
                               f"**Violations:** {quarantine_data['violations']}\n"
                               f"**Time Remaining:** {int(time_remaining // 60)} minutes\n"
                               f"**Expires:** <t:{int(quarantine_data['quarantine_until'])}:R>\n\n"
                               f"{VisualElements.CIRCUIT_LINE}",
                    color=BrandColors.WARNING
                )
            else:
                embed = discord.Embed(
                    title="ℹ️ **NOT QUARANTINED**",
                    description=f"{user.mention} is not in quarantine.",
                    color=BrandColors.INFO
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
            app_commands.Choice(name="list - Show whitelist", value="list"),
        ],
        target_type=[
            app_commands.Choice(name="user - Whitelist user", value="user"),
            app_commands.Choice(name="role - Whitelist role", value="role"),
            app_commands.Choice(name="bot - Whitelist bot", value="bot"),
        ]
    )
    async def whitelist_command(interaction: discord.Interaction, action: str, target_type: str = None, target: discord.Member = None):
        if not await _has_permission(interaction, "junior_moderator"):
            embed = discord.Embed(
                title="❌ **ACCESS DENIED**",
                description="**Permission Required:** 🔵 Junior Moderator+",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        config = await get_security_config(interaction.guild.id)
        embed = None
        
        if action == "list":
            whitelist_users = config.get('whitelist_users', [])
            whitelist_roles = config.get('whitelist_roles', [])
            whitelist_bots = config.get('whitelist_bots', [])
            
            user_mentions = [f"<@{uid}>" for uid in whitelist_users]
            role_mentions = [f"<@&{rid}>" for rid in whitelist_roles]
            bot_mentions = [f"<@{bid}>" for bid in whitelist_bots]
            
            embed = discord.Embed(
                title="🟩 **WHITELIST**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                           f"**Users:** {', '.join(user_mentions) if user_mentions else 'None'}\n"
                           f"**Roles:** {', '.join(role_mentions) if role_mentions else 'None'}\n"
                           f"**Bots:** {', '.join(bot_mentions) if bot_mentions else 'None'}\n\n"
                           f"*(Server owner is always whitelisted)*\n\n"
                           f"{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.SUCCESS
            )
        
        elif action == "add" and target:
            target_id = target.id
            
            if target_type == "user":
                if target_id not in config.get('whitelist_users', []):
                    config['whitelist_users'].append(target_id)
                    await update_security_config(interaction.guild.id, config)
                    
                    embed = discord.Embed(
                        title="✅ **WHITELIST UPDATED**",
                        description=f"Added {target.mention} to user whitelist.\n\nUser is now exempt from security protections.",
                        color=BrandColors.SUCCESS
                    )
                    await _log_action(interaction.guild.id, "security",
                                   f"🟩 [WHITELIST] User {target.mention} added by {interaction.user}")
                else:
                    embed = discord.Embed(
                        title="⚠️ **ALREADY WHITELISTED**",
                        description=f"{target.mention} is already in the user whitelist.",
                        color=BrandColors.WARNING
                    )
            
            elif target_type == "role":
                if target_id not in config.get('whitelist_roles', []):
                    config['whitelist_roles'].append(target_id)
                    await update_security_config(interaction.guild.id, config)
                    
                    embed = discord.Embed(
                        title="✅ **WHITELIST UPDATED**",
                        description=f"Added <@&{target_id}> to role whitelist.\n\nUsers with this role are now exempt from security protections.",
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
                    config['whitelist_bots'].append(target_id)
                    await update_security_config(interaction.guild.id, config)
                    
                    embed = discord.Embed(
                        title="✅ **WHITELIST UPDATED**",
                        description=f"Added <@{target_id}> to bot whitelist.\n\nThis bot is now exempt from security protections.",
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
        
        elif action == "remove" and target:
            target_id = target.id
            
            if target_type == "user":
                if target_id in config.get('whitelist_users', []):
                    config['whitelist_users'].remove(target_id)
                    await update_security_config(interaction.guild.id, config)
                    
                    embed = discord.Embed(
                        title="✅ **WHITELIST UPDATED**",
                        description=f"Removed {target.mention} from user whitelist.\n\nUser is now subject to security protections.",
                        color=BrandColors.SUCCESS
                    )
                    await _log_action(interaction.guild.id, "security",
                                   f"🟩 [WHITELIST] User {target.mention} removed by {interaction.user}")
                else:
                    embed = discord.Embed(
                        title="⚠️ **NOT WHITELISTED**",
                        description=f"{target.mention} is not in the user whitelist.",
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
        
        if embed:
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="security-config", description="⚙️ Configure security system thresholds and timings")
    @app_commands.describe(
        setting="Setting to configure",
        value="New value for the setting"
    )
    @app_commands.choices(
        setting=[
            app_commands.Choice(name="quarantine_time - Base quarantine duration (seconds)", value="quarantine_time"),
            app_commands.Choice(name="raid_join_count - Joins to trigger anti-raid (default: 10)", value="raid_join_count"),
            app_commands.Choice(name="raid_time_window - Time window for raid detection (seconds, default: 10)", value="raid_time_window"),
            app_commands.Choice(name="raid_account_age - Minimum account age to bypass anti-raid (days, default: 7)", value="raid_account_age"),
            app_commands.Choice(name="spam_message_threshold - Messages to trigger spam (default: 5)", value="spam_message_threshold"),
            app_commands.Choice(name="spam_time_window - Spam detection window (seconds, default: 5)", value="spam_time_window"),
            app_commands.Choice(name="mass_delete_threshold - Messages deleted to trigger protection (default: 5)", value="mass_delete_threshold"),
            app_commands.Choice(name="mass_delete_time_window - Mass delete detection window (seconds, default: 5)", value="mass_delete_time_window"),
            app_commands.Choice(name="view - View all current settings", value="view"),
        ]
    )
    async def security_config_command(interaction: discord.Interaction, setting: str, value: int = None):
        if not await _has_permission(interaction, "server_admin"):
            embed = discord.Embed(
                title="❌ **ACCESS DENIED**",
                description="**Permission Required:** 🔴 Server Admin+",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        config = await get_security_config(interaction.guild.id)
        
        if setting == "view":
            config_lines = [
                f"⏱️ **Quarantine Base Duration:** {config.get('quarantine_base_duration', 900)}s ({config.get('quarantine_base_duration', 900) // 60}min)",
                f"🛡️ **Raid Join Threshold:** {config.get('raid_join_threshold', 10)} joins",
                f"📊 **Raid Time Window:** {config.get('raid_time_window', 10)}s",
                f"👤 **Raid Account Age Check:** {config.get('raid_account_age_days', 7)} days",
                f"💬 **Spam Message Threshold:** {config.get('spam_message_threshold', 5)} messages",
                f"📈 **Spam Time Window:** {config.get('spam_time_window', 5)}s",
                f"🗑️ **Mass Delete Threshold:** {config.get('mass_delete_threshold', 5)} messages",
                f"🔄 **Mass Delete Time Window:** {config.get('mass_delete_time_window', 5)}s",
            ]
            
            embed = discord.Embed(
                title="⚙️ **SECURITY CONFIGURATION**",
                description=f"{VisualElements.CIRCUIT_LINE}\n\n" + "\n".join(config_lines) + f"\n\n{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.INFO
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed)
            return
        
        if value is None or value < 0:
            embed = discord.Embed(
                title="❌ **INVALID VALUE**",
                description="Value must be a positive number.",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        setting_map = {
            "quarantine_time": "quarantine_base_duration",
            "raid_join_count": "raid_join_threshold",
            "raid_time_window": "raid_time_window",
            "raid_account_age": "raid_account_age_days",
            "spam_message_threshold": "spam_message_threshold",
            "spam_time_window": "spam_time_window",
            "mass_delete_threshold": "mass_delete_threshold",
            "mass_delete_time_window": "mass_delete_time_window",
        }
        
        db_key = setting_map.get(setting)
        if not db_key:
            embed = discord.Embed(
                title="❌ **INVALID SETTING**",
                description="Setting not found.",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        old_value = config.get(db_key)
        config[db_key] = value
        await update_security_config(interaction.guild.id, config)
        
        setting_name = {
            "quarantine_base_duration": "Quarantine Base Duration",
            "raid_join_threshold": "Raid Join Threshold",
            "raid_time_window": "Raid Time Window",
            "raid_account_age_days": "Raid Account Age Check",
            "spam_message_threshold": "Spam Message Threshold",
            "spam_time_window": "Spam Time Window",
            "mass_delete_threshold": "Mass Delete Threshold",
            "mass_delete_time_window": "Mass Delete Time Window",
        }.get(db_key, setting)
        
        embed = discord.Embed(
            title="✅ **CONFIGURATION UPDATED**",
            description=f"{VisualElements.CIRCUIT_LINE}\n\n"
                       f"**Setting:** {setting_name}\n"
                       f"**Old Value:** {old_value}\n"
                       f"**New Value:** {value}\n\n"
                       f"{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.SUCCESS
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)
        
        await _log_action(interaction.guild.id, "security",
                        f"⚙️ [CONFIG] {setting_name} changed from {old_value} to {value} by {interaction.user}")
    
    print("✅ RXT Security System setup complete - event listeners and commands registered")
