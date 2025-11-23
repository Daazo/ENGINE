
import discord
from discord.ext import commands
from discord import app_commands
from main import bot
from brand_config import create_permission_denied_embed, create_owner_only_embed,  BOT_FOOTER, BrandColors
from main import has_permission, get_server_data, update_server_data, log_action

@bot.tree.command(name="autorole", description="🎭 Configure auto role for new members")
@app_commands.describe(
    action="Set or remove auto role",
    role="Role to automatically assign to new members"
)
@app_commands.choices(action=[
    app_commands.Choice(name="set", value="set"),
    app_commands.Choice(name="remove", value="remove")
])
async def autorole_setup(
    interaction: discord.Interaction,
    action: str,
    role: discord.Role = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True, ephemeral=True)
        return
    
    server_data = await get_server_data(interaction.guild.id)
    
    if action == "set":
        if not role:
            await interaction.response.send_message("❌ Please specify a role to set as auto role!", ephemeral=True)
            return
        
        # Check if bot can assign this role
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message("❌ I cannot assign this role! Please make sure my role is higher than the auto role.", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'auto_role': str(role.id)})
        
        embed = discord.Embed(
            title="✅ Auto Role Set",
            description=f"**Auto Role:** {role.mention}\n**Action:** New members will automatically receive this role\n**Set by:** {interaction.user.mention}",
            color=BrandColors.SUCCESS
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)
        
    elif action == "remove":
        current_auto_role = server_data.get('auto_role')
        if not current_auto_role:
            await interaction.response.send_message("❌ No auto role is currently set!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'auto_role': None})
        
        embed = discord.Embed(
            title="✅ Auto Role Removed",
            description=f"**Action:** Auto role has been disabled\n**Removed by:** {interaction.user.mention}",
            color=BrandColors.WARNING
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)
