import discord
from discord.ext import commands
from discord import ButtonStyle
from discord.ui import Button, View
import yt_dlp
import asyncio
import webserver
import os
import subprocess
from datetime import datetime

# Previous FFmpeg check and options remain the same
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

class MusicControls(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Previous", style=ButtonStyle.green, emoji="⏮️")
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.bot.previous(interaction)

    @discord.ui.button(label="Stop", style=ButtonStyle.red, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.bot.stop(interaction)

    @discord.ui.button(label="Pause", style=ButtonStyle.blurple, emoji="⏯️")
    async def pause_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if button.label == "Pause":
            button.label = "Resume"
            await self.bot.pause(interaction)
        else:
            button.label = "Pause"
            await self.bot.resume(interaction)
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Skip", style=ButtonStyle.green, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.bot.skip(interaction)

    @discord.ui.button(label="Like", style=ButtonStyle.green, emoji="❤️")
    async def like_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Added to your favorites! (Feature coming soon)", ephemeral=True)

class VolumeControls(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Volume Down", style=ButtonStyle.green, emoji="🔉")
    async def volume_down(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.bot.volume_down(interaction)

    @discord.ui.button(label="Volume Up", style=ButtonStyle.green, emoji="🔊")
    async def volume_up(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.bot.volume_up(interaction)

class QueueControls(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Loop", style=ButtonStyle.blurple, emoji="🔄")
    async def loop_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.bot.loop(interaction)

    @discord.ui.button(label="Shuffle Queue", style=ButtonStyle.blurple, emoji="🔀")
    async def shuffle_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.bot.shuffle(interaction)

class MusicBot(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.now_playing = None
        self.loop_mode = False
        self.start_time = None
        self.volume = 1.0
        self.is_paused = False
        self.current_message = None

    async def update_player_message(self, ctx):
        if self.now_playing:
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**{self.now_playing['title']}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Duration", value=self.format_duration(self.now_playing['duration']))
            embed.add_field(name="Requested by", value=self.now_playing['requester'])
            embed.set_thumbnail(url=self.now_playing['thumbnail'])

            # Create views with controls
            music_controls = MusicControls(self)
            volume_controls = VolumeControls(self)
            queue_controls = QueueControls(self)

            if self.current_message:
                try:
                    await self.current_message.delete()
                except:
                    pass

            self.current_message = await ctx.send(
                embed=embed,
                views=[music_controls, volume_controls, queue_controls]
            )

    @commands.command()
    async def play(self, ctx, *, search):
        # Previous play logic remains the same until playing the song
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
                    
                    song_info = {
                        'url': info['url'],
                        'title': info['title'],
                        'duration': info.get('duration', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'requester': ctx.author.name
                    }
                    
                    self.queue.append(song_info)
                    
                    embed = discord.Embed(
                        title="🎵 Added to Queue",
                        description=f"**{song_info['title']}**",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Duration", value=self.format_duration(song_info['duration']))
                    embed.set_thumbnail(url=song_info['thumbnail'])
                    await ctx.send(embed=embed)

            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"An error occurred: {str(e)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

        if not ctx.voice_client.is_playing() and not self.is_paused:
            await self.play_next(ctx)

    # Button control methods
    async def pause(self, interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            self.is_paused = True
            await interaction.followup.send("⏸️ Paused the music", ephemeral=True)

    async def resume(self, interaction):
        if interaction.guild.voice_client and self.is_paused:
            interaction.guild.voice_client.resume()
            self.is_paused = False
            await interaction.followup.send("▶️ Resumed the music", ephemeral=True)

    async def stop(self, interaction):
        if interaction.guild.voice_client:
            self.queue.clear()
            interaction.guild.voice_client.stop()
            await interaction.guild.voice_client.disconnect()
            await interaction.followup.send("⏹️ Stopped the music and cleared the queue", ephemeral=True)

    async def skip(self, interaction):
        if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or self.is_paused):
            interaction.guild.voice_client.stop()
            await interaction.followup.send("⏭️ Skipped the current song", ephemeral=True)

    async def previous(self, interaction):
        # Implement previous track functionality
        await interaction.followup.send("Previous track feature coming soon!", ephemeral=True)

    async def volume_up(self, interaction):
        if interaction.guild.voice_client:
            self.volume = min(2.0, self.volume + 0.1)
            if interaction.guild.voice_client.source:
                interaction.guild.voice_client.source.volume = self.volume
            await interaction.followup.send(f"🔊 Volume set to {int(self.volume * 100)}%", ephemeral=True)

    async def volume_down(self, interaction):
        if interaction.guild.voice_client:
            self.volume = max(0.0, self.volume - 0.1)
            if interaction.guild.voice_client.source:
                interaction.guild.voice_client.source.volume = self.volume
            await interaction.followup.send(f"🔉 Volume set to {int(self.volume * 100)}%", ephemeral=True)

    async def shuffle(self, interaction):
        if len(self.queue) > 1:
            random.shuffle(self.queue)
            await interaction.followup.send("🔀 Queue shuffled!", ephemeral=True)
        else:
            await interaction.followup.send("Not enough songs in queue to shuffle!", ephemeral=True)

    # Keep the previous helper methods (format_duration, create_progress_bar)
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
