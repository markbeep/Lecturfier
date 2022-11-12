import json
import discord
from discord.ext import commands
from helper.sql import SQLFunctions
import os
import asyncio

with open("./config/settings.json", "r", encoding="utf8") as f:
    prefix = json.load(f)

async def main():
    # Load the token
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("NO TOKEN IN LECTURFIER.json! Stopping bot.")
        exit()
        
    # connects to the db
    conn = SQLFunctions.connect()
    intents = discord.Intents()
    async with commands.Bot(command_prefix=prefix["prefix"], description='Lecture Notifier', intents=intents.all(), owner_id=205704051856244736) as bot:
        # Loads the sub_bot cog, which can then easily be reloaded
        await bot.load_extension("cogs.mainbot")
        
        # Loads the help page, as it has an on_ready event that needs to be called
        await bot.load_extension("cogs.help")
        
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
        
        await bot.start(token)

asyncio.run(main())
