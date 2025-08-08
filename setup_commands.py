
import discord
from discord.ext import commands
from discord import app_commands
from main import bot, has_permission, get_server_data, update_server_data, log_action

@bot.tree.command(name="setup", description="Configure bot settings")
@app_commands.describe(
    action="What to setup",
    value="Value to set",
    role="Role to assign",
    channel="Channel to set"
)
@app_commands.choices(action=[
    app_commands.Choice(name="main_moderator", value="main_moderator"),
    app_commands.Choice(name="junior_moderator", value="junior_moderator"),
    app_commands.Choice(name="welcome", value="welcome"),
    app_commands.Choice(name="logs", value="logs"),
    app_commands.Choice(name="xp", value="xp"),
    app_commands.Choice(name="ticket_support_role", value="ticket_support_role")
])
async def setup(
    interaction: discord.Interaction,
    action: str,
    value: str = None,
    role: discord.Role = None,
    channel: discord.TextChannel = None
):
    # Check permissions
    if action == "main_moderator":
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Only the server owner can set main moderator role!", ephemeral=True)
            return
    else:
        if not await has_permission(interaction, "main_moderator"):
            await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
            return
    
    server_data = await get_server_data(interaction.guild.id)
    
    if action == "main_moderator":
        if not role:
            await interaction.response.send_message("❌ Please specify a role!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'main_moderator_role': str(role.id)})
        
        embed = discord.Embed(
            title="✅ Main Moderator Role Set",
            description=f"**Role:** {role.mention}\n**Set by:** {interaction.user.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild.id, "setup", f"⚙️ [SETUP] Main moderator role set to {role.name} by {interaction.user}")
    
    elif action == "junior_moderator":
        if not role:
            await interaction.response.send_message("❌ Please specify a role!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'junior_moderator_role': str(role.id)})
        
        embed = discord.Embed(
            title="✅ Junior Moderator Role Set",
            description=f"**Role:** {role.mention}\n**Set by:** {interaction.user.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild.id, "setup", f"⚙️ [SETUP] Junior moderator role set to {role.name} by {interaction.user}")
    
    elif action == "welcome":
        if not channel or not value:
            await interaction.response.send_message("❌ Please specify both channel and welcome message!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {
            'welcome_channel': str(channel.id),
            'welcome_message': value
        })
        
        embed = discord.Embed(
            title="✅ Welcome Settings Updated",
            description=f"**Channel:** {channel.mention}\n**Message:** {value}\n**Set by:** {interaction.user.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild.id, "setup", f"⚙️ [SETUP] Welcome channel set to {channel.name} by {interaction.user}")
    
    elif action == "prefix":
        if not value:
            await interaction.response.send_message("❌ Please specify a prefix!", ephemeral=True)
            return
        
        if len(value) > 5:
            await interaction.response.send_message("❌ Prefix must be 5 characters or less!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'prefix': value})
        
        embed = discord.Embed(
            title="✅ Prefix Updated",
            description=f"**New Prefix:** `{value}`\n**Set by:** {interaction.user.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild.id, "setup", f"⚙️ [SETUP] Prefix set to '{value}' by {interaction.user}")
    
    elif action == "logs":
        if not value or not channel:
            await interaction.response.send_message("❌ Please specify log type and channel!\n**Log types:** all, moderation, xp, communication", ephemeral=True)
            return
        
        valid_log_types = ["all", "moderation", "xp", "communication"]
        if value not in valid_log_types:
            await interaction.response.send_message(f"❌ Invalid log type! Valid types: {', '.join(valid_log_types)}", ephemeral=True)
            return
        
        log_channels = server_data.get('log_channels', {})
        log_channels[value] = str(channel.id)
        
        await update_server_data(interaction.guild.id, {'log_channels': log_channels})
        
        embed = discord.Embed(
            title="✅ Log Channel Set",
            description=f"**Log Type:** {value}\n**Channel:** {channel.mention}\n**Set by:** {interaction.user.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild.id, "setup", f"⚙️ [SETUP] {value} log channel set to {channel.name} by {interaction.user}")
    
    elif action == "xp":
        if not channel:
            await interaction.response.send_message("❌ Please specify a channel for XP announcements!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'xp_channel': str(channel.id)})
        
        embed = discord.Embed(
            title="✅ XP Channel Set",
            description=f"**Channel:** {channel.mention}\n**Set by:** {interaction.user.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild.id, "setup", f"⚙️ [SETUP] XP channel set to {channel.name} by {interaction.user}")
    
    elif action == "ticket_support_role":
        if not role:
            await interaction.response.send_message("❌ Please specify a role for ticket support!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'ticket_support_role': str(role.id)})
        
        embed = discord.Embed(
            title="✅ Ticket Support Role Set",
            description=f"**Role:** {role.mention}\n**Set by:** {interaction.user.mention}\n\n*This role will be mentioned when tickets are created.*",
            color=0x43b581
        )
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild.id, "setup", f"⚙️ [SETUP] Ticket support role set to {role.name} by {interaction.user}")
