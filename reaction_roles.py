
import discord
from discord.ext import commands
from discord import app_commands
from main import bot
from brand_config import create_permission_denied_embed, create_owner_only_embed,  BOT_FOOTER, BrandColors, create_success_embed, create_error_embed, create_info_embed, create_command_embed, create_warning_embed
from main import has_permission, get_server_data, update_server_data, log_action

@bot.tree.command(name="reactionrole", description="🎭 Setup reaction roles with multiple emoji/role pairs")
@app_commands.describe(
    channel="Channel to send the reaction role message",
    title="Title for the reaction role embed",
    description="Description explaining the roles",
    auto_remove_role="Role to automatically remove when users get any reaction role"
)
async def reaction_role_setup(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    title: str,
    description: str,
    auto_remove_role: discord.Role = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True)
        return

    # Create the setup modal
    class ReactionRoleModal(discord.ui.Modal):
        def __init__(self, channel, title, description, auto_remove_role):
            super().__init__(title="🎭 Reaction Role Setup")
            self.channel = channel
            self.embed_title = title
            self.embed_description = description
            self.auto_remove_role = auto_remove_role

        emoji_role_pairs = discord.ui.TextInput(
            label="Emoji:Role Pairs (one per line)",
            placeholder="🎯:@Role1\n⭐:@Role2\n🎮:@Role3\n(Max 10 pairs)",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )

        async def on_submit(self, modal_interaction: discord.Interaction):
            await modal_interaction.response.defer()

            try:
                # Parse emoji:role pairs
                pairs = []
                lines = self.emoji_role_pairs.value.strip().split('\n')
                
                for line in lines:
                    if ':' not in line:
                        continue
                    
                    emoji_part, role_part = line.split(':', 1)
                    emoji = emoji_part.strip()
                    role_mention = role_part.strip()
                    
                    # Extract role ID from mention
                    role_id = None
                    if role_mention.startswith('<@&') and role_mention.endswith('>'):
                        role_id = role_mention[3:-1]
                    elif role_mention.startswith('@'):
                        # Try to find role by name
                        role_name = role_mention[1:]
                        for guild_role in modal_interaction.guild.roles:
                            if guild_role.name.lower() == role_name.lower():
                                role_id = str(guild_role.id)
                                break
                    
                    if role_id:
                        role = modal_interaction.guild.get_role(int(role_id))
                        if role:
                            pairs.append((emoji, role))

                if not pairs:
                    await modal_interaction.followup.send("❌ No valid emoji:role pairs found! Format: 🎯:@Role1", ephemeral=True)
                    return

                if len(pairs) > 10:
                    await modal_interaction.followup.send("❌ Maximum 10 emoji:role pairs allowed!", ephemeral=True)
                    return

                # Create the embed
                embed = discord.Embed(
                    title=f"🎭 {self.embed_title}",
                    description=self.embed_description,
                    color=BrandColors.PRIMARY
                )

                # Add field showing available roles
                role_list = []
                for emoji, role in pairs:
                    role_list.append(f"{emoji} - {role.mention}")

                embed.add_field(
                    name="📋 Available Roles",
                    value="\n".join(role_list),
                    inline=False
                )

                if self.auto_remove_role:
                    embed.add_field(
                        name="🔄 Auto-Remove Role",
                        value=f"Getting any role will remove: {self.auto_remove_role.mention}",
                        inline=False
                    )

                embed.set_footer(text=f"React below to get your roles! • {BOT_FOOTER}")

                # Send the message
                sent_message = await self.channel.send(embed=embed)

                # Add all reactions
                for emoji, role in pairs:
                    try:
                        await sent_message.add_reaction(emoji)
                    except discord.HTTPException:
                        await modal_interaction.followup.send(f"⚠️ Failed to add reaction {emoji} - invalid emoji", ephemeral=True)

                # Store reaction role data
                server_data = await get_server_data(modal_interaction.guild.id)
                reaction_roles = server_data.get('reaction_roles', {})

                reaction_roles[str(sent_message.id)] = {
                    'channel_id': str(self.channel.id),
                    'pairs': [(emoji, str(role.id)) for emoji, role in pairs],
                    'auto_remove_role_id': str(self.auto_remove_role.id) if self.auto_remove_role else None,
                    'title': self.embed_title,
                    'description': self.embed_description
                }

                await update_server_data(modal_interaction.guild.id, {'reaction_roles': reaction_roles})

                # Success response
                success_embed = discord.Embed(
                    title="✅ Reaction Role Setup Complete",
                    description=f"**Message:** {self.channel.mention}\n**Emoji/Role Pairs:** {len(pairs)}\n**Auto-Remove Role:** {self.auto_remove_role.mention if self.auto_remove_role else 'None'}",
                    color=BrandColors.SUCCESS
                )

                success_embed.add_field(
                    name="🎭 Configured Pairs",
                    value="\n".join([f"{emoji} → {role.mention}" for emoji, role in pairs]),
                    inline=False
                )

                success_embed.set_footer(text=BOT_FOOTER)
                await modal_interaction.followup.send(embed=success_embed)

                await log_action(modal_interaction.guild.id, "reaction_role", f"🎭 [REACTION ROLE] Multi-setup by {modal_interaction.user} - {len(pairs)} pairs in {self.channel.name}")

            except Exception as e:
                await modal_interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

    # Show the modal properly
    modal = ReactionRoleModal(channel, title, description, auto_remove_role)
    await interaction.response.send_modal(modal)

# Alternative command for quick single reaction role setup
@bot.tree.command(name="quickreactionrole", description="🎭 Quick setup for single reaction role")
@app_commands.describe(
    message="Message for the embed",
    emoji="Emoji for reaction",
    role="Role to give when user reacts",
    channel="Channel to send message",
    auto_remove_role="Role to remove when user gets this role"
)
async def quick_reaction_role_setup(
    interaction: discord.Interaction,
    message: str,
    emoji: str,
    role: discord.Role,
    channel: discord.TextChannel,
    auto_remove_role: discord.Role = None
):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True)
        return

    try:
        # Send the message
        embed = discord.Embed(
            title="🎭 Reaction Roles",
            description=message,
            color=BrandColors.PRIMARY
        )

        if auto_remove_role:
            embed.add_field(
                name="🔄 Auto-Remove",
                value=f"Getting {role.mention} will remove: {auto_remove_role.mention}",
                inline=False
            )

        embed.set_footer(text=BOT_FOOTER)

        sent_message = await channel.send(embed=embed)

        # Add reaction
        await sent_message.add_reaction(emoji)

        # Store reaction role data
        server_data = await get_server_data(interaction.guild.id)
        reaction_roles = server_data.get('reaction_roles', {})

        reaction_roles[str(sent_message.id)] = {
            'channel_id': str(channel.id),
            'pairs': [(emoji, str(role.id))],
            'auto_remove_role_id': str(auto_remove_role.id) if auto_remove_role else None,
            'title': "Reaction Roles",
            'description': message
        }

        await update_server_data(interaction.guild.id, {'reaction_roles': reaction_roles})

        response_embed = discord.Embed(
            title="✅ Quick Reaction Role Setup Complete",
            description=f"**Message:** {channel.mention}\n**Emoji:** {emoji}\n**Role:** {role.mention}\n**Auto-Remove Role:** {auto_remove_role.mention if auto_remove_role else 'None'}",
            color=BrandColors.SUCCESS
        )
        response_embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=response_embed)

        await log_action(interaction.guild.id, "reaction_role", f"🎭 [QUICK REACTION ROLE] Setup by {interaction.user} - {emoji} → {role.name}")

    except Exception as e:
        await interaction.response.send_message(embed=create_error_embed(f"An error occurred: {str(e)}"), ephemeral=True)

@bot.event
async def on_raw_reaction_add(payload):
    """Handle reaction role assignment with multiple emoji support"""
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
        member = guild.get_member(payload.user_id)

        if not member:
            return

        # Check for multiple emoji/role pairs
        pairs = reaction_data.get('pairs', [])
        auto_remove_role_id = reaction_data.get('auto_remove_role_id')

        for emoji, role_id in pairs:
            if str(payload.emoji) == emoji:
                give_role = guild.get_role(int(role_id))
                
                if give_role and member:
                    try:
                        # Handle auto-remove role functionality
                        if auto_remove_role_id:
                            auto_remove_role = guild.get_role(int(auto_remove_role_id))
                            if auto_remove_role and auto_remove_role in member.roles:
                                await member.remove_roles(auto_remove_role, reason="Auto-remove role on reaction role assignment")
                                await log_action(guild.id, "reaction_role", f"🔄 [AUTO-REMOVE] {auto_remove_role.name} removed from {member}")

                        # Add the reaction role
                        if give_role not in member.roles:
                            await member.add_roles(give_role, reason="Reaction role assignment")
                            await log_action(guild.id, "reaction_role", f"🎭 [REACTION ROLE] {give_role.name} added to {member}")

                    except discord.Forbidden:
                        print(f"Missing permissions to modify roles for {member}")
                    except discord.HTTPException as e:
                        print(f"Failed to modify role: {e}")
                break

@bot.event
async def on_raw_reaction_remove(payload):
    """Handle reaction role removal with multiple emoji support"""
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
        member = guild.get_member(payload.user_id)

        if not member:
            return

        # Check for multiple emoji/role pairs
        pairs = reaction_data.get('pairs', [])
        auto_remove_role_id = reaction_data.get('auto_remove_role_id')

        for emoji, role_id in pairs:
            if str(payload.emoji) == emoji:
                remove_role = guild.get_role(int(role_id))
                
                if remove_role and member:
                    try:
                        # Remove the reaction role when unreacting
                        if remove_role in member.roles:
                            await member.remove_roles(remove_role, reason="Reaction role removal")
                            await log_action(guild.id, "reaction_role", f"🎭 [REACTION ROLE] {remove_role.name} removed from {member}")

                        # Restore auto-remove role if enabled and user has no other reaction roles
                        if auto_remove_role_id:
                            auto_remove_role = guild.get_role(int(auto_remove_role_id))
                            if auto_remove_role:
                                # Check if user has any other reaction roles from this message
                                has_other_roles = False
                                for other_emoji, other_role_id in pairs:
                                    if other_emoji != emoji:
                                        other_role = guild.get_role(int(other_role_id))
                                        if other_role and other_role in member.roles:
                                            has_other_roles = True
                                            break

                                # Only restore auto-remove role if user has no other reaction roles
                                if not has_other_roles and auto_remove_role not in member.roles:
                                    await member.add_roles(auto_remove_role, reason="Auto-remove role restoration")
                                    await log_action(guild.id, "reaction_role", f"🔄 [AUTO-RESTORE] {auto_remove_role.name} restored to {member}")

                    except discord.Forbidden:
                        print(f"Missing permissions to modify roles for {member}")
                    except discord.HTTPException as e:
                        print(f"Failed to modify role: {e}")
                break

# List reaction roles command
@bot.tree.command(name="listreactionroles", description="📋 List all active reaction role setups")
async def list_reaction_roles(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    server_data = await get_server_data(interaction.guild.id)
    reaction_roles = server_data.get('reaction_roles', {})

    if not reaction_roles:
        embed = discord.Embed(
            title="📋 No Reaction Roles Found",
            description="No reaction role setups are currently active in this server.\n\nUse `/reactionrole` or `/quickreactionrole` to create one!",
            color=BrandColors.WARNING
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)
        return

    embed = discord.Embed(
        title="📋 **Active Reaction Role Setups**",
        description=f"*Found {len(reaction_roles)} reaction role setup(s)*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        color=BrandColors.PRIMARY
    )

    count = 0
    for message_id, data in list(reaction_roles.items())[:5]:  # Show max 5
        count += 1
        channel = bot.get_channel(int(data['channel_id']))
        channel_name = channel.mention if channel else f"Unknown Channel"
        
        pairs = data.get('pairs', [])
        auto_remove_role_id = data.get('auto_remove_role_id')
        auto_remove_role = interaction.guild.get_role(int(auto_remove_role_id)) if auto_remove_role_id else None
        
        pair_text = []
        for emoji, role_id in pairs[:3]:  # Show max 3 pairs per setup
            role = interaction.guild.get_role(int(role_id))
            role_name = role.mention if role else "Unknown Role"
            pair_text.append(f"{emoji} → {role_name}")

        if len(pairs) > 3:
            pair_text.append(f"... +{len(pairs)-3} more")

        field_value = f"**Channel:** {channel_name}\n**Pairs:** {', '.join(pair_text) if pair_text else 'None'}"
        if auto_remove_role:
            field_value += f"\n**Auto-Remove:** {auto_remove_role.mention}"

        embed.add_field(
            name=f"#{count} Message ID: {message_id}",
            value=field_value,
            inline=False
        )

    if len(reaction_roles) > 5:
        embed.add_field(
            name="📊 Additional Setups",
            value=f"*{len(reaction_roles) - 5} more setups not shown*",
            inline=False
        )

    embed.set_footer(text=BOT_FOOTER, icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)