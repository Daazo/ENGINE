import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from main import bot
from brand_config import BOT_FOOTER, BrandColors, create_success_embed, create_error_embed, create_info_embed, create_command_embed, create_warning_embed
from main import has_permission, get_server_data, update_server_data, log_action

class TicketCategorySelect(discord.ui.Select):
    def __init__(self, categories):
        options = []
        for cat_num, cat_data in sorted(categories.items()):
            if cat_data.get('enabled', False):
                emoji = cat_data.get('emoji', '🎫')
                options.append(
                    discord.SelectOption(
                        label=cat_data.get('name', f'Category {cat_num}'),
                        description=cat_data.get('description', 'Click to open a ticket'),
                        value=str(cat_num),
                        emoji=emoji
                    )
                )
        
        super().__init__(
            custom_id="persistent_ticket_select",
            placeholder="📋 Select a ticket category...",
            min_values=1,
            max_values=1,
            options=options if options else [discord.SelectOption(label="No categories", value="none")]
        )
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ No ticket categories are configured!", ephemeral=True)
            return
        
        category_num = int(self.values[0])
        server_data = await get_server_data(interaction.guild.id)
        ticket_categories = server_data.get('ticket_categories', {})
        category_data = ticket_categories.get(str(category_num), {})
        
        if not category_data:
            await interaction.response.send_message("❌ This ticket category no longer exists! Please contact an administrator.", ephemeral=True)
            return
        
        modal = TicketModal(category_num, category_data, server_data)
        await interaction.response.send_modal(modal)

class TicketSelectionView(discord.ui.View):
    def __init__(self, categories=None):
        super().__init__(timeout=None)
        if categories is None:
            categories = {}
        self.add_item(TicketCategorySelect(categories))

class TicketModal(discord.ui.Modal):
    def __init__(self, category_num, category_data, server_data):
        super().__init__(title=f"🎫 {category_data.get('name', 'Support Ticket')}")
        self.category_num = category_num
        self.category_data = category_data
        self.server_data = server_data
        self.field_values = {}
        
        form_fields = category_data.get('form_fields', [])
        
        if not form_fields:
            form_fields = [
                {'label': 'Name', 'placeholder': 'Your full name...', 'style': 'short', 'required': True, 'max_length': 100},
                {'label': 'Describe your issue', 'placeholder': 'Describe in detail...', 'style': 'long', 'required': True, 'max_length': 1000}
            ]
        
        for idx, field_config in enumerate(form_fields[:5]):
            style = discord.TextStyle.long if field_config.get('style') == 'long' else discord.TextStyle.short
            field = discord.ui.TextInput(
                label=field_config.get('label', f'Field {idx + 1}'),
                placeholder=field_config.get('placeholder', ''),
                style=style,
                required=field_config.get('required', True),
                max_length=field_config.get('max_length', 1000)
            )
            setattr(self, f'field_{idx}', field)
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        server_data = await get_server_data(interaction.guild.id)
        ticket_cooldowns = server_data.get('ticket_cooldowns', {})
        user_id = str(interaction.user.id)

        if user_id in ticket_cooldowns:
            last_ticket = datetime.fromisoformat(ticket_cooldowns[user_id])
            if datetime.now() - last_ticket < timedelta(minutes=10):
                embed = discord.Embed(
                    title="⏳ Ticket Cooldown",
                    description="You must wait 10 minutes between creating tickets!",
                    color=BrandColors.WARNING
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        open_category_id = self.category_data.get('open_category_id')
        if not open_category_id:
            await interaction.response.send_message("❌ This ticket category is not properly configured!", ephemeral=True)
            return
        
        category = interaction.guild.get_channel(int(open_category_id))
        if not category:
            await interaction.response.send_message("❌ Ticket category channel not found!", ephemeral=True)
            return

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

        ticket_categories = server_data.get('ticket_categories', {})
        category_ticket_count = ticket_categories.get(str(self.category_num), {}).get('ticket_count', 0) + 1
        
        ticket_categories[str(self.category_num)]['ticket_count'] = category_ticket_count
        await update_server_data(interaction.guild.id, {'ticket_categories': ticket_categories})
        
        clean_username = ''.join(c for c in interaction.user.name if c.isalnum() or c in ['-', '_']).lower()[:20]
        category_name_short = ''.join(c for c in self.category_data.get('name', 'ticket') if c.isalnum() or c in ['-', '_']).lower()[:15]
        channel_name = f"{category_name_short}-{clean_username}-{category_ticket_count}"
        
        ticket_channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"Category: {self.category_data.get('name')} | Ticket #{category_ticket_count} | Creator ID: {interaction.user.id} | Category Number: {self.category_num}"
        )

        embed = discord.Embed(
            title=f"🎟️ {self.category_data.get('name', 'Support Ticket')}",
            description=f"**Created by:** {interaction.user.mention}\n**Category:** {self.category_data.get('name')}\n**Ticket Number:** #{category_ticket_count}\n**Created:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            color=BrandColors.INFO
        )
        
        form_fields = self.category_data.get('form_fields', [])
        for idx, field_config in enumerate(form_fields[:5]):
            field_attr = getattr(self, f'field_{idx}', None)
            if field_attr:
                field_emoji = field_config.get('emoji', '📋')
                embed.add_field(
                    name=f"{field_emoji} {field_config.get('label', f'Field {idx + 1}')}",
                    value=field_attr.value or 'N/A',
                    inline=True if field_config.get('style') == 'short' else False
                )
        
        embed.set_footer(text=BOT_FOOTER)

        view = TicketControlView()

        mention_text = ""
        if support_role_id:
            support_role = interaction.guild.get_role(int(support_role_id))
            if support_role:
                mention_text = f"{support_role.mention} "

        await ticket_channel.send(content=mention_text, embed=embed, view=view)
        
        ticket_cooldowns[user_id] = datetime.now().isoformat()
        await update_server_data(interaction.guild.id, {'ticket_cooldowns': ticket_cooldowns})

        success_embed = discord.Embed(
            title="✅ Ticket Created",
            description=f"Your ticket has been created: {ticket_channel.mention}",
            color=BrandColors.SUCCESS
        )
        await interaction.response.send_message(embed=success_embed, ephemeral=True)

        await log_action(
            interaction.guild.id,
            "tickets",
            f"🎫 [TICKET CREATED] {interaction.user.mention} created ticket {ticket_channel.mention} in category **{self.category_data.get('name')}**"
        )

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        server_data = await get_server_data(interaction.guild.id)
        
        if not await has_permission(interaction, 'junior_moderator'):
            await interaction.response.send_message("❌ You don't have permission to close tickets!", ephemeral=True)
            return

        channel = interaction.channel
        if not channel.topic or "Category Number:" not in channel.topic:
            await interaction.response.send_message("❌ This doesn't appear to be a valid ticket!", ephemeral=True)
            return

        try:
            category_num = channel.topic.split("Category Number:")[1].strip()
            ticket_categories = server_data.get('ticket_categories', {})
            category_data = ticket_categories.get(category_num, {})
            
            closed_category_id = category_data.get('closed_category_id')
            if not closed_category_id:
                await interaction.response.send_message("❌ Closed category not configured for this ticket type!", ephemeral=True)
                return
            
            closed_category = interaction.guild.get_channel(int(closed_category_id))
            if not closed_category:
                await interaction.response.send_message("❌ Closed category channel not found!", ephemeral=True)
                return

            await channel.edit(category=closed_category)
            
            creator_id = None
            if "Creator ID:" in channel.topic:
                try:
                    creator_id = int(channel.topic.split("Creator ID:")[1].split("|")[0].strip())
                    creator = interaction.guild.get_member(creator_id)
                    if creator:
                        await channel.set_permissions(creator, read_messages=False, send_messages=False)
                except:
                    pass

            embed = discord.Embed(
                title="🔒 Ticket Closed",
                description=f"This ticket has been closed by {interaction.user.mention}.\n\nModerators can reopen or permanently delete this ticket using the buttons below.",
                color=BrandColors.DANGER,
                timestamp=datetime.now()
            )
            embed.set_footer(text=BOT_FOOTER)

            reopen_delete_view = ReopenDeleteTicketView()
            await interaction.response.send_message(embed=embed, view=reopen_delete_view)

            await log_action(
                interaction.guild.id,
                "tickets",
                f"🔒 [TICKET CLOSED] {interaction.user.mention} closed ticket {channel.mention}"
            )

        except Exception as e:
            await interaction.response.send_message(f"❌ Error closing ticket: {str(e)}", ephemeral=True)

class ReopenDeleteTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reopen Ticket", style=discord.ButtonStyle.success, custom_id="reopen_ticket", emoji="🔓")
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        server_data = await get_server_data(interaction.guild.id)
        
        if not await has_permission(interaction, 'junior_moderator'):
            await interaction.response.send_message("❌ You don't have permission to reopen tickets!", ephemeral=True)
            return

        channel = interaction.channel
        if not channel.topic or "Category Number:" not in channel.topic:
            await interaction.response.send_message("❌ This doesn't appear to be a valid ticket!", ephemeral=True)
            return

        try:
            category_num = channel.topic.split("Category Number:")[1].strip()
            ticket_categories = server_data.get('ticket_categories', {})
            category_data = ticket_categories.get(category_num, {})
            
            open_category_id = category_data.get('open_category_id')
            if not open_category_id:
                await interaction.response.send_message("❌ Open category not configured for this ticket type!", ephemeral=True)
                return
            
            open_category = interaction.guild.get_channel(int(open_category_id))
            if not open_category:
                await interaction.response.send_message("❌ Open category channel not found!", ephemeral=True)
                return

            await channel.edit(category=open_category)
            
            creator_id = None
            if "Creator ID:" in channel.topic:
                try:
                    creator_id = int(channel.topic.split("Creator ID:")[1].split("|")[0].strip())
                    creator = interaction.guild.get_member(creator_id)
                    if creator:
                        await channel.set_permissions(creator, read_messages=True, send_messages=True)
                except:
                    pass

            embed = discord.Embed(
                title="🔓 Ticket Reopened",
                description=f"This ticket has been reopened by {interaction.user.mention}.\n\nThe conversation can continue.",
                color=BrandColors.SUCCESS,
                timestamp=datetime.now()
            )
            embed.set_footer(text=BOT_FOOTER)

            control_view = TicketControlView()
            await interaction.response.send_message(embed=embed, view=control_view)

            await log_action(
                interaction.guild.id,
                "tickets",
                f"🔓 [TICKET REOPENED] {interaction.user.mention} reopened ticket {channel.mention}"
            )

        except Exception as e:
            await interaction.response.send_message(f"❌ Error reopening ticket: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Permanently Delete", style=discord.ButtonStyle.danger, custom_id="delete_ticket_confirm", emoji="🗑️")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        server_data = await get_server_data(interaction.guild.id)
        
        is_owner = interaction.user.id == interaction.guild.owner_id
        is_main_mod = await has_permission(interaction, 'main_moderator')
        
        if not (is_owner or is_main_mod):
            await interaction.response.send_message("❌ Only the server owner and main moderators can permanently delete tickets!", ephemeral=True)
            return

        confirm_view = ConfirmDeleteView(interaction.channel)
        embed = discord.Embed(
            title="⚠️ Confirm Permanent Deletion",
            description=f"Are you sure you want to **permanently delete** this ticket?\n\n**Channel:** {interaction.channel.mention}\n**This action cannot be undone!**",
            color=BrandColors.DANGER
        )
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)

class ConfirmDeleteView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=60)
        self.channel = channel

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            channel_name = self.channel.name
            
            await log_action(
                interaction.guild.id,
                "tickets",
                f"🗑️ [TICKET DELETED] {interaction.user.mention} permanently deleted ticket **{channel_name}**"
            )
            
            await interaction.response.send_message("🗑️ Deleting ticket in 3 seconds...", ephemeral=True)
            await asyncio.sleep(3)
            await self.channel.delete(reason=f"Ticket permanently deleted by {interaction.user}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error deleting ticket: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Deletion cancelled.", ephemeral=True)
        self.stop()

@bot.tree.command(name="ticketpanel", description="Create a ticket selection panel")
async def ticketpanel(interaction: discord.Interaction):
    server_data = await get_server_data(interaction.guild.id)
    
    if not await has_permission(interaction, 'main_moderator') and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Only server owners and main moderators can create ticket panels!", ephemeral=True)
        return

    ticket_categories = server_data.get('ticket_categories', {})
    enabled_cats = {k: v for k, v in ticket_categories.items() if v.get('enabled', False)}
    
    if not enabled_cats:
        await interaction.response.send_message("❌ No ticket categories are configured! Use `/ticketcategory` to set them up first.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 RXT ENGINE Support System",
        description="Need help? Select a ticket category from the dropdown menu below.\n\n**Choose the category that best matches your issue:**",
        color=BrandColors.PRIMARY
    )
    
    for cat_num, cat_data in sorted(enabled_cats.items()):
        emoji = cat_data.get('emoji', '🎫')
        name = cat_data.get('name', f'Category {cat_num}')
        desc = cat_data.get('description', 'No description')
        embed.add_field(
            name=f"{emoji} {name}",
            value=desc,
            inline=False
        )
    
    embed.set_footer(text=BOT_FOOTER)

    view = TicketSelectionView(enabled_cats)
    
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Ticket panel created!", ephemeral=True)

@bot.tree.command(name="ticketcategory", description="Configure a ticket category (1-7)")
@app_commands.describe(
    category_number="Category number (1-7)",
    action="What do you want to do?",
    name="Category name (e.g., 'Technical Support')",
    description="Short description of this category",
    emoji="Emoji for this category (e.g., 🛠️)",
    open_category="Discord category for open tickets",
    closed_category="Discord category for closed tickets"
)
async def ticketcategory(
    interaction: discord.Interaction,
    category_number: int,
    action: str,
    name: str = None,
    description: str = None,
    emoji: str = None,
    open_category: discord.CategoryChannel = None,
    closed_category: discord.CategoryChannel = None
):
    server_data = await get_server_data(interaction.guild.id)
    
    if not await has_permission(interaction, 'main_moderator') and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Only server owners and main moderators can configure ticket categories!", ephemeral=True)
        return

    if category_number < 1 or category_number > 7:
        await interaction.response.send_message("❌ Category number must be between 1 and 7!", ephemeral=True)
        return

    ticket_categories = server_data.get('ticket_categories', {})
    cat_key = str(category_number)
    
    if action == "setup":
        if not name or not open_category or not closed_category:
            await interaction.response.send_message("❌ For setup, you must provide: name, open_category, and closed_category!", ephemeral=True)
            return
        
        ticket_categories[cat_key] = {
            'name': name,
            'description': description or f"Open a {name} ticket",
            'emoji': emoji or '🎫',
            'open_category_id': str(open_category.id),
            'closed_category_id': str(closed_category.id),
            'enabled': True,
            'ticket_count': 0,
            'form_fields': [
                {'label': 'Name', 'placeholder': 'Your full name...', 'style': 'short', 'emoji': '👤', 'required': True, 'max_length': 100},
                {'label': 'Issue Description', 'placeholder': 'Describe in detail...', 'style': 'long', 'emoji': '📝', 'required': True, 'max_length': 1000}
            ]
        }
        
        await update_server_data(interaction.guild.id, {'ticket_categories': ticket_categories})
        
        embed = discord.Embed(
            title="✅ Ticket Category Created",
            description=f"**Category {category_number}:** {name}\n**Emoji:** {emoji or '🎫'}\n**Open Category:** {open_category.mention}\n**Closed Category:** {closed_category.mention}",
            color=BrandColors.SUCCESS
        )
        await interaction.response.send_message(embed=embed)
        
    elif action == "disable":
        if cat_key in ticket_categories:
            ticket_categories[cat_key]['enabled'] = False
            await update_server_data(interaction.guild.id, {'ticket_categories': ticket_categories})
            await interaction.response.send_message(f"✅ Category {category_number} has been disabled.")
        else:
            await interaction.response.send_message(f"❌ Category {category_number} doesn't exist!")
            
    elif action == "enable":
        if cat_key in ticket_categories:
            ticket_categories[cat_key]['enabled'] = True
            await update_server_data(interaction.guild.id, {'ticket_categories': ticket_categories})
            await interaction.response.send_message(f"✅ Category {category_number} has been enabled.")
        else:
            await interaction.response.send_message(f"❌ Category {category_number} doesn't exist!")
            
    elif action == "view":
        if cat_key in ticket_categories:
            cat = ticket_categories[cat_key]
            embed = discord.Embed(
                title=f"📋 Category {category_number}: {cat.get('name')}",
                description=cat.get('description'),
                color=BrandColors.INFO
            )
            embed.add_field(name="Emoji", value=cat.get('emoji', '🎫'), inline=True)
            embed.add_field(name="Status", value="✅ Enabled" if cat.get('enabled') else "❌ Disabled", inline=True)
            embed.add_field(name="Tickets Created", value=str(cat.get('ticket_count', 0)), inline=True)
            
            open_cat = interaction.guild.get_channel(int(cat.get('open_category_id', 0)))
            closed_cat = interaction.guild.get_channel(int(cat.get('closed_category_id', 0)))
            
            embed.add_field(name="Open Category", value=open_cat.mention if open_cat else "Not found", inline=True)
            embed.add_field(name="Closed Category", value=closed_cat.mention if closed_cat else "Not found", inline=True)
            
            fields_text = "\n".join([f"{i+1}. {f.get('label')} ({f.get('style')})" for i, f in enumerate(cat.get('form_fields', []))])
            embed.add_field(name="Form Fields", value=fields_text or "None", inline=False)
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ Category {category_number} doesn't exist!")
    
    else:
        await interaction.response.send_message("❌ Invalid action! Use: setup, disable, enable, or view")

@ticketcategory.autocomplete('action')
async def action_autocomplete(interaction: discord.Interaction, current: str):
    actions = ['setup', 'disable', 'enable', 'view']
    return [app_commands.Choice(name=action, value=action) for action in actions if current.lower() in action.lower()]

@bot.tree.command(name="ticketfields", description="Configure form fields for a ticket category")
@app_commands.describe(
    category_number="Category number (1-7) to configure fields for"
)
async def ticketfields(interaction: discord.Interaction, category_number: int):
    server_data = await get_server_data(interaction.guild.id)
    
    if not await has_permission(interaction, 'main_moderator') and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Only server owners and main moderators can configure ticket fields!", ephemeral=True)
        return

    if category_number < 1 or category_number > 7:
        await interaction.response.send_message("❌ Category number must be between 1 and 7!", ephemeral=True)
        return

    ticket_categories = server_data.get('ticket_categories', {})
    cat_key = str(category_number)
    
    if cat_key not in ticket_categories:
        await interaction.response.send_message(f"❌ Category {category_number} doesn't exist! Create it with `/ticketcategory` first.", ephemeral=True)
        return

    modal = FieldConfigModal(category_number)
    await interaction.response.send_modal(modal)

class FieldConfigModal(discord.ui.Modal, title='Configure Form Fields'):
    def __init__(self, category_num):
        super().__init__()
        self.category_num = category_num
    
    num_fields = discord.ui.TextInput(
        label='Number of Fields (1-5)',
        placeholder='Enter number of fields (e.g., 3)',
        style=discord.TextStyle.short,
        required=True,
        max_length=1
    )
    
    field1 = discord.ui.TextInput(
        label='Field 1: Label|Placeholder|Style|Emoji',
        placeholder='Name|Enter your name...|short|👤',
        style=discord.TextStyle.short,
        required=False,
        max_length=200
    )
    
    field2 = discord.ui.TextInput(
        label='Field 2: Label|Placeholder|Style|Emoji',
        placeholder='Issue|Describe your issue...|long|📝',
        style=discord.TextStyle.short,
        required=False,
        max_length=200
    )
    
    field3 = discord.ui.TextInput(
        label='Field 3: Label|Placeholder|Style|Emoji',
        placeholder='Priority|Low/Medium/High|short|⚠️',
        style=discord.TextStyle.short,
        required=False,
        max_length=200
    )
    
    field4 = discord.ui.TextInput(
        label='Field 4: Label|Placeholder|Style|Emoji',
        placeholder='Additional Info|Any other details...|long|ℹ️',
        style=discord.TextStyle.short,
        required=False,
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            num_fields_int = int(self.num_fields.value)
            if num_fields_int < 1 or num_fields_int > 5:
                await interaction.response.send_message("❌ Number of fields must be between 1 and 5!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number!", ephemeral=True)
            return
        
        form_fields = []
        field_inputs = [self.field1.value, self.field2.value, self.field3.value, self.field4.value]
        
        for i in range(num_fields_int):
            if i < len(field_inputs) and field_inputs[i]:
                parts = field_inputs[i].split('|')
                if len(parts) >= 2:
                    label = parts[0].strip()
                    placeholder = parts[1].strip() if len(parts) > 1 else ''
                    style = parts[2].strip().lower() if len(parts) > 2 else 'short'
                    emoji = parts[3].strip() if len(parts) > 3 else '📋'
                    
                    form_fields.append({
                        'label': label,
                        'placeholder': placeholder,
                        'style': style if style in ['short', 'long'] else 'short',
                        'emoji': emoji,
                        'required': True,
                        'max_length': 1000 if style == 'long' else 100
                    })
        
        if not form_fields:
            await interaction.response.send_message("❌ No valid fields were provided!", ephemeral=True)
            return
        
        server_data = await get_server_data(interaction.guild.id)
        ticket_categories = server_data.get('ticket_categories', {})
        cat_key = str(self.category_num)
        
        if cat_key in ticket_categories:
            ticket_categories[cat_key]['form_fields'] = form_fields
            await update_server_data(interaction.guild.id, {'ticket_categories': ticket_categories})
            
            embed = discord.Embed(
                title=f"✅ Form Fields Updated for Category {self.category_num}",
                description=f"**{ticket_categories[cat_key].get('name')}**\n\nConfigured {len(form_fields)} field(s):",
                color=BrandColors.SUCCESS
            )
            
            for idx, field in enumerate(form_fields, 1):
                embed.add_field(
                    name=f"{field.get('emoji', '📋')} Field {idx}: {field['label']}",
                    value=f"Style: {field['style']}\nPlaceholder: {field['placeholder']}",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ Category {self.category_num} not found!", ephemeral=True)

@bot.tree.command(name="tnamechange", description="Rename a ticket channel")
@app_commands.describe(new_name="New name for the ticket channel")
async def tnamechange(interaction: discord.Interaction, new_name: str):
    server_data = await get_server_data(interaction.guild.id)
    
    if not await has_permission(interaction, 'junior_moderator'):
        await interaction.response.send_message("❌ You don't have permission to rename tickets!", ephemeral=True)
        return

    if not interaction.channel.topic or "Creator ID:" not in interaction.channel.topic:
        await interaction.response.send_message("❌ This command can only be used in ticket channels!", ephemeral=True)
        return

    old_name = interaction.channel.name
    clean_name = ''.join(c for c in new_name if c.isalnum() or c in ['-', '_']).lower()
    
    await interaction.channel.edit(name=clean_name)
    
    embed = discord.Embed(
        title="✅ Ticket Renamed",
        description=f"**Old Name:** {old_name}\n**New Name:** {clean_name}",
        color=BrandColors.SUCCESS
    )
    await interaction.response.send_message(embed=embed)
    
    await log_action(
        interaction.guild.id,
        "tickets",
        f"✏️ [TICKET RENAMED] {interaction.user.mention} renamed ticket from **{old_name}** to **{clean_name}**"
    )

def setup(bot):
    pass
