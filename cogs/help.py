import discord
from discord.ext import commands
import datetime
from pytz import timezone

# TODO: make a proper help page
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def helptest(self, ctx):
        commands = {}
        for cog in self.bot.cogs:
            commands[cog] = []
            all_commands = self.bot.get_cog(cog).get_commands()
            for com in all_commands:
                commands[cog].append(com)
        msg = ""
        for key in commands.keys():
            msg += f"**{key}**\n"
            for com in commands[key]:
                msg += f"-- {com}\n"
        embed = discord.Embed(title="HELP", description=msg)
        await ctx.send(embed=embed)

    @commands.group(aliases=["halp", "commands", "h", "c"])
    async def help(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="Commands List",
                description="Use `$help <command>` to get help about a specific command.\n"
                            "`< >` are required parameters, `[ ]` are optional parameters.",
                color=0xF4C06A, timestamp=datetime.datetime.now(timezone("Europe/Zurich")))
            embed.set_footer(text=f"Called by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
            embed.set_thumbnail(url=self.bot.user.avatar_url)
            embed.set_author(name=self.bot.user.display_name, icon_url=self.bot.user.avatar_url)
            embed.add_field(
                name="Quote Command(s)",
                value="""`quote` > Call upon a quote or create a new one.""",
                inline=False)
            embed.add_field(
                name="Reputation Command(s)",
                value="""`rep` > Give positive reputation to other people.""",
                inline=False)
            embed.add_field(
                name="Statistics Command(s)",
                value="""`statistics` > Displays statistics for the server.""",
                inline=False)
            embed.add_field(
                name="Useful Command(s)",
                value="`hangman` > Too lazy to solve hangman puzzles? Use this.\n"
                      "`solve` > Solves an equation. Deprecated, as it causes the bot to crash :)\n"
                      "`cipher` > Cipher a word or sentence into some unread-able gibberish.",
                inline=False)
            embed.add_field(
                name="Fun Command(s)",
                value="`minesweeper` > Play some of that nostalgic minesweeper.\n"
                      "`calc` > Calculates something.",
                inline=False)
            embed.add_field(
                name="Usual Bot Command(s)",
                value="`help` > Get help on commands\n"
                      "`ping` > Displays the bot ping to the discord server.\n"
                      "`info` > Displays running time and cpu info about the bot.",
                inline=False)
            embed.add_field(
                name="Admin Command(s)",
                value="`ban` > bans? Or not? I dunno. At your own risk.\n"
                      "`test_welcome` > Used to test the welcome message functionality.",
                inline=False)
            embed.add_field(
                name="Owner Command(s)",
                value="`loading` > Simulates a loading bar.\n"
                      "`say` > Repeats a message.\n"
                      "`spam_till_youre_dead` > Spam. Till. You're. Dead.\n"
                      "`reboot` > Reboots the bot.",
                inline=False)
            await ctx.send(embed=embed)
    """
    Quote
    """
    @help.command(aliases=["q", "quotes"])
    async def quote(self, ctx):
        embed = discord.Embed(title="Quote Command Help", description="""**Description:**
Sends a completely random quote from the server if all parameters are empty. \
If only a name is given, it sends a random quote from that user.
**Aliases:**
`quotes`  |  `q`  |  `-` *(only works for calling upon a user)*
**Usage:**
`$quote [user] [quote/command] [index]`  |  `-<user>`
**Examples:**
`$quote`   - sends a random quote from any user
`$quote ueli`   - sends a random quote from the user ueli
`$quote ueli haHaa`   - adds "haHaa" as a quote to the user ueli
`$quote ueli all`   - displays all quotes from the user ueli
`$quote ueli 23`   - displays the 23rd indexed quote from the user ueli
`$quote names`   - displays all names that have a quote
`-ueli`   - displays a random quote from the user ueli
**Permissions:**
`@everyone`
""", color=0xF4C06A)
        embed.set_footer(text=f"Called by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url=self.bot.user.avatar_url)
        embed.set_author(name=self.bot.user.display_name, icon_url=self.bot.user.avatar_url)
        await ctx.send(embed=embed)

    """
    Hangman
    """
    @help.command(aliases=["hm"])
    async def hangman(self, ctx):
        embed = discord.Embed(title="Hangman Solver Command Help", description="""**Description:**
Sends the most probable letter for each hangman guess in either German or English. Defaults to English.
**Aliases:**
`hm`
**Usage:**
`$hangman [word to guess] [unused letters (0 if there are none)] <language>`
**Examples:**
`$hangman _____ 0`   - displays the most probable letter for a 5 letter word with 0 ununused letters in English
`$hm _th aoiu g`   - displays the most probably letter that is not one of aoiu in English
**Permissions:**
`@everyone`
""", color=0xF4C06A)
        embed.set_footer(text=f"Called by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url=self.bot.user.avatar_url)
        embed.set_author(name=self.bot.user.display_name, icon_url=self.bot.user.avatar_url)
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Help(bot))
