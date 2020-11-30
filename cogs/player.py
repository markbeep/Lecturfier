import discord
from discord.ext import commands
from datetime import datetime
import psutil
import time
import random
from sympy.solvers import solve
from sympy import symbols, simplify
import multiprocessing
from helper.log import log
import string
import hashlib
import json
import aiohttp
from bs4 import BeautifulSoup as bs
import asyncio


# TODO Source command that displays the source code of a command using the inspect library
# labels: idea
class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.script_start = time.time()
        self.clap_counter = 0
        self.time = 0
        self.covid_guesses = {}
        self.confirmed_cases = 0
        self.confirm_msg = None  # Confirmed message
        with open("./data/covid_guesses.json") as f:
            self.covid_points = json.load(f)
        with open("./data/covid19.txt") as f:
            self.cases_today = int(f.read())

        self.task = self.bot.loop.create_task(self.background_check_cases())

    def heartbeat(self):
        return self.task

    async def background_check_cases(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://www.covid19.admin.ch/en/overview") as r:
                    response = await r.read()
            soup = bs(response.decode('utf-8'), "html.parser")
            new_cases = int(soup.find_all("span", class_="bag-key-value-list__entry-value")[0].get_text())
            if self.cases_today != new_cases:
                self.cases_today = new_cases
                self.confirmed_cases = new_cases
                with open("./data/covid19.txt", "w") as f:
                    f.write(str(new_cases))
                log("Daily cases have been updated", "COVID")
                guild = self.bot.get_guild(747752542741725244)
                channel = guild.get_channel(747752542741725247)
                await self.send_message(channel, guild)
            await asyncio.sleep(10)

    @commands.Cog.listener()
    async def on_ready(self):
        self.script_start = time.time()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            if message.content == "Hello there <@!<@!755781649643470868>>":
                await message.channel.send("General kenobi <@!306523617188118528>")
            return
        if "<@!755781649643470868>" in message.content:
            for i in range(5):
                await message.author.send(message.author.mention)
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
            if str(reaction) == "<:checkmark:776717335242211329>":
                await self.confirm_msg.delete()
                self.confirm_msg = None
                await self.send_message(reaction.message.channel, reaction.message.guild)
            elif str(reaction) == "<:xmark:776717315139698720>":
                await self.confirm_msg.delete()
                self.confirm_msg = None
                self.confirmed_cases = 0
                await reaction.message.channel.send("Confirmed cases amount was stated as being wrong and was therefore deleted.")

    async def send_message(self, channel, guild):
        points_list = await self.point_distribute(guild)
        embed = discord.Embed(title="Covid Guesses",
                              description=f"Confirmed cases: `{self.confirmed_cases}`",
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
        await self.bot.change_presence(activity=discord.Activity(name=f'closely', type=discord.ActivityType.watching))
        self.confirmed_cases = 0

    async def point_distribute(self, guild):
        # if the server key is not in the file yet
        if str(guild.id) not in self.covid_points:
            self.covid_points[str(guild.id)] = {}

        sorted_keys = {}
        points = []
        log(f"Starting COVID points distribution", "COVID")
        for u in self.covid_guesses:
            user_id = u
            difference = abs(self.confirmed_cases - self.covid_guesses[user_id])
            points_gotten = float(self.confirmed_cases - difference) / self.confirmed_cases * 1000
            if points_gotten < 0:
                points_gotten = 0
            sorted_keys[user_id] = points_gotten

            # if the user has no key entry in the covid_guesses.json yet
            if user_id not in self.covid_points[str(guild.id)]:
                self.covid_points[str(guild.id)][user_id] = [round(points_gotten, 1), round(points_gotten, 1), 1]
            else:
                self.covid_points[str(guild.id)][user_id][0] += round(points_gotten, 1)
                self.covid_points[str(guild.id)][user_id][1] += round(points_gotten, 1)
                self.covid_points[str(guild.id)][user_id][2] += 1

        sorted_keys = sorted(sorted_keys.items(), key=lambda x: x[1], reverse=True)
        rank = 1
        for key in sorted_keys:
            user_id = key[0]
            member = guild.get_member(int(user_id))
            msg = f"**{rank}:** {member.mention} got {int(round(key[1]))} points *(guess: {self.covid_guesses[user_id]})*"
            points.append(msg)
            rank += 1

        with open("./data/covid_guesses.json", "w") as f:
            json.dump(self.covid_points, f, indent=2)
        log("Saved covid_guesses.json", "COVID")

        self.covid_guesses = {}
        return points

    async def send_leaderboard(self, ctx, average=False):
        async with ctx.typing():
            try:
                """
                Creates a list with sorted dicts
                """
                temp = {}
                if average:
                    title = "Average"
                    for user in self.covid_points[str(ctx.message.guild.id)].keys():
                        if self.covid_points[str(ctx.message.guild.id)][user][2] != 0:
                            temp[user] = round(self.covid_points[str(ctx.message.guild.id)][user][1] / self.covid_points[str(ctx.message.guild.id)][user][2])
                        else:
                            temp[user] = 0
                else:
                    title = "'rona"
                    for user in self.covid_points[str(ctx.message.guild.id)].keys():
                        temp[user] = self.covid_points[str(ctx.message.guild.id)][user][0]
                temp = sorted(temp.items(), key=lambda v: v[1], reverse=True)

                """
                Creates the message content
                """
                i = 1
                cont = ""
                for profile in temp:
                    member = ctx.message.guild.get_member(int(profile[0]))
                    if member is None:
                        pass
                    else:
                        if i == 1:
                            cont += "<:gold:413030003639582731>"
                        elif i == 2:
                            cont += "<:silver:413030018881552384>"
                        elif i == 3:
                            cont += "<:bronze:413030030076149776>"
                        else:
                            cont += "<:invisible:413030446327267328>"

                        if average:
                            if self.covid_points[str(ctx.message.guild.id)][str(member.id)][2] != 0:
                                avg = round(self.covid_points[str(ctx.message.guild.id)][str(member.id)][1] /
                                            self.covid_points[str(ctx.message.guild.id)][str(member.id)][2])
                            else:
                                avg = 0
                            cont += f"**{i}.** {member.mention} | Points: {avg}\n\n"
                        else:
                            cont += f"**{i}.** {member.mention} | Points: {round(self.covid_points[str(ctx.message.guild.id)][str(member.id)][0])}\n\n"
                        i += 1
                        if i >= 11:
                            break
                embed = discord.Embed(
                    title=f"Top {title} Guessers: **{ctx.message.guild.name}** <:coronavirus:767839970303410247>",
                    description=cont, color=0x00FF00)
            except KeyError:
                embed = discord.Embed(title=f"Error", description="There are no covid guessing points yet", color=0xFF0000)
        await ctx.send(embed=embed)

    @commands.command(aliases=["g"])
    async def guess(self, ctx, number=None, confirmed_number=None):
        total_points = 0
        avg = 0
        amt = 0
        if str(ctx.message.guild.id) in self.covid_points and str(ctx.message.author.id) in self.covid_points[str(ctx.message.guild.id)]:
            total_points = self.covid_points[str(ctx.message.guild.id)][str(ctx.message.author.id)][0]
            avg = self.covid_points[str(ctx.message.guild.id)][str(ctx.message.author.id)][1]
            amt = self.covid_points[str(ctx.message.guild.id)][str(ctx.message.author.id)][2]
        if str(ctx.message.guild.id) not in self.covid_points:
            self.covid_points[ctx.message.guild.id] = {}
        # Send last guess from user
        leaderboard_aliases = ["leaderboard", "lb", "top", "best", "ranking"]
        average_aliases = ["avg", "average"]
        if number is None:
            if amt != 0:
                avg = round(avg/amt)
            if str(ctx.message.author.id) in self.covid_guesses:
                await ctx.send(f"{ctx.message.author.mention}, "
                               f"your final guess is `{self.covid_guesses[str(ctx.message.author.id)]}`.\n"
                               f"Your total points: {int(round(total_points))} | Average points/guess: {avg} | Total Guesses: {amt}", delete_after=7)
                await ctx.message.delete()
            else:
                await ctx.send(f"{ctx.message.author.mention}, you don't have a guess yet.\n"
                               f"Your total points: {int(round(total_points))} | Average points/guess: {avg} | Total Guesses: {amt}", delete_after=7)
                await ctx.message.delete()
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
                else:
                    number = int(number)
                    if number < 0:
                        raise ValueError
                    if number > 1000000:
                        number = 1000000
                    user_count = len(self.covid_guesses)
                    self.covid_guesses[str(ctx.message.author.id)] = number
                    await ctx.send(f"{ctx.message.author.mention}, your new guess is: `{number}`", delete_after=7)
                    await ctx.message.delete()

                    new_user_count = len(self.covid_guesses)
                    if new_user_count > user_count:
                        await self.bot.change_presence(activity=discord.Activity(name=f'{new_user_count} guessers', type=discord.ActivityType.watching))
            except ValueError:
                await ctx.send(f"{ctx.message.author.mention}, no proper positive integer given.", delete_after=7)
                await ctx.message.delete()
                raise discord.ext.commands.errors.BadArgument

    @commands.command(aliases=["source", "code"])
    async def info(self, ctx):
        """
        Get some info about the bot
        """
        async with ctx.typing():
            b_time = time_up(time.time() - self.script_start)  # uptime of the script
            s_time = time_up(seconds_elapsed())  # uptime of the pc
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory()

            cont = f"**Instance uptime: **`{b_time}`\n" \
                   f"**Computer uptime: **`{s_time}`\n" \
                   f"**CPU: **`{round(cpu)}%` | **RAM: **`{round(ram.percent)}%`\n"\
                   f"**Discord.py Rewrite Version:** `{discord.__version__}`\n" \
                   f"**Bot source code:** [Click here for source code](https://github.com/markbeep/Lecturfier)"
            embed = discord.Embed(title="Bot Information:", description=cont, color=0xD7D7D7,
                                  timestamp=datetime.now())
            embed.set_footer(text=f"Called by {ctx.author.display_name}")
            embed.set_thumbnail(url=self.bot.user.avatar_url)
            embed.set_author(name=self.bot.user.display_name, icon_url=self.bot.user.avatar_url)
        await ctx.send(embed=embed)

    @commands.command()
    async def calc(self, ctx):
        if "iq" in ctx.message.content.lower():
            await ctx.send(f"Stop asking for your fucking IQ. Nobody cares about your {random.randint(1,10)} IQ")
            return
        await ctx.send(f"{ctx.message.author.mention}: I guess {random.randrange(-1000000, 1000000)}. Could be wrong tho...")

    def simp(self, eq):
        eq = simplify(eq)
        return eq

    @commands.command()
    async def solve(self, ctx, *num1):
        """
        Solves an equation and then sends it. Deprecated, as it causes the bot to crash
        :param ctx: message object
        :param num1: equation to solve
        :return: None
        """
        if not await self.bot.is_owner(ctx.author):
            raise discord.ext.commands.errors.NotOwner
        try:
            inp = " ".join(num1)
            cont = inp.replace(" ", "").replace("^", "**")

            sides = cont.split("=")
            if "=" in cont:
                fixed = f"{sides[0]} - ({sides[1]})"
            else:
                fixed = sides[0]

            p = multiprocessing.Process(target=self.simp, name="simplify", args=(fixed,))
            p.start()

            p.join(5)

            if p.is_alive():
                await ctx.send("Solving took more than 2 seconds and was therefore stopped. Probably because of a too big of an input.")
                # Terminate simp
                p.terminate()
                p.join()
                return
            log(fixed, "SOLVE")

            variables = []
            for element in list(fixed):
                if element.isalpha() and symbols(element) not in variables:
                    variables.append(symbols(element))

            solution = ""
            for v in variables:
                log(v, "SOLVE")
                solved = solve(fixed, v)
                log(solved, "SOLVE")
                if len(solved) > 0:
                    solution += f"{v} = {{{str(solved).replace('[', '').replace(']', '')}}}\n"

            if len(solution) > 3000:
                await ctx.send("Lol there are too many numbers in that solution to display here on discord...")
                return
            embed = discord.Embed(title=f"Solved {str(fixed).replace('**', '^')}", description=solution.replace('**', '^'))
            await ctx.send(embed=embed)
        except ValueError:
            await ctx.send("Wrong syntax. You probably forgot some multiplication signs (*) or you're trying too hard to break the bot.")
        except IndexError:
            await ctx.send("No answer. Whoops")
        except NotImplementedError:
            await ctx.send("You've bested me. Don't have an algorithm to solve that yet.")

    def random_string(self, n):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=n))

    @commands.command()
    async def token(self, ctx):
        token = self.random_string(24) + "." + self.random_string(6) + "." + self.random_string(27)
        embed = discord.Embed(title="Bot Token", description=f"||`{token}`||")
        await ctx.send(embed=embed)

    @commands.command(aliases=["pong", "ding"])
    async def ping(self, ctx):
        """
        Check the ping of the bot
        """
        title = "Pong!"
        if "pong" in ctx.message.content.lower():
            title = "Ping!"
        if "pong" in ctx.message.content.lower() and "ping" in ctx.message.content.lower():
            title = "Ding?"
        if "ding" in ctx.message.content.lower():
            title = "*slap!*"

        embed = discord.Embed(
            title=f"{title} 🏓",
            description=f"🌐 Ping: \n"
                        f"❤ HEARTBEAT:")

        start = time.perf_counter()
        ping = await ctx.send(embed=embed)
        end = time.perf_counter()
        embed = discord.Embed(
            title=f"{title} 🏓",
            description=f"🌐 Ping: `{round((end-start)*1000)}` ms\n"
                        f"❤ HEARTBEAT: `{round(self.bot.latency * 1000)}` ms")
        await ping.edit(embed=embed)

    @commands.command(aliases=["cypher"])
    async def cipher(self, ctx, amount=None, *msg):
        printable = list(string.printable)
        printable = printable[0:-5]
        if len(msg) == 0:
            await ctx.send("No message specified.")
            raise discord.ext.commands.errors.BadArgument
        try:
            amount = int(amount)
        except ValueError:
            await ctx.send("Amount is not an int.")
            raise discord.ext.commands.errors.BadArgument
        msg = " ".join(msg)
        encoded_msg = ""
        amount = amount % len(printable)
        for letter in msg:
            index = printable.index(letter) + amount
            if index >= len(printable) - 1:
                index = index - (len(printable))
            encoded_msg += printable[index]

        await ctx.send(f"```{encoded_msg}```")

    @commands.command()
    async def hash(self, ctx, algo=None, *msg):
        if algo is None:
            await ctx.send("No Algorithm given. `$hash <OPENSSL algo> <msg>`")
            raise discord.ext.commands.errors.BadArgument
        try:
            joined_msg = " ".join(msg)
            msg = joined_msg.encode('UTF-8')
            h = hashlib.new(algo)
            h.update(msg)
            output = h.hexdigest()
            embed = discord.Embed(
                title=f"**Hashed message using {algo.lower()}**",
                colour=0x000000
            )
            embed.add_field(name="Input:", value=f"{joined_msg}", inline=False)
            embed.add_field(name="Output:", value=f"`{output}`", inline=False)
            await ctx.send(embed=embed)
        except ValueError:
            await ctx.send("Invalid hash type. Most OpenSSL algorithms are supported. Usage: `$hash <hash algo> <msg>`")
            raise discord.ext.commands.errors.BadArgument


def setup(bot):
    bot.add_cog(Player(bot))


def time_up(t):
    if t <= 60:
        return f"{int(t)} seconds"
    elif 3600 > t > 60:
        minutes = t // 60
        seconds = t % 60
        return f"{int(minutes)} minutes and {int(seconds)} seconds"
    elif t >= 3600:
        hours = t // 3600  # Seconds divided by 3600 gives amount of hours
        minutes = (t % 3600) // 60  # The remaining seconds are looked at to see how many minutes they make up
        seconds = (t % 3600) - minutes*60  # Amount of minutes remaining minus the seconds the minutes "take up"
        if hours >= 24:
            days = hours // 24
            hours = hours % 24
            return f"{int(days)} days, {int(hours)} hours, {int(minutes)} minutes and {int(seconds)} seconds"
        else:
            return f"{int(hours)} hours, {int(minutes)} minutes and {int(seconds)} seconds"


def seconds_elapsed():
    now = datetime.now()
    current_timestamp = time.mktime(now.timetuple())
    return current_timestamp - psutil.boot_time()
