
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
from datetime import datetime, timedelta
from main import bot, has_permission, get_server_data, update_server_data, log_action
import json

# Security tracking data
security_data = {
    'join_tracking': {},  # Track recent joins for anti-raid
    'permission_changes': {},  # Track permission changes
    'channel_deletions': {},  # Track channel deletions
    'role_deletions': {},  # Track role deletions
    'ban_tracking': {},  # Track recent bans
    'whitelist_cache': {}  # Cache for bot/role whitelists
}

# Security settings command
@bot.tree.command(name="security", description="🛡️ Configure security system settings")
@app_commands.describe(
    feature="Security feature to configure",
    enabled="Enable or disable the feature",
    threshold="Threshold value for the feature (where applicable)",
    role="Role for verification or whitelist"
)
@app_commands.choices(feature=[
    app_commands.Choice(name="anti_raid", value="anti_raid"),
    app_commands.Choice(name="anti_nuke", value="anti_nuke"),
    app_commands.Choice(name="permission_monitoring", value="permission_monitoring"),
    app_commands.Choice(name="auto_ban", value="auto_ban"),
    app_commands.Choice(name="verification_system", value="verification_system"),
    app_commands.Choice(name="bot_whitelist", value="bot_whitelist"),
    app_commands.Choice(name="security_logs", value="security_logs")
])
async def security_settings(
    interaction: discord.Interaction,
    feature: str,
    enabled: bool,
    threshold: int = None,
    role: discord.Role = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    security_settings = server_data.get('security_settings', {})

    # Update the specific security feature
    if feature == "verification_system" and role:
        security_settings[feature] = {
            'enabled': enabled,
            'verified_role': str(role.id)
        }
    elif threshold is not None:
        security_settings[feature] = {
            'enabled': enabled,
            'threshold': threshold
        }
    else:
        security_settings[feature] = {'enabled': enabled}

    await update_server_data(interaction.guild.id, {'security_settings': security_settings})

    feature_names = {
        'anti_raid': '🛡️ Anti-Raid Protection',
        'anti_nuke': '🚫 Anti-Nuke Protection', 
        'permission_monitoring': '👁️ Permission Monitoring',
        'auto_ban': '🔨 Auto Ban System',
        'verification_system': '✅ Verification System',
        'bot_whitelist': '🤖 Bot Whitelist',
        'security_logs': '📋 Security Logs'
    }

    status = "✅ Enabled" if enabled else "❌ Disabled"
    extra_info = ""
    
    if threshold:
        extra_info = f"\n**Threshold:** {threshold}"
    if role:
        extra_info += f"\n**Role:** {role.mention}"

    embed = discord.Embed(
        title="🛡️ **Security Settings Updated**",
        description=f"**Feature:** {feature_names.get(feature, feature)}\n**Status:** {status}{extra_info}",
        color=0x43b581 if enabled else 0xe74c3c
    )
    embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ Security System", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
    await log_action(interaction.guild.id, "security", f"🛡️ [SECURITY] {feature_names.get(feature, feature)} {status.lower()} by {interaction.user}")

# Verification setup command
@bot.tree.command(name="verification-setup", description="✅ Setup verification system for new members")
@app_commands.describe(
    channel="Channel where verification button will be posted",
    verified_role="Role to give verified members",
    message="Custom verification message"
)
async def verification_setup(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    verified_role: discord.Role,
    message: str = "Click the button below to verify and gain access to the server!"
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    # Update security settings
    server_data = await get_server_data(interaction.guild.id)
    security_settings = server_data.get('security_settings', {})
    security_settings['verification_system'] = {
        'enabled': True,
        'verified_role': str(verified_role.id),
        'channel': str(channel.id)
    }
    await update_server_data(interaction.guild.id, {'security_settings': security_settings})

    # Create verification embed and button
    embed = discord.Embed(
        title="✅ **Server Verification Required**",
        description=f"**{message}**\n\n🔒 You must verify to access all channels and features.\n\n📋 **What verification gives you:**\n• Access to all server channels\n• Ability to participate in discussions\n• Full server member privileges",
        color=0x43b581
    )
    embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ Security System", icon_url=bot.user.display_avatar.url)

    view = VerificationView(verified_role.id)
    await channel.send(embed=embed, view=view)

    response_embed = discord.Embed(
        title="✅ **Verification System Setup Complete**",
        description=f"**Channel:** {channel.mention}\n**Verified Role:** {verified_role.mention}\n**Status:** Active\n\n*New members will need to verify before accessing the server.*",
        color=0x43b581
    )
    await interaction.response.send_message(embed=response_embed)
    await log_action(interaction.guild.id, "security", f"✅ [VERIFICATION] Verification system setup by {interaction.user}")

class VerificationView(discord.ui.View):
    def __init__(self, verified_role_id):
        super().__init__(timeout=None)
        self.verified_role_id = verified_role_id

    @discord.ui.button(label='✅ Verify Me', style=discord.ButtonStyle.success, emoji='✅', custom_id='verify_member')
    async def verify_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        verified_role = interaction.guild.get_role(self.verified_role_id)
        if not verified_role:
            await interaction.response.send_message("❌ Verification role not found! Contact administrators.", ephemeral=True)
            return

        if verified_role in interaction.user.roles:
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return

        try:
            await interaction.user.add_roles(verified_role, reason="Member verification")
            
            embed = discord.Embed(
                title="✅ **Verification Successful!**",
                description="**Welcome to the server!** 🎉\n\nYou now have access to all channels and can participate fully in our community.\n\n*Enjoy your stay!* 🌴",
                color=0x43b581
            )
            embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ Security", icon_url=bot.user.display_avatar.url)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await log_action(interaction.guild.id, "security", f"✅ [VERIFICATION] {interaction.user} verified successfully")
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to assign the verified role. Contact administrators.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Verification failed: {str(e)}", ephemeral=True)

# Bot whitelist command
@bot.tree.command(name="whitelist", description="🤖 Manage bot and role whitelist for security")
@app_commands.describe(
    action="Add or remove from whitelist",
    target="Bot or role to whitelist",
    target_type="Whether it's a bot or role"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="list", value="list")
    ],
    target_type=[
        app_commands.Choice(name="bot", value="bot"),
        app_commands.Choice(name="role", value="role")
    ]
)
async def whitelist_command(
    interaction: discord.Interaction,
    action: str,
    target_type: str = None,
    target: discord.Member = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    whitelist = server_data.get('security_whitelist', {'bots': [], 'roles': []})

    if action == "list":
        bot_list = [f"<@{bot_id}>" for bot_id in whitelist.get('bots', [])]
        role_list = [f"<@&{role_id}>" for role_id in whitelist.get('roles', [])]
        
        embed = discord.Embed(
            title="🤖 **Security Whitelist**",
            color=0x3498db
        )
        embed.add_field(
            name="🤖 Whitelisted Bots",
            value="\n".join(bot_list) if bot_list else "*None*",
            inline=False
        )
        embed.add_field(
            name="👥 Whitelisted Roles", 
            value="\n".join(role_list) if role_list else "*None*",
            inline=False
        )
        embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ Security System")
        
        await interaction.response.send_message(embed=embed)
        return

    if not target or not target_type:
        await interaction.response.send_message("❌ Please specify a target and target type!", ephemeral=True)
        return

    target_id = str(target.id)
    target_list = whitelist.get(target_type + 's', [])

    if action == "add":
        if target_id not in target_list:
            target_list.append(target_id)
            whitelist[target_type + 's'] = target_list
            await update_server_data(interaction.guild.id, {'security_whitelist': whitelist})
            
            embed = discord.Embed(
                title="✅ **Added to Whitelist**",
                description=f"**{target_type.title()}:** {target.mention}\n**Action:** Added to security whitelist",
                color=0x43b581
            )
            await log_action(interaction.guild.id, "security", f"🤖 [WHITELIST] {target} added to {target_type} whitelist by {interaction.user}")
        else:
            embed = discord.Embed(
                title="⚠️ **Already Whitelisted**",
                description=f"{target.mention} is already in the {target_type} whitelist.",
                color=0xf39c12
            )
    
    elif action == "remove":
        if target_id in target_list:
            target_list.remove(target_id)
            whitelist[target_type + 's'] = target_list
            await update_server_data(interaction.guild.id, {'security_whitelist': whitelist})
            
            embed = discord.Embed(
                title="✅ **Removed from Whitelist**",
                description=f"**{target_type.title()}:** {target.mention}\n**Action:** Removed from security whitelist",
                color=0xe74c3c
            )
            await log_action(interaction.guild.id, "security", f"🤖 [WHITELIST] {target} removed from {target_type} whitelist by {interaction.user}")
        else:
            embed = discord.Embed(
                title="⚠️ **Not Whitelisted**",
                description=f"{target.mention} is not in the {target_type} whitelist.",
                color=0xf39c12
            )

    await interaction.response.send_message(embed=embed)

# Event handlers for security monitoring
@bot.event
async def on_member_join_security_check(member):
    """Anti-raid detection on member join"""
    guild_id = str(member.guild.id)
    current_time = time.time()
    
    # Initialize tracking if not exists
    if guild_id not in security_data['join_tracking']:
        security_data['join_tracking'][guild_id] = []
    
    # Add this join to tracking
    security_data['join_tracking'][guild_id].append(current_time)
    
    # Remove joins older than 1 minute
    security_data['join_tracking'][guild_id] = [
        join_time for join_time in security_data['join_tracking'][guild_id] 
        if current_time - join_time <= 60
    ]
    
    # Check for raid (more than 10 joins in 1 minute by default)
    server_data = await get_server_data(member.guild.id)
    security_settings = server_data.get('security_settings', {})
    anti_raid = security_settings.get('anti_raid', {'enabled': False})
    
    if anti_raid.get('enabled', False):
        threshold = anti_raid.get('threshold', 10)
        
        if len(security_data['join_tracking'][guild_id]) > threshold:
            # Raid detected - take action
            await handle_raid_detection(member.guild, len(security_data['join_tracking'][guild_id]))
    
    # Auto-ban suspicious accounts
    auto_ban = security_settings.get('auto_ban', {'enabled': False})
    if auto_ban.get('enabled', False):
        if await is_suspicious_account(member):
            try:
                await member.ban(reason="Auto-ban: Suspicious account detected")
                await log_action(member.guild.id, "security", f"🔨 [AUTO-BAN] Suspicious account {member} automatically banned")
            except:
                pass

async def handle_raid_detection(guild, join_count):
    """Handle detected raid"""
    # Log the raid
    await log_action(guild.id, "security", f"🚨 [ANTI-RAID] Raid detected! {join_count} members joined in 1 minute")
    
    # Send alert to staff
    server_data = await get_server_data(guild.id)
    log_channels = server_data.get('log_channels', {})
    
    alert_channel = None
    if 'security' in log_channels:
        alert_channel = bot.get_channel(int(log_channels['security']))
    elif 'moderation' in log_channels:
        alert_channel = bot.get_channel(int(log_channels['moderation']))
    elif 'all' in log_channels:
        alert_channel = bot.get_channel(int(log_channels['all']))
    
    if alert_channel:
        embed = discord.Embed(
            title="🚨 **RAID ALERT**",
            description=f"**Potential raid detected!**\n\n**Members joined:** {join_count}\n**Time frame:** Last 60 seconds\n**Action recommended:** Review recent joins and take appropriate action",
            color=0xe74c3c
        )
        embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ Security Alert")
        await alert_channel.send(embed=embed)

async def is_suspicious_account(member):
    """Check if account is suspicious"""
    # Check account age (less than 1 day old)
    account_age = (datetime.now() - member.created_at.replace(tzinfo=None)).days
    if account_age < 1:
        return True
    
    # Check for suspicious username patterns
    suspicious_patterns = ['discord', 'admin', 'mod', 'bot', 'official']
    username_lower = member.name.lower()
    
    for pattern in suspicious_patterns:
        if pattern in username_lower and not member.bot:
            return True
    
    # Check for default avatar (no custom avatar set)
    if member.avatar is None:
        return True
    
    return False

@bot.event
async def on_guild_channel_delete_security(channel):
    """Monitor channel deletions for anti-nuke"""
    guild_id = str(channel.guild.id)
    current_time = time.time()
    
    # Initialize tracking
    if guild_id not in security_data['channel_deletions']:
        security_data['channel_deletions'][guild_id] = []
    
    # Add deletion to tracking
    security_data['channel_deletions'][guild_id].append(current_time)
    
    # Remove deletions older than 5 minutes
    security_data['channel_deletions'][guild_id] = [
        del_time for del_time in security_data['channel_deletions'][guild_id]
        if current_time - del_time <= 300
    ]
    
    # Check for nuke attempt
    server_data = await get_server_data(channel.guild.id)
    security_settings = server_data.get('security_settings', {})
    anti_nuke = security_settings.get('anti_nuke', {'enabled': False})
    
    if anti_nuke.get('enabled', False):
        threshold = anti_nuke.get('threshold', 5)
        
        if len(security_data['channel_deletions'][guild_id]) >= threshold:
            await handle_nuke_detection(channel.guild, 'channel', len(security_data['channel_deletions'][guild_id]))

@bot.event 
async def on_member_update_security(before, after):
    """Monitor role changes for permission monitoring"""
    if before.roles == after.roles:
        return
    
    server_data = await get_server_data(after.guild.id)
    security_settings = server_data.get('security_settings', {})
    perm_monitoring = security_settings.get('permission_monitoring', {'enabled': False})
    
    if not perm_monitoring.get('enabled', False):
        return
    
    # Check for dangerous permission changes
    dangerous_perms = [
        'administrator', 'manage_guild', 'manage_channels', 
        'manage_roles', 'ban_members', 'kick_members'
    ]
    
    new_roles = set(after.roles) - set(before.roles)
    for role in new_roles:
        role_perms = role.permissions
        
        for perm in dangerous_perms:
            if getattr(role_perms, perm, False):
                await log_action(after.guild.id, "security", f"⚠️ [PERMISSION ALERT] {after} received dangerous permission '{perm}' via role {role.name}")
                break

async def handle_nuke_detection(guild, nuke_type, count):
    """Handle detected nuke attempt"""
    await log_action(guild.id, "security", f"🚨 [ANTI-NUKE] Potential {nuke_type} nuke detected! {count} {nuke_type}s affected in 5 minutes")

# Note: VerificationView will be added in main.py after bot is ready to avoid event loop issues
