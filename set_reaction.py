import discord
from discord.ext import commands
from discord import app_commands
from main import bot, has_permission, get_server_data, update_server_data, db, log_action
from brand_config import BOT_FOOTER, BrandColors
from datetime import datetime
import os

BOT_OWNER_ID = os.getenv('BOT_OWNER_ID')

async def get_reactions(guild_id):
    """Get all set reactions for a server"""
    if db is not None:
        reactions = await db.reactions.find_one({'guild_id': str(guild_id)})
        return reactions.get('members', {}) if reactions else {}
    return {}

async def set_user_reaction(guild_id, user_id, emoji):
    """Set reaction for a user in a server"""
    if db is not None:
        guild_id = str(guild_id)
        user_id = str(user_id)
        
        # Get current reactions
        reactions = await db.reactions.find_one({'guild_id': guild_id})
        members = reactions.get('members', {}) if reactions else {}
        
        # Add or update reaction
        members[user_id] = emoji
        
        # Keep only 10 members
        if len(members) > 10:
            # Remove oldest (first entry)
            first_key = next(iter(members))
            del members[first_key]
        
        await db.reactions.update_one(
            {'guild_id': guild_id},
            {'$set': {'members': members, 'guild_id': guild_id}},
            upsert=True
        )

async def get_user_reaction(guild_id, user_id):
    """Get reaction emoji for a user"""
    reactions = await get_reactions(guild_id)
    return reactions.get(str(user_id), None)

async def initialize_bot_owner_reaction():
    """Set 👑 reaction for bot owner on all servers"""
    if BOT_OWNER_ID and db is not None:
        try:
            # Get all servers with reactions
            all_reactions = await db.reactions.find({}).to_list(None)
            for reaction_doc in all_reactions:
                guild_id = reaction_doc.get('guild_id')
                members = reaction_doc.get('members', {})
                members[str(BOT_OWNER_ID)] = '👑'
                await db.reactions.update_one(
                    {'guild_id': guild_id},
                    {'$set': {'members': members}},
                    upsert=True
                )
            print(f"✅ Bot owner emoji (👑) initialized for all servers (Owner: {BOT_OWNER_ID})")
        except Exception as e:
            print(f"Error initializing bot owner reaction: {e}")

@bot.tree.command(name="set-reaction", description="Set custom emoji reaction when user is mentioned")
@app_commands.describe(user="User to set reaction for", emoji="Emoji to react with")
async def set_reaction(interaction: discord.Interaction, user: discord.User, emoji: str):
    """Set reaction emoji for a user"""
    
    # Check permission
    if interaction.user.id != interaction.guild.owner_id:
        if not await has_permission(interaction, "main_moderator"):
            await interaction.response.send_message("❌ Only Server Owner or Main Moderator can use this!", ephemeral=True)
            return
    
    # Prevent changing bot owner reaction
    if BOT_OWNER_ID and user.id == int(BOT_OWNER_ID):
        await interaction.response.send_message("❌ Cannot change Bot Owner reaction! It's permanently set to 👑", ephemeral=True)
        return
    
    try:
        # Validate emoji
        await interaction.response.defer()
        
        await set_user_reaction(interaction.guild.id, user.id, emoji)
        
        # Logging
        await log_action(interaction.guild.id, "setup", f"✨ [REACTION SET] {emoji} reaction set for {user.mention} by {interaction.user.mention}")
        
        # Send success message
        embed = discord.Embed(
            title="✨ **Reaction Set**",
            description=f"**User:** {user.mention}\n**Emoji:** {emoji}\n**Action:** When this user is mentioned, I'll react with {emoji}",
            color=BrandColors.SUCCESS,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"{BOT_FOOTER} • Set by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        await log_action(interaction.guild.id, "error-log", f"⚠️ [REACTION SET ERROR] Error setting reaction for {user}: {str(e)}")
