from datetime import datetime
import time
import aiohttp
import discord
from discord.ext import commands, tasks
import os
import json

from pytz import timezone
from cogs.quote import PagesView
from helper.log import log
from helper.sql import SQLFunctions
from .information import get_formatted_time

def create_pages(msg: str, CHAR_LIMIT: int) -> list[str]:
    pages = []
    while len(msg) > 0:
        # split quotes into multiple fields of max 1000 chars
        if len(msg) >= CHAR_LIMIT:
            rind2 = msg.rindex("\n", 0, CHAR_LIMIT)
            if rind2 == 0:
                # one quote is more than 1000 chars
                rind2 = msg.rindex(" ", 0, CHAR_LIMIT)
                if rind2 == 0:
                    # the quote is longer than 1000 chars and has no spaces
                    rind2 = CHAR_LIMIT
        else:
            rind2 = len(msg)
        pages.append(msg[0:rind2])
        msg = msg[rind2:]
    return pages

class AdventOfCode(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()
        self.aoc_path = "./data/aoc_data.json"
        self.data = {}
        if os.path.isfile(self.aoc_path):
            with open(self.aoc_path, "r") as f:
                self.data: dict = json.load(f)
        self.last_updated = 0
        
        # temp channel is so the linter stops complaining
        temp_channel = self.bot.get_channel(910450760234467328)
        if not temp_channel:
            temp_channel = self.bot.get_channel(1046168961189941369)
        assert isinstance(temp_channel, discord.abc.Messageable)
        self.aoc_channel = temp_channel
        self.aoc_loop.start()  # pylint: disable=no-member

    def heartbeat(self):
        return self.aoc_loop.is_running()  # pylint: disable=no-member

    def cog_unload(self) -> None:
        self.aoc_loop.cancel()  # pylint: disable=no-member

    @tasks.loop(minutes=15)
    async def aoc_loop(self):
        await self.bot.wait_until_ready()
        dt = datetime.now(timezone("Europe/Zurich"))
        if dt.minute > 5:
            self.sent_advent = False
        if dt.month == 12 and not self.sent_advent and 1 <= dt.day <= 25 and dt.hour == 6 and dt.minute <= 5:
            msg = f"Good Morning! It's time for **Advent of Code** day #{dt.day}!\n\
                [*Click here to get to the challenge*](https://adventofcode.com/2022/day/{dt.day})"
            embed = discord.Embed(
                description=msg,
                color=discord.Color.red())
            await self.aoc_channel.send("<@&1046388087837704293>", embed=embed)
            self.sent_advent = True
        
        # fetches the stats
        await self.bot.wait_until_ready()
        session_key = os.getenv("AOC_SESSION_KEY")
        if not session_key:
            print("Session key not available. Skipping AoC request.")
            return
        
        return 
        cookie = {"session": session_key}
        async with aiohttp.ClientSession(cookies=cookie) as session:
            async with session.get("https://adventofcode.com/2022/leaderboard/private/view/951576.json") as response:
                if response.status == 200:
                    temp_data = await response.read()
                    self.data = json.loads(temp_data)
                    log("Got new advent of code data", True)
                    self.last_updated = time.time()
                    # saves the file to the data folder
                    with open(self.aoc_path, "w") as f:
                        json.dump(self.data, f)
                    log("Successfully updated the AoC data.", True)
        

    @commands.guild_only()
    @commands.group(aliases=["adventofcode", "AdventOfCode"])
    async def aoc(self, ctx, day: int = -1, star: int = -1):
        """
        `{prefix}aoc` - Total Leaderboard
        `{prefix}aoc 1-25` - Day Leaderboard
        `{prefix}aoc 1-25 1-2` - Day Leaderboard with star
        """
        d = self.data
        desc = f"Last Updated: `{get_formatted_time(int(time.time() - self.last_updated))}` ago"
        if day == -1 and star == -1:  # send the general lb
            pages = []
            members = [d["members"][key] for key in d["members"]]

            points_fn = lambda k: k["local_score"]
            members.sort(key=points_fn, reverse=True)

            msg = []
            for i, m in enumerate(members):
                msg.append(f"`[{i+1}]` **{m['name']}** - {m['local_score']} points | {m['stars']} stars")
            pages = create_pages("\n".join(msg), 500)

            view = PagesView(self.bot, ctx, pages, ctx.author.id, "Total AoC Leaderboard", description=desc)
            await ctx.send(embed=view.embed, view=view)
        elif star == -1 and 1 <= day <= 25:  # send the lb for that day

            pages = []
            members = [d["members"][key] for key in d["members"]
                       if len(d["members"][key]["completion_day_level"])>0 
                       and f"{day}" in d["members"][key]["completion_day_level"]]

            members, points = self.sort_by_times(members, len(d["members"]), day)
            msg = []
            for i, m in enumerate(members):
                msg.append(f"`[{i+1}]` **{d['members'][m]['name']}** - {points[d['members'][m]['id']]} points")
            pages = create_pages("\n".join(msg), 500)

            if len(pages) > 0:
                view = PagesView(self.bot, ctx, pages, ctx.author.id, f"Day {day} AoC Leaderboard", description=desc)
                await ctx.message.send(embed=view.embed, view=view)
            else:
                await ctx.reply("There are no stats for that day yet.", delete_after=10)
                await ctx.message.delete(delay=10)
        elif 1 <= day <= 25 and star in [1, 2]:  # sends the lb for that day and star
            pages = []
            members = [d["members"][key] for key in d["members"]
                       if len(d["members"][key]["completion_day_level"])>0
                       and f"{day}" in d["members"][key]["completion_day_level"]
                       and f"{star}" in d["members"][key]["completion_day_level"][f"{day}"]]

            points_fn = lambda m: m["completion_day_level"][f"{day}"][f"{star}"]["get_star_ts"]
            members.sort(key=points_fn)

            min_time = 0
            if len(members) > 0:
                min_time = members[0]["completion_day_level"][f"{day}"][f"{star}"]["get_star_ts"]
            mytz = timezone("Europe/Zurich")
            dt = datetime.fromtimestamp(min_time).strftime(f"{day}/%m/%Y, 06:00:00")
            dt = datetime.strptime(dt, "%d/%m/%Y, %H:%M:%S")
            dt = mytz.normalize(mytz.localize(dt, is_dst=True))
            min_hour = dt.timestamp()

            msg = []
            for i, m in enumerate(members):
                form = get_formatted_time(m['completion_day_level'][f'{day}'][f'{star}']['get_star_ts']-min_hour)
                msg.append(f"`[{i+1}]` **{m['name']}** - {form}")
            pages = create_pages("\n".join(msg), 500)

            if len(pages) > 0:
                view = PagesView(self.bot, ctx, pages, ctx.author.id, f"Day {day} Star {star} AoC Leaderboard", description=desc)
                await ctx.message.send(embed=view.embed, view=view)
            else:
                await ctx.reply("There are no stats for that day or star yet.", delete_after=10)
                await ctx.message.delete(delay=10)
        else:
            await ctx.reply("Unrecognized command parameters. Please check the help page.", delete_after=10)
            await ctx.message.delete(delay=10)

    def sort_by_times(self, members: list[dict], total: int, day: int):
        points = {m["id"]:0 for m in members}
        first_star = [m for m in members if "1" in m["completion_day_level"][f"{day}"]]
        second_star = [m for m in members if "2" in m["completion_day_level"][f"{day}"]]
        
        # sort by the person's submission time (earliest times at the end)
        sort_fn1 = lambda m: m["completion_day_level"][f"{day}"]["1"]["get_star_ts"]
        sort_fn2 = lambda m: m["completion_day_level"][f"{day}"]["2"]["get_star_ts"]
        first_star.sort(key=sort_fn1)
        second_star.sort(key=sort_fn2)
        
        for i, m in enumerate(first_star):
            points[m["id"]] = total - i
        for i, m in enumerate(second_star):
            points[m["id"]] += total - i
        
        final = sorted(points, key= lambda x: points[x], reverse=True)  # sorted by final points
        return final, points


async def setup(bot):
    await bot.add_cog(AdventOfCode(bot))
