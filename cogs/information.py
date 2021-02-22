import discord
from discord.ext import commands
from datetime import datetime
import psutil
import time
import random
import string
import hashlib


class Information(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.script_start = time.time()

    @commands.Cog.listener()
    async def on_ready(self):
        self.script_start = time.time()

    @commands.command(usage="guild")
    async def guild(self, ctx):
        """
        Used to display information about the server.
        """
        guild = ctx.message.guild
        embed = discord.Embed(title=f"Guild Statistics", color=discord.colour.Color.dark_blue())
        embed.add_field(name="Categories", value=f"Server Name:\n"
                                                 f"Server ID:\n"
                                                 f"Member Count:\n"
                                                 f"Categories:\n"
                                                 f"Text Channels:\n"
                                                 f"Voice Channels:\n"
                                                 f"Emoji Count / Max emojis:\n"
                                                 f"Owner:\n"
                                                 f"Roles:")
        embed.add_field(name="Values", value=f"{guild.name}\n"
                                             f"{guild.id}\n"
                                             f"{guild.member_count}\n"
                                             f"{len(guild.categories)}\n"
                                             f"{len(guild.text_channels)}\n"
                                             f"{len(guild.voice_channels)}\n"
                                             f"{len(guild.emojis)} / {guild.emoji_limit}\n"
                                             f"{guild.owner.mention}\n"
                                             f"{len(guild.roles)}")
        await ctx.send(embed=embed)

    @commands.command(aliases=["source", "code"], usage="info")
    async def info(self, ctx):
        """
        Sends some info about the bot.
        """
        async with ctx.typing():
            b_time = time_up(time.time() - self.script_start)  # uptime of the script
            s_time = time_up(seconds_elapsed())  # uptime of the pc
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory()

            cont = f"**Instance uptime: **`{b_time}`\n" \
                   f"**Computer uptime: **`{s_time}`\n" \
                   f"**CPU: **`{round(cpu)}%` | **RAM: **`{round(ram.percent)}%`\n" \
                   f"**Discord.py Rewrite Version:** `{discord.__version__}`\n" \
                   f"**Bot source code:** [Click here for source code](https://github.com/markbeep/Lecturfier)"
            embed = discord.Embed(title="Bot Information:", description=cont, color=0xD7D7D7,
                                  timestamp=datetime.now())
            embed.set_footer(text=f"Called by {ctx.author.display_name}")
            embed.set_thumbnail(url=self.bot.user.avatar_url)
            embed.set_author(name=self.bot.user.display_name, icon_url=self.bot.user.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(usage="token")
    async def token(self, ctx):
        """
        Sends a bot token.
        """
        token = random_string(24) + "." + random_string(6) + "." + random_string(27)
        embed = discord.Embed(title="Bot Token", description=f"||`{token}`||")
        await ctx.send(embed=embed)

    @commands.command(aliases=["pong", "ding", "pingpong"], usage="ping")
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
            description=f"🌐 Ping: `{round((end - start) * 1000)}` ms\n"
                        f"❤ HEARTBEAT: `{round(self.bot.latency * 1000)}` ms")
        await ping.edit(embed=embed)

    @commands.command(aliases=["cypher"], usage="cipher <amount to displace> <msg>")
    async def cipher(self, ctx, amount=None, *msg):
        """
        This is Caesar's cipher, but instead of only using the alphabet, it uses all printable characters.
        Negative values are allowed and can be used to decipher messages.
        """
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

    @commands.command(usage="hash <OpenSSL algo> <msg>")
    async def hash(self, ctx, algo=None, *msg):
        """
        Hash a message using an OpenSSL algorithm (sha256 for example).
        """
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
    bot.add_cog(Information(bot))


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


def random_string(n):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))
