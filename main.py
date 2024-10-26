import discord
from discord.ext import commands
import yt_dlp
import asyncio
import webserver
import os
import subprocess

# Check if FFmpeg is installed
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
    'options': '-vn -bufsize 5000k'}
YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': True}

class MusicBot(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.queue = []

    @commands.command()
    async def play(self, ctx, *, search):
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None
        if not voice_channel:
            return await ctx.send("You're not in a voice channel!")

        if not ctx.voice_client:
            await voice_channel.connect()

        async with ctx.typing():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(f"ytsearch:{search}", download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                url = info['url']
                title = info['title']
                self.queue.append((url, title))
                await ctx.send(f'Added to queue: **{title}**')

        # Check if anything is playing; if not, play the next song in the queue
        if not ctx.voice_client.is_playing():
            await self.play_next(ctx)

    async def play_next(self, ctx):
        print("In play_next")  # Debugging: check if play_next is being called
        if self.queue:
            print(f"Queue has {len(self.queue)} items")  # Debugging: check queue length
            url, title = self.queue.pop(0)
            source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
            print(f"Playing {title}")  # Debugging: check what's playing
            ctx.voice_client.play(source, after=lambda _: self.client.loop.create_task(self.play_next(ctx)))
            await ctx.send(f"Now playing: **{title}**")
        else:
            print("Queue is empty")  # Debugging: check if the queue is empty
            await ctx.send("Queue is empty!")

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Skipped")

client = commands.Bot(command_prefix="!", intents=intents)

async def main():
    await client.add_cog(MusicBot(client))
    await client.start(os.getenv('DISCORD_TOKEN'))

webserver.keep_alive()
asyncio.run(main())
