import discord
from discord.ext import commands
import datetime
import psutil
import time
import random
from sympy.solvers import solve
from sympy import symbols, simplify
import multiprocessing
from helper.log import log
import string


class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.script_start = 0
        self.clap_counter = 0
        self.time = 0

    @commands.Cog.listener()
    async def on_ready(self):
        self.script_start = time.time()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
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

    @commands.command(aliases=["uptime"])
    async def info(self, ctx):
        """
        Get some info about the bot
        """
        async with ctx.typing():
            b_time = time_up(time.time() - self.script_start)  # uptime of the script
            s_time = time_up(seconds_elapsed())  # uptime of the pc
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory()

            cont = f"""**Instance uptime: **`{b_time}`
    **Computer uptime: **`{s_time}`
    **CPU: **`{round(cpu)}%` | **RAM: **`{round(ram.percent)}%`
    **Discord.py Rewrite Version:** `{discord.__version__}`"""
            embed = discord.Embed(title="Bot Information:", description=cont, color=0xD7D7D7,
                                  timestamp=datetime.datetime.now())
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
            return
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

    @commands.command(aliases=["pong"])
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
        embed = discord.Embed(title=f"{title} 🏓", description=f"🌐 Ping: `{round(self.bot.latency * 1000)}` ms")
        await ctx.send(embed=embed)

    @commands.command()
    async def cipher(self, ctx, amount=None, *msg):
        printable = list(string.printable)
        printable = printable[0:-5]
        if len(msg) == 0:
            return
        try:
            amount = int(amount)
        except ValueError:
            ctx.send("Amount is not an int.")
            return
        msg = " ".join(msg)
        encoded_msg = ""
        amount = amount % len(printable)
        print(len(printable))
        for letter in msg:
            index = printable.index(letter) + amount
            if index >= len(printable) - 1:
                index = index - (len(printable))
            encoded_msg += printable[index]

        await ctx.send(f"`{encoded_msg}`")


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
    now = datetime.datetime.now()
    current_timestamp = time.mktime(now.timetuple())
    return current_timestamp - psutil.boot_time()
