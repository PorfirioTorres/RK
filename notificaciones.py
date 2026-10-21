import discord
import asyncio
import os
from pathlib import Path

# Configuration
# In a real scenario, this should be in a .env file or settings.json
# For now, we'll look for a discord_token.txt file
DATOS = Path(os.environ.get("RYUKO_DATOS") or Path(__file__).parent)
TOKEN_FILE = DATOS / "discord_token.txt"

class RyukoDiscordBridge:
    def __init__(self):
        self.client = None
        self.token = self._load_token()
        self.user_channel_id = None # ID of the channel where notifications go

    def _load_token(self):
        try:
            if TOKEN_FILE.exists():
                return TOKEN_FILE.read_text(encoding="utf-8").strip()
        except Exception as e:
            print(f"[Discord Bridge] Error loading token: {e}")
        return None

    async def start(self):
        if not self.token:
            print("[Discord Bridge] No token found in discord_token.txt. Bridge will not start.")
            return

        intents = discord.Intents.default()
        self.client = discord.Client(intents=intents)

        @self.client.event
        async def on_ready():
            print(f"[Discord Bridge] Logged in as {self.client.user}")
            # Optional: Try to find the user's DM channel if the token is a User Token
            # (Note: User tokens are against Discord TOS, Bot tokens are recommended)
            # For this bridge, we assume the user provides a Channel ID in settings.json
            # or we just send to the first available channel the bot has access to.

        try:
            await self.client.start(self.token)
        except Exception as e:
            print(f"[Discord Bridge] Failed to start: {e}")

    async def send_notification(self, message: str):
        if not self.client or not self.client.is_ready():
            print("[Discord Bridge] Client not ready, cannot send notification.")
            return False

        try:
            # We need a target. Ideally, this is configured in settings.json
            # For now, we'll look for a 'discord_channel_id' in settings.json via a helper
            from ajustes import cargar_ajustes
            settings = cargar_ajustes(DATOS / "settings.json")
            channel_id = settings.get("discord_channel_id")

            if not channel_id:
                print("[Discord Bridge] No discord_channel_id found in settings.json")
                return False

            channel = await self.client.fetch_channel(int(channel_id))
            await channel.send(f"🤖 **Ryuko**: {message}")
            return True
        except Exception as e:
            print(f"[Discord Bridge] Error sending notification: {e}")
            return False

    async def stop(self):
        if self.client:
            await self.client.close()

# Global instance to be managed by the server
bridge = RyukoDiscordBridge()
