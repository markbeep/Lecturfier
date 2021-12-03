import json

import discord
from discord.ext import commands
from discord_components import DiscordComponents

from helper.sql import SQLFunctions

with open("./data/settings.json", "r") as f:
    prefix = json.load(f)

intents = discord.Intents()
bot = commands.Bot(
    command_prefix=prefix["prefix"],
    description='Lecture Notifier',
    intents=intents.all(),
    owner_id=205704051856244736)

# Loads the sub_bot cog, which can then easily be reloaded
bot.load_extension("cogs.mainbot")
# Loads the help page, as it has an on_ready event that needs to be called
bot.load_extension("cogs.help")
# enables discord components
DiscordComponents(bot)
# connects to the db
conn = SQLFunctions.connect()


@bot.event
async def on_message(message):
    await bot.process_commands(message)


@bot.check
async def globally_handle_permissions(ctx):
    """
    Checks if the command can be used in the channel. It's a blacklist system, so by default all commands
    can be used. Hierarchy is USER > ROLE > CHANNEL > GUILD.
    0 is the default value
    1 is allowed
    -1 is not allowed
    """
    guild_id = 0
    role_ids = []
    if ctx.message.guild is not None:
        guild_id = ctx.message.guild.id
        role_ids = [role.id for role in ctx.message.author.roles]
    command_name = ctx.command.name
    if ctx.command.root_parent is not None:
        command_name = ctx.command.root_parent.name
    permission_level = SQLFunctions.get_command_level(command_name, ctx.message.author.id, role_ids, ctx.message.channel.id, guild_id, conn)
    return permission_level != -1


# Load the token
with open("../LECTURFIER.json", "r") as f:
    settings = json.load(f)

if len(settings["token"]) == 0:
    print("NO TOKEN IN LECTURFIER.json! Stopping bot.")
    exit()

bot.run(settings["token"])
