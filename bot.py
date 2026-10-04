import os

import discord
from dotenv import load_dotenv

from commands import register_commands
from config import DEVELOPMENT_GUILD_ID
from quiz_engine import QuizEngine
from storage import DataStore


store = DataStore()
store.reset_daily_period_if_needed()
store.save()

intents = discord.Intents.default()
intents.message_content = True


class QuizClient(discord.Client):
	def __init__(self, *, intents):
		super().__init__(intents=intents)
		self.tree = discord.app_commands.CommandTree(self)


client = QuizClient(intents=intents)
quiz_engine = QuizEngine(store)
register_commands(client, store, quiz_engine)


@client.event
async def on_ready():
	guild = discord.Object(id=int(DEVELOPMENT_GUILD_ID))
	await client.tree.sync()
	client.tree.clear_commands(guild=guild)
	client.tree.copy_global_to(guild=guild)
	synced_commands = await client.tree.sync(guild=guild)
	print(f"Synced {len(synced_commands)} commands to Knight Arena.")
	print("KnightQuiz is online!")


load_dotenv()
token = os.getenv("DISCORD_TOKEN")

if not token:
	raise RuntimeError("DISCORD_TOKEN environment variable is not set")

client.run(token)
