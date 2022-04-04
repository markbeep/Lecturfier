import asyncio
import io
import time
from datetime import datetime
from types import new_class

import aiohttp
import discord
from bs4 import BeautifulSoup as bs
from colorthief import ColorThief
from discord.ext import commands, tasks
from discord.ext.commands.cooldowns import BucketType
from PIL import UnidentifiedImageError
from pytz import timezone

from helper.log import log
from helper.sql import SQLFunctions


def calculate_points(confirmed_cases, guess):
    points_gotten = float(
        confirmed_cases - abs(confirmed_cases - guess)) / confirmed_cases * 1000
    if points_gotten > 1000:
        points_gotten = 1000
    if points_gotten < 0:
        points_gotten = 0
    return points_gotten


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.clap_counter = 0
        self.time = 0
        self.confirmed_cases = 0
        self.confirm_msg = None  # Confirmed message
        self.conn = SQLFunctions.connect()
        self.time_since_task_start = time.time()
        self.background_check_cases.start()
        self.sent_covid = False
        recent_covid_cases = SQLFunctions.get_config("COVID_Cases", self.conn)
        recent_covid_day = SQLFunctions.get_config("COVID_Day", self.conn)
        if len(recent_covid_cases) > 0:
            self.cases_today = recent_covid_cases[0]
        else:
            self.cases_today = 0
        if len(recent_covid_day) > 0:
            self.last_cases_day = recent_covid_day[0]
        else:
            self.last_cases_day = 0

    def heartbeat(self):
        return self.background_check_cases.is_running()

    def get_task(self):
        return self.background_check_cases

    @tasks.loop(seconds=10)
    async def background_check_cases(self):
        try:
            await self.bot.wait_until_ready()

            # only post on tuesdays
            dt = datetime.now(timezone("Europe/Zurich"))
            if dt.weekday() != 1:
                return

            # Send the covid guesser notification
            general_channel = 898674880864743444
            try:
                cur_time = datetime.now(
                    timezone("Europe/Zurich")).strftime("%a:%H:%M")
                if not self.sent_covid and "10:00" in cur_time and "Sat" not in cur_time and "Sun" not in cur_time:
                    self.sent_covid = True
                    general = self.bot.get_channel(general_channel)
                    msg = "Good Morning!\nGuess today's covid cases using `$g <guess>`!"
                    embed = discord.Embed(
                        description=msg, color=discord.Color.gold())
                    await general.send("<@&770968106679926868>", embed=embed)
                if "10:00" not in cur_time:
                    self.sent_covid = False
            except Exception as e:
                print(e)

            # checks the daily cases
            url = "https://www.covid19.admin.ch/api/data/context/history"
            response = {}
            async with aiohttp.ClientSession() as cs:
                async with cs.get(url) as r:
                    response = await r.json()
            # gets the last updated day from the website
            last_updated = response["dataContexts"][0]["date"]
            daily_url = response["dataContexts"][0]["dataContextUrl"]
            if len(last_updated) > 0:  # to make sure we even got anything
                day = int(last_updated.split("-")[2])
            else:
                owner = self.bot.get_user(205704051856244736)
                await owner.send(content=f"Covid cases failed updating. Last updated is empty:\n```{last_updated}```")
                raise ValueError

            # fetches the new cases
            # daily_url is of format https://www.covid19.admin.ch/api/data/DATE-random-gibberish/context
            # we want to go to this instead: https://www.covid19.admin.ch/api/data/DATE-random-gibberish/sources/COVID19Cases_geoRegion.json

            if self.last_cases_day != day:
                daily_url = daily_url.replace(
                    "context", "sources/COVID19Cases_geoRegion.json")
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(daily_url) as r:
                        response = await r.json()
                new_cases = -1
                for line in response:
                    # finds the cases for today's date and for all of switzrland and liechtenstein
                    if line["geoRegion"] == "CHFL" and line["datum"] == last_updated:
                        new_cases = line["entries_diff_last"]
                        break
                if new_cases == -1:
                    print("Wasn't able to get daily covid cases")
                    raise ValueError
                self.cases_today = new_cases
                self.last_cases_day = day
                guild = self.bot.get_guild(747752542741725244)
                if guild is None:
                    guild = self.bot.get_guild(237607896626495498)
                channel = guild.get_channel(general_channel)
                if channel is None:
                    channel = guild.get_channel(402563165247766528)
                await self.send_message(channel, new_cases)
                log("Daily cases have been updated", print_it=True)
                SQLFunctions.insert_or_update_config(
                    "COVID_Cases", new_cases, self.conn)
                SQLFunctions.insert_or_update_config(
                    "COVID_Day", day, self.conn)
                SQLFunctions.store_covid_cases(new_cases, conn=self.conn)
        except Exception as e:
            print(f"COVID loop messed up:\n{e}")
            await asyncio.sleep(20)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.content.lower().replace("!", "") == "hello there <@755781649643470868>":
            await message.channel.send(f"General Kenobi {message.author.mention}")
        if time.time() - self.time > 10:
            self.clap_counter = 0
        if "👏" in message.content:
            await message.add_reaction("👏")
            self.clap_counter += 1
            self.time = time.time()
            if self.clap_counter >= 3:
                self.clap_counter = 0
                await message.channel.send("👏\n👏\n👏")

    async def send_message(self, channel, confirmed_cases):
        points_list = await self.point_distribute(confirmed_cases)
        embed = discord.Embed(title="Covid Guesses",
                              description=f"Confirmed cases: `{confirmed_cases}`",
                              color=0xFF0000)
        c = 0
        msg = ""
        for p in range(len(points_list)):
            msg += f"{points_list[p]}\n"
            c += 1
            if c == 5:
                embed.add_field(name=f"Top {p + 1}", value=msg, inline=False)
                msg = ""
                c = 0
        if c != 0:
            embed.add_field(
                name=f"Top {len(points_list)}", value=msg, inline=False)
        # Pings the Covid Guesser Role on sending the leaderboard message
        await channel.send(content="<@&770968106679926868>", embed=embed)

    async def point_distribute(self, confirmed_cases):
        log(f"Starting COVID points distribution", "COVID")
        lb_messages = []
        rank = 1
        guessers = SQLFunctions.get_covid_guessers(self.conn, guessed=True)
        for g in guessers:
            g.TempPoints = int(calculate_points(confirmed_cases, g.NextGuess))
        # Sort the guessers by their gotten points
        guessers.sort(key=lambda x: x.TempPoints, reverse=True)
        for g in guessers:
            msg = f"**{rank}:** <@{g.member.DiscordUserID}> got {g.TempPoints} points *(guess: {g.NextGuess})*"
            rank += 1
            lb_messages.append(msg)
        SQLFunctions.clear_covid_guesses(
            users=guessers, increment=True, conn=self.conn)

        return lb_messages

    async def send_leaderboard(self, ctx, average=False):
        async with ctx.typing():
            try:
                """
                Creates a list with sorted dicts
                """
                guessers = SQLFunctions.get_covid_guessers(self.conn)
                if average:
                    title = "Average"
                    max_count = 0
                    # gets the max guess count of the server
                    for g in guessers:
                        max_count = max(g.GuessCount, max_count)
                    for g in guessers:
                        # We assign the weighted average to the TempPoints variable
                        # for every guess less than the max your weighted average goes down by 2
                        g.TempPoints = g.average - (max_count - g.GuessCount)*2
                    guessers.sort(key=lambda x: x.TempPoints, reverse=True)
                else:
                    title = "'rona"
                    guessers.sort(
                        key=lambda x: x.TotalPointsAmount, reverse=True)

                """
                Creates the message content
                """
                i = 1
                cont = ""
                for g in guessers:
                    if i == 1:
                        cont += "<:gold:944970589158920222>"
                    elif i == 2:
                        cont += "<:silver:944970589133766717>"
                    elif i == 3:
                        cont += "<:bronze:944970589481869352>"
                    else:
                        cont += "<:invisible:944970589196652564>"

                    if average:
                        # Show users with the best weighted average
                        cont += f"**{i}.** <@{g.member.DiscordUserID}> | AVG Points: **{round(g.average, 2)}** *({round(g.TempPoints, 2)})*\n\n"

                    else:
                        # Show users with the most points
                        cont += f"**{i}.** <@{g.member.DiscordUserID}> | Points: {g.TotalPointsAmount}\n\n"
                    i += 1
                    if i >= 11:
                        break
                guild_name = ctx.message.guild.name
                embed = discord.Embed(
                    title=f"Top {title} Guessers: **{guild_name}** <:coronavirus:767839970303410247>",
                    description=cont, color=0x00FF00)
                if average:
                    embed.set_footer(
                        text="Ordered by decay (value to the right). Left is actual average.")
            except KeyError:
                embed = discord.Embed(
                    title=f"Error", description="There are no covid guessing points yet", color=0xFF0000)
        await ctx.send(embed=embed)

    @commands.cooldown(1, 10, BucketType.user)
    @commands.guild_only()
    @commands.command(aliases=["g"], usage="guess [guess amount | lb | avg]")
    async def guess(self, ctx, number=None, confirmed_number=None):
        """
        Daily covid cases guessing game. You guess how many covid cases will be reported by the BAG and depending \
        on how close you are, you get more points.
        `$guess avg` to get a leaderboard with average guessing scores
        `$guess lb` to get the total leaderboard with all points
        Leaderboard aliases: `leaderboard`, `lb`, `top`, `best`, `ranking`
        Average aliases: `avg`, `average`
        """

        leaderboard_aliases = ["leaderboard", "lb", "top", "best", "ranking"]
        average_aliases = ["avg", "average"]

        await ctx.message.delete()

        if number is None:
            # No values were given in the command:
            guesser = SQLFunctions.get_covid_guessers(
                self.conn, discord_user_id=ctx.message.author.id, guild_id=ctx.message.guild.id)
            if len(guesser) == 0:
                await ctx.send(f"{ctx.message.author.mention}, you have not made any guesses yet. Guess with `$guess <integer>`.", delete_after=7)
                return
            async with ctx.typing():
                guesser = guesser[0]
                image_url = str(ctx.message.author.avatar_url_as(format="png"))
                try:
                    async with aiohttp.ClientSession() as cs:
                        async with cs.get(image_url) as r:
                            buffer = io.BytesIO(await r.read())
                    color_thief = ColorThief(buffer)
                    dominant_color = color_thief.get_palette(
                        color_count=2, quality=10)[0]
                    hex_color = int('0x%02x%02x%02x' % dominant_color, 0)
                except UnidentifiedImageError as e:
                    hex_color = 0x808080
                already_guessed = "<a:cross:944970382694314044>"
                if guesser.NextGuess is not None:
                    already_guessed = "<a:checkmark:944970382522351627>"
                embed = discord.Embed(title="Covid Guesser Profile",
                                      description=f"**User:** <@{ctx.message.author.id}>\n"
                                                  f"**Total Points:** `{guesser.TotalPointsAmount}`\n"
                                                  f"**Total Guesses:** `{guesser.GuessCount}`\n"
                                                  f"**Average:** `{round(guesser.average, 2)}`\n"
                                                  f"**Guessed:** {already_guessed}",
                                      color=hex_color)
                embed.set_thumbnail(url=image_url)
            await ctx.send(embed=embed, delete_after=15)
        else:
            try:
                if number.lower() == "confirm" and ctx.author.guild_permissions.kick_members:
                    # if the number of cases gets confirmed

                    if confirmed_number is None:
                        raise ValueError
                    self.confirmed_cases = int(confirmed_number)
                    if self.confirm_msg is not None:
                        # Deletes the previous confirm message if there are multiple
                        await self.confirm_msg.delete()
                        self.confirm_msg = None
                    self.confirm_msg = await ctx.send(f"Confirmed cases: {self.confirmed_cases}\nA mod or higher, press the <a:checkmark:944970382522351627> to verify.")
                    await self.confirm_msg.add_reaction("<a:checkmark:944970382522351627>")
                    await self.confirm_msg.add_reaction("<a:cross:944970382694314044>")
                elif number.lower() in leaderboard_aliases:
                    await self.send_leaderboard(ctx)
                elif number.lower() in average_aliases:
                    await self.send_leaderboard(ctx, True)
                else:
                    number = int(number)
                    if number < 0:
                        raise ValueError
                    if number > 1000000:
                        number = 1000000
                    member = SQLFunctions.get_or_create_discord_member(
                        ctx.message.author, conn=self.conn)
                    SQLFunctions.insert_or_update_covid_guess(
                        member, number, conn=self.conn)
                    await ctx.send(f"{ctx.message.author.mention}, received your guess.", delete_after=7)
            except ValueError:
                await ctx.send(f"{ctx.message.author.mention}, no proper positive integer given.", delete_after=7)
                raise discord.ext.commands.errors.BadArgument


def setup(bot):
    bot.add_cog(Games(bot))
