import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import asyncio
import re

from brand_config import BrandColors, BOT_FOOTER, VisualElements

bot = None
db = None
has_permission = None
log_action = None
create_error_embed = None
create_permission_denied_embed = None
_setup_complete = False

YOUTUBE_RSS_BASE = "https://www.youtube.com/feeds/videos.xml?channel_id="
MAX_CHANNELS_PER_SERVER = 10
POLL_INTERVAL_MINUTES = 5

yt_channel_cache = {}

def setup(bot_instance, db_instance, permission_func, log_func, error_embed_func, permission_denied_func):
    """Setup the YouTube notifier module"""
    global bot, db, has_permission, log_action, create_error_embed, create_permission_denied_embed, _setup_complete
    
    if _setup_complete:
        return
    
    bot = bot_instance
    db = db_instance
    has_permission = permission_func
    log_action = log_func
    create_error_embed = error_embed_func
    create_permission_denied_embed = permission_denied_func
    
    bot.tree.command(name="yt", description="🔔 YouTube Notifier - Add, remove, or list YouTube channels")(yt_command)
    
    _setup_complete = True
    print("✅ YouTube Notifier system loaded")


async def extract_channel_id(input_str: str) -> str:
    """Extract YouTube channel ID from URL or direct ID"""
    input_str = input_str.strip()
    
    if re.match(r'^UC[\w-]{22}$', input_str):
        return input_str
    
    patterns = [
        r'youtube\.com/channel/(UC[\w-]{22})',
        r'youtube\.com/@[\w-]+',
        r'youtube\.com/c/[\w-]+',
        r'youtube\.com/user/[\w-]+'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, input_str)
        if match:
            if 'channel/UC' in input_str:
                return match.group(1)
            else:
                return await resolve_channel_id(input_str)
    
    return None


async def resolve_channel_id(url: str) -> str:
    """Resolve channel ID from YouTube URL by fetching page"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    html = await response.text()
                    match = re.search(r'"channelId":"(UC[\w-]{22})"', html)
                    if match:
                        return match.group(1)
                    match = re.search(r'channel_id=(UC[\w-]{22})', html)
                    if match:
                        return match.group(1)
    except Exception as e:
        print(f"❌ [YT] Error resolving channel ID: {e}")
    return None


async def fetch_rss_feed(channel_id: str) -> dict:
    """Fetch and parse YouTube RSS feed"""
    url = f"{YOUTUBE_RSS_BASE}{channel_id}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    return None
                
                xml_content = await response.text()
                root = ET.fromstring(xml_content)
                
                ns = {
                    'atom': 'http://www.w3.org/2005/Atom',
                    'yt': 'http://www.youtube.com/xml/schemas/2015',
                    'media': 'http://search.yahoo.com/mrss/'
                }
                
                channel_name = root.find('atom:title', ns)
                channel_name = channel_name.text if channel_name is not None else "Unknown Channel"
                
                entries = root.findall('atom:entry', ns)
                videos = []
                
                for entry in entries[:5]:
                    video_id = entry.find('yt:videoId', ns)
                    title = entry.find('atom:title', ns)
                    published = entry.find('atom:published', ns)
                    author = entry.find('atom:author/atom:name', ns)
                    
                    media_group = entry.find('media:group', ns)
                    thumbnail = None
                    if media_group is not None:
                        media_thumb = media_group.find('media:thumbnail', ns)
                        if media_thumb is not None:
                            thumbnail = media_thumb.get('url')
                    
                    if video_id is not None:
                        videos.append({
                            'video_id': video_id.text,
                            'title': title.text if title is not None else "Untitled",
                            'published': published.text if published is not None else None,
                            'author': author.text if author is not None else channel_name,
                            'thumbnail': thumbnail or f"https://i.ytimg.com/vi/{video_id.text}/maxresdefault.jpg",
                            'url': f"https://www.youtube.com/watch?v={video_id.text}"
                        })
                
                return {
                    'channel_name': channel_name,
                    'channel_id': channel_id,
                    'videos': videos
                }
    except Exception as e:
        print(f"❌ [YT] Error fetching RSS for {channel_id}: {e}")
        return None


async def send_video_notification(guild_id: str, discord_channel_id: str, role_id: str, video: dict, yt_channel_name: str):
    """Send video notification to Discord channel"""
    try:
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return False
        
        channel = guild.get_channel(int(discord_channel_id))
        if not channel:
            return False
        
        embed = discord.Embed(
            title=f"⚡ {video['title']}",
            url=video['url'],
            description=f"{VisualElements.CIRCUIT_LINE}\n**◆ Channel:** {yt_channel_name}\n**◆ Uploaded:** <t:{int(datetime.fromisoformat(video['published'].replace('Z', '+00:00')).timestamp())}:R>\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.DANGER
        )
        embed.set_image(url=video['thumbnail'])
        embed.set_footer(text=f"{BOT_FOOTER} • YouTube Notifier")
        embed.set_author(name=f"🔔 New Video from {yt_channel_name}", icon_url="https://www.youtube.com/s/desktop/f506bd45/img/favicon_144x144.png")
        
        content = ""
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                content = f"{role.mention} "
        
        content += f"**{yt_channel_name}** just uploaded a new video!"
        
        await channel.send(content=content, embed=embed)
        return True
    except Exception as e:
        print(f"❌ [YT] Error sending notification: {e}")
        return False


class YTChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, yt_channel_id: str, yt_channel_name: str):
        super().__init__(
            placeholder="Select notification channel...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        self.yt_channel_id = yt_channel_id
        self.yt_channel_name = yt_channel_name
    
    async def callback(self, interaction: discord.Interaction):
        selected_channel = self.values[0]
        
        view = YTRoleSelectView(
            yt_channel_id=self.yt_channel_id,
            yt_channel_name=self.yt_channel_name,
            discord_channel=selected_channel
        )
        
        embed = discord.Embed(
            title="⚡ STEP 3: Role Mention (Optional)",
            description=f"{VisualElements.CIRCUIT_LINE}\n**YouTube Channel:** {self.yt_channel_name}\n**Notification Channel:** {selected_channel.mention}\n\nSelect a role to mention when new videos are posted, or click **Skip** to continue without mentions.\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PRIMARY
        )
        embed.set_footer(text=BOT_FOOTER)
        
        await interaction.response.edit_message(embed=embed, view=view)


class YTChannelSelectView(discord.ui.View):
    def __init__(self, yt_channel_id: str, yt_channel_name: str):
        super().__init__(timeout=120)
        self.add_item(YTChannelSelect(yt_channel_id, yt_channel_name))
    
    async def on_timeout(self):
        pass


class YTRoleSelect(discord.ui.RoleSelect):
    def __init__(self, yt_channel_id: str, yt_channel_name: str, discord_channel: discord.TextChannel):
        super().__init__(
            placeholder="Select a role to mention...",
            min_values=1,
            max_values=1
        )
        self.yt_channel_id = yt_channel_id
        self.yt_channel_name = yt_channel_name
        self.discord_channel = discord_channel
    
    async def callback(self, interaction: discord.Interaction):
        selected_role = self.values[0]
        await show_confirmation(
            interaction,
            self.yt_channel_id,
            self.yt_channel_name,
            self.discord_channel,
            selected_role
        )


class YTRoleSelectView(discord.ui.View):
    def __init__(self, yt_channel_id: str, yt_channel_name: str, discord_channel: discord.TextChannel):
        super().__init__(timeout=120)
        self.yt_channel_id = yt_channel_id
        self.yt_channel_name = yt_channel_name
        self.discord_channel = discord_channel
        self.add_item(YTRoleSelect(yt_channel_id, yt_channel_name, discord_channel))
    
    @discord.ui.button(label="Skip Role Mention", style=discord.ButtonStyle.secondary, emoji="◆", row=1)
    async def skip_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_confirmation(
            interaction,
            self.yt_channel_id,
            self.yt_channel_name,
            self.discord_channel,
            None
        )


async def show_confirmation(interaction: discord.Interaction, yt_channel_id: str, yt_channel_name: str, discord_channel: discord.TextChannel, role: discord.Role):
    """Show confirmation before saving"""
    role_text = role.mention if role else "None"
    
    embed = discord.Embed(
        title="⚡ CONFIRM SETUP",
        description=f"{VisualElements.CIRCUIT_LINE}\n**◆ YouTube Channel:** {yt_channel_name}\n**◆ Channel ID:** `{yt_channel_id}`\n**◆ Notification Channel:** {discord_channel.mention}\n**◆ Role Mention:** {role_text}\n**◆ Check Interval:** Every 5 minutes\n{VisualElements.CIRCUIT_LINE}",
        color=BrandColors.SUCCESS
    )
    embed.set_footer(text=BOT_FOOTER)
    
    view = YTConfirmView(yt_channel_id, yt_channel_name, discord_channel, role)
    await interaction.response.edit_message(embed=embed, view=view)


class YTConfirmView(discord.ui.View):
    def __init__(self, yt_channel_id: str, yt_channel_name: str, discord_channel: discord.TextChannel, role: discord.Role):
        super().__init__(timeout=120)
        self.yt_channel_id = yt_channel_id
        self.yt_channel_name = yt_channel_name
        self.discord_channel = discord_channel
        self.role = role
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✓")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await save_yt_subscription(
            interaction,
            self.yt_channel_id,
            self.yt_channel_name,
            self.discord_channel,
            self.role
        )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✗")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✗ SETUP CANCELLED",
            description=f"YouTube notifier setup has been cancelled.\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.DANGER
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.edit_message(embed=embed, view=None)


async def save_yt_subscription(interaction: discord.Interaction, yt_channel_id: str, yt_channel_name: str, discord_channel: discord.TextChannel, role: discord.Role):
    """Save YouTube subscription to database"""
    guild_id = str(interaction.guild.id)
    
    existing = await db.youtube_channels.count_documents({'guild_id': guild_id})
    if existing >= MAX_CHANNELS_PER_SERVER:
        embed = discord.Embed(
            title="✗ LIMIT REACHED",
            description=f"You can only track up to **{MAX_CHANNELS_PER_SERVER}** YouTube channels per server.\n\nUse `/yt remove` to remove existing channels.\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.DANGER
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.edit_message(embed=embed, view=None)
        return
    
    already_exists = await db.youtube_channels.find_one({
        'guild_id': guild_id,
        'yt_channel_id': yt_channel_id
    })
    
    if already_exists:
        embed = discord.Embed(
            title="✗ ALREADY TRACKING",
            description=f"This YouTube channel is already being tracked in this server.\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.DANGER
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.edit_message(embed=embed, view=None)
        return
    
    feed = await fetch_rss_feed(yt_channel_id)
    last_video_id = None
    if feed and feed['videos']:
        last_video_id = feed['videos'][0]['video_id']
    
    await db.youtube_channels.insert_one({
        'guild_id': guild_id,
        'yt_channel_id': yt_channel_id,
        'yt_channel_name': yt_channel_name,
        'discord_channel_id': str(discord_channel.id),
        'role_id': str(role.id) if role else None,
        'last_video_id': last_video_id,
        'added_by': str(interaction.user.id),
        'added_at': datetime.now(timezone.utc)
    })
    
    embed = discord.Embed(
        title="✓ YOUTUBE NOTIFIER ADDED",
        description=f"{VisualElements.CIRCUIT_LINE}\n**◆ YouTube Channel:** {yt_channel_name}\n**◆ Notification Channel:** {discord_channel.mention}\n**◆ Role Mention:** {role.mention if role else 'None'}\n**◆ Status:** Active\n{VisualElements.CIRCUIT_LINE}\n\nYou will receive notifications when new videos are uploaded!",
        color=BrandColors.SUCCESS
    )
    embed.set_footer(text=BOT_FOOTER)
    await interaction.response.edit_message(embed=embed, view=None)
    
    await log_action(
        interaction.guild.id,
        "youtube",
        f"🔔 [YOUTUBE] {interaction.user} added YouTube notifier for **{yt_channel_name}** → {discord_channel.mention}"
    )
    
    try:
        from advanced_logging import send_global_log
        await send_global_log(
            "youtube",
            f"**🔔 YouTube Notifier Added**\n**Server:** {interaction.guild.name}\n**YouTube:** {yt_channel_name}\n**Channel:** {discord_channel.mention}\n**Added by:** {interaction.user.mention}",
            interaction.guild
        )
    except:
        pass


class YTRemoveSelect(discord.ui.Select):
    def __init__(self, channels: list):
        options = []
        for ch in channels[:25]:
            options.append(discord.SelectOption(
                label=ch['yt_channel_name'][:100],
                value=ch['yt_channel_id'],
                description=f"ID: {ch['yt_channel_id'][:20]}..."
            ))
        super().__init__(placeholder="Select channel to remove...", options=options)
        self.channels = channels
    
    async def callback(self, interaction: discord.Interaction):
        selected_id = self.values[0]
        channel_data = next((c for c in self.channels if c['yt_channel_id'] == selected_id), None)
        
        if channel_data:
            await db.youtube_channels.delete_one({
                'guild_id': str(interaction.guild.id),
                'yt_channel_id': selected_id
            })
            
            embed = discord.Embed(
                title="✓ YOUTUBE NOTIFIER REMOVED",
                description=f"Removed **{channel_data['yt_channel_name']}** from YouTube notifications.\n{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.SUCCESS
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.edit_message(embed=embed, view=None)
            
            await log_action(
                interaction.guild.id,
                "youtube",
                f"🔔 [YOUTUBE] {interaction.user} removed YouTube notifier for **{channel_data['yt_channel_name']}**"
            )
            
            try:
                from advanced_logging import send_global_log
                await send_global_log(
                    "youtube",
                    f"**🔔 YouTube Notifier Removed**\n**Server:** {interaction.guild.name}\n**YouTube:** {channel_data['yt_channel_name']}\n**Removed by:** {interaction.user.mention}",
                    interaction.guild
                )
            except:
                pass


class YTRemoveView(discord.ui.View):
    def __init__(self, channels: list):
        super().__init__(timeout=120)
        self.add_item(YTRemoveSelect(channels))


@app_commands.describe(
    action="Action to perform: add, remove, or list",
    channel="YouTube Channel ID or URL (for add action)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="remove", value="remove"),
    app_commands.Choice(name="list", value="list")
])
async def yt_command(interaction: discord.Interaction, action: str, channel: str = None):
    """YouTube Notifier - Add, remove, or list YouTube channels"""
    
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message(
            embed=create_permission_denied_embed("Junior Moderator"),
            ephemeral=True
        )
        return
    
    if action == "add":
        if not channel:
            embed = discord.Embed(
                title="✗ MISSING CHANNEL",
                description=f"Please provide a YouTube channel ID or URL.\n\n**Usage:** `/yt add channel:UC...` or `/yt add channel:https://youtube.com/...`\n{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        channel_id = await extract_channel_id(channel)
        
        if not channel_id:
            embed = discord.Embed(
                title="✗ INVALID CHANNEL",
                description=f"Could not find a valid YouTube channel ID.\n\n**Accepted formats:**\n◆ Channel ID: `UCxxxx...`\n◆ Channel URL: `youtube.com/channel/UCxxxx...`\n◆ Handle URL: `youtube.com/@username`\n{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        feed = await fetch_rss_feed(channel_id)
        
        if not feed:
            embed = discord.Embed(
                title="✗ RSS FEED UNAVAILABLE",
                description=f"Could not access the YouTube RSS feed for this channel.\n\nThe channel may not exist or may have no public videos.\n{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.DANGER
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚡ STEP 2: Select Notification Channel",
            description=f"{VisualElements.CIRCUIT_LINE}\n**YouTube Channel Found:** {feed['channel_name']}\n**Channel ID:** `{channel_id}`\n\nSelect the Discord channel where notifications will be sent.\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PRIMARY
        )
        embed.set_footer(text=BOT_FOOTER)
        
        view = YTChannelSelectView(channel_id, feed['channel_name'])
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    elif action == "remove":
        channels = await db.youtube_channels.find({'guild_id': str(interaction.guild.id)}).to_list(length=25)
        
        if not channels:
            embed = discord.Embed(
                title="◆ NO CHANNELS FOUND",
                description=f"No YouTube channels are being tracked in this server.\n\nUse `/yt add` to add a YouTube channel.\n{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.PRIMARY
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚡ REMOVE YOUTUBE NOTIFIER",
            description=f"Select a YouTube channel to remove from notifications.\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PRIMARY
        )
        embed.set_footer(text=BOT_FOOTER)
        
        view = YTRemoveView(channels)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    elif action == "list":
        channels = await db.youtube_channels.find({'guild_id': str(interaction.guild.id)}).to_list(length=25)
        
        if not channels:
            embed = discord.Embed(
                title="◆ NO CHANNELS FOUND",
                description=f"No YouTube channels are being tracked in this server.\n\nUse `/yt add` to add a YouTube channel.\n{VisualElements.CIRCUIT_LINE}",
                color=BrandColors.PRIMARY
            )
            embed.set_footer(text=BOT_FOOTER)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        channel_list = ""
        for i, ch in enumerate(channels, 1):
            discord_ch = interaction.guild.get_channel(int(ch['discord_channel_id']))
            channel_mention = discord_ch.mention if discord_ch else "Unknown"
            role_text = f"<@&{ch['role_id']}>" if ch.get('role_id') else "None"
            channel_list += f"**{i}.** {ch['yt_channel_name']}\n   ◆ Notify: {channel_mention} | Ping: {role_text}\n\n"
        
        embed = discord.Embed(
            title="🔔 YOUTUBE NOTIFIERS",
            description=f"{VisualElements.CIRCUIT_LINE}\n{channel_list}**Tracking:** {len(channels)}/{MAX_CHANNELS_PER_SERVER} channels\n{VisualElements.CIRCUIT_LINE}",
            color=BrandColors.PRIMARY
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def check_youtube_feeds():
    """Background task to check YouTube feeds for new videos"""
    if db is None:
        return
    
    try:
        unique_channels = {}
        async for doc in db.youtube_channels.find():
            yt_id = doc['yt_channel_id']
            if yt_id not in unique_channels:
                unique_channels[yt_id] = []
            unique_channels[yt_id].append(doc)
        
        for yt_channel_id, subscriptions in unique_channels.items():
            try:
                feed = await fetch_rss_feed(yt_channel_id)
                
                if not feed or not feed['videos']:
                    continue
                
                latest_video = feed['videos'][0]
                
                for sub in subscriptions:
                    if sub.get('last_video_id') != latest_video['video_id']:
                        success = await send_video_notification(
                            sub['guild_id'],
                            sub['discord_channel_id'],
                            sub.get('role_id'),
                            latest_video,
                            feed['channel_name']
                        )
                        
                        if success:
                            await db.youtube_channels.update_one(
                                {'_id': sub['_id']},
                                {'$set': {'last_video_id': latest_video['video_id']}}
                            )
                            
                            print(f"🔔 [YT] Sent notification for {feed['channel_name']} to guild {sub['guild_id']}")
                            
                            try:
                                guild = bot.get_guild(int(sub['guild_id']))
                                if guild:
                                    await log_action(
                                        sub['guild_id'],
                                        "youtube",
                                        f"🔔 [YOUTUBE] New video detected: **{latest_video['title']}** from {feed['channel_name']}"
                                    )
                                    
                                    try:
                                        from advanced_logging import send_global_log
                                        await send_global_log(
                                            "youtube",
                                            f"**🔔 New Video Detected**\n**Server:** {guild.name}\n**Channel:** {feed['channel_name']}\n**Video:** {latest_video['title']}\n**URL:** {latest_video['url']}",
                                            guild
                                        )
                                    except:
                                        pass
                            except:
                                pass
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ [YT] Error checking {yt_channel_id}: {e}")
                continue
                
    except Exception as e:
        print(f"❌ [YT] Error in check_youtube_feeds: {e}")


@tasks.loop(minutes=POLL_INTERVAL_MINUTES)
async def youtube_check_task():
    """Background task loop for YouTube feed checking"""
    await check_youtube_feeds()


@youtube_check_task.before_loop
async def before_youtube_check():
    """Wait for bot to be ready before starting task"""
    await bot.wait_until_ready()
    print(f"✅ YouTube notifier task started (checking every {POLL_INTERVAL_MINUTES} minutes)")


def start_youtube_task():
    """Start the YouTube checking background task"""
    if not youtube_check_task.is_running():
        youtube_check_task.start()


print("✅ YouTube Notifier module loaded")
