import discord
from discord.ext import commands
import yt_dlp
import asyncio
import webserver
import os
import subprocess
from datetime import datetime

def check_ffmpeg():
    try:
        output = subprocess.check_output('ffmpeg -version', shell=True)
        print(output.decode())
    except Exception as e:
        print(f"FFmpeg error: {e}")

check_ffmpeg()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -timeout 1000000',
    'options': '-vn -bufsize 5000k'
}
YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': True}

class MusicBot(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.now_playing = None
        self.loop_mode = False
        self.start_time = None

    @commands.command()
    async def play(self, ctx, *, search):
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None
        if not voice_channel:
            embed = discord.Embed(
                title="❌ Error",
                description="You need to be in a voice channel to use this command!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        if not ctx.voice_client:
            await voice_channel.connect()

        async with ctx.typing():
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(f"ytsearch:{search}", download=False)
                    if 'entries' in info:
                        info = info['entries'][0]
                    url = info['url']
                    title = info['title']
                    duration = info.get('duration', 0)
                    thumbnail = info.get('thumbnail', '')

                    embed = discord.Embed(
                        title="🎵 Added to Queue",
                        description=f"**{title}**",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Duration", value=self.format_duration(duration))
                    embed.set_thumbnail(url=thumbnail)
                    
                    self.queue.append({
                        'url': url,
                        'title': title,
                        'duration': duration,
                        'thumbnail': thumbnail,
                        'requester': ctx.author.name
                    })
                    
                    await ctx.send(embed=embed)

            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"An error occurred: {str(e)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

        if not ctx.voice_client.is_playing():
            await self.play_next(ctx)

    async def play_next(self, ctx):
        if not self.queue and self.loop_mode and self.now_playing:
            self.queue.append(self.now_playing)

        if self.queue:
            self.now_playing = self.queue.pop(0)
            source = await discord.FFmpegOpusAudio.from_probe(self.now_playing['url'], **FFMPEG_OPTIONS)
            
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**{self.now_playing['title']}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Duration", value=self.format_duration(self.now_playing['duration']))
            embed.add_field(name="Requested by", value=self.now_playing['requester'])
            embed.set_thumbnail(url=self.now_playing['thumbnail'])
            
            self.start_time = datetime.now()
            ctx.voice_client.play(source, after=lambda _: self.client.loop.create_task(self.play_next(ctx)))
            await ctx.send(embed=embed)
        else:
            self.now_playing = None
            self.start_time = None
            await ctx.send("📪 Queue is empty!")

    @commands.command()
    async def skip(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("❌ Nothing is playing right now!")
        
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped the current song!")

    @commands.command()
    async def queue(self, ctx):
        if not self.queue and not self.now_playing:
            return await ctx.send("📪 Queue is empty!")

        embed = discord.Embed(
            title="🎵 Music Queue",
            color=discord.Color.blue()
        )

        if self.now_playing:
            elapsed = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
            progress = self.create_progress_bar(elapsed, self.now_playing['duration'])
            
            embed.add_field(
                name="Now Playing",
                value=f"**{self.now_playing['title']}**\n{progress}\n`{self.format_duration(elapsed)}/{self.format_duration(self.now_playing['duration'])}`",
                inline=False
            )

        queue_list = ""
        for i, song in enumerate(self.queue, 1):
            queue_list += f"`{i}.` **{song['title']}** ({self.format_duration(song['duration'])}) - Requested by {song['requester']}\n"

        if queue_list:
            embed.add_field(name="Up Next", value=queue_list, inline=False)
        
        embed.set_footer(text=f"🔄 Loop Mode: {'On' if self.loop_mode else 'Off'}")
        await ctx.send(embed=embed)

    @commands.command()
    async def loop(self, ctx):
        self.loop_mode = not self.loop_mode
        await ctx.send(f"🔄 Loop mode is now {'on' if self.loop_mode else 'off'}")

    @commands.command()
    async def clear(self, ctx):
        self.queue.clear()
        await ctx.send("🗑️ Queue cleared!")

    @commands.command()
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Goodbye!")

    def format_duration(self, seconds):
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def create_progress_bar(self, elapsed, total, length=20):
        filled = int((elapsed / total) * length) if total > 0 else 0
        bar = "▓" * filled + "░" * (length - filled)
        return f"[{bar}]"

client = commands.Bot(command_prefix="!", intents=intents)

async def main():
    await client.add_cog(MusicBot(client))
    await client.start(os.getenv('DISCORD_TOKEN'))

webserver.keep_alive()
asyncio.run(main())
