import os
import time
import asyncio
import discord
from discord import app_commands
from discord.app_commands import AppCommandError
import libtorrent as lt
from torrentp import TorrentDownloader
from dotenv import load_dotenv

load_dotenv()

timestamp = time.time()
formatted_time = time.strftime("%m-%d-%Y %H:%M:%S", time.localtime(timestamp))

def magnet_info(magnet):
    session = lt.session()
    params = lt.parse_magnet_uri(magnet)
    params.save_path = os.getenv('DOWNLOAD_PATH')
    params.flags = lt.torrent_flags.upload_mode
    handle = session.add_torrent(params)
    print(f"{formatted_time}   Processing magnet: {magnet.split('&')[0]}")
    while not handle.status().has_metadata:
        time.sleep(1)
    print(f"{formatted_time}   Getting metadata from magnet...")
    torrent_info = handle.status()
    name = torrent_info.name
    size = torrent_info.total
    session.remove_torrent(handle)
    return {'name': name, 'size': size / (1024 * 1024)}

class BotClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
    async def setup_hook(self):
        await self.tree.sync()

intents = discord.Intents.default()
client = BotClient(intents=intents)

@client.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: AppCommandError):
    await interaction.response.defer()
    print(f"{formatted_time}   {error}")
    await interaction.followup.send(f'❌ An error has occured. Check console for the full trace.', ephemeral=True)

@client.event
async def on_ready():
    await client.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.watching, name='completely legal movies'))
    print(f'{formatted_time}   Logged in as {client.user} (ID: {client.user.id})')

@client.tree.command()
async def ping(interaction: discord.Interaction):
    """Latency test."""
    pong = round((client.latency * 1000), 1)
    await interaction.response.send_message(f'🏓 Pong! Latency: **{pong}** ms')
    print(f"{formatted_time}   Client pinged at {pong}ms")

class DownloadManager(discord.ui.Button):
    def __init__(self, file):
        super().__init__(timeout=None)
        self.file = file

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="🛑")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.file.stop_download()
        button.disabled = True
        await interaction.response.send_message("🛑 Download stopped.")
        print(f"{formatted_time}   Download stopped.")

@client.tree.command()
async def download(interaction: discord.Interaction, magnet: str):
    """Downloads torrent via magnet."""
    await interaction.response.defer()
    if interaction.user.id != int(os.getenv('OWNER_ID')):
        return
    
    torrent_data = magnet_info(magnet)
    file = TorrentDownloader(magnet, os.getenv('DOWNLOAD_PATH'), stop_after_download=True)
    buttons = DownloadManager(file)
    
    print(f"{formatted_time}   Starting download of {torrent_data['name']} ({round(torrent_data['size'], 2)}MB)")
    await interaction.followup.send(f"🟡 Starting download of: **{torrent_data['name']}** [{round(torrent_data['size'], 2)} MB] to `{os.getenv('DOWNLOAD_PATH')}`", view=buttons)
    msg = await interaction.original_response()

    async def progress_bar():
        while True:
            progress = file.get_progress()
            if progress >= 100 or file._download_task.done() or not file._download_task:
                break
            pb_length = 20
            pb_filled_length = int(pb_length * progress / 100)
            bar = '█' * pb_filled_length + '░️' * (pb_length - pb_filled_length)
            await msg.edit(content=f"🟢 Downloading: **{torrent_data['name']}** [{round(torrent_data['size'], 2)} MB] to `{os.getenv('DOWNLOAD_PATH')}`\n\n{round((progress), 2)}% `[  {bar}  ]`")
            print(f"\n{formatted_time}   Download progress: {progress}%")
            await asyncio.sleep(0.5)

    await asyncio.gather(file.start_download(), progress_bar())
    await msg.edit(content=f"🎉 Downloaded: **{torrent_data['name']}** [{round(torrent_data['size'], 2)} MB] to `{os.getenv('DOWNLOAD_PATH')}`")
    print(f"{formatted_time}   Download of {torrent_data['name']} completed.")
    
client.run(os.getenv('BOT_TOKEN'))