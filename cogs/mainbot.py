import random

import discord
from discord.ext import commands

from helper import file_creator
from helper.log import log


class MainBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        file_creator.createFiles()
        self.bot = bot
        self.startup_extensions = [
            "statistics",
            "minesweeper",
            "hangman",
            "quote",
            "help",
            "reputation",
            "admin",
            "owner",
            "voice",
            "updates",
            "information",
            "draw",
            "mainbot"
        ]
        self.watching_messages = [
            "students",
            "your grades",
            "Star Wars",
            "random Youtube videos",
            "you",
            "lecture updates",
            "closely",
            "the other bots",
            "how to git gud",
            "memes",
            "the void"
        ]

    @commands.Cog.listener()
    async def on_ready(self):
        print("\n----------------------------")
        log("Starting up bot")
        log("Logged in as:")
        log(f"Name: {self.bot.user.name if self.bot.user else '<no name>'}")
        log(f"ID: {self.bot.user.id if self.bot.user else '<no id>'}")
        log(f"Version: {discord.__version__}")
        await self.bot.change_presence(activity=discord.Activity(name=random.choice(self.watching_messages), type=discord.ActivityType.watching))
        print("-------------")
        count = await self.load_all_extensions(self.startup_extensions)
        log(f"Started up bot with {count}/{len(self.startup_extensions)-2} extensions loaded successfully.")
        print("-------------")

    async def load_all_extensions(self, extensions_to_load) -> int:
        count = 0
        for extension in extensions_to_load:
            try:
                await self.bot.load_extension("cogs." + extension)
                log(f"Loaded extension \"{extension}\".")
                count += 1
            except commands.errors.ExtensionAlreadyLoaded:
                pass
            except Exception as e:
                log(f"Failed loading extension \"{extension}\"\n-{e}: {type(e)}", print_it=True, warning=True)
        return count

    @commands.is_owner()
    @commands.command()
    async def reload(self, ctx, cog=None):
        """
        Used to reload a cog. Does not load a cog if the cog is unloaded.
        Permissions: Owner
        """
        if cog is None:
            cog_list = '\n'.join(self.startup_extensions)
            await ctx.send(f"Following cogs exist:\n"
                           f"{cog_list}")
        elif cog in self.startup_extensions:
            await ctx.send(await self.reload_cog(cog))
            await ctx.send(f"DONE - Reloaded `{cog}`")
        elif cog == "all":
            await ctx.send("Reloading all cogs")
            log("Reloading all cogs", True)
            for cog in self.startup_extensions:
                await ctx.send(await self.reload_cog(cog))
            await ctx.send("DONE - Reloaded all cogs")
        else:
            await ctx.send("Cog does not exist.")

    async def reload_cog(self, cog):
        await self.bot.reload_extension("cogs." + cog)
        return f"Reloaded `{cog}`"


async def setup(bot):
    await bot.add_cog(MainBot(bot))
