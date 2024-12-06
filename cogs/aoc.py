from dataclasses import dataclass
from datetime import datetime, time as dt_time
import time
from typing import Optional
import aiohttp
import discord
from discord.ext import commands, tasks
import os
import json

from pytz import timezone
from cogs.quote import PagesView
from helper.log import log
from helper.sql import SQLFunctions
from .information import get_formatted_time, get_formatted_time_short


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


@dataclass
class AoCStar:
    get_star_ts: int
    star_index: int


@dataclass
class AoCDay:
    star1: Optional[AoCStar]
    star2: Optional[AoCStar]

    def diff(self) -> Optional[int]:
        if not self.star1 or not self.star2:
            return None
        return self.star2.get_star_ts - self.star1.get_star_ts


@dataclass
class AoCMember:
    last_star_ts: int
    local_score: int
    id: int
    global_score: int
    name: str
    stars: int
    completion_day_level: dict[int, AoCDay]

    def __post_init__(self):
        n = {}
        for k, args in self.completion_day_level.items():
            star1 = AoCStar(**args["1"]) if "1" in args else None
            star2 = AoCStar(**args["2"]) if "2" in args else None
            n[int(k)] = AoCDay(star1, star2)
        self.completion_day_level = n

    @staticmethod
    def parse_string(content: str) -> list["AoCMember"]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            print(e)
            return []
        return [AoCMember(**parsed["members"][key]) for key in parsed["members"]]


class AdventOfCode(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()
        self.aoc_path = "./data/aoc_data.json"
        self.data: list[AoCMember] = []
        if os.path.isfile(self.aoc_path):
            with open(self.aoc_path, "r") as f:
                self.data = AoCMember.parse_string(f.read())
        self.last_updated = 0

        # temp channel is so the linter stops complaining
        temp_channel = self.bot.get_channel(910450760234467328)
        if not temp_channel:
            temp_channel = self.bot.get_channel(1046168961189941369)
        assert isinstance(temp_channel, discord.abc.Messageable)
        self.aoc_channel = temp_channel
        self.aoc_loop.start()  # pylint: disable=no-member
        self.aoc_ping.start()  # pylint: disable=no-member

    def heartbeat(self):
        return self.aoc_loop.is_running()  # pylint: disable=no-member

    def cog_unload(self) -> None:
        self.aoc_loop.cancel()  # pylint: disable=no-member

    @tasks.loop(time=[dt_time(hour=h, minute=0) for h in range(24)])
    async def aoc_ping(self):
        await self.bot.wait_until_ready()
        dt = datetime.now(timezone("Europe/Zurich"))
        if dt.month == 12 and 1 <= dt.day <= 25 and dt.hour == 6 and dt.minute == 0:
            msg = f"Good Morning! It's time for **Advent of Code** day #{dt.day}!\n\
                [*Click here to get to the challenge*](https://adventofcode.com/2024/day/{dt.day})"
            embed = discord.Embed(description=msg, color=discord.Color.red())
            await self.aoc_channel.send("<@&1046388087837704293>", embed=embed)

    @tasks.loop(minutes=15)
    async def aoc_loop(self):
        # fetches the stats
        await self.bot.wait_until_ready()
        dt = datetime.now(timezone("Europe/Zurich"))
        if dt.month != 12:  # only scrape in december
            return
        session_key = os.getenv("AOC_SESSION_KEY")
        if not session_key:
            print("Session key not available. Skipping AoC request.")
            return

        cookie = {"session": session_key}
        email = os.getenv("EMAIL", "(no email given)")
        headers = {"User-Agent": f"https://github.com/markbeep/Lecturfier by {email}"}
        async with aiohttp.ClientSession(cookies=cookie, headers=headers) as session:
            async with session.get(
                "https://adventofcode.com/2024/leaderboard/private/view/1501119.json"
            ) as response:
                if response.status == 200:
                    response_data = await response.read()
                    # saves the file to the data folder
                    with open(self.aoc_path, "w") as f:
                        f.write(response_data.decode())
                    self.data = AoCMember.parse_string(response_data.decode())
                    self.last_updated = time.time()
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
            members = [mem for mem in d if len(mem.completion_day_level) > 0]

            if len(members) == 0:
                await ctx.reply(
                    "There are no stats for this leaderboard yet.", delete_after=10
                )
                await ctx.message.delete(delay=10)
                return

            def sort_by_local_score(mem: AoCMember):
                return mem.local_score

            members.sort(key=sort_by_local_score, reverse=True)

            msg = []
            for i, m in enumerate(members):
                msg.append(
                    f"`[{i+1}]` **{m.name}** - {m.local_score} points | {m.stars} stars"
                )
            pages = create_pages("\n".join(msg), 500)

            view = PagesView(
                self.bot,
                ctx,
                pages,
                ctx.author.id,
                "Total AoC Leaderboard",
                description=desc,
            )
            msg = await ctx.send(embed=view.embed, view=view)
            view.add_message(msg)
        elif star == -1 and 1 <= day <= 25:  # send the lb for that day
            pages = []
            members = [
                mem
                for mem in d
                if len(mem.completion_day_level) > 0
                and day in mem.completion_day_level.keys()
            ]

            ranking = self.sort_by_times(members, len(d), day)
            msg = []
            for i, (mem, points) in enumerate(ranking):
                star_diff = mem.completion_day_level[day].diff()
                if star_diff:
                    msg.append(
                        f"`[{i+1}]` **{mem.name}** - {points} points *[Star diff: {get_formatted_time_short(star_diff)}]*"
                    )
                else:
                    msg.append(
                        f"`[{i+1}]` **{mem.name}** - {points} points *[Star diff: unfinished]*"
                    )
            pages = create_pages("\n".join(msg), 500)

            if len(pages) > 0:
                view = PagesView(
                    self.bot,
                    ctx,
                    pages,
                    ctx.author.id,
                    f"Day {day} AoC Leaderboard",
                    description=desc,
                )
                msg = await ctx.send(embed=view.embed, view=view)
                view.add_message(msg)
            else:
                await ctx.reply("There are no stats for that day yet.", delete_after=10)
                await ctx.message.delete(delay=10)
        elif 1 <= day <= 25 and star in [1, 2]:  # sends the lb for that day and star
            pages = []
            if star == 1:
                members = [
                    mem
                    for mem in d
                    if len(mem.completion_day_level) > 0
                    and day in mem.completion_day_level.keys()
                    and mem.completion_day_level[day].star1
                ]
            else:
                members = [
                    mem
                    for mem in d
                    if len(mem.completion_day_level) > 0
                    and day in mem.completion_day_level.keys()
                    and mem.completion_day_level[day].star2
                ]

            def star_ts(mem: AoCMember) -> int:
                if star == 1 and mem.completion_day_level[day].star1:
                    return mem.completion_day_level[day].star1.get_star_ts
                elif mem.completion_day_level[day].star2:
                    return mem.completion_day_level[day].star2.get_star_ts
                else:
                    return 999999999999999999999

            members.sort(key=star_ts)

            min_time = min(
                mem.completion_day_level[day].star1.get_star_ts
                for mem in members
                if day in mem.completion_day_level
            )
            mytz = timezone("Europe/Zurich")
            dt = datetime.fromtimestamp(min_time).strftime(f"{day}/%m/%Y, 06:00:00")
            dt = datetime.strptime(dt, "%d/%m/%Y, %H:%M:%S")
            dt = mytz.normalize(mytz.localize(dt, is_dst=True))
            min_hour = dt.timestamp()

            msg = []
            for i, mem in enumerate(members):
                if star == 1 and mem.completion_day_level[day].star1:
                    form = get_formatted_time_short(
                        mem.completion_day_level[day].star1.get_star_ts - min_hour
                    )
                elif mem.completion_day_level[day].star2:
                    form = get_formatted_time_short(
                        mem.completion_day_level[day].star2.get_star_ts - min_hour
                    )
                else:
                    continue

                msg.append(f"`[{i+1}]` **{mem.name}** - {form}")
            pages = create_pages("\n".join(msg), 500)

            if len(pages) > 0:
                view = PagesView(
                    self.bot,
                    ctx,
                    pages,
                    ctx.author.id,
                    f"Day {day} Star {star} AoC Leaderboard",
                    description=desc,
                )
                msg = await ctx.send(embed=view.embed, view=view)
                view.add_message(msg)
            else:
                await ctx.reply(
                    "There are no stats for that day or star yet.", delete_after=10
                )
                await ctx.message.delete(delay=10)
        else:
            await ctx.reply(
                "Unrecognized command parameters. Please check the help page.",
                delete_after=10,
            )
            await ctx.delete(delay=10)

    def sort_by_times(
        self, members: list[AoCMember], total: int, day: int
    ) -> list[tuple[AoCMember, int]]:
        points = {m.id: 0 for m in members}
        mem_dict = {m.id: m for m in members}
        first_star = [m for m in members if m.completion_day_level[day].star1]
        second_star = [m for m in members if m.completion_day_level[day].star2]

        # sort by the person's submission time (earliest times at the end)
        def star1_ts(m: AoCMember) -> int:
            return m.completion_day_level[day].star1.get_star_ts

        def star2_ts(m: AoCMember) -> int:
            return m.completion_day_level[day].star2.get_star_ts

        first_star.sort(key=star1_ts)
        second_star.sort(key=star2_ts)

        for i, m in enumerate(first_star):
            points[m.id] = total - i
        for i, m in enumerate(second_star):
            points[m.id] += total - i

        final = sorted(
            points, key=lambda x: points[x], reverse=True
        )  # sorted by final points

        return [(mem_dict[id], points[id]) for id in final]


async def setup(bot):
    await bot.add_cog(AdventOfCode(bot))
