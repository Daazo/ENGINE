
import discord
from discord.ext import commands, tasks
from discord import app_commands
from main import bot, db
from brand_config import create_permission_denied_embed, create_owner_only_embed,  BOT_FOOTER, BrandColors, create_success_embed, create_error_embed, create_info_embed, create_command_embed, create_warning_embed
from main import has_permission, log_action
from datetime import datetime, timedelta
import asyncio

@bot.tree.command(name="mute", description="🔇 Mute user in voice channel")
@app_commands.describe(user="User to mute")
async def mute(interaction: discord.Interaction, user: discord.Member):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not user.voice:
        await interaction.response.send_message("❌ User is not in a voice channel!", ephemeral=True)
        return

    try:
        await user.edit(mute=True)

        embed = discord.Embed(
            title="🔇 User Muted",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.WARNING
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🔇 [MUTE] {user} muted by {interaction.user}")

        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔇 Mute**\n**User:** {user}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to mute this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="unmute", description="🔊 Unmute user in voice channel")
@app_commands.describe(user="User to unmute")
async def unmute(interaction: discord.Interaction, user: discord.Member):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not user.voice:
        await interaction.response.send_message("❌ User is not in a voice channel!", ephemeral=True)
        return

    try:
        await user.edit(mute=False)

        embed = discord.Embed(
            title="🔊 User Unmuted",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.SUCCESS
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🔊 [UNMUTE] {user} unmuted by {interaction.user}")

        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔊 Unmute**\n**User:** {user}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to unmute this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="movevc", description="Move user to different voice channel")
@app_commands.describe(user="User to move", channel="Voice channel to move to")
async def movevc(interaction: discord.Interaction, user: discord.Member, channel: discord.VoiceChannel):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not user.voice:
        await interaction.response.send_message("❌ User is not in a voice channel!", ephemeral=True)
        return

    try:
        await user.move_to(channel)

        embed = discord.Embed(
            title="🔀 User Moved",
            description=f"**User:** {user.mention}\n**Moved to:** {channel.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.SUCCESS
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🛡 [MOVE VC] {user} moved to {channel.name} by {interaction.user}")

        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔀 Move VC**\n**User:** {user}\n**Moved to:** {channel.mention}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to move this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="vckick", description="Kick user from voice channel")
@app_commands.describe(user="User to kick from voice")
async def vckick(interaction: discord.Interaction, user: discord.Member):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not user.voice:
        await interaction.response.send_message("❌ User is not in a voice channel!", ephemeral=True)
        return

    try:
        await user.move_to(None)

        embed = discord.Embed(
            title="👢 User Kicked from VC",
            description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.WARNING
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🛡 [VC KICK] {user} kicked from voice by {interaction.user}")

        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**👢 VC Kick**\n**User:** {user}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to disconnect this user!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="vclock", description="Lock current voice channel")
async def vclock(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not interaction.user.voice:
        await interaction.response.send_message("❌ You need to be in a voice channel to use this command!", ephemeral=True)
        return

    channel = interaction.user.voice.channel

    try:
        await channel.set_permissions(interaction.guild.default_role, connect=False)

        embed = discord.Embed(
            title="🔒 Voice Channel Locked",
            description=f"**Channel:** {channel.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.DANGER
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🛡 [VC LOCK] {channel.name} locked by {interaction.user}")

        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔒 VC Lock**\n**Channel:** {channel.mention}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to modify this channel!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="vcunlock", description="Unlock current voice channel")
async def vcunlock(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not interaction.user.voice:
        await interaction.response.send_message("❌ You need to be in a voice channel to use this command!", ephemeral=True)
        return

    channel = interaction.user.voice.channel

    try:
        await channel.set_permissions(interaction.guild.default_role, connect=None)

        embed = discord.Embed(
            title="🔓 Voice Channel Unlocked",
            description=f"**Channel:** {channel.mention}\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.SUCCESS
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🛡 [VC UNLOCK] {channel.name} unlocked by {interaction.user}")

        try:
            from advanced_logging import send_global_log
            await send_global_log("moderation", f"**🔓 VC Unlock**\n**Channel:** {channel.mention}\n**Moderator:** {interaction.user}", interaction.guild)
        except:
            pass

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to modify this channel!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="vclimit", description="Set voice channel user limit")
@app_commands.describe(limit="User limit (0-99, 0 = unlimited)")
async def vclimit(interaction: discord.Interaction, limit: int):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Junior Moderator"), ephemeral=True)
        return

    if not interaction.user.voice:
        await interaction.response.send_message("❌ You need to be in a voice channel to use this command!", ephemeral=True)
        return

    if limit < 0 or limit > 99:
        await interaction.response.send_message("❌ Limit must be between 0-99 (0 = unlimited)!", ephemeral=True)
        return

    channel = interaction.user.voice.channel

    try:
        await channel.edit(user_limit=limit)

        limit_text = "Unlimited" if limit == 0 else str(limit)
        embed = discord.Embed(
            title="🔢 Voice Channel Limit Set",
            description=f"**Channel:** {channel.mention}\n**Limit:** {limit_text} users\n**Moderator:** {interaction.user.mention}",
            color=BrandColors.INFO
        )
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "moderation", f"🛡 [VC LIMIT] {channel.name} limit set to {limit_text} by {interaction.user}")

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to modify this channel!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

# ═══════════════════════════════════════════════════════════════════════════
# CUSTOM VOICE CHANNEL SYSTEM - FULLY AUTOMATIC
# ═══════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="custom-vc", description="🔊 Setup dynamic custom voice channel system")
@app_commands.describe(category="Category to create custom VCs in")
async def custom_vc_setup(interaction: discord.Interaction, category: discord.CategoryChannel):
    if not await has_permission(interaction, "main_moderator"):
        await interaction.response.send_message(embed=create_permission_denied_embed("Main Moderator"), ephemeral=True)
        return
    
    try:
        hub_channel = await category.create_voice_channel(
            name="🔊 CUSTOM VC",
            reason=f"Custom VC hub created by {interaction.user}"
        )
        
        if db is not None:
            await db.custom_vc_hubs.update_one(
                {'guild_id': str(interaction.guild.id)},
                {'$set': {
                    'hub_channel_id': str(hub_channel.id),
                    'category_id': str(category.id),
                    'created_by': str(interaction.user.id),
                    'created_at': datetime.utcnow()
                }},
                upsert=True
            )
        
        embed = discord.Embed(
            title="⚡ **Custom VC System Setup Complete**",
            description=f"**🔊 Hub Channel:** {hub_channel.mention}\n**📁 Category:** {category.mention}\n**Status:** Active & Ready",
            color=BrandColors.PRIMARY
        )
        embed.add_field(
            name="🎯 How It Works",
            value="✓ Users join 🔊 CUSTOM VC\n✓ Bot automatically creates personal channel\n✓ User auto-moved to their VC\n✓ Auto-deletes after 5 min inactivity",
            inline=False
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)
        
        await log_action(interaction.guild.id, "custom_vc", f"⚡ [CUSTOM VC SETUP] System setup by {interaction.user}")
        
    except Exception as e:
        await interaction.response.send_message(embed=create_error_embed(f"Setup failed: {str(e)}"), ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    """Auto-create VC when user joins hub and track activity for all VCs"""
    try:
        if db is not None:
            # Handle joining a channel
            if after.channel is not None:
                # Check if user joined a hub channel
                hub_data = await db.custom_vc_hubs.find_one({'hub_channel_id': str(after.channel.id)})
                
                if hub_data and before.channel != after.channel:
                    # User just joined the hub - auto-create personal VC
                    category = after.channel.category
                    guild = after.channel.guild
                    
                    try:
                        # Create personal VC with user's name
                        vc_name = f"🔊 {member.display_name}"
                        new_vc = await category.create_voice_channel(
                            name=vc_name,
                            reason=f"Auto-created VC for {member}"
                        )
                        
                        # Move user to their new channel
                        await member.move_to(new_vc)
                        
                        # Store in database
                        await db.custom_vcs.insert_one({
                            'guild_id': str(guild.id),
                            'channel_id': str(new_vc.id),
                            'creator_id': str(member.id),
                            'created_at': datetime.utcnow(),
                            'last_activity': datetime.utcnow()
                        })
                        
                        await log_action(guild.id, "custom_vc", f"🔊 [AUTO VC] Created for {member}: {vc_name}")
                        
                        try:
                            from advanced_logging import send_global_log
                            await send_global_log("custom_vc", f"**🔊 Auto VC Created**\n**User:** {member}\n**Channel:** {new_vc.mention}", guild)
                        except:
                            pass
                        
                    except Exception as e:
                        print(f"Error creating auto VC: {e}")
                
                # Track activity for joining any custom VC
                custom_vc = await db.custom_vcs.find_one({'channel_id': str(after.channel.id)})
                if custom_vc:
                    await db.custom_vcs.update_one(
                        {'channel_id': str(after.channel.id)},
                        {'$set': {'last_activity': datetime.utcnow()}}
                    )
            
            # Handle leaving a channel - update activity when users leave custom VCs
            if before.channel is not None:
                custom_vc = await db.custom_vcs.find_one({'channel_id': str(before.channel.id)})
                if custom_vc:
                    # Update last_activity when member leaves
                    await db.custom_vcs.update_one(
                        {'channel_id': str(before.channel.id)},
                        {'$set': {'last_activity': datetime.utcnow()}}
                    )
    
    except Exception as e:
        print(f"Error in on_voice_state_update: {e}")

@tasks.loop(seconds=30)
async def cleanup_empty_custom_vcs():
    """Auto-delete empty custom VCs after 5 minutes"""
    if db is None:
        return
    
    try:
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)
        
        # Find all VCs that have been inactive for 5+ minutes
        expired_vcs = await db.custom_vcs.find({
            'last_activity': {'$lt': cutoff_time}
        }).to_list(length=None)
        
        if expired_vcs:
            print(f"[CLEANUP] Found {len(expired_vcs)} expired VCs to check...")
        
        for vc_data in expired_vcs:
            try:
                guild_id = int(vc_data['guild_id'])
                channel_id = int(vc_data['channel_id'])
                vc_name = vc_data.get('channel_name', 'Unknown')
                
                guild = bot.get_guild(guild_id)
                if not guild:
                    await db.custom_vcs.delete_one({'_id': vc_data['_id']})
                    continue
                
                channel = guild.get_channel(channel_id)
                
                # Check if channel exists and is empty
                if channel:
                    member_count = len(channel.members)
                    print(f"[CLEANUP] Checking {channel.name} (ID: {channel_id}): {member_count} members, last activity: {vc_data.get('last_activity')}")
                    
                    if member_count == 0:
                        try:
                            await channel.delete(reason="Auto-cleanup - 5 min inactivity")
                            print(f"[CLEANUP] ✅ Deleted {channel.name}")
                            await log_action(guild_id, "custom_vc", f"🗑️ [VC DELETED] {channel.name} - auto cleanup")
                            
                            try:
                                from advanced_logging import send_global_log
                                await send_global_log("custom_vc", f"**🗑️ Auto VC Deleted**\n**Channel:** {channel.name}\n**Reason:** Inactivity", guild)
                            except:
                                pass
                        except Exception as e:
                            print(f"[CLEANUP] ❌ Failed to delete {channel.name}: {e}")
                    else:
                        print(f"[CLEANUP] ⏭️ Skipped {channel.name} - still has {member_count} members")
                else:
                    print(f"[CLEANUP] Channel {channel_id} not found in guild {guild_id}")
                
                # Remove from database
                await db.custom_vcs.delete_one({'_id': vc_data['_id']})
            
            except Exception as e:
                print(f"[CLEANUP] Error processing VC {vc_data.get('channel_id')}: {e}")
                try:
                    await db.custom_vcs.delete_one({'_id': vc_data['_id']})
                except:
                    pass
    
    except Exception as e:
        print(f"[CLEANUP] Error in cleanup_empty_custom_vcs: {e}")

def start_custom_vc_cleanup():
    """Start the custom VC cleanup task"""
    try:
        if not cleanup_empty_custom_vcs.is_running():
            cleanup_empty_custom_vcs.start()
            print("✅ Custom VC cleanup task started (30s interval)")
        else:
            print("⚠️ Custom VC cleanup task already running")
    except Exception as e:
        print(f"⚠️ Custom VC cleanup task failed to start: {e}")
