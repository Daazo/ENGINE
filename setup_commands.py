
import discord
from discord.ext import commands
from discord import app_commands
from main import bot, has_permission, get_server_data, update_server_data, log_action

@bot.tree.command(name="setup", description="Setup bot configurations")
@app_commands.describe(
    action="What to setup",
    value="The value to set",
    channel="Channel for certain setups",
    role="Role for certain setups"
)
async def setup(
    interaction: discord.Interaction,
    action: str,
    value: str = None,
    channel: discord.TextChannel = None,
    role: discord.Role = None
):
    # Check permissions based on action
    if action == "main_moderator":
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Only the server owner can setup main moderator!", ephemeral=True)
            return
    elif action in ["junior_moderator", "welcome", "logs", "xp", "ticketopen", "ticketclose", "reactionroles", "prefix"]:
        if not await has_permission(interaction, "main_moderator"):
            await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
            return
    
    if action == "main_moderator":
        if not role:
            await interaction.response.send_message("❌ Please provide a role for main moderator!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'main_moderator_role': str(role.id)})
        
        embed = discord.Embed(
            title="✅ Main Moderator Setup",
            description=f"Main moderator role set to {role.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "setup", f"⚙ [SETUP] Main moderator role set to {role.name} by {interaction.user.mention}")
    
    elif action == "junior_moderator":
        if not role:
            await interaction.response.send_message("❌ Please provide a role for junior moderator!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'junior_moderator_role': str(role.id)})
        
        embed = discord.Embed(
            title="✅ Junior Moderator Setup",
            description=f"Junior moderator role set to {role.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "setup", f"⚙ [SETUP] Junior moderator role set to {role.name} by {interaction.user.mention}")
    
    elif action == "welcome":
        if not channel or not value:
            await interaction.response.send_message("❌ Please provide both channel and welcome message!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {
            'welcome_channel': str(channel.id),
            'welcome_message': value
        })
        
        embed = discord.Embed(
            title="✅ Welcome Setup",
            description=f"Welcome channel set to {channel.mention}\nMessage: {value[:100]}{'...' if len(value) > 100 else ''}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "setup", f"⚙ [SETUP] Welcome configured for {channel.mention} by {interaction.user.mention}")
    
    elif action == "prefix":
        if not value:
            await interaction.response.send_message("❌ Please provide a prefix!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'prefix': value})
        
        embed = discord.Embed(
            title="✅ Prefix Setup",
            description=f"Server prefix set to `{value}`",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "setup", f"⚙ [SETUP] Prefix set to {value} by {interaction.user.mention}")
    
    elif action == "logs":
        if not value or not channel:
            await interaction.response.send_message("❌ Please provide log type and channel!\nTypes: all, moderation, xp, tickets, setup, communication", ephemeral=True)
            return
        
        log_types = ["all", "moderation", "xp", "tickets", "setup", "communication"]
        if value not in log_types:
            await interaction.response.send_message(f"❌ Invalid log type! Available: {', '.join(log_types)}", ephemeral=True)
            return
        
        server_data = await get_server_data(interaction.guild.id)
        log_channels = server_data.get('log_channels', {})
        log_channels[value] = str(channel.id)
        
        await update_server_data(interaction.guild.id, {'log_channels': log_channels})
        
        embed = discord.Embed(
            title="✅ Logs Setup",
            description=f"{value.title()} logs will be sent to {channel.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "setup", f"⚙ [SETUP] {value} logs configured for {channel.mention} by {interaction.user.mention}")
    
    elif action == "xp":
        if not channel:
            await interaction.response.send_message("❌ Please provide a channel for XP announcements!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'xp_channel': str(channel.id)})
        
        embed = discord.Embed(
            title="✅ XP Setup",
            description=f"XP level-up messages will be sent to {channel.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "setup", f"⚙ [SETUP] XP channel configured for {channel.mention} by {interaction.user.mention}")
    
    else:
        embed = discord.Embed(
            title="❌ Invalid Setup Action",
            description="Available actions:\n• `main_moderator` - Set main moderator role\n• `junior_moderator` - Set junior moderator role\n• `welcome` - Configure welcome messages\n• `prefix` - Set custom prefix\n• `logs` - Configure log channels\n• `xp` - Set XP announcement channel",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Setup command choices
@setup.autocomplete('action')
async def setup_action_autocomplete(interaction: discord.Interaction, current: str):
    actions = [
        app_commands.Choice(name="Main Moderator Role", value="main_moderator"),
        app_commands.Choice(name="Junior Moderator Role", value="junior_moderator"),
        app_commands.Choice(name="Welcome Messages", value="welcome"),
        app_commands.Choice(name="Custom Prefix", value="prefix"),
        app_commands.Choice(name="Log Channels", value="logs"),
        app_commands.Choice(name="XP Channel", value="xp"),
    ]
    return [action for action in actions if current.lower() in action.name.lower()]
