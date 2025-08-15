
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from main import bot, has_permission, get_server_data, update_server_data, log_action

class TicketModal(discord.ui.Modal, title='🎫 Create Support Ticket'):
    def __init__(self, category_id):
        super().__init__()
        self.category_id = category_id
    
    name = discord.ui.TextInput(
        label='Full Name',
        placeholder='Enter your full name...',
        required=True,
        max_length=100
    )
    
    issue = discord.ui.TextInput(
        label='Describe Your Issue',
        placeholder='Please describe your issue in detail...',
        style=discord.TextStyle.long,
        required=True,
        max_length=1000
    )
    
    urgency = discord.ui.TextInput(
        label='Urgency Level',
        placeholder='Low, Medium, or High',
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Check cooldown
        server_data = await get_server_data(interaction.guild.id)
        ticket_cooldowns = server_data.get('ticket_cooldowns', {})
        user_id = str(interaction.user.id)
        
        if user_id in ticket_cooldowns:
            last_ticket = datetime.fromisoformat(ticket_cooldowns[user_id])
            if datetime.now() - last_ticket < timedelta(minutes=10):
                embed = discord.Embed(
                    title="⏳ Ticket Cooldown",
                    description="You must wait 10 minutes between creating tickets!",
                    color=0xf39c12
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Create ticket channel
        category = interaction.guild.get_channel(int(self.category_id))
        if not category:
            await interaction.response.send_message("❌ Ticket category not found!", ephemeral=True)
            return
        
        # Get moderator roles
        main_mod_role_id = server_data.get('main_moderator_role')
        junior_mod_role_id = server_data.get('junior_moderator_role')
        support_role_id = server_data.get('ticket_support_role')
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        if main_mod_role_id:
            main_mod_role = interaction.guild.get_role(int(main_mod_role_id))
            if main_mod_role:
                overwrites[main_mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        if junior_mod_role_id:
            junior_mod_role = interaction.guild.get_role(int(junior_mod_role_id))
            if junior_mod_role:
                overwrites[junior_mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        if support_role_id:
            support_role = interaction.guild.get_role(int(support_role_id))
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel_name = f"ticket-{interaction.user.name.lower()}{interaction.user.discriminator}"
        ticket_channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"Support ticket for {interaction.user}"
        )
        
        # Create ticket embed
        urgency_colors = {
            'low': 0x43b581,
            'medium': 0xf39c12,
            'high': 0xe74c3c
        }
        
        urgency_level = self.urgency.value.lower()
        color = urgency_colors.get(urgency_level, 0x3498db)
        
        embed = discord.Embed(
            title="🎟️ New Support Ticket",
            description=f"**Ticket created by:** {interaction.user.mention}\n**Created at:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            color=color
        )
        embed.add_field(name="👤 Full Name", value=self.name.value, inline=True)
        embed.add_field(name="⚠️ Urgency", value=self.urgency.value.title(), inline=True)
        embed.add_field(name="📝 Issue Description", value=self.issue.value, inline=False)
        embed.set_footer(text="Support team will be with you shortly!")
        
        view = TicketControlView()
        
        # Send ticket embed and mention support role if available
        support_role_id = server_data.get('ticket_support_role')
        mention_text = ""
        if support_role_id:
            support_role = interaction.guild.get_role(int(support_role_id))
            if support_role:
                mention_text = f"{support_role.mention} "
        
        await ticket_channel.send(mention_text, embed=embed, view=view)
        
        # Update cooldown
        ticket_cooldowns[user_id] = datetime.now().isoformat()
        await update_server_data(interaction.guild.id, {'ticket_cooldowns': ticket_cooldowns})
        
        # Response to user
        response_embed = discord.Embed(
            title="✅ Ticket Created Successfully",
            description=f"Your support ticket has been created: {ticket_channel.mention}\nOur team will assist you shortly!",
            color=0x43b581
        )
        await interaction.response.send_message(embed=response_embed, ephemeral=True)
        
        await log_action(interaction.guild.id, "tickets", f"🎫 [TICKET OPENED] {interaction.user} - Urgency: {self.urgency.value}")

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Close Ticket', style=discord.ButtonStyle.danger, emoji='🔒', custom_id='ticket_close_button')
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has moderator permissions OR ticket support role
        has_mod_permission = await has_permission(interaction, "junior_moderator")
        
        server_data = await get_server_data(interaction.guild.id)
        support_role_id = server_data.get('ticket_support_role')
        has_support_role = False
        
        if support_role_id:
            support_role = interaction.guild.get_role(int(support_role_id))
            if support_role and support_role in interaction.user.roles:
                has_support_role = True
        
        if not has_mod_permission and not has_support_role:
            await interaction.response.send_message("❌ You need Junior Moderator permissions or Ticket Support role to close tickets!", ephemeral=True)
            return</old_str>
        
        server_data = await get_server_data(interaction.guild.id)
        close_category_id = server_data.get('ticket_close_category')
        
        if not close_category_id:
            await interaction.response.send_message("❌ Ticket close category not set! Use `/setup ticketclose` first.", ephemeral=True)
            return
        
        close_category = interaction.guild.get_channel(int(close_category_id))
        if not close_category:
            await interaction.response.send_message("❌ Ticket close category not found!", ephemeral=True)
            return
        
        # Move channel to closed category
        await interaction.channel.edit(
            category=close_category,
            name=f"closed-{interaction.channel.name}"
        )
        
        # Remove user access
        for member in interaction.channel.members:
            if not await has_permission_user(member, interaction.guild, "junior_moderator"):
                await interaction.channel.set_permissions(member, read_messages=False)
        
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"This ticket has been closed by {interaction.user.mention}",
            color=0xe74c3c
        )
        
        reopen_view = ReopenTicketView()
        await interaction.response.send_message(embed=embed, view=reopen_view)
        
        await log_action(interaction.guild.id, "tickets", f"🔒 [TICKET CLOSED] {interaction.channel.name} by {interaction.user}")

class ReopenTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Reopen Ticket', style=discord.ButtonStyle.success, emoji='🔓', custom_id='ticket_reopen_button')
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await has_permission(interaction, "junior_moderator"):
            await interaction.response.send_message("❌ You need Junior Moderator permissions or higher to reopen tickets!", ephemeral=True)
            return</old_str>
        
        server_data = await get_server_data(interaction.guild.id)
        open_category_id = server_data.get('ticket_open_category')
        
        if not open_category_id:
            await interaction.response.send_message("❌ Ticket open category not set!", ephemeral=True)
            return
        
        open_category = interaction.guild.get_channel(int(open_category_id))
        if not open_category:
            await interaction.response.send_message("❌ Ticket open category not found!", ephemeral=True)
            return
        
        # Move back to open category
        new_name = interaction.channel.name.replace("closed-", "")
        await interaction.channel.edit(
            category=open_category,
            name=new_name
        )
        
        embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description=f"This ticket has been reopened by {interaction.user.mention}",
            color=0x43b581
        )
        
        # Add close button back to the reopened ticket
        close_view = TicketControlView()
        await interaction.response.send_message(embed=embed, view=close_view)</old_str>
        
        await log_action(interaction.guild.id, "tickets", f"🔓 [TICKET REOPENED] {interaction.channel.name} by {interaction.user}")

class TicketOpenView(discord.ui.View):
    def __init__(self, category_id):
        super().__init__(timeout=None)
        self.category_id = category_id
    
    @discord.ui.button(label='🎫 Open Support Ticket', style=discord.ButtonStyle.primary, emoji='🎫', custom_id='ticket_open_button')
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get the actual category from server data since we can't store it persistently
        server_data = await get_server_data(interaction.guild.id)
        category_id = server_data.get('ticket_open_category')
        
        if not category_id:
            await interaction.response.send_message("❌ Ticket system not properly configured! Contact an administrator.", ephemeral=True)
            return
        
        modal = TicketModal(category_id)
        await interaction.response.send_modal(modal)

async def has_permission_user(member, guild, permission_level):
    """Check if user has required permission level"""
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

@bot.tree.command(name="ticketsetup", description="Setup ticket system")
@app_commands.describe(
    action="Setup action",
    category="Category for tickets",
    channel="Channel to send ticket button",
    description="Description for ticket message"
)
@app_commands.choices(action=[
    app_commands.Choice(name="open", value="open"),
    app_commands.Choice(name="close", value="close")
])
async def ticket_setup(
    interaction: discord.Interaction,
    action: str,
    category: discord.CategoryChannel,
    channel: discord.TextChannel = None,
    description: str = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message("❌ You need Main Moderator permissions to use this command!", ephemeral=True)
        return
    
    if action == "open":
        if not channel or not description:
            await interaction.response.send_message("❌ Please provide channel and description for ticket setup!", ephemeral=True)
            return
        
        await update_server_data(interaction.guild.id, {'ticket_open_category': str(category.id)})
        
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description=f"{description}\n\n**Need help?** Click the button below to create a support ticket!\nOur team will assist you as soon as possible.",
            color=0x3498db
        )
        embed.set_footer(text="🌴 ᴠᴀᴀᴢʜᴀ Support System")
        
        view = TicketOpenView(str(category.id))
        await channel.send(embed=embed, view=view)
        
        response_embed = discord.Embed(
            title="✅ Ticket System Setup Complete",
            description=f"**Open Category:** {category.mention}\n**Button Channel:** {channel.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=response_embed)
        
    elif action == "close":
        await update_server_data(interaction.guild.id, {'ticket_close_category': str(category.id)})
        
        response_embed = discord.Embed(
            title="✅ Ticket Close Category Set",
            description=f"**Close Category:** {category.mention}",
            color=0x43b581
        )
        await interaction.response.send_message(embed=response_embed)
    
    await log_action(interaction.guild.id, "setup", f"🎫 [TICKET SETUP] {action} category set by {interaction.user}")
