
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
from main import bot, has_permission, log_action

# Music queue for each guild
music_queues = {}
voice_clients = {}

# YT-DLP options
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@bot.tree.command(name="play", description="🎵 Play music from YouTube")
@app_commands.describe(query="Song name or YouTube URL")
async def play(interaction: discord.Interaction, query: str):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return

    if not interaction.user.voice:
        await interaction.response.send_message("❌ You need to be in a voice channel to use this command!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    guild_id = interaction.guild.id

    if guild_id not in voice_clients:
        try:
            voice_client = await channel.connect()
            voice_clients[guild_id] = voice_client
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to connect to voice channel: {str(e)}", ephemeral=True)
            return
    
    await interaction.response.defer()

    try:
        player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
        
        if guild_id not in music_queues:
            music_queues[guild_id] = []
        
        music_queues[guild_id].append(player)
        
        if not voice_clients[guild_id].is_playing():
            await play_next(guild_id)
        
        embed = discord.Embed(
            title="🎵 Added to Queue",
            description=f"**{player.title}** has been added to the queue!",
            color=0x43b581
        )
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ Music")
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {str(e)}")

async def play_next(guild_id):
    if guild_id in music_queues and music_queues[guild_id]:
        player = music_queues[guild_id].pop(0)
        voice_clients[guild_id].play(player, after=lambda e: bot.loop.create_task(play_next(guild_id)) if e else None)

@bot.tree.command(name="stop", description="🛑 Stop music and disconnect")
async def stop(interaction: discord.Interaction):
    if not await has_permission(interaction, "junior_moderator"):
        await interaction.response.send_message("❌ You need Junior Moderator permissions to use this command!", ephemeral=True)
        return

    guild_id = interaction.guild.id
    
    if guild_id in voice_clients:
        await voice_clients[guild_id].disconnect()
        del voice_clients[guild_id]
        if guild_id in music_queues:
            del music_queues[guild_id]
        
        embed = discord.Embed(
            title="🛑 Music Stopped",
            description="Disconnected from voice channel and cleared queue.",
            color=0xe74c3c
        )
        embed.set_footer(text="ᴠᴀᴀᴢʜᴀ Music")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Not connected to a voice channel!", ephemeral=True)

@bot.tree.command(name="queue", description="📋 Show music queue")
async def queue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    
    if guild_id not in music_queues or not music_queues[guild_id]:
        await interaction.response.send_message("❌ No songs in queue!", ephemeral=True)
        return
    
    queue_text = ""
    for i, player in enumerate(music_queues[guild_id][:10]):
        queue_text += f"{i+1}. **{player.title}**\n"
    
    embed = discord.Embed(
        title="📋 Music Queue",
        description=queue_text,
        color=0x3498db
    )
    embed.set_footer(text="ᴠᴀᴀᴢʜᴀ Music")
    await interaction.response.send_message(embed=embed)
