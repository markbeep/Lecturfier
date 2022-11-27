import discord
from discord.ext import commands
from helper.sql import SQLFunctions
import os
import asyncio
from cogs.quote import quote_setup_hook

prefix = os.getenv("BOT_PREFIX")


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents()
        assert prefix
        super().__init__(command_prefix=prefix, intents=intents.all(), description="Lecture Notifier", owner_id=205704051856244736)

    async def setup_hook(self):
        await quote_setup_hook(self)

    
async def main():
    # Load the token
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("BOT_TOKEN environment variable doesn't exist")
        exit()
        
    # connects to the db
    conn = SQLFunctions.connect()
    async with Bot() as bot:
        # Loads the sub_bot cog, which can then easily be reloaded
        await bot.load_extension("cogs.mainbot")
        
        # Loads the help page, as it has an on_ready event that needs to be called
        await bot.load_extension("cogs.help")

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
