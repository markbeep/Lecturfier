import discord
from discord.ext import commands
import json
from helper import file_creator

file_creator.createFiles()

with open("./data/settings.json", "r") as f:
    prefix = json.load(f)

intents = discord.Intents()
bot = commands.Bot(command_prefix=prefix["prefix"], description='Lecture Notifier', intents=intents.all(), owner_id=205704051856244736)

bot.remove_command("help")

# Loads the sub_bot cog, which can then easily be reloaded
bot.load_extension("cogs.mainbot")
# Loads the help page, as it has an on_ready event that needs to be called
bot.load_extension("cogs.help")


@bot.event
async def on_message(message):
    await bot.process_commands(message)

# Load the token
with open("../LECTURFIER.json", "r") as f:
    settings = json.load(f)
if len(settings["token"]) == 0:
    print("NO TOKEN IN LECTURFIER.json! Stopping bot.", "TOKEN")
    exit()

bot.run(settings["token"])
