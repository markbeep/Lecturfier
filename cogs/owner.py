import discord
from discord.ext import commands
import random
import asyncio
import inspect
import os
import time
from cogs import admin, hangman, help, updates, minesweeper, owner, player, quote, reputation, statistics, voice


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == 755781649643470868:
            return

    async def loading_bar(self, bars, max_length=None, failed=None):
        bars = round(bars)
        if max_length is None:
            max_length = 10
        if failed is None:
            return "<:blue_box:764901467097792522>" * bars + "<:grey_box:764901465592037388>" * (max_length - bars)  # First is blue square, second is grey
        elif failed:
            return "<:red_box:764901465872662528>"*bars  # Red square
        else:
            return "<:green_box:764901465948684289>"*bars  # Green square

    @commands.command(usage="bully <user>")
    async def bully(self, ctx, user=None):
        """
        Bully a user by pinging that person in random intervals, then instantly deleting that message again.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            await ctx.message.delete()
            if user is None:
                await ctx.send("No user")
                raise discord.ext.commands.errors.NotOwner
            for i in range(10):
                await asyncio.sleep(random.randint(10, 100))
                msg = await ctx.send(user)
                await msg.delete()
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="inspect <cmd>")
    async def inspect(self, ctx, cmd="minesweeper"):
        """
        Used to send the code of any given command. **Does not work yet.**
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            source_code = inspect.getsource(minesweeper.Minesweeper)
            await ctx.send(f"```python\n"
                           f"{source_code}\n"
                           f"```")
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="loops")
    async def loops(self, ctx):
        """
        Displays all running background tasks
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            all_loops = {
                "Lecture Updates Loop": self.bot.get_cog("Updates").heartbeat(),
                "Statistics file save Loop": self.bot.get_cog("Statistics").heartbeat(),
                "Voice XP track Loop": self.bot.get_cog("Voice").heartbeat(),
                "COVID Web Scraper": self.bot.get_cog("Player").heartbeat()
            }

            msg = ""
            cur_time = time.time()
            for name in all_loops.keys():
                seconds_elapsed = cur_time - all_loops[name]
                if seconds_elapsed <= 120:
                    msg += f"\n**{name}:** <:checkmark:776717335242211329> | Last Heartbeat: `{int(round(seconds_elapsed))}` seconds ago"
                elif all_loops[name] == 0:
                    msg += f"\n**{name}:** <:xmark:776717315139698720> | Last Heartbeat: **background task never even started**"
                else:
                    msg += f"\n**{name}:** <:xmark:776717315139698720> | Last Heartbeat: `{int(round(seconds_elapsed))}` seconds ago"
            await ctx.send(msg)
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="loading")
    async def loading(self, ctx):
        """
        Plays a little loading animation in a message.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            msg = await ctx.send("Loading:\n0% | " + await self.loading_bar(0))
            for i in range(1, 10):
                await msg.edit(
                    content=("Loading:\n" + f"{random.randint(i * 10, i * 10 + 5)}% | " + await self.loading_bar(i)))
                await asyncio.sleep(0.75)
            await msg.edit(content=("Loading: DONE\n" + "100% | " + await self.loading_bar(10, 10, False)))
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="reboot")
    async def reboot(self, ctx):
        """
        Uses `reboot now` in the command line. Restarts the current device if it runs on linux.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            await ctx.send("Rebooting...")
            os.system('reboot now')  # Only works on linux (saved me a few times)
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="react <message_id> <reaction>")
    async def react(self, ctx, message_id, reaction):
        """
        React to a message using the bot.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            message = await ctx.fetch_message(int(message_id))
            await message.add_reaction(reaction)
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="spam")
    async def spam(self, ctx):
        """
        Sends close to the maximum allowed characters on Discord in one single message
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            spam = "\n" * 1900
            embed = discord.Embed(title="." + "\n" * 250 + ".", description="." + "\n" * 2000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 700 + ".")
            await ctx.send(f"\"{spam}\"", embed=embed)
            await ctx.send(f"{len(spam) + len(embed)} chars")
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(aliases=["send", "repeatme", "echo"], usage="say <msg>")
    async def say(self, ctx, *, cont):
        """
        Repeats a message
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            await ctx.send(cont)
        else:
            raise discord.ext.commands.errors.NotOwner


def setup(bot):
    bot.add_cog(Owner(bot))
