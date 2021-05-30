import discord
from discord.ext import commands
from helper.log import log
from helper import file_creator


class MainBot(commands.Cog):
    def __init__(self, bot):
        file_creator.createFiles()
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
            "draw",
            "mainbot"
        ]

    @commands.Cog.listener()
    async def on_ready(self):
        print("\n----------------------------")
        log("Starting up bot")
        log("Logged in as:")
        log(f"Name: {self.bot.user.name}")
        log(f"ID: {self.bot.user.id}")
        log(f"Version: {discord.__version__}")
        await self.bot.change_presence(activity=discord.Activity(name="myself startup", type=discord.ActivityType.watching))
        print("-------------")
        count = await self.load_all_extensions(self.startup_extensions)
        log(f"Started up bot with {count}/{len(self.startup_extensions)-2} extensions loaded successfully.")
        print("-------------")

    async def load_all_extensions(self, extensions_to_load) -> int:
        count = 0
        for extension in extensions_to_load:
            try:
                loaded_cog = self.bot.load_extension("cogs." + extension)
                log("Loaded extension \"{}\".".format(extension))
                count += 1
            except discord.ext.commands.errors.ExtensionAlreadyLoaded:
                pass
            except Exception as e:
                log("Failed loading extension \"{}\"\n-{}: {}".format(extension, e, type(e)), print_it=True, warning=True)
        return count

    @commands.command()
    async def reload(self, ctx, cog=None):
        """
        Used to reload a cog. Does not load a cog if the cog is unloaded.
        Permissions: Owner
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
            "updates": self.bot.get_cog("Updates"),
            "statistics": self.bot.get_cog("Statistics"),
            "voice": self.bot.get_cog("Voice"),
            "games": self.bot.get_cog("Games"),
            "information": self.bot.get_cog("Information"),
            "draw": self.bot.get_cog("Draw")
        }
        if task in all_loops:
            all_loops[task].get_task().cancel()
            return True
        return False


def setup(bot):
    bot.add_cog(MainBot(bot))
