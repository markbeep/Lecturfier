import discord
from discord.ext import commands, tasks
from datetime import datetime
import time
from helper.log import log
from PIL import UnidentifiedImageError
import aiohttp
from bs4 import BeautifulSoup as bs
from pytz import timezone
from helper.sql import SQLFunctions
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
        self.conn = SQLFunctions.connect()
        self.time_since_task_start = time.time()
        self.background_check_cases.start()
        self.cases_updated = False

    def heartbeat(self):
        return self.background_check_cases.is_running()

    def get_task(self):
        return self.background_check_cases

    @tasks.loop(seconds=10)
    async def background_check_cases(self):
        await self.bot.wait_until_ready()
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
            if guild is None:
                return
            channel = guild.get_channel(747752542741725247)
            await self.send_message(channel, new_cases)
        self.cases_updated = True

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
                    await self.send_message(reaction.message.channel, self.confirmed_cases)
                elif str(reaction) == "<:xmark:776717315139698720>":
                    await self.confirm_msg.delete()
                    self.confirm_msg = None
                    self.confirmed_cases = 0
                    await reaction.message.channel.send("Confirmed cases amount was stated as being wrong and was therefore deleted.")

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
            embed.add_field(name=f"Top {len(points_list)}", value=msg, inline=False)
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
        SQLFunctions.clear_covid_guesses(increment=True, conn=self.conn)

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
                    guessers.sort(key=lambda x: x.TotalPointsAmount, reverse=True)

                """
                Creates the message content
                """
                i = 1
                cont = ""
                for g in guessers:
                    if i == 1:
                        cont += "<:gold:413030003639582731>"
                    elif i == 2:
                        cont += "<:silver:413030018881552384>"
                    elif i == 3:
                        cont += "<:bronze:413030030076149776>"
                    else:
                        cont += "<:invisible:413030446327267328>"

                    if average:
                        # Show users with the best weighted average
                        cont += f"**{i}.** <@{g.member.DiscordUserID}> | AVG Points: **{g.average}** *({g.TempPoints})*\n\n"

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
                    embed.set_footer(text="Ordered by decay (value to the right). Left is actual average.")
            except KeyError:
                embed = discord.Embed(title=f"Error", description="There are no covid guessing points yet", color=0xFF0000)
        await ctx.send(embed=embed)

    @commands.cooldown(4, 10, BucketType.user)
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

        # Get the current hour and minute
        hour = int(datetime.now(timezone("Europe/Zurich")).strftime("%H"))
        minute = int(datetime.now(timezone("Europe/Zurich")).strftime("%M"))

        await ctx.message.delete()


        if number is None:
            # No values were given in the command:
            async with ctx.typing():
                guesser = SQLFunctions.get_covid_guessers(self.conn, discord_user_id=ctx.message.author.id)
                if len(guesser) is None:
                    await ctx.send(f"{ctx.message.author.mention}, you have not made any guesses yet. Guess with `$guess <integer>`.", delete_after=7)
                    return
                guesser = guesser[0]
                image_url = f"https://robohash.org/{guesser.member.UniqueMemberID}.png"
                try:
                    async with aiohttp.ClientSession() as cs:
                        async with cs.get(image_url) as r:
                            buffer = io.BytesIO(await r.read())
                    color_thief = ColorThief(buffer)
                    dominant_color = color_thief.get_palette(color_count=2, quality=10)[0]
                    hex_color = int('0x%02x%02x%02x' % dominant_color, 0)
                except UnidentifiedImageError as e:
                    hex_color = 0x808080
                embed = discord.Embed(title="Covid Guesser Profile",
                                      description=f"**User:** <@{ctx.message.author.id}>\n"
                                                  f"**Total Points:** `{guesser.TotalPointsAmount}`\n"
                                                  f"**Total Guesses:** `{guesser.GuessCount}`\n"
                                                  f"**Average:** `{guesser.average}`",
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
                    member = SQLFunctions.get_or_create_discord_member(ctx.message.author, conn=self.conn)
                    SQLFunctions.insert_or_update_covid_guess(member, number, conn=self.conn)
                    await ctx.send(f"{ctx.message.author.mention}, received your guess.", delete_after=7)
            except ValueError:
                await ctx.send(f"{ctx.message.author.mention}, no proper positive integer given.", delete_after=7)
                raise discord.ext.commands.errors.BadArgument


def setup(bot):
    bot.add_cog(Games(bot))
