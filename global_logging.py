"""Global logging system for RXT ENGINE bot - tracks activity across all servers"""

import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime
from brand_config import BOT_FOOTER, BrandColors


async def log_global_activity(activity_type, guild_id, user_id, description):
    """Log global activity to the system-log channel"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        # Import bot from main to avoid circular imports
        from main import bot
        
        # Get global category
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        # Find system-log channel
        system_channel = discord.utils.get(global_category.text_channels, name="system-log")
        if not system_channel:
            return
        
        embed = discord.Embed(
            title=f"🌍 **{activity_type}**",
            description=description,
            color=BrandColors.INFO,
            timestamp=datetime.now()
        )
        
        # Add server info if available
        try:
            guild = bot.get_guild(int(guild_id))
            if guild:
                embed.add_field(name="🏰 Server", value=f"{guild.name}\n`{guild.id}`", inline=True)
        except:
            pass
        
        # Add user info
        embed.add_field(name="👤 User", value=f"`{user_id}`", inline=True)
        
        embed.set_footer(text=f"{BOT_FOOTER} • Global Activity", icon_url=bot.user.display_avatar.url)
        
        try:
            await system_channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending global activity log: {e}")
            
    except Exception as e:
        print(f"Global activity logging error: {e}")


async def log_per_server_activity(guild_id, activity_type, description):
    """Create per-server log channels in global category"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        from main import bot, db
        
        # Get global category
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return
        
        # Create per-server channel if it doesn't exist
        channel_name = f"server-{guild.name[:20]}".lower().replace(" ", "-")
        
        server_channel = discord.utils.get(global_category.text_channels, name=channel_name)
        if not server_channel:
            server_channel = await global_category.create_text_channel(
                name=channel_name,
                topic=f"Global logs for {guild.name} (ID: {guild_id})"
            )
        
        # Send log
        embed = discord.Embed(
            title=f"📋 **{activity_type}**",
            description=description,
            color=BrandColors.INFO,
            timestamp=datetime.now()
        )
        embed.add_field(name="🏰 Server", value=f"{guild.name}\n`{guild_id}`", inline=False)
        embed.set_footer(text=f"{BOT_FOOTER} • Server Activity", icon_url=bot.user.display_avatar.url)
        
        try:
            await server_channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending per-server log: {e}")
            
    except Exception as e:
        print(f"Per-server logging error: {e}")


async def on_bot_dm_send(recipient, message_content):
    """Log when bot sends DMs to users"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        from main import bot
        
        # Get global category
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        # Find dm-sent channel
        dm_channel = discord.utils.get(global_category.text_channels, name="dm-sent")
        if not dm_channel:
            return
        
        embed = discord.Embed(
            title="💬 **DM Sent**",
            description=f"```{message_content[:500]}```",
            color=BrandColors.SUCCESS,
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 Recipient", value=f"{recipient.mention}\n`{recipient.id}`", inline=False)
        embed.set_footer(text=f"{BOT_FOOTER} • DM Sent", icon_url=bot.user.display_avatar.url)
        
        try:
            await dm_channel.send(embed=embed)
        except Exception as e:
            print(f"Error logging DM sent: {e}")
            
    except Exception as e:
        print(f"DM send logging error: {e}")


async def log_dm_sent(recipient_id, message_content):
    """Log DM sent to a user (alternative function name)"""
    try:
        from main import bot
        
        recipient = None
        try:
            recipient = await bot.fetch_user(int(recipient_id))
        except:
            pass
        
        if recipient:
            await on_bot_dm_send(recipient, message_content)
    except Exception as e:
        print(f"DM logging error: {e}")


async def log_to_global(log_type, message, guild=None):
    """Generic function to log to global system"""
    try:
        global_category_id = os.getenv('GLOBAL_LOG_CATEGORY_ID')
        if not global_category_id:
            return
        
        from main import bot
        
        # Get global category
        global_category = bot.get_channel(int(global_category_id))
        if not global_category or not isinstance(global_category, discord.CategoryChannel):
            return
        
        # Map log type to channel
        channel_mapping = {
            "live-console": "live-console",
            "dm-received": "dm-received",
            "dm-sent": "dm-sent",
            "command-errors": "command-errors",
            "system-log": "system-log",
        }
        
        channel_name = channel_mapping.get(log_type.lower(), "system-log")
        channel = discord.utils.get(global_category.text_channels, name=channel_name)
        
        if channel:
            embed = discord.Embed(
                description=f"```{message[:500]}```",
                color=BrandColors.INFO,
                timestamp=datetime.now()
            )
            
            if guild:
                embed.add_field(name="🏰 Server", value=f"{guild.name}\n`{guild.id}`", inline=False)
            
            embed.set_footer(text=f"{BOT_FOOTER} • {log_type}", icon_url=bot.user.display_avatar.url)
            
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"Error sending {log_type} log: {e}")
    except Exception as e:
        print(f"Global logging error: {e}")
