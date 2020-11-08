import discord
from discord.ext import commands, tasks
import os
import random
import asyncio
from cogs import statistics, voice_xp, lecture_updates
import time


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @commands.command()
    async def loops(self, ctx):
        if await self.bot.is_owner(ctx.author):
            all_loops = {
                "Lecture Updates Loop": self.bot.get_cog("Updates").heartbeat(),
                "Save Statistics Loop": self.bot.get_cog("Statistics").heartbeat(),
                "Save Voice Loop": self.bot.get_cog("Voice").heartbeat()
            }

            msg = ""
            cur_time = time.time()
            for name in all_loops.keys():
                seconds_elapsed = cur_time - all_loops[name]
                if seconds_elapsed <= 120:
                    msg += f"\n**{name}:** <:checkmark:769279808244809798> | Last Heartbeat: `{int(round(seconds_elapsed))}` seconds ago"
                else:
                    msg += f"\n**{name}:** <:xmark:769279807916998728> | Last Heartbeat: `{int(round(seconds_elapsed))}` seconds ago"
            await ctx.send(msg)

    @commands.command()
    async def loading(self, ctx):
        if await self.bot.is_owner(ctx.author):
            msg = await ctx.send("Loading:\n0% | " + await self.loading_bar(0))
            for i in range(1, 10):
                await msg.edit(
                    content=("Loading:\n" + f"{random.randint(i * 10, i * 10 + 5)}% | " + await self.loading_bar(i)))
                await asyncio.sleep(0.75)
            await msg.edit(content=("Loading: DONE\n" + "100% | " + await self.loading_bar(10, 10, False)))

    @commands.command()
    async def reboot(self, ctx):
        if await self.bot.is_owner(ctx.author):
            await ctx.send("Rebooting...")
            os.system('reboot now')  # Only works on linux (saved me a few times)

    @commands.command()
    async def spam_till_youre_dead(self, ctx):
        if await self.bot.is_owner(ctx.author):
            spam = "\n" * 1900
            embed = discord.Embed(title="." + "\n" * 250 + ".", description="." + "\n" * 2000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 700 + ".")
            await ctx.send(f"\"{spam}\"", embed=embed)
            await ctx.send(f"{len(spam) + len(embed)} chars")

    @commands.command(aliases=["send", "repeatme"])
    async def say(self, ctx, *, cont):
        """
        Repeats a message
        """
        if await self.bot.is_owner(ctx.author):
            await ctx.send(cont)


def setup(bot):
    bot.add_cog(Owner(bot))
