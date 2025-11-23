import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
from main import bot, has_permission, log_action, get_server_data, update_server_data, db
from brand_config import BOT_FOOTER, BrandColors, VisualElements
from datetime import datetime, timedelta

print("✅ Event system module loading...")

# Event Entry View with Button
class EventEntryView(discord.ui.View):
    def __init__(self, event_name: str, guild_id: int):
        super().__init__(timeout=None)
        self.event_name = event_name
        self.guild_id = guild_id
    
    @discord.ui.button(label="👑 Enter Event", style=discord.ButtonStyle.primary, custom_id="event_entry_button")
    async def enter_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle event entry button click"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if db is None:
                await interaction.followup.send("❌ Database unavailable!", ephemeral=True)
                return
            
            # Get the event
            event = await db.events.find_one({
                'guild_id': str(self.guild_id),
                'event_name': self.event_name.lower()
            })
            
            if not event:
                await interaction.followup.send("❌ Event not found!", ephemeral=True)
                return
            
            # Check if user already entered
            if interaction.user.id in event.get('participants', []):
                await interaction.followup.send(
                    f"⚠️ You already entered this event!\n\n**Event:** {self.event_name}\n**Your Status:** Already Registered",
                    ephemeral=True
                )
                return
            
            # Add user to participants
            await db.events.update_one(
                {'_id': event['_id']},
                {'$push': {'participants': interaction.user.id}}
            )
            
            # Get updated participant count
            updated_event = await db.events.find_one({'_id': event['_id']})
            participant_count = len(updated_event.get('participants', []))
            
            # Create success embed
            success_embed = discord.Embed(
                title="✅ Event Entry Confirmed",
                description=f"**Event:** {self.event_name}",
                color=BrandColors.SUCCESS,
                timestamp=datetime.now()
            )
            success_embed.add_field(name="📋 Type", value=updated_event.get('event_type', 'Unknown'), inline=True)
            success_embed.add_field(name="👥 Total Participants", value=str(participant_count), inline=True)
            success_embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
            # Log the entry
            guild = bot.get_guild(self.guild_id)
            if guild:
                log_msg = f"👑 [EVENT-ENTRY] {interaction.user.mention} entered event **{self.event_name}** (Total: {participant_count})"
                await log_action(self.guild_id, "events", log_msg)
        
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            print(f"Event entry error: {e}")

# Helper functions for event role permissions
async def has_event_role_permission(interaction):
    """Check if user has event role or higher permissions"""
    if interaction.user.id == interaction.guild.owner_id:
        return True
    
    server_data = await get_server_data(interaction.guild.id)
    event_role_id = server_data.get('event_role')
    
    # Check if user has event role
    if event_role_id:
        event_role = interaction.guild.get_role(int(event_role_id))
        if event_role and event_role in interaction.user.roles:
            return True
    
    # Check if user is main moderator or junior moderator
    if await has_permission(interaction, "main_moderator"):
        return True
    if await has_permission(interaction, "junior_moderator"):
        return True
    
    return False

async def create_event_storage(guild_id, event_name, event_type, duration_value, duration_unit, description, channel_id):
    """Create an event in MongoDB"""
    if db is None:
        return False
    
    guild_id = str(guild_id)
    
    # Calculate end time
    if duration_unit == "minutes":
        end_time = datetime.now() + timedelta(minutes=duration_value)
    elif duration_unit == "hours":
        end_time = datetime.now() + timedelta(hours=duration_value)
    elif duration_unit == "days":
        end_time = datetime.now() + timedelta(days=duration_value)
    
    event_data = {
        'guild_id': guild_id,
        'event_name': event_name.lower(),
        'event_type': event_type,
        'created_at': datetime.now(),
        'end_time': end_time,
        'description': description,
        'channel_id': str(channel_id),
        'participants': [],
        'winner': None,
        'winner_type': None
    }
    
    try:
        result = await db.events.insert_one(event_data)
        return result.inserted_id is not None
    except Exception as e:
        print(f"Error creating event: {e}")
        return False

async def get_event(guild_id, event_name):
    """Get event data from MongoDB"""
    if db is None:
        return None
    
    guild_id = str(guild_id)
    try:
        event = await db.events.find_one({
            'guild_id': guild_id,
            'event_name': event_name.lower()
        })
        return event
    except Exception as e:
        print(f"Error getting event: {e}")
        return None

async def check_event_exists(guild_id, event_name):
    """Check if event already exists in server"""
    event = await get_event(guild_id, event_name)
    return event is not None

@bot.tree.command(name="event-role", description="🎯 Set the event role")
@app_commands.describe(role="Role that can create/announce events")
async def event_role(interaction: discord.Interaction, role: discord.Role):
    """Set the event role - only server owner can use"""
    
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Only server owner can set the event role!", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        await update_server_data(interaction.guild.id, {'event_role': str(role.id)})
        
        embed = discord.Embed(
            title="✅ Event Role Updated",
            description=f"**Role:** {role.mention}\n**Permissions:** Can create and announce events",
            color=BrandColors.SUCCESS,
            timestamp=datetime.now()
        )
        embed.add_field(name="🎯 Authorized Actions", value="• Create Events\n• Announce Winners", inline=False)
        embed.add_field(name=f"{VisualElements.CIRCUIT_LINE}", value="", inline=False)
        embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
        
        # Log action
        log_msg = f"🎯 [EVENT-ROLE] {interaction.user.mention} set event role to {role.mention}"
        await log_action(interaction.guild.id, "events", log_msg)
        
        # Log to global
        try:
            from advanced_logging import send_global_log
            global_log_msg = f"**🎯 Event Role Set**\n**Role:** {role.name}\n**User:** {interaction.user}"
            await send_global_log("events", global_log_msg, interaction.guild)
        except:
            pass
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        await log_action(interaction.guild.id, "error-log", f"⚠️ [EVENT-ROLE ERROR] {interaction.user}: {str(e)}")

@bot.tree.command(name="create-event", description="🎊 Create a new event with button entry")
@app_commands.describe(
    event_name="Name of the event (unique per server)",
    event_type="Type of event (giveaway, contest, raffle, etc)",
    duration_value="Duration value",
    duration_unit="Duration unit",
    description="Event description",
    channel="Channel to send event announcement"
)
@app_commands.choices(duration_unit=[
    app_commands.Choice(name="Minutes", value="minutes"),
    app_commands.Choice(name="Hours", value="hours"),
    app_commands.Choice(name="Days", value="days")
])
async def create_event(
    interaction: discord.Interaction,
    event_name: str,
    event_type: str,
    duration_value: int,
    duration_unit: str,
    description: str,
    channel: discord.TextChannel
):
    """Create a new event - Server owner, main moderator, junior moderator, or event role"""
    
    # Check permissions
    if interaction.user.id != interaction.guild.owner_id:
        if not await has_event_role_permission(interaction):
            await interaction.response.send_message("❌ You don't have permission to create events!", ephemeral=True)
            return
    
    await interaction.response.defer()
    
    try:
        # Check if event name already exists in server
        if await check_event_exists(interaction.guild.id, event_name):
            await interaction.followup.send(f"❌ Event name **{event_name}** already exists in this server!", ephemeral=True)
            return
        
        # Create event in database
        success = await create_event_storage(
            interaction.guild.id,
            event_name,
            event_type,
            duration_value,
            duration_unit,
            description,
            channel.id
        )
        
        if not success:
            await interaction.followup.send("❌ Failed to create event in database!", ephemeral=True)
            return
        
        # Calculate end time for display
        if duration_unit == "minutes":
            end_time = datetime.now() + timedelta(minutes=duration_value)
        elif duration_unit == "hours":
            end_time = datetime.now() + timedelta(hours=duration_value)
        else:
            end_time = datetime.now() + timedelta(days=duration_value)
        
        # Create beautiful announcement embed
        embed = discord.Embed(
            title=f"🎊 {event_name}",
            description=description,
            color=BrandColors.PRIMARY,
            timestamp=datetime.now()
        )
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━",
            value=f"{VisualElements.CIRCUIT_LINE}",
            inline=False
        )
        embed.add_field(name="📋 Event Type", value=f"**{event_type}**", inline=True)
        embed.add_field(name="⏱️ Duration", value=f"**{duration_value} {duration_unit}**", inline=True)
        embed.add_field(name="⏰ Event Ends", value=f"<t:{int(end_time.timestamp())}:f>", inline=False)
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━",
            value=f"{VisualElements.CIRCUIT_LINE}",
            inline=False
        )
        embed.add_field(name="👥 Participants", value="**0 Entered**", inline=True)
        embed.add_field(name="🎯 Status", value="**OPEN**", inline=True)
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━",
            value=f"{VisualElements.CIRCUIT_LINE}",
            inline=False
        )
        embed.add_field(
            name="📝 How to Enter",
            value="Click the **👑 Enter Event** button below to participate.\n*One entry per user - duplicate entries are not allowed.*",
            inline=False
        )
        embed.set_footer(text=f"{BOT_FOOTER} • Event: {event_name}", icon_url=interaction.client.user.display_avatar.url)
        
        # Create view and send announcement
        view = EventEntryView(event_name, interaction.guild.id)
        event_msg = await channel.send(embed=embed, view=view)
        
        # Add persistent view to bot
        bot.add_view(view)
        
        # Update event with message ID
        if db is not None:
            await db.events.update_one(
                {'guild_id': str(interaction.guild.id), 'event_name': event_name.lower()},
                {'$set': {'message_id': str(event_msg.id), 'message_channel': str(channel.id)}}
            )
        
        # Send confirmation to creator
        confirm_embed = discord.Embed(
            title="✅ Event Created Successfully",
            description=f"Your event has been posted!",
            color=BrandColors.SUCCESS,
            timestamp=datetime.now()
        )
        confirm_embed.add_field(name="🎊 Event Name", value=f"**{event_name}**", inline=True)
        confirm_embed.add_field(name="📋 Type", value=f"**{event_type}**", inline=True)
        confirm_embed.add_field(name="📢 Channel", value=f"{channel.mention}", inline=False)
        confirm_embed.add_field(name="⏰ Ends", value=f"<t:{int(end_time.timestamp())}:R>", inline=False)
        confirm_embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
        await interaction.followup.send(embed=confirm_embed)
        
        # Log action
        log_msg = f"🎊 [CREATE-EVENT] {interaction.user.mention} created event **{event_name}** ({event_type}) in {channel.mention}"
        await log_action(interaction.guild.id, "events", log_msg)
        
        # Log to global logging
        try:
            from advanced_logging import send_global_log
            global_log_msg = f"**🎊 Event Created**\n**Name:** {event_name}\n**Type:** {event_type}\n**User:** {interaction.user}\n**Channel:** {channel.name}\n**Duration:** {duration_value} {duration_unit}"
            await send_global_log("events", global_log_msg, interaction.guild)
        except:
            pass
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        await log_action(interaction.guild.id, "error-log", f"⚠️ [CREATE-EVENT ERROR] {interaction.user}: {str(e)}")

@bot.tree.command(name="announce-random-winner", description="🏆 Announce random winner from event")
@app_commands.describe(
    event_name="Name of the event",
    channel="Channel to announce winner",
    description="Winner announcement description",
    image_url="Image URL (optional)"
)
async def announce_random_winner(
    interaction: discord.Interaction,
    event_name: str,
    channel: discord.TextChannel,
    description: str,
    image_url: str = None
):
    """Announce random winner - Server owner, main moderator, junior moderator only"""
    
    if interaction.user.id != interaction.guild.owner_id:
        if not await has_permission(interaction, "main_moderator"):
            await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
            return
    
    await interaction.response.defer()
    
    try:
        event = await get_event(interaction.guild.id, event_name)
        
        if not event:
            await interaction.followup.send(f"❌ Event **{event_name}** not found!", ephemeral=True)
            return
        
        if not event.get('participants'):
            await interaction.followup.send("❌ No participants in this event!", ephemeral=True)
            return
        
        # Select random winner
        winner_id = random.choice(event['participants'])
        winner = interaction.guild.get_member(winner_id)
        
        if not winner:
            await interaction.followup.send("❌ Could not find winner member!", ephemeral=True)
            return
        
        # Create beautiful winner announcement
        embed = discord.Embed(
            title="🏆 WINNER ANNOUNCED! 🏆",
            description=description,
            color=BrandColors.PRIMARY,
            timestamp=datetime.now()
        )
        embed.add_field(name="━━━━━━━━━━━━━━━━━", value=f"{VisualElements.CIRCUIT_LINE}", inline=False)
        embed.add_field(name="🎉 WINNER", value=f">>> # {winner.mention}", inline=False)
        embed.add_field(name="━━━━━━━━━━━━━━━━━", value=f"{VisualElements.CIRCUIT_LINE}", inline=False)
        embed.add_field(name="📋 Event", value=f"**{event_name}**", inline=True)
        embed.add_field(name="👥 Participants", value=f"**{len(event['participants'])}**", inline=True)
        embed.add_field(name="🎯 Method", value="**Random Selection**", inline=True)
        embed.add_field(name="━━━━━━━━━━━━━━━━━", value=f"{VisualElements.CIRCUIT_LINE}", inline=False)
        
        if image_url:
            embed.set_image(url=image_url)
        
        embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
        
        # Send announcement
        await channel.send(embed=embed)
        
        # Update event
        if db is not None:
            await db.events.update_one(
                {'_id': event['_id']},
                {'$set': {'winner': winner_id, 'winner_type': 'random', 'announced': True}}
            )
        
        # Confirm to caller
        confirm_embed = discord.Embed(
            title="✅ Winner Announced",
            description=f"🏆 **{winner.mention}** has been announced as the winner!",
            color=BrandColors.SUCCESS,
            timestamp=datetime.now()
        )
        confirm_embed.add_field(name="📋 Event", value=f"**{event_name}**", inline=False)
        confirm_embed.add_field(name="📢 Announced in", value=f"{channel.mention}", inline=False)
        confirm_embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
        await interaction.followup.send(embed=confirm_embed)
        
        # Log action
        log_msg = f"🏆 [RANDOM-WINNER] {interaction.user.mention} announced {winner.mention} as winner of **{event_name}** in {channel.mention}"
        await log_action(interaction.guild.id, "events", log_msg)
        
        # Log to global
        try:
            from advanced_logging import send_global_log
            global_log_msg = f"**🏆 Random Winner Announced**\n**Event:** {event_name}\n**Winner:** {winner}\n**Participants:** {len(event['participants'])}\n**Channel:** {channel.name}"
            await send_global_log("events", global_log_msg, interaction.guild)
        except:
            pass
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        await log_action(interaction.guild.id, "error-log", f"⚠️ [RANDOM-WINNER ERROR] {interaction.user}: {str(e)}")

@bot.tree.command(name="announce-custom-winner", description="🎯 Announce custom winner")
@app_commands.describe(
    event_name="Name of the event",
    winner="Winner mention or name",
    channel="Channel to announce winner",
    description="Winner announcement description",
    image_url="Image URL (optional)"
)
async def announce_custom_winner(
    interaction: discord.Interaction,
    event_name: str,
    winner: discord.User,
    channel: discord.TextChannel,
    description: str,
    image_url: str = None
):
    """Announce custom winner - Server owner, main moderator, junior moderator only (HIDDEN FROM HELP)"""
    
    if interaction.user.id != interaction.guild.owner_id:
        if not await has_permission(interaction, "main_moderator"):
            await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
            return
    
    await interaction.response.defer()
    
    try:
        event = await get_event(interaction.guild.id, event_name)
        
        if not event:
            await interaction.followup.send(f"❌ Event **{event_name}** not found!", ephemeral=True)
            return
        
        # Create beautiful winner announcement
        embed = discord.Embed(
            title="🎯 WINNER ANNOUNCED! 🎯",
            description=description,
            color=BrandColors.PRIMARY,
            timestamp=datetime.now()
        )
        embed.add_field(name="━━━━━━━━━━━━━━━━━", value=f"{VisualElements.CIRCUIT_LINE}", inline=False)
        embed.add_field(name="🎉 WINNER", value=f">>> # {winner.mention}", inline=False)
        embed.add_field(name="━━━━━━━━━━━━━━━━━", value=f"{VisualElements.CIRCUIT_LINE}", inline=False)
        embed.add_field(name="📋 Event", value=f"**{event_name}**", inline=True)
        embed.add_field(name="🎯 Method", value="**Custom Selection**", inline=True)
        embed.add_field(name="━━━━━━━━━━━━━━━━━", value=f"{VisualElements.CIRCUIT_LINE}", inline=False)
        
        if image_url:
            embed.set_image(url=image_url)
        
        embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
        
        # Send announcement
        await channel.send(embed=embed)
        
        # Update event
        if db is not None:
            await db.events.update_one(
                {'_id': event['_id']},
                {'$set': {'winner': winner.id, 'winner_type': 'custom', 'announced': True}}
            )
        
        # Confirm to caller
        confirm_embed = discord.Embed(
            title="✅ Custom Winner Announced",
            description=f"🎯 **{winner.mention}** has been announced as the winner!",
            color=BrandColors.SUCCESS,
            timestamp=datetime.now()
        )
        confirm_embed.add_field(name="📋 Event", value=f"**{event_name}**", inline=False)
        confirm_embed.add_field(name="📢 Announced in", value=f"{channel.mention}", inline=False)
        confirm_embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
        await interaction.followup.send(embed=confirm_embed)
        
        # Log action
        log_msg = f"🎯 [CUSTOM-WINNER] {interaction.user.mention} announced {winner.mention} as custom winner of **{event_name}** in {channel.mention}"
        await log_action(interaction.guild.id, "events", log_msg)
        
        # Log to global
        try:
            from advanced_logging import send_global_log
            global_log_msg = f"**🎯 Custom Winner Announced**\n**Event:** {event_name}\n**Winner:** {winner}\n**Channel:** {channel.name}"
            await send_global_log("events", global_log_msg, interaction.guild)
        except:
            pass
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        await log_action(interaction.guild.id, "error-log", f"⚠️ [CUSTOM-WINNER ERROR] {interaction.user}: {str(e)}")

print("  ✓ /event-role command registered")
print("  ✓ /create-event command registered")
print("  ✓ /announce-random-winner command registered")
print("  ✓ /announce-custom-winner command registered (hidden from menu)")
print("✅ Event system loaded with button entry & MongoDB persistence")
