
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

# Automod functionality is now integrated into main.py's on_message event
# This prevents conflicts between multiple on_message handlers

# Permission checking function moved to main.py to avoid duplication

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
