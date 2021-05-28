import math
import discord
from discord.ext import commands, menus
import datetime
import json
from pytz import timezone
from discord.ext.commands.cooldowns import BucketType
from helper import handySQL
from discord_components import DiscordComponents, Button, ButtonStyle, InteractionType
import time

def isascii(s):
    """Checks how many bytes of non-ascii characters there is in the quote"""
    total = 0
    for t in s:
        q = len(t.encode('utf-8'))
        if q > 2:
            total += q
    return total < 300


async def send_quote(channel: discord.channel, quote, date, name, index=None):
    embed = discord.Embed(description=quote, color=0x404648)
    footer_txt = ""
    local_tz = timezone("Europe/Zurich")
    dt = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S").astimezone(local_tz).strftime("%d.%b %Y").lstrip("0")
    if index is not None:
        footer_txt += f" | Quote ID: {index}"
    embed.set_footer(text=f"-{name}, {dt}" + footer_txt)
    await channel.send(embed=embed)


class Quote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        DiscordComponents(self.bot)
        self.time = 0
        with open("./data/ignored_users.json") as f:
            self.ignored_users = json.load(f)
        self.db_path = "./data/discord.db"
        self.conn = handySQL.create_connection(self.db_path)

    def get_connection(self):
        """
        Retreives the current database connection
        :return: Database Connection
        """
        if self.conn is None:
            self.conn = handySQL.create_connection(self.db_path)
        return self.conn

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        # To get a random quote you can just type `-name`
        if message.content.startswith("-"):
            name = message.content.replace("-", "")
            try:
                guild_id = message.guild.id
            except AttributeError:
                return
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("SELECT Quote, QuoteID, Name, CreatedAt FROM Quotes WHERE Name LIKE ? AND DiscordGuildID=? ORDER BY RANDOM() LIMIT 1",
                      (name, guild_id))
            res = c.fetchone()
            if res is None:
                return  # if that name has no quote
            await send_quote(message.channel, res[0], res[3], res[2], res[1])

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # Returns if the reacted message is not in a channel
        if payload.guild_id is None or payload.channel_id is None or payload.message_id is None or payload.member is None:
            return

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        user = str(message.author.id)
        quoteAdder = payload.member
        emoji = payload.emoji
        if str(emoji) == "<:addQuote:840982832654712863>":
            # We first check if the channel is an announcement channel
                # To avoid unecessary queries
            if channel.type == discord.ChannelType.news:
                print("Channel is an announcement channel. Ignoring Quote.")
                return

            conn = self.get_connection()
            result = conn.execute("SELECT ConfigValue FROM Config WHERE ConfigKey=='BlockedQuoteChannel'").fetchall()
            blocked_channels = [x[0] for x in result]
            if channel.id in blocked_channels:
                print("Blocked Quote Channel. Ignoring quote.")
                return

            await self.add_quote(user=user, message=message, quote=message.content, quoteAdder=quoteAdder, reactionQuote=True)

    @commands.cooldown(4, 10, BucketType.user)
    @commands.group(aliases=["q", "quotes"], usage="quote [user] [quote/command/index]", invoke_without_command=True)
    async def quote(self, ctx, name=None, *, quote=""):
        """
        Sends a completely random quote from the server if all parameters are empty. \
        If only a name is given, it sends a random quote from that user.
        By using `-name` for any name that has quotes you can display a random quote from that person \
        directly.

        Some examples:
        `$quote`   - sends a random quote from any user
        `$quote ueli`   - sends a random quote from the user ueli
        `$quote ueli haHaa`   - adds "haHaa" as a quote to the user ueli
        `$quote ueli all`   - displays all quotes from the user ueli
        `$quote ueli 23`   - displays the 23rd indexed quote from the user ueli
        `$quote names`   - displays all names that have a quote
        `-ueli`   - displays a random quote from the one and only ueli
        """

        # creates the db connection
        conn = self.get_connection()
        c = conn.cursor()

        if ctx.invoked_subcommand is not None:
            return

        # if message is a reply, add the replied message as a quote
        reply = ctx.message.reference
        if reply is not None and name is None and len(quote) == 0:
            reply_message = await ctx.message.channel.fetch_message(reply.message_id)
            name = str(reply_message.author.id)
            quote = reply_message.content
            await self.add_quote(user=name, message=reply_message, quote=quote, quoteAdder=ctx.message.author)
            return

        if name is None:  # no user is given, so send a random quote
            # If $quote is written on its own, send a random quote from any user
            c.execute("SELECT Quote, QuoteID, Name, CreatedAt FROM Quotes WHERE DiscordGuildID=? ORDER BY RANDOM() LIMIT 1", (ctx.message.guild.id,))
            res = c.fetchone()
            if res is None:
                embed = discord.Embed(title="Quote Error", description="There are no quotes on this server yet.", color=0xFF0000)
                await ctx.send(embed=embed)
                raise discord.ext.commands.errors.BadArgument
            await send_quote(ctx, res[0], res[3], res[2], res[1])

        else:  # there's a user given
            # if there is only a name/ID given, send a random quote from that user
            if len(quote) == 0:

                # tries to first query if its a quote ID
                c.execute("SELECT Quote, QuoteID, Name, CreatedAt FROM Quotes WHERE QuoteID=? AND DiscordGuildID=?", (name, ctx.message.guild.id))
                res = c.fetchone()

                username = name

                if res is None:
                    # if its a user ID, gets a random quote from the user with that ID
                    member, multUniqueIDs = await self.get_quote_member(ctx, conn, name)
                    if member is not None:
                        username = str(member)
                        uniqueID = multUniqueIDs[0]
                        c.execute(
                            "SELECT Quote, QuoteID, Name, CreatedAt FROM Quotes WHERE UniqueMemberID=? AND DiscordGuildID=? ORDER BY RANDOM() LIMIT 1",
                            (uniqueID, ctx.message.guild.id))
                    else:
                        c.execute(
                            "SELECT Quote, QuoteID, Name, CreatedAt FROM Quotes WHERE Name LIKE ? AND DiscordGuildID=? ORDER BY RANDOM() LIMIT 1",
                            (name, ctx.message.guild.id))
                    res = c.fetchone()

                if res is None:
                    # userID has no quote on this server
                    embed = discord.Embed(title="Quotes", description=f"No quote found from user or with ID `{username}`")
                    await ctx.send(embed=embed)
                    raise discord.ext.commands.errors.BadArgument

                await send_quote(ctx, res[0], res[3], res[2], res[1])
                return

            else:
                # if theres something behind the name

                # if its an index behind the user
                if quote.isnumeric():
                    index = int(quote)
                    await self.get_quote_by_index(ctx, name, index)

                else:  # its a new quote to add
                    if quote.lower().split(" ")[0] == "all":
                        await self.get_all_quotes(ctx, name)
                        return

                    await self.add_quote(user=name, quote=quote, message=ctx.message)

    async def get_guild_for_quotes(self, channel: discord.channel):
        # Get the guild ID or returns an error message
        try:
            return channel.guild.id
        except AttributeError:
            await channel.send("Quotes are currently not supported in private messages")
            raise discord.ext.commands.BadArgument

    async def get_quote_member(self, channel: discord.channel, conn, user):
        guild_id = await self.get_guild_for_quotes(channel)
        uniqueIDs = []  # list of all matching uniqueIDs
        member = None

        user_id = user.replace("<@", "").replace(">", "").replace("!", "")
        if user_id.isnumeric():
            member = channel.guild.get_member(int(user_id))
            uniqueIDs.append(handySQL.get_uniqueMemberID(conn, user_id, guild_id))
        else:
            # Not a discord member ID
            # We make a list of all uniqueIDs with the matching name
            c = conn.cursor()
            c.execute("SELECT UniqueMemberID FROM Quotes WHERE Name LIKE ? GROUP BY UniqueMemberID", (user,))
            res = c.fetchall()
            uniqueIDs = [x[0] for x in res]

        return member, uniqueIDs

    async def get_quote_by_index(self, message: discord.Message, user, index):
        conn = self.get_connection()
        c = conn.cursor()
        channel = message.channel

        member, multUniqueIDs = await self.get_quote_member(channel, conn, user)
        guild_id = await self.get_guild_for_quotes(channel)
        name = user
        uniqueID = -1
        if member is not None:
            uniqueID = multUniqueIDs[0]
            name = str(member)

        # checks if the user even has any quotes
        if member is not None:
            c.execute("SELECT * FROM Quotes WHERE UniqueMemberID=? AND DiscordGuildID=?", (uniqueID, guild_id))
        else:
            c.execute("SELECT * FROM Quotes WHERE Name LIKE ? AND DiscordGuildID=?", (name, guild_id))
        res = c.fetchall()

        # checks if there are any quotes from that user
        quote_amt = len(res)  # this is used to display the index below
        if quote_amt == 0:
            embed = discord.Embed(
                title="Quotes Error",
                description=f"There does not exist any quote for the user `{name}`",
                color=0xFF0000)
            await channel.send(embed=embed)
            raise discord.ext.commands.errors.BadArgument

        # checks if the index exists
        if member is not None:
            c.execute(
                "SELECT Quote, Name, CreatedAt, QuoteID FROM Quotes WHERE UniqueMemberID=? AND DiscordGuildID=? ORDER BY QuoteID LIMIT 1 OFFSET ?",
                (uniqueID, guild_id, index))
        else:
            c.execute("SELECT Quote, Name, CreatedAt, QuoteID FROM Quotes WHERE Name LIKE ? AND DiscordGuildID=? ORDER BY QuoteID LIMIT 1 OFFSET ?",
                      (name, guild_id, index))
        res = c.fetchone()
        if res is None:
            embed = discord.Embed(
                title="Quotes Error",
                description=f"There does not exist a quote with that index for the user \"{name}\". "
                            f"Keep the index between `0 <= index < {quote_amt}`.",
                color=0xFF0000)
            await channel.send(embed=embed)
            raise discord.ext.commands.errors.BadArgument
        await send_quote(channel, res[0], res[2], res[1], res[3])

    async def add_quote(self, user, message: discord.Message, quote, quoteAdder=None, reactionQuote=False):
        conn = self.get_connection()
        c = conn.cursor()
        channel = message.channel
        if quoteAdder is None:
            quoteAdder = message.author

        try:
            await message.add_reaction("<:addedQuote:840985556304265237>")
        except discord.errors.NotFound:
            pass

        member, multipleUniqueIDs = await self.get_quote_member(channel, conn, user)
        guild_id = await self.get_guild_for_quotes(channel)

        # Some error messages ------------------------------
        # If the quote is too long
        if len(quote) > 500 and not await self.bot.is_owner(quoteAdder):
            embed = discord.Embed(
                title="Quote Error",
                description="This quote exceeds the max_length length of 500 chars. Ping Mark if you want the quote added.",
                color=0xFF0000)
            if reactionQuote:
                try:
                    await message.add_reaction("<:failedQuote:840988109578698782>")
                except discord.errors.Forbidden:
                    pass
            else:
                await channel.send(content=quoteAdder.mention, embed=embed, delete_after=5)
            raise discord.ext.commands.errors.NotOwner

        # If the quote has too many non-ascii characters
        if not isascii(quote) and not await self.bot.is_owner(quoteAdder):
            embed = discord.Embed(
                title="Quote Error",
                description="This quote contains too many non-ascii characters. Ping Mark if you want the quote added.",
                color=0xFF0000)
            if reactionQuote:
                try:
                    await message.add_reaction("<:failedQuote:840988109578698782>")
                except discord.errors.Forbidden:
                    pass
            else:
                await channel.send(content=quoteAdder.mention, embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument

        c.execute("SELECT ConfigValue FROM Config WHERE ConfigKey=='BlockQuote'")
        blocked_ids = [x[0] for x in c.fetchall()]  # makes a list of all returned values of the above sql query

        # If the user is blocked from adding quotes
        if quoteAdder.id in blocked_ids:
            embed = discord.Embed(
                title="Quote Error",
                description="You are blocked from adding new quotes. Possible reasons include adding too many fake quotes or "
                            "simply spamming the quote command.",
                color=0xFF0000)
            if reactionQuote:
                try:
                    await message.add_reaction("<:failedQuote:840988109578698782>")
                except discord.errors.Forbidden:
                    pass
            else:
                await channel.send(content=quoteAdder.mention, embed=embed, delete_after=5)
                await message.delete(delay=2)
            raise discord.ext.commands.errors.BadArgument

        uniqueID = None
        if member is None:  # that user is not a discord user and has no uniqueID
            quoted_name = user
        else:
            quoted_name = member.name
            uniqueID = multipleUniqueIDs[0]
        addedByUniqueID = handySQL.get_uniqueMemberID(conn, quoteAdder.id, guild_id)

        # checks if its a self quote
        if addedByUniqueID in multipleUniqueIDs:
            embed = discord.Embed(
                title="Quote Error",
                description="You can't quote yourself. That's pretty lame.",
                color=0xFF0000)
            embed.set_footer(text="(Or your username is the same as the person you're trying to quote.)")
            if reactionQuote:
                try:
                    await message.add_reaction("<:failedQuote:840988109578698782>")
                except discord.errors.Forbidden:
                    pass
            else:
                await channel.send(content=quoteAdder.mention, embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument

        # checks if the quote exists already
        if uniqueID is None:
            c.execute("SELECT * FROM Quotes WHERE Quote LIKE ? AND Name LIKE ?", (quote, user))
        else:
            c.execute("SELECT * FROM Quotes WHERE Quote LIKE ? AND UniqueMemberID=?", (quote, uniqueID))
        if c.fetchone() is not None:
            embed = discord.Embed(
                title="Quote Error",
                description="This quote has been added already.",
                color=0xFF0000)
            if reactionQuote:
                try:
                    await message.add_reaction("<:failedQuote:840988109578698782>")
                except discord.errors.Forbidden:
                    pass
            else:
                await channel.send(content=quoteAdder.mention, embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument

        # gets the alias of the user, if it exists
        c.execute("SELECT NameTo FROM QuoteAliases WHERE NameFrom LIKE ?", (quoted_name,))
        res = c.fetchone()
        if res is not None:
            quoted_name = res[0]

        sql = """   INSERT INTO Quotes(Quote, Name, UniqueMemberID, AddedByUniqueMemberID, DiscordGuildID)
                                        VALUES (?,?,?,?,?)"""
        c.execute(sql, (quote, quoted_name, uniqueID, addedByUniqueID, guild_id))
        conn.commit()
        row_id = c.lastrowid
        c.execute("SELECT QuoteID FROM Quotes WHERE ROWID=?", (row_id,))
        res = c.fetchone()
        quoteID = "n/a"
        if res is not None:
            quoteID = res[0]

        embed = discord.Embed(title="Added Quote", description=f"Added quote for {quoted_name}\nQuoteID: `{quoteID}`", color=0x00FF00)

        if reactionQuote:
            await message.reply(embed=embed, mention_author=False)
        else:
            await channel.send(embed=embed)

    @quote.command(name="all", usage="all <user>")
    async def all_quotes(self, ctx, user=None):
        """
        Gets all quotes from a user. If there are too many quotes, \
        the quotes are shown in a menu with reactions. Usually you have to wait \
        a few seconds before the menu reactions are active.

        By default menu quote embeds delete after 180 seconds while single page  \
        quote pages delete after 120 seconds.
        """
        if user is None:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM Quotes")
            total_quotes = c.fetchone()[0]
            c.execute("SELECT COUNT(DISTINCT Name) FROM Quotes")
            total_names = c.fetchone()[0]

            embed = discord.Embed(
                title="All Quotes Stats",
                description="You didn't specify what user to get quotes off. So here are some stats."
            )
            embed.add_field(name="Total Quotes", value=total_quotes)
            embed.add_field(name="Total Names", value=total_names)
            await ctx.message.reply(embed=embed)
            return

        await self.get_all_quotes(ctx, user)

    @quote.group(aliases=["rep"], usage="report <quote ID>", invoke_without_command=True)
    async def report(self, ctx, quoteID=None):
        """
        Report quotes which should be deleted. This makes deleting quotes a lot easier \
        and more organized. Additionally ping @mark so he knows a quote was reported.
        """
        if ctx.invoked_subcommand is not None:
            return
        
        # input parsing
        if quoteID is None:
            embed = discord.Embed(title="Quotes Error", description=f"No quote ID given.", color=0xFF0000)
            await ctx.send(embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument
        if not quoteID.isnumeric():
            embed = discord.Embed(title="Quotes Error", description=f"Quote ID has to be an integer.", color=0xFF0000)
            await ctx.send(embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument
        quoteID = int(quoteID)

        conn = self.get_connection()
        c = conn.cursor()

        # check if quote ID is a valid ID
        c.execute("SELECT * FROM Quotes WHERE QuoteID=?", (quoteID,))
        if c.fetchone() is None:
            embed = discord.Embed(
                title="Quotes Error",
                description=f"The given quote ID can't be assigned to a valid quote. Did you type the right ID?",
                color=0xFF0000)
            await ctx.send(embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument

        # check if quote ID is already listed in db
        c.execute("SELECT * FROM QuotesToRemove WHERE QuoteID=?", (quoteID,))
        if c.fetchone() is not None:
            embed = discord.Embed(
                title="Quotes Error",
                description=f"The given quote ID is already listed in the quotes to remove list.",
                color=0xFF0000)
            await ctx.send(embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument
        
        # At this point we have a valid Quote ID, so add it to the database
        c.execute("INSERT INTO QuotesToRemove(QuoteID, ReporterID) VALUES(?,?)", (quoteID, ctx.message.author.id))
        conn.commit()
        embed = discord.Embed(
            title="Added Quote Report",
            description=f"Succesfully requested quote {quoteID} to be deleted.",
            color=0x00FF00)
        await ctx.send(embed=embed, delete_after=5)

    @commands.is_owner()
    @report.command(aliases=["show", "all"], usage="showReports")
    async def showReports(self, ctx):
        """
        Shows all reported quotes in an easy to use fashion.
        Permissions: Owner
        """
        # get all the reports
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT QuoteID, ReporterID FROM QuotesToRemove")
        rows = c.fetchall()

        # fetches each quote and adds it to a page
        # 1 quote per page
        pages = []
        while len(rows) > 0:
            quoteID, reporterID = rows.pop()
            c.execute("SELECT UniqueMemberID, Quote, Name FROM Quotes WHERE QuoteID=?", (quoteID,))
            res = c.fetchone()
            # res can be None if the quote was removed in another way
            if res is None:
                # remove the quote from the table and continue
                c.execute("DELETE FROM QuotesToRemove WHERE QuoteID=?", (quoteID,))
                conn.commit()
                continue
            uniqueID, quote, name = res
            userID = handySQL.get_DiscordUserID(conn, uniqueID)
            pages.append([userID, quoteID, quote, reporterID, name])

        # should have a list of page lists, each with a max of 10 elements
        # in each page element we have user ID, quoute ID and the quote itself
        if len(pages) == 0:
            await ctx.send("There are no reported quotes to remove.")
            return
        
        m = QuotesToRemove(pages, conn)
        await m.start(ctx=ctx, channel=ctx.channel)

    async def get_all_quotes(self, ctx, user):
        channel = ctx.message.channel
        conn = self.get_connection()
        c = conn.cursor()

        guild_id = await self.get_guild_for_quotes(channel)
        member, multUniqueIDs = await self.get_quote_member(channel, conn, user)

        quote_list = ""

        # executes query to get all quotes
        if member is not None:
            c.execute("SELECT Quote, Name, CreatedAt, QuoteID FROM Quotes WHERE UniqueMemberID=? AND DiscordGuildID=? ORDER BY QuoteID",
                      (multUniqueIDs[0], guild_id))
        else:
            c.execute("SELECT Quote, Name, CreatedAt, QuoteID FROM Quotes WHERE Name LIKE ? AND DiscordGuildID=? ORDER BY QuoteID", (user, guild_id))
        res = c.fetchall()

        # If there are no quotes for the given person;
        if len(res) == 0:
            embed = discord.Embed(title="Quotes Error", description=f"{user} doesn't have any quotes yet.", color=0xFF0000)
            await channel.send(embed=embed)
            raise discord.ext.commands.errors.BadArgument

        i = 0
        for row in res:
            quote_to_add = row[0].replace("*", "").replace("~", "").replace("\\", "").replace("`", "")
            if quote_to_add.count("\n") > 2:
                # makes multiline quotes not show too much
                split_lines = quote_to_add.split("\n")
                quote_to_add = "\n".join(split_lines[:2]) + "\n **[...]**"
            if len(quote_to_add) > 150:
                quote_to_add = quote_to_add[:150] + "**[...]**"
            quote_list += f"\n**#{i}:** {quote_to_add} `[ID: {row[3]}]`"
            i += 1

        # splits the messages into different pages by character length
        pages = []
        quoted_name = user
        if member is not None:
            quoted_name = member.name

        # creates the pages
        while len(quote_list) > 0:
            # split quotes into multiple fields of max 1000 chars
            if len(quote_list) >= 1000:
                rind2 = quote_list.rindex("\n", 0, 1000)
                if rind2 == 0:
                    # one quote is more than 1000 chars
                    rind2 = quote_list.rindex(" ", 0, 1000)
                    if rind2 == 0:
                        # the quote is longer than 1000 chars and has no spaces
                        rind2 = 1000
            else:
                rind2 = len(quote_list)
            pages.append(quote_list[0:rind2])
            quote_list = quote_list[rind2:]

        p = Pages(self.bot, ctx, pages, ctx.message.author.id, f"All quotes from {quoted_name}", 180)
        if len(pages) > 1:
            #m = QuoteMenu(pages, quoted_name)
            await p.handle_pages()
            #await m.start(channel)
        else:
            await channel.message.delete(delay=120)
            await channel.send(embed=p.create_embed(0), delete_after=120)

    @commands.is_owner()
    @quote.command(name="delete", aliases=["del"], usage="delete <Quote ID>")
    async def delete_quote(self, ctx, quoteID=None):
        """
        Deletes the quote with the given ID.
        Permissions: Owner
        """
        conn = self.get_connection()
        c = conn.cursor()
        try:
            quote_id = int(quoteID)
            try:
                c.execute("DELETE FROM Quotes WHERE QuoteID=?", (quote_id,))
                conn.commit()

                await ctx.send(f"Deleted quote with quote ID {quote_id}.")
            except IndexError:
                await ctx.send("No name with that index.")
        except (IndexError, ValueError):
            await ctx.send("You forgot to add an index.")

    @quote.command(name="names", aliases=["name"], usage="names")
    async def quote_names(self, channel: discord.channel):
        """
        Lists all names/discord id's that have at least one quote.
        It's sorted by amount of quotes each user has in descending order.
        """
        conn = self.get_connection()
        c = conn.cursor()
        guild_id = await self.get_guild_for_quotes(channel)
        sql = """   SELECT Q.Name, Q.UniqueMemberID
                                    FROM Quotes Q
                                    WHERE Q.DiscordGuildID=?
                                    GROUP BY Q.Name
                                    ORDER BY COUNT(*) DESC"""
        c.execute(sql, (guild_id,))
        res = c.fetchall()

        embed = discord.Embed(title="Quote Names")
        # If there are no quotes on the server
        if len(res) == 0:
            embed = discord.Embed(title="Quote Error", description="There are no quotes on this server yet.", color=0xFF0000)
            await channel.send(embed=embed)
            raise discord.ext.commands.errors.BadArgument
        else:
            embed.description = "Everybody with a quote as of now:"
            MAX_FIELDS = 21
            per_field = math.ceil(len(res) / MAX_FIELDS)  # the amount of names per field to have a max of 21 fields
            index = 0

            # splits the names into the given amount of MAX_FIELDS
            msg_number = 1
            while len(res[index:]) > 0:
                field_msg = ""
                for row in res[index: index + per_field]:
                    if row[1] is None:
                        quoted_name = row[0]
                    else:
                        quoted_name = f"<@{handySQL.get_DiscordUserID(conn, row[1])}>"
                    field_msg += f"- {quoted_name}\n"
                embed.add_field(name=f"Field #{msg_number}", value=field_msg)
                index += per_field
                msg_number += 1
            await channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Quote(bot))


class QuoteMenu(menus.Menu):
    def __init__(self, pages, quoted_name):
        super().__init__(clear_reactions_after=True, delete_message_after=True)
        self.quoted_name = quoted_name
        self.pages = pages
        self.page_count = 0
        self.ctx = None

    def get_page(self, page_number):
        embed = discord.Embed(title=f"All quotes from {self.quoted_name}", color=0x404648)
        embed.add_field(name=f"Page {page_number + 1} / {len(self.pages)}", value=self.pages[page_number])
        if len(self.pages) > 1:
            embed.set_footer(text="⬅️ prev page | ➡️ next page | ❌ delete message")
        return embed

    async def send_initial_message(self, ctx, channel):
        embed = self.get_page(self.page_count)
        self.ctx = ctx
        return await ctx.send(embed=embed)

    @menus.button("⬅️")
    async def page_down(self, payload):
        self.page_count = (self.page_count - 1) % len(self.pages)
        embed = self.get_page(self.page_count)
        await self.message.edit(embed=embed)

    @menus.button("➡️")
    async def page_up(self, payload):
        self.page_count = (self.page_count + 1) % len(self.pages)
        embed = self.get_page(self.page_count)
        await self.message.edit(embed=embed)

    @menus.button("❌")
    async def delete(self, payload):
        if self.ctx is not None:
            # if the message was already deleted
            # this seems to throw an error
            # and then the quote msg can't be deleted
            try:
                await self.ctx.message.delete()
            except:
                pass
        self.stop()


class QuotesToRemove(menus.Menu):
    def __init__(self, pages, conn):
        super().__init__(clear_reactions_after=True, delete_message_after=True)
        self.pages = pages
        self.page_count = 0
        self.ctx = None
        self.conn = conn

    async def send_initial_message(self, ctx, channel):
        embed = self.create_embed(self.page_count)
        self.ctx = ctx
        return await ctx.send(embed=embed)

    def create_embed(self, page_number):
        embed = discord.Embed(title="Quotes to Remove", description=f"Page {page_number+1}/{len(self.pages)}", color=0x00003f)
        userID, quoteID, quote, reporterID, name = self.pages[page_number]
        if userID is not None:
            embed.add_field(name=f"ID: {quoteID} | {name}", value=f"Discord User: <@{userID}>\nReported by: <@{reporterID}>\n**Quote:**\n{quote}")
        else:
            embed.add_field(name=f"ID: {quoteID} | {name}", value=quote)
        return embed

    @menus.button("⬅️")
    async def page_down(self, payload):
        self.page_count = (self.page_count - 1) % len(self.pages)
        embed = self.create_embed(self.page_count)
        await self.message.edit(embed=embed)

    @menus.button("➡️")
    async def page_up(self, payload):
        self.page_count = (self.page_count + 1) % len(self.pages)
        embed = self.create_embed(self.page_count)
        await self.message.edit(embed=embed)

    @menus.button("❌")
    async def delete(self, payload):
        if self.ctx is not None:
            # if the message was already deleted
            # this seems to throw an error
            # and then the quote msg can't be deleted
            try:
                await self.ctx.message.delete()
            except:
                pass
        self.stop()

    @menus.button("<:DeletThis:843908352999686234>")
    async def deleteQuote(self, payload):
        userID, quoteID, quote, reporterID, name = self.pages[self.page_count]
        c = self.conn.cursor()
        c.execute("DELETE FROM Quotes WHERE QuoteID=?", (quoteID,))
        c.execute("DELETE FROM QuotesToRemove WHERE QuoteID=?", (quoteID,))
        self.conn.commit()
        self.pages.pop(self.page_count)
        embed = discord.Embed(title="Deleted Quote", description=f"Quote with ID {quoteID} was YEEEEEETED.", color=0xffff00)
        await self.ctx.send(content=f"Reported by <@{reporterID}>", embed=embed)

        if len(self.pages) == 0:
            embed = discord.Embed(title="Cleansing is done", description=f"All reported quotes were yeeted.", color=0xffff00)
            await self.ctx.send(embed=embed)
            self.stop()
            return
        # get new page
        self.page_count = self.page_count % len(self.pages)
        embed = self.create_embed(self.page_count)
        await self.message.edit(embed=embed)

    @menus.button("<a:IgnoreReport:844678929751212083>")
    async def ignoreQuote(self, payload):
        userID, quoteID, quote, reporterID, name = self.pages[self.page_count]
        c = self.conn.cursor()
        c.execute("DELETE FROM QuotesToRemove WHERE QuoteID=?", (quoteID,))
        self.conn.commit()
        self.pages.pop(self.page_count)
        embed = discord.Embed(title="Ignored Quote", description=f"Quote with ID {quoteID} was ignored.", color=0xffff00)
        await self.ctx.send(content=f"Reported by <@{reporterID}>", embed=embed)

        if len(self.pages) == 0:
            embed = discord.Embed(title="Cleansing is done", description=f"All reported quotes were yeeted.", color=0xffff00)
            await self.ctx.send(embed=embed)
            self.stop()
            return
        # get new page
        self.page_count = self.page_count % len(self.pages)
        embed = self.create_embed(self.page_count)
        await self.message.edit(embed=embed)


class Pages:
    def __init__(self, bot: discord.Client, ctx: discord.ext.commands.Context, pages: list, user_id: int, embed_title: str, seconds=60):
        self.bot = bot  # bot object required so we can wait for the button click
        self.ctx = ctx  # so that we can remove the original message in the end
        self.page_count = 0  # current page
        self.pages = pages  # list of strings
        self.start_time = time.time()
        self.user_id = user_id  # the user ID that can change the pages
        self.embed_title = embed_title  # the title of each page
        self.seconds = seconds  # time in seconds to wait until we delete the message
        self.message = None  # the quotes message sent by the bot

    async def handle_pages(self):
        """
        The meat of the pages which handles what shall be done depending
        on what button was pressed. This sits in a while loop until the time
        of self.seconds passes.
        """
        self.message = await self.send_initial_message()
        while time.time() < self.start_time + self.seconds:
            # waits for a button click event
            res = await self.bot.wait_for("button_click")
            if res.message is not None and res.message.id == self.message.id:
                if res.user.id == self.user_id:
                    if res.component.label == "<":  # prev page
                        await self.page_down()
                    elif res.component.label == ">":  # next page
                        await self.page_up()
                    elif res.component.label == "X":  # break resulting in deleting the page and user message
                        break
                    elif res.component.label == "<<":  # first page
                        await self.first_page()
                    elif res.component.label == ">>":  # last page
                        await self.last_page()
                    # Responds by updating the message
                    await res.respond(type=InteractionType.UpdateMessage, components=self.get_components())
                else:
                    await res.respond(type=InteractionType.ChannelMessageWithSource, content="This page wasn't called by you.")
        try:
            await self.ctx.message.delete()
        except AttributeError:
            pass
        await self.message.delete()

    async def send_initial_message(self) -> discord.Message:
        """
        Sends the initial message on page 1 (index 0) with
        the buttons
        """
        embed = self.create_embed()
        return await self.ctx.send(
            embed=embed,
            components=self.get_components()
        )

    def get_components(self) -> list:
        """
        Returns the buttons correctly colored. Depending if
        it's the first or last page, some buttons will be disabled.
        """
        components = [
            Button(style=ButtonStyle.blue, label="<<"),
            Button(style=ButtonStyle.blue, label="<"),
            Button(style=ButtonStyle.red, label="X"),
            Button(style=ButtonStyle.blue, label=">"),
            Button(style=ButtonStyle.blue, label=">>")
        ]
        if self.page_count == len(self.pages)-1:  # we are on the last page
            components[3] = Button(style=ButtonStyle.grey, label=">", disabled=True)
            components[4] = Button(style=ButtonStyle.grey, label=">>", disabled=True)

        if self.page_count == 0:  # we are on the first page
            components[0] = Button(style=ButtonStyle.grey, label="<<", disabled=True)
            components[1] = Button(style=ButtonStyle.grey, label=">", disabled=True)

        return [components]

    def create_embed(self) -> discord.Embed:
        """
        Creates a discord embed with the given self.embed_title as
        the title and the page depending on the current page we're on.
        """
        embed = discord.Embed(title=self.embed_title, color=0x404648)
        embed.add_field(name=f"Page {self.page_count + 1} / {len(self.pages)}", value=self.pages[self.page_count])
        if len(self.pages) > 1:
            embed.set_footer(text="<< first page | < prev page | ❌ delete message | > next page | >> last page")
        return embed

    async def page_down(self) -> None:
        """
        Goes down a page
        """
        self.page_count = (self.page_count - 1) % len(self.pages)
        embed = self.create_embed()
        await self.message.edit(embed=embed)

    async def page_up(self) -> None:
        """
        Goes up a page
        """
        self.page_count = (self.page_count + 1) % len(self.pages)
        embed = self.create_embed()
        await self.message.edit(embed=embed)

    async def last_page(self) -> None:
        """
        Heads to the last page
        """
        self.page_count = len(self.pages) - 1
        embed = self.create_embed()
        await self.message.edit(embed=embed)

    async def first_page(self) -> None:
        """
        Heads to the first page
        """
        self.page_count = 0
        embed = self.create_embed()
        await self.message.edit(embed=embed)
