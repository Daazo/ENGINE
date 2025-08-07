
import discord
from discord.ext import commands
from discord import app_commands
from main import bot, has_permission, get_server_data, update_server_data, log_action

@bot.tree.command(name="reactionrole", description="Setup reaction roles")
@app_commands.describe(
    message="Message description for reaction roles",
    emoji="Emoji to react with",
    role="Role to assign",
    channel="Channel to send the message"
)
async def setup_reaction_role(
    interaction: discord.Interaction,
    message: str,
    emoji: str,
    role: discord.Role,
    channel: discord.TextChannel
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    # Create embed for reaction role message
    embed = discord.Embed(
        title="🎭 Reaction Roles",
        description=f"{message}\n\nReact with {emoji} to get {role.mention}",
        color=0x3498db
    )
    embed.set_footer(text="Click the reaction below to get your role!")
    
    # Send message to channel
    sent_message = await channel.send(embed=embed)
    
    # Add reaction
    try:
        await sent_message.add_reaction(emoji)
    except:
        await interaction.response.send_message("❌ Invalid emoji!", ephemeral=True)
        return
    
    # Store in database
    server_data = await get_server_data(interaction.guild.id)
    reaction_roles = server_data.get('reaction_roles', {})
    reaction_roles[str(sent_message.id)] = {
        'emoji': emoji,
        'role_id': str(role.id),
        'channel_id': str(channel.id)
    }
    
    await update_server_data(interaction.guild.id, {'reaction_roles': reaction_roles})
    
    response_embed = discord.Embed(
        title="✅ Reaction Role Setup Complete",
        description=f"**Message:** {message}\n**Emoji:** {emoji}\n**Role:** {role.mention}\n**Channel:** {channel.mention}",
        color=0x43b581
    )
    await interaction.response.send_message(embed=response_embed, ephemeral=True)
    
    await log_action(interaction.guild.id, "setup", f"🎭 [REACTION ROLE] Setup by {interaction.user} - Role: {role.name}, Emoji: {emoji}")

@bot.event
async def on_raw_reaction_add(payload):
    """Handle reaction role assignment"""
    if payload.user_id == bot.user.id:
        return
    
    server_data = await get_server_data(payload.guild_id)
    reaction_roles = server_data.get('reaction_roles', {})
    
    message_id = str(payload.message_id)
    if message_id in reaction_roles:
        reaction_data = reaction_roles[message_id]
        if str(payload.emoji) == reaction_data['emoji']:
            guild = bot.get_guild(payload.guild_id)
            role = guild.get_role(int(reaction_data['role_id']))
            member = guild.get_member(payload.user_id)
            
            if role and member and role not in member.roles:
                await member.add_roles(role)
                await log_action(payload.guild_id, "moderation", f"🎭 [REACTION ROLE] {member} received role {role.name}")

@bot.event
async def on_raw_reaction_remove(payload):
    """Handle reaction role removal"""
    if payload.user_id == bot.user.id:
        return
    
    server_data = await get_server_data(payload.guild_id)
    reaction_roles = server_data.get('reaction_roles', {})
    
    message_id = str(payload.message_id)
    if message_id in reaction_roles:
        reaction_data = reaction_roles[message_id]
        if str(payload.emoji) == reaction_data['emoji']:
            guild = bot.get_guild(payload.guild_id)
            role = guild.get_role(int(reaction_data['role_id']))
            member = guild.get_member(payload.user_id)
            
            if role and member and role in member.roles:
                await member.remove_roles(role)
                await log_action(payload.guild_id, "moderation", f"🎭 [REACTION ROLE] {member} removed role {role.name}")
