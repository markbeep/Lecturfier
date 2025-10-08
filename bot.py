import asyncio
import os
import traceback

import discord
from discord.ext import commands

from cogs.quote import quote_setup_hook

# makes sure the correct files exist
from helper import file_creator
from helper.sql import SQLFunctions
from dotenv import load_dotenv

file_creator.createFiles()

load_dotenv()
prefix = os.getenv("BOT_PREFIX")
guild_id = os.getenv("TEST_GUILD_ID")
TEST_GUILD = None
if guild_id:
    TEST_GUILD = discord.Object(int(guild_id))
assert prefix


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents()
        assert prefix  # to shut the linter up
        super().__init__(
            command_prefix=prefix,
            intents=intents.all(),
            description="Lecture Notifier",
            owner_id=205704051856244736,
        )

    async def setup_hook(self):
        await self.load_extension("cogs.lecture_updates.slash")
        await self.load_extension("cogs.lecture_updates.task")
        await self.load_extension("cogs.moderate")
        if TEST_GUILD:
            self.tree.copy_global_to(guild=TEST_GUILD)
            synced = await self.tree.sync(guild=TEST_GUILD)
        else:
            synced = await self.tree.sync()
        print(f"Synced {len(synced)} slash commands")
        await quote_setup_hook(self)


async def main():
    # Load the token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("DISCORD_TOKEN environment variable doesn't exist")
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
            permission_level = SQLFunctions.get_command_level(
                command_name,
                ctx.message.author.id,
                role_ids,
                ctx.message.channel.id,
                guild_id,
                conn,
            )
            return permission_level != -1

        tree = bot.tree

        @tree.error
        async def on_app_command_error(
            inter: discord.Interaction, error: discord.app_commands.AppCommandError
        ):
            if isinstance(error, discord.app_commands.CheckFailure):
                await inter.response.send_message(error.args[0], ephemeral=True)
            else:
                traceback.print_exception(error)
                await inter.response.send_message(
                    "Something went wrong.", ephemeral=True
                )

        await bot.start(token)


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
