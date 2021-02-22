import discord
from discord.ext import commands
from helper.log import log
from helper import file_creator


class MainBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.startup_extensions = [
            "games",
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
            "mainbot",
        ]

    @commands.Cog.listener()
    async def on_ready(self):
        log("\n----------------------------\nStarting up bot")
        print("Logged in as:", "LOGIN")
        print(f"Name: {self.bot.user.name}", "LOGIN")
        print(f"ID: {self.bot.user.id}", "LOGIN")
        print(f"Version: {discord.__version__}", "LOGIN")
        await self.bot.change_presence(activity=discord.Activity(name='myself just boot up', type=discord.ActivityType.watching))
        print("-------------")
        await self.load_all_extensions(self.startup_extensions)
        file_creator.createFiles()
        log("Started up bot\n-------------")

    async def load_all_extensions(self, extensions_to_load):
        for extension in extensions_to_load:
            try:
                loaded_cog = self.bot.load_extension("cogs." + extension)
                print("Loaded extension \"{}\".".format(extension), "EXTENSION")
            except discord.ext.commands.errors.ExtensionAlreadyLoaded:
                pass
            except Exception as e:
                print("Failed loading extension \"{}\"\n-{}: {}".format(extension, e, type(e)), "EXTENSION")
        print("-------------------")

    @commands.command()
    async def reload(self, ctx, cog=None):
        """
        Used to reload a cog. Does not load a cog if the cog is unloaded.

        """
        if await self.bot.is_owner(ctx.author):
            if cog is None:
                cog_list = '\n'.join(self.startup_extensions)
                await ctx.send(f"Following cogs exist:\n"
                               f"{cog_list}")
            elif cog in self.startup_extensions:
                await ctx.send(await self.reload_cog(cog))
                await ctx.send(f"DONE - Reloaded `{cog}`")
            elif cog == "all":
                await ctx.send("Reloading all cogs")
                log("Reloading all cogs", "COGS")
                for cog in self.startup_extensions:
                    await ctx.send(await self.reload_cog(cog))
                await ctx.send("DONE - Reloaded all cogs")
            else:
                await ctx.send(f"Cog does not exist.")
        else:
            raise discord.ext.commands.errors.NotOwner

    async def reload_cog(self, cog):
        if await self.stop_bg_task(cog):
            msg = "--Stopped background task--"
        else:
            msg = "--No background task to stop--"
        if cog == "games":
            games = self.bot.get_cog("Games")
            games.save("./data/guesses.json")
            msg += "\n--Saved covid guesses--"
        self.bot.reload_extension("cogs." + cog)
        return f"Reloaded `{cog}`\n{msg}"

    async def stop_bg_task(self, task):
        """
        Stops the given background task
        :param task: The task to stop
        :return: True if the task was stopped, False if no task was stopped
        """
        task = task.lower()
        all_loops = {
            "lecture_updates": self.bot.get_cog("Updates").get_task(),
            "statistics": self.bot.get_cog("Statistics").get_task(),
            "voice_xp": self.bot.get_cog("Voice").get_task(),
            "games": self.bot.get_cog("Games").get_task()
        }
        if task in all_loops:
            return all_loops[task].cancel()
        return False


def setup(bot):
    bot.add_cog(MainBot(bot))
