import discord
from discord.ext import commands
from datetime import datetime
import time
from helper.log import log
from PIL import UnidentifiedImageError
import aiohttp
from bs4 import BeautifulSoup as bs
import asyncio
from pytz import timezone
from helper import handySQL
from sqlite3 import Error
import io
from colorthief import ColorThief
from discord.ext.commands.cooldowns import BucketType


def calculate_points(confirmed_cases, guess):
    points_gotten = float(confirmed_cases - abs(confirmed_cases - guess)) / confirmed_cases * 1000
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
        with open("./data/covid19.txt") as f:
            self.cases_today = int(f.read())
        self.db_path = "./data/discord.db"
        self.conn = handySQL.create_connection(self.db_path)
        self.time_heartbeat = 0
        self.time_since_task_start = time.time()
        self.task = self.bot.loop.create_task(self.background_check_cases())

    def heartbeat(self):
        return self.time_heartbeat

    def get_task(self):
        return self.task

    def get_connection(self):
        """
        Retreives the current database connection
        :return: Database Connection
        """
        if self.conn is None:
            self.conn = handySQL.create_connection(self.db_path)
        return self.conn

    async def background_check_cases(self):
        counter = 0
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.time_heartbeat = time.time()
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://www.covid19.admin.ch/en/overview") as r:
                    response = await r.read()
            soup = bs(response.decode('utf-8'), "html.parser")
            new_cases = int(soup.find_all("span", class_="bag-key-value-list__entry-value")[0].get_text().replace(" ", ""))
            if self.cases_today != new_cases:
                self.cases_today = new_cases
                with open("./data/covid19.txt", "w") as f:
                    f.write(str(new_cases))
                log("Daily cases have been updated", "COVID")
                guild = self.bot.get_guild(747752542741725244)
                channel = guild.get_channel(747752542741725247)
                await self.send_message(channel, guild, new_cases)
            await asyncio.sleep(10)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            if message.content == "Hello there <@!755781649643470868>":
                await message.channel.send("General kenobi <@!306523617188118528>")
            return
        if time.time() - self.time > 10:
            self.clap_counter = 0
        if "👏" in message.content:
            await message.add_reaction("👏")
            self.clap_counter += 1
            self.time = time.time()
            if self.clap_counter >= 3:
                self.clap_counter = 0
                await message.channel.send("👏\n👏\n👏")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, member):
        if member.bot:
            return
        if member.guild_permissions.kick_members:
            if len(reaction.message.embeds) > 0 and reaction.message.embeds[0].title is not discord.Embed.Empty and "Covid Guesser Profile" in reaction.message.embeds[0].title:
                if str(reaction) == "<:checkmark:776717335242211329>":
                    await self.confirm_msg.delete()
                    self.confirm_msg = None
                    await self.send_message(reaction.message.channel, reaction.message.guild, self.confirmed_cases)
                elif str(reaction) == "<:xmark:776717315139698720>":
                    await self.confirm_msg.delete()
                    self.confirm_msg = None
                    self.confirmed_cases = 0
                    await reaction.message.channel.send("Confirmed cases amount was stated as being wrong and was therefore deleted.")

    async def send_message(self, channel, guild, confirmed_cases):
        points_list = await self.point_distribute(guild, confirmed_cases)
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
            embed.add_field(name=f"Top {len(points_list)}", value=msg, inline=False)
        await channel.send(embed=embed)

    async def point_distribute(self, guild, confirmed_cases):
        log(f"Starting COVID points distribution", "COVID")
        conn = self.get_connection()
        lb_messages = []
        rank = 1
        for row in conn.execute("SELECT UniqueMemberID, NextGuess FROM CovidGuessing WHERE NextGuess IS NOT NULL"):
            print(row)
            conn.execute("UPDATE CovidGuessing SET TempPoints=? WHERE UniqueMemberID=?", (int(calculate_points(confirmed_cases, row[1])), row[0]))
            conn.commit()
        for row in conn.execute(""" SELECT
                                        DM.DiscordUserID,
                                        CG.UniqueMemberID,
                                        CG.NextGuess,
                                        CG.TempPoints
                                    FROM
                                        CovidGuessing as CG
                                    INNER JOIN
                                        DiscordMembers as DM
                                        on CG.UniqueMemberID=DM.UniqueMemberID
                                    WHERE CG.NextGuess IS NOT NULL AND DM.DiscordGuildID=?
                                    ORDER BY CG.TempPoints DESC""", (guild.id,)):
            print(row)
            msg = f"**{rank}:** <@{row[0]}> got {row[3]} points *(guess: {row[2]})*"
            rank += 1
            lb_messages.append(msg)
        conn.execute("""UPDATE
                            CovidGuessing
                        SET
                            TotalPointsAmount=TotalPointsAmount+TempPoints,
                            GuessCount=GuessCount+1,
                            TempPoints=NULL,
                            NextGuess=NULL
                        WHERE
                            TempPoints IS NOT NULL""")
        conn.commit()

        return lb_messages

    async def send_leaderboard(self, ctx, average=False):
        async with ctx.typing():
            try:
                """
                Creates a list with sorted dicts
                """
                conn = self.get_connection()
                c = conn.cursor()
                try:
                    guild_id = ctx.message.guild.id
                except AttributeError:
                    guild_id = 0
                if average:
                    title = "Average"
                    sql = """   SELECT DM.DiscordUserID, CG.TotalPointsAmount, CG.GuessCount
                                FROM CovidGuessing CG
                                INNER JOIN DiscordMembers DM on CG.UniqueMemberID=DM.UniqueMemberID
                                WHERE DM.DiscordGuildID=?
                                ORDER BY TotalPointsAmount/GuessCount DESC"""
                    c.execute(sql, (guild_id,))
                    user_rows = c.fetchall()
                else:
                    title = "'rona"
                    sql = """   SELECT DM.DiscordUserID, CG.TotalPointsAmount, CG.GuessCount
                                                    FROM CovidGuessing CG
                                                    INNER JOIN DiscordMembers DM on CG.UniqueMemberID=DM.UniqueMemberID
                                                    WHERE DM.DiscordGuildID=?
                                                    ORDER BY TotalPointsAmount DESC"""
                    c.execute(sql, (guild_id,))
                    user_rows = c.fetchall()

                """
                Creates the message content
                """
                i = 1
                cont = ""
                for profile in user_rows:
                    if i == 1:
                        cont += "<:gold:413030003639582731>"
                    elif i == 2:
                        cont += "<:silver:413030018881552384>"
                    elif i == 3:
                        cont += "<:bronze:413030030076149776>"
                    else:
                        cont += "<:invisible:413030446327267328>"

                    if average:
                        if profile[2] != 0:
                            avg = round(profile[1] / profile[2])
                        else:
                            avg = 0
                        cont += f"**{i}.** <@{profile[0]}> | AVG Points: {avg}\n\n"

                    else:
                        cont += f"**{i}.** <@{profile[0]}> | Points: {profile[1]}\n\n"
                    i += 1
                    if i >= 11:
                        break
                if ctx.message.guild is None:
                    guild_name = "Direct Message Channel"
                else:
                    guild_name = ctx.message.guild.name
                embed = discord.Embed(
                    title=f"Top {title} Guessers: **{guild_name}** <:coronavirus:767839970303410247>",
                    description=cont, color=0x00FF00)
            except KeyError:
                embed = discord.Embed(title=f"Error", description="There are no covid guessing points yet", color=0xFF0000)
        await ctx.send(embed=embed)

    @commands.cooldown(4, 10, BucketType.user)
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

        # Get the current hour and minute
        hour = int(datetime.now(timezone("Europe/Zurich")).strftime("%H"))
        minute = int(datetime.now(timezone("Europe/Zurich")).strftime("%M"))

        # Gets the proper guild id (0 if in DM)
        try:
            guild_obj = ctx.message.guild
        except AttributeError:
            guild_obj = None

        await ctx.message.delete()

        conn = self.get_connection()
        c = conn.cursor()
        uniqueID = handySQL.get_or_create_member(conn, ctx.message.author, guild_obj)

        if number is None:
            # No values were given in the command:
            async with ctx.typing():
                c.execute("SELECT TotalPointsAmount, GuessCount, NextGuess FROM CovidGuessing WHERE UniqueMemberID=?", (uniqueID,))
                row = c.fetchone()
                if row is None:
                    await ctx.send(f"{ctx.message.author.mention}, you have not made any guesses yet. Guess with `$guess <integer>`.", delete_after=7)
                    return
                image_url = f"https://robohash.org/{uniqueID}.png"
                try:
                    async with aiohttp.ClientSession() as cs:
                        async with cs.get(image_url) as r:
                            buffer = io.BytesIO(await r.read())
                    color_thief = ColorThief(buffer)
                    dominant_color = color_thief.get_palette(color_count=2, quality=10)[0]
                    hex_color = int('0x%02x%02x%02x' % dominant_color, 0)
                except UnidentifiedImageError as e:
                    hex_color = 0x808080
                if row[1] != 0:
                    avg = round(row[0] / row[1])
                    acc = round(avg/10, 2)
                else:
                    avg = 0
                    acc = 0.0
                embed = discord.Embed(title="Covid Guesser Profile",
                                      description=f"**User:** <@{ctx.message.author.id}>\n"
                                                  f"**Total Points:** `{row[0]}`\n"
                                                  f"**Total Guesses:** `{row[1]}`\n"
                                                  f"**Average:** `{avg}`\n"
                                                  f"**Accuracy:** `{acc}`%\n"
                                                  f"**Next Guess:** `{row[2]}`",
                                      color=hex_color)
                embed.set_thumbnail(url=image_url)
            await ctx.send(embed=embed, delete_after=7)
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
                    self.confirm_msg = await ctx.send(f"Confirmed cases: {self.confirmed_cases}\nA mod or higher, press the <:checkmark:769279808244809798> to verify.")
                    await self.confirm_msg.add_reaction("<:checkmark:776717335242211329>")
                    await self.confirm_msg.add_reaction("<:xmark:776717315139698720>")
                elif number.lower() in leaderboard_aliases:
                    await self.send_leaderboard(ctx)
                elif number.lower() in average_aliases:
                    await self.send_leaderboard(ctx, True)
                elif 13 <= hour < 16:
                    await ctx.send("Can't guess from 13:00 till 16:00. The confirmed amount of cases will be released soon.", delete_after=7)
                else:
                    number = int(number)
                    if number < 0:
                        raise ValueError
                    if number > 1000000:
                        number = 1000000
                    try:
                        c.execute("INSERT INTO CovidGuessing(UniqueMemberID, NextGuess) VALUES(?,?)", (uniqueID, number))
                    except Error as e:
                        c.execute("UPDATE CovidGuessing SET NextGuess=? WHERE UniqueMemberID=?", (number, uniqueID))
                    conn.commit()
                    await ctx.send(f"{ctx.message.author.mention}, received your guess.", delete_after=7)
            except ValueError:
                await ctx.send(f"{ctx.message.author.mention}, no proper positive integer given.", delete_after=7)
                raise discord.ext.commands.errors.BadArgument


def setup(bot):
    bot.add_cog(Games(bot))
