import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from main import bot, has_permission, log_action
from brand_config import BOT_FOOTER, BrandColors, VisualElements, create_success_embed, create_error_embed, create_info_embed, create_command_embed, create_warning_embed
from datetime import datetime

print("✅ Role commands module loading...")

@bot.tree.command(name="listrole", description="📋 Show all users in a role with beautiful embed")
@app_commands.describe(role="Role to list members from")
async def listrole(interaction: discord.Interaction, role: discord.Role):
    """List all members in a role"""
    
    # Check permission: junior moderator, main moderator, or server owner
    if interaction.user.id != interaction.guild.owner_id:
        if not await has_permission(interaction, "junior_moderator"):
            await interaction.response.send_message("❌ You need Junior Moderator or higher permissions to use this command!", ephemeral=True)
            return
    
    await interaction.response.defer()
    
    try:
        # Get members with this role
        members = [m for m in interaction.guild.members if role in m.roles]
        
        # Create paginated embeds if there are many members
        if not members:
            embed = discord.Embed(
                title=f"📋 Role: {role.name}",
                description="No members found with this role",
                color=BrandColors.INFO,
                timestamp=datetime.now()
            )
            embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
            await interaction.followup.send(embed=embed)
        else:
            # Split members into chunks of 25 per embed
            chunk_size = 25
            chunks = [members[i:i + chunk_size] for i in range(0, len(members), chunk_size)]
            
            for page_num, chunk in enumerate(chunks, 1):
                embed = discord.Embed(
                    title=f"📋 Role: {role.name}",
                    description=f"**Total Members:** {len(members)}\n**Page:** {page_num}/{len(chunks)}\n\n{VisualElements.CIRCUIT_LINE}",
                    color=BrandColors.PRIMARY,
                    timestamp=datetime.now()
                )
                
                member_list = []
                for idx, member in enumerate(chunk, 1):
                    status = "🟣 Online" if member.status == discord.Status.online else "⚪ Offline"
                    member_list.append(f"**{idx}.** {member.mention} • {status}")
                
                embed.add_field(
                    name=f"👥 Members ({len(chunk)})",
                    value="\n".join(member_list),
                    inline=False
                )
                
                embed.set_footer(text=f"{BOT_FOOTER} • Role ID: {role.id}", icon_url=interaction.client.user.display_avatar.url)
                await interaction.followup.send(embed=embed)
        
        # Log action
        await log_action(interaction.guild.id, "general", f"📋 [LISTROLE] {interaction.user.mention} listed {len(members)} members in role {role.mention}")
        
        # Log to global logging
        try:
            from advanced_logging import send_global_log
            await send_global_log("general", f"**📋 List Role**\n**Role:** {role.name}\n**Members:** {len(members)}\n**User:** {interaction.user}", interaction.guild)
        except:
            pass
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        await log_action(interaction.guild.id, "error-log", f"⚠️ [LISTROLE ERROR] {interaction.user}: {str(e)}")

print("  ✓ /listrole command registered")

@bot.tree.command(name="dm-role", description="📧 Send DM to all users in a role")
@app_commands.describe(role="Role to send DM to", message="Message to send", image_url="Optional image URL (jpg, png, gif)")
async def dm_role(interaction: discord.Interaction, role: discord.Role, message: str, image_url: str = None):
    """Send DM to all members in a role"""
    
    # Check permission: main moderator or server owner only
    if interaction.user.id != interaction.guild.owner_id:
        if not await has_permission(interaction, "main_moderator"):
            await interaction.response.send_message("❌ You need Main Moderator or higher permissions to use this command!", ephemeral=True)
            return
    
    await interaction.response.defer()
    
    try:
        # Get members with this role
        members = [m for m in interaction.guild.members if role in m.roles and not m.bot]
        
        if not members:
            await interaction.followup.send("❌ No members found in this role!", ephemeral=True)
            return
        
        # Create DM embed
        dm_embed = discord.Embed(
            title=f"📧 Message from {interaction.guild.name}",
            description=message,
            color=BrandColors.PRIMARY,
            timestamp=datetime.now()
        )
        
        # Add image if URL provided (jpg, png, gif only)
        has_image = False
        if image_url:
            try:
                dm_embed.set_image(url=image_url)
                has_image = True
            except:
                pass
        
        dm_embed.set_footer(text=f"{BOT_FOOTER} • {role.name}", icon_url=interaction.client.user.display_avatar.url)
        dm_embed.add_field(
            name="Sent by",
            value=f"{interaction.user.mention}",
            inline=True
        )
        
        # Send DMs
        sent_count = 0
        failed_count = 0
        
        for member in members:
            try:
                await member.send(embed=dm_embed)
                sent_count += 1
            except:
                failed_count += 1
        
        # Send confirmation
        result_embed = discord.Embed(
            title="⚡ DM TRANSMISSION COMPLETE",
            description=f"Messages have been delivered via quantum channels.",
            color=BrandColors.PRIMARY,
            timestamp=datetime.now()
        )
        result_embed.add_field(name="━━━━━━━━━━━━━━━━━━━━━━━━━", value=f"{VisualElements.CIRCUIT_LINE}", inline=False)
        result_embed.add_field(name="🎯 Target Role", value=f"{role.mention}", inline=True)
        result_embed.add_field(name="✓ Delivered", value=f"**{sent_count}/{len(members)}**", inline=True)
        result_embed.add_field(name="✗ Failed", value=f"**{failed_count}**", inline=True)
        result_embed.add_field(
            name="📝 Message Preview",
            value=message[:100] + "..." if len(message) > 100 else message,
            inline=False
        )
        result_embed.add_field(name="━━━━━━━━━━━━━━━━━━━━━━━━━", value=f"{VisualElements.CIRCUIT_LINE}", inline=False)
        result_embed.set_footer(text=BOT_FOOTER, icon_url=interaction.client.user.display_avatar.url)
        await interaction.followup.send(embed=result_embed)
        
        # Log action
        log_msg = f"📧 [DM-ROLE] {interaction.user.mention} sent DM to {sent_count} members in {role.mention}"
        if has_image:
            log_msg += f" (with image)"
        await log_action(interaction.guild.id, "communication", log_msg)
        
        # Log to global logging
        try:
            from advanced_logging import send_global_log
            image_info = 'Yes' if has_image else 'No'
            global_log_msg = f"**📧 DM Sent to Role**\n**Role:** {role.name}\n**Members Sent:** {sent_count}/{len(members)}\n**User:** {interaction.user}\n**Image:** {image_info}"
            await send_global_log("communication", global_log_msg, interaction.guild)
        except:
            pass
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        await log_action(interaction.guild.id, "error-log", f"⚠️ [DM-ROLE ERROR] {interaction.user}: {str(e)}")

print("  ✓ /dm-role command registered")

@bot.tree.command(name="send-image", description="🖼️ Send up to 10 images to the channel")
@app_commands.describe(
    image1="First image URL (jpg, png, gif)",
    image2="Second image URL (optional)",
    image3="Third image URL (optional)",
    image4="Fourth image URL (optional)",
    image5="Fifth image URL (optional)",
    image6="Sixth image URL (optional)",
    image7="Seventh image URL (optional)",
    image8="Eighth image URL (optional)",
    image9="Ninth image URL (optional)",
    image10="Tenth image URL (optional)"
)
async def send_image(
    interaction: discord.Interaction,
    image1: str,
    image2: str = None,
    image3: str = None,
    image4: str = None,
    image5: str = None,
    image6: str = None,
    image7: str = None,
    image8: str = None,
    image9: str = None,
    image10: str = None
):
    """Send up to 10 images to the channel"""
    
    # Check permission: junior moderator, main moderator, or server owner
    if interaction.user.id != interaction.guild.owner_id:
        if not await has_permission(interaction, "junior_moderator"):
            await interaction.response.send_message("❌ You need Junior Moderator or higher permissions to use this command!", ephemeral=True)
            return
    
    await interaction.response.defer()
    
    try:
        # Collect all image URLs
        image_urls = [img for img in [image1, image2, image3, image4, image5, image6, image7, image8, image9, image10] if img]
        
        if not image_urls:
            await interaction.followup.send("❌ At least one image URL is required!", ephemeral=True)
            return
        
        # Send each image directly as a simple embed
        for idx, img_url in enumerate(image_urls, 1):
            embed = discord.Embed(
                description=f"🖼️ **Image {idx}/{len(image_urls)}**",
                color=BrandColors.PRIMARY,
                timestamp=datetime.now()
            )
            embed.set_image(url=img_url)
            embed.set_footer(text=f"{BOT_FOOTER} • Sent by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed)
        
        # Log action
        log_msg = f"🖼️ [SEND-IMAGE] {interaction.user.mention} sent {len(image_urls)} image(s) to {interaction.channel.mention}"
        await log_action(interaction.guild.id, "general", log_msg)
        
        # Log to global logging
        try:
            from advanced_logging import send_global_log
            global_log_msg = f"**🖼️ Images Sent**\n**User:** {interaction.user}\n**Channel:** {interaction.channel.name}\n**Image Count:** {len(image_urls)}"
            await send_global_log("general", global_log_msg, interaction.guild)
        except:
            pass
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        await log_action(interaction.guild.id, "error-log", f"⚠️ [SEND-IMAGE ERROR] {interaction.user}: {str(e)}")

print("  ✓ /send-image command registered")
print("✅ All role commands loaded successfully")
