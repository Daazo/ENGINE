
import discord
from discord.ext import commands
from discord import app_commands
import re
import asyncio
from main import bot, has_permission, get_server_data, update_server_data, log_action

# Bad words list (can be expanded)
BAD_WORDS = [
    'fuck', 'thayoli', 'poori', 'thandha', 'stupid', 'bitch', 'dick', 'andi', 
    'pussy', 'whore', 'vedi', 'vedichi', 'slut', 'punda', 'nayinta mon', 'gay'
]

# URL regex pattern
URL_PATTERN = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if not message.guild:
        return
    
    # Check if user has moderator permissions (exempt from automod)
    if await has_permission_user_message(message.author, message.guild, "junior_moderator"):
        await bot.process_commands(message)
        return
    
    server_data = await get_server_data(message.guild.id)
    automod_settings = server_data.get('automod', {})
    disabled_channels = automod_settings.get('disabled_channels', [])
    
    # Skip automod in disabled channels
    if str(message.channel.id) in disabled_channels:
        await bot.process_commands(message)
        return
    
    # Check for bad words
    if automod_settings.get('bad_words', False):
        content_lower = message.content.lower()
        for bad_word in BAD_WORDS:
            if bad_word in content_lower:
                await message.delete()
                
                embed = discord.Embed(
                    title="🚫 Message Deleted",
                    description=f"**{message.author.mention}**, your message contained inappropriate language!",
                    color=0xe74c3c
                )
                warning_msg = await message.channel.send(embed=embed)
                await asyncio.sleep(5)
                await warning_msg.delete()
                
                await log_action(message.guild.id, "moderation", f"🚫 [AUTOMOD] Bad word detected from {message.author} in {message.channel}")
                return
    
    # Check for links
    if automod_settings.get('links', False):
        if URL_PATTERN.search(message.content):
            await message.delete()
            
            embed = discord.Embed(
                title="🔗 Link Blocked",
                description=f"**{message.author.mention}**, links are not allowed in this channel!",
                color=0xe74c3c
            )
            warning_msg = await message.channel.send(embed=embed)
            await asyncio.sleep(5)
            await warning_msg.delete()
            
            await log_action(message.guild.id, "moderation", f"🔗 [AUTOMOD] Link blocked from {message.author} in {message.channel}")
            return
    
    # Check for spam (messages sent too quickly)
    if automod_settings.get('spam', False):
        # Simple spam detection - user sends more than 5 messages in 10 seconds
        user_id = str(message.author.id)
        spam_tracking = automod_settings.get('spam_tracking', {})
        
        import time
        current_time = time.time()
        
        if user_id not in spam_tracking:
            spam_tracking[user_id] = []
        
        # Clean old messages (older than 10 seconds)
        spam_tracking[user_id] = [t for t in spam_tracking[user_id] if current_time - t < 10]
        spam_tracking[user_id].append(current_time)
        
        if len(spam_tracking[user_id]) > 5:
            await message.delete()
            
            # Timeout user for 5 minutes
            try:
                await message.author.timeout(duration=300, reason="Spam detection")
                embed = discord.Embed(
                    title="⏱️ Timeout Applied",
                    description=f"**{message.author.mention}** has been timed out for 5 minutes due to spam!",
                    color=0xf39c12
                )
                await message.channel.send(embed=embed)
            except:
                embed = discord.Embed(
                    title="🚫 Spam Detected",
                    description=f"**{message.author.mention}**, please slow down your messages!",
                    color=0xe74c3c
                )
                warning_msg = await message.channel.send(embed=embed)
                await asyncio.sleep(5)
                await warning_msg.delete()
            
            # Reset spam tracking for user
            spam_tracking[user_id] = []
            automod_settings['spam_tracking'] = spam_tracking
            await update_server_data(message.guild.id, {'automod': automod_settings})
            
            await log_action(message.guild.id, "moderation", f"⏱️ [AUTOMOD] Spam timeout applied to {message.author}")
            return
        
        automod_settings['spam_tracking'] = spam_tracking
        await update_server_data(message.guild.id, {'automod': automod_settings})
    
    await bot.process_commands(message)

async def has_permission_user_message(member, guild, permission_level):
    """Check if user has required permission level (for message events)"""
    if member.id == guild.owner_id:
        return True
    
    server_data = await get_server_data(guild.id)
    
    if permission_level == "main_moderator":
        main_mod_role_id = server_data.get('main_moderator_role')
        if main_mod_role_id:
            main_mod_role = guild.get_role(int(main_mod_role_id))
            return main_mod_role in member.roles
    
    elif permission_level == "junior_moderator":
        junior_mod_role_id = server_data.get('junior_moderator_role')
        main_mod_role_id = server_data.get('main_moderator_role')
        
        if junior_mod_role_id:
            junior_mod_role = guild.get_role(int(junior_mod_role_id))
            if junior_mod_role in member.roles:
                return True
        
        if main_mod_role_id:
            main_mod_role = guild.get_role(int(main_mod_role_id))
            if main_mod_role in member.roles:
                return True
    
    return False

@bot.tree.command(name="automod", description="Configure auto moderation")
@app_commands.describe(
    feature="Automod feature to configure",
    enabled="Enable or disable the feature",
    channel="Channel to disable automod in (optional)"
)
@app_commands.choices(feature=[
    app_commands.Choice(name="bad_words", value="bad_words"),
    app_commands.Choice(name="links", value="links"),
    app_commands.Choice(name="spam", value="spam"),
    app_commands.Choice(name="disable_channel", value="disable_channel")
])
async def automod_setup(
    interaction: discord.Interaction,
    feature: str,
    enabled: bool = None,
    channel: discord.TextChannel = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    server_data = await get_server_data(interaction.guild.id)
    automod_settings = server_data.get('automod', {})
    
    if feature == "disable_channel":
        if not channel:
            await interaction.response.send_message("❌ Please specify a channel!", ephemeral=True)
            return
        
        disabled_channels = automod_settings.get('disabled_channels', [])
        channel_id = str(channel.id)
        
        if enabled is False:  # Remove from disabled list
            if channel_id in disabled_channels:
                disabled_channels.remove(channel_id)
                action = "enabled"
            else:
                await interaction.response.send_message("❌ Automod is already enabled in that channel!", ephemeral=True)
                return
        else:  # Add to disabled list
            if channel_id not in disabled_channels:
                disabled_channels.append(channel_id)
                action = "disabled"
            else:
                await interaction.response.send_message("❌ Automod is already disabled in that channel!", ephemeral=True)
                return
        
        automod_settings['disabled_channels'] = disabled_channels
        await update_server_data(interaction.guild.id, {'automod': automod_settings})
        
        embed = discord.Embed(
            title=f"✅ Automod {action.title()} in Channel",
            description=f"**Channel:** {channel.mention}\n**Status:** {action.title()}",
            color=0x43b581 if action == "enabled" else 0xf39c12
        )
        await interaction.response.send_message(embed=embed)
        
    else:
        if enabled is None:
            await interaction.response.send_message("❌ Please specify enabled status (True/False)!", ephemeral=True)
            return
        
        automod_settings[feature] = enabled
        await update_server_data(interaction.guild.id, {'automod': automod_settings})
        
        feature_names = {
            'bad_words': 'Bad Words Filter',
            'links': 'Link Blocker',
            'spam': 'Spam Protection'
        }
        
        embed = discord.Embed(
            title=f"✅ {feature_names[feature]} {'Enabled' if enabled else 'Disabled'}",
            description=f"**Feature:** {feature_names[feature]}\n**Status:** {'Enabled' if enabled else 'Disabled'}",
            color=0x43b581 if enabled else 0xe74c3c
        )
        await interaction.response.send_message(embed=embed)
    
    await log_action(interaction.guild.id, "setup", f"🛡️ [AUTOMOD] {feature} configured by {interaction.user}")
