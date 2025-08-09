
import discord
from discord.ext import commands
from discord import app_commands
from main import bot, has_permission, get_server_data, update_server_data, log_action

@bot.tree.command(name="reactionrole", description="🎭 Setup reaction roles")
@app_commands.describe(
    message="Message to send",
    emoji="Emoji for reaction",
    role="Role to give when user reacts",
    channel="Channel to send message",
    remove_role="Role to remove when user reacts (optional)",
    remove_role_enabled="Enable remove role functionality"
)
async def reaction_role_setup(
    interaction: discord.Interaction,
    message: str,
    emoji: str,
    role: discord.Role,
    channel: discord.TextChannel,
    remove_role: discord.Role = None,
    remove_role_enabled: bool = False
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    try:
        # Validate remove role setup
        if remove_role_enabled and not remove_role:
            await interaction.response.send_message("❌ Please specify a role to remove when remove_role_enabled is True!", ephemeral=True)
            return
        
        # Send the message
        embed = discord.Embed(
            title="🎭 Reaction Roles",
            description=message,
            color=0x9b59b6
        )
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
        
        sent_message = await channel.send(embed=embed)
        
        # Add reaction
        await sent_message.add_reaction(emoji)
        
        # Store reaction role data
        server_data = await get_server_data(interaction.guild.id)
        reaction_roles = server_data.get('reaction_roles', {})
        
        reaction_roles[str(sent_message.id)] = {
            'emoji': emoji,
            'role_id': str(role.id),
            'channel_id': str(channel.id),
            'remove_role_enabled': remove_role_enabled,
            'remove_role_id': str(remove_role.id) if remove_role else None
        }
        
        await update_server_data(interaction.guild.id, {'reaction_roles': reaction_roles})
        
        mode_description = "Normal (adds role)"
        if remove_role_enabled:
            mode_description = f"Remove & Add (removes {remove_role.mention}, adds {role.mention})"
        
        response_embed = discord.Embed(
            title="✅ Reaction Role Setup Complete",
            description=f"**Message:** {channel.mention}\n**Emoji:** {emoji}\n**Give Role:** {role.mention}\n**Remove Role:** {remove_role.mention if remove_role else 'None'}\n**Mode:** {mode_description}",
            color=0x43b581
        )
        response_embed.set_footer(text="ᴠᴀᴀᴢʜᴀ")
        await interaction.response.send_message(embed=response_embed)
        
        await log_action(interaction.guild.id, "setup", f"🎭 [REACTION ROLE] Setup by {interaction.user} - {emoji} → {role.name}")
    
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.event
async def on_raw_reaction_add(payload):
    """Handle reaction role assignment"""
    if payload.user_id == bot.user.id:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    
    server_data = await get_server_data(guild.id)
    reaction_roles = server_data.get('reaction_roles', {})
    
    message_id = str(payload.message_id)
    if message_id in reaction_roles:
        reaction_data = reaction_roles[message_id]
        
        if str(payload.emoji) == reaction_data['emoji']:
            give_role = guild.get_role(int(reaction_data['role_id']))
            member = guild.get_member(payload.user_id)
            remove_role_enabled = reaction_data.get('remove_role_enabled', False)
            remove_role_id = reaction_data.get('remove_role_id')
            
            if give_role and member:
                try:
                    # Handle remove role functionality
                    if remove_role_enabled and remove_role_id:
                        remove_role = guild.get_role(int(remove_role_id))
                        if remove_role and remove_role in member.roles:
                            await member.remove_roles(remove_role, reason="Reaction role removal")
                            await log_action(guild.id, "moderation", f"🎭 [REACTION ROLE] {remove_role.name} removed from {member}")
                    
                    # Add the verification/give role
                    if give_role not in member.roles:
                        await member.add_roles(give_role, reason="Reaction role assignment")
                        await log_action(guild.id, "moderation", f"🎭 [REACTION ROLE] {give_role.name} added to {member}")
                        
                except discord.Forbidden:
                    print(f"Missing permissions to modify roles for {member}")
                except discord.HTTPException as e:
                    print(f"Failed to modify role: {e}")

@bot.event
async def on_raw_reaction_remove(payload):
    """Handle reaction role removal with verification"""
    if payload.user_id == bot.user.id:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    
    server_data = await get_server_data(guild.id)
    reaction_roles = server_data.get('reaction_roles', {})
    
    message_id = str(payload.message_id)
    if message_id in reaction_roles:
        reaction_data = reaction_roles[message_id]
        
        if str(payload.emoji) == reaction_data['emoji']:
            give_role = guild.get_role(int(reaction_data['role_id']))
            member = guild.get_member(payload.user_id)
            remove_role_enabled = reaction_data.get('remove_role_enabled', False)
            remove_role_id = reaction_data.get('remove_role_id')
            
            if give_role and member:
                try:
                    # Remove the give role when unreacting
                    if give_role in member.roles:
                        await member.remove_roles(give_role, reason="Reaction role removal")
                        await log_action(guild.id, "moderation", f"🎭 [REACTION ROLE] {give_role.name} removed from {member}")
                    
                    # Restore remove role if enabled
                    if remove_role_enabled and remove_role_id:
                        remove_role = guild.get_role(int(remove_role_id))
                        if remove_role and remove_role not in member.roles:
                            await member.add_roles(remove_role, reason="Reaction role restoration")
                            await log_action(guild.id, "moderation", f"🎭 [REACTION ROLE] {remove_role.name} restored to {member}")
                            
                except discord.Forbidden:
                    print(f"Missing permissions to modify roles for {member}")
                except discord.HTTPException as e:
                    print(f"Failed to modify role: {e}")

# Remove duplicate event handlers - keeping only the first set
