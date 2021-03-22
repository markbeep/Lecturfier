import math

import discord
from discord.ext import commands
import datetime
import time
import random
import json
from pytz import timezone
import traceback
from helper.log import log
from discord.ext.commands.cooldowns import BucketType
from helper import handySQL


def isascii(s):
    """Checks how many bytes of non-ascii characters there is in the quote"""
    total = 0
    for t in s:
        q = len(t.encode('utf-8'))
        if q > 2:
            total += q
    return total < 300


async def send_quote(ctx, quote, date, name, index=None):
    embed = discord.Embed(description=quote, color=0x404648)
    footer_txt = ""
    if index is not None:
        footer_txt += f"| Quote ID: {index}"
    embed.set_footer(text=f"-{name}, {date}" + footer_txt)
    await ctx.send(embed=embed)


class Quote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.time = 0
        with open("./data/ignored_users.json") as f:
            self.ignored_users = json.load(f)
        self.quotes_filepath = "./data/quotes.json"
        with open(self.quotes_filepath, "r") as f:
            self.quotes = json.load(f)
        self.aliases = {
            "püschel": [
                "pueschel",
                "peuschel",
                "pushel",
                "puschel"
            ],
            "steurer": [
                "streuer",
                "steuer"
            ],
            "cannas": [
                "ana",
                "canas",
                "annas",
                "anna",
                "canna"

            ],
            "gross": [
                "thomas",
                "thoma"
            ],
            "olga": [
                "olge",
                "sorkine",
                "sarkine"
            ],
            "burger": [

            ],
            "barbara": [

            ],
            "onur": [
                "mutlu",
                "mutu",
                "multu"
            ],
            "lengler": [
                "lenger"
            ]
        }
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

    @commands.cooldown(4, 10, BucketType.user)
    @commands.command(aliases=["q", "quotes"], usage="quote [user] [quote/command/index]")
    async def quote(self, ctx, name=None, *quote):
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

        # Get the guild ID or returns an error message
        try:
            guild_id = ctx.message.guild.id
        except AttributeError:
            await ctx.send("Quotes are currently not supported in private messages")
            raise discord.ext.commands.BadArgument

        # creates the db connection
        conn = self.get_connection()
        c = conn.cursor()
        if name is not None:
            if name.lower() in ["del", "all"]:
                embed = discord.Embed(title="Quote Error", description=f"Can't use `all` or `del` as names. Did you mean to do `$quote <user> {name.lower()}`?", color=0xFF0000)
                await ctx.send(embed=embed)
                raise discord.ext.commands.errors.BadArgument
            if name == "names":
                # lists all names/discord id's of users with quotes
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
                    await ctx.send(embed=embed)
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
                        for row in res[index: index+per_field]:
                            if row[1] is None:
                                quoted_name = row[0]
                            else:
                                quoted_name = f"<@{handySQL.get_DiscordUserID(conn, row[1])}>"
                            field_msg += f"- {quoted_name}\n"
                        embed.add_field(name=f"Field #{msg_number}", value=field_msg)
                        index += per_field
                        msg_number += 1
                    await ctx.send(embed=embed)
            else:
                # first checks if its a valid discord user ID. If not, sets member to None
                try:
                    user_id = name.replace("<@", "").replace(">", "").replace("!", "")
                    member = ctx.message.guild.get_member(int(user_id))
                    uniqueID = handySQL.get_uniqueMemberID(conn, user_id, guild_id)
                except ValueError:
                    print("Not a discord member ID")
                    member = None
                    uniqueID = -1

                # if there is only a name/ID given, send a random quote from that user
                if len(quote) == 0:
                    if name.lower() in ["del", "all"]:
                        embed = discord.Embed(
                            title="Quotes Error",
                            description=f"Incorrect arguments for delete/add command.",
                            color=0xFF0000)
                        await ctx.send(embed=embed)
                        raise discord.ext.commands.BadArgument

                    # tries to first query if its a quote ID
                    c.execute("SELECT Quote, QuoteID, Name, CreatedAt FROM Quotes WHERE QuoteID=? AND DiscordGuildID=?", (name, ctx.message.guild.id))
                    res = c.fetchone()
                    if res is None:
                        # if its a user ID, gets all quotes from the user with that ID
                        if member is not None:
                            c.execute("SELECT Quote, QuoteID, Name, CreatedAt FROM Quotes WHERE UniqueMemberID=? AND DiscordGuildID=? ORDER BY RANDOM() LIMIT 1", (uniqueID, ctx.message.guild.id))
                        else:
                            c.execute("SELECT Quote, QuoteID, Name, CreatedAt FROM Quotes WHERE Name LIKE ? AND DiscordGuildID=? ORDER BY RANDOM() LIMIT 1", (f"%{name}%", ctx.message.guild.id))
                        res = c.fetchone()

                    if res is None:
                        # userID has no quote on this server
                        embed = discord.Embed(title="Quotes", description=f"No quote found from user or with ID `{name}`")
                        await ctx.send(embed=embed)
                        raise discord.ext.commands.errors.BadArgument

                    await send_quote(ctx, res[0], res[3], res[2], res[1])
                    return

                else:
                    # if theres something behind the name
                    # this makes the array of parameters into a string
                    quote = " ".join(quote)

                    try:
                        # Checks if the quote is a quote index
                        index = int(quote)
                        # checks if the user even has any quotes
                        if member is not None:
                            c.execute("SELECT * FROM Quotes WHERE UniqueMemberID=? AND DiscordGuildID=?", (uniqueID, guild_id))
                        else:
                            c.execute("SELECT * FROM Quotes WHERE Name LIKE ? AND DiscordGuildID=?", (f"%{name}%", guild_id))
                        res = c.fetchall()
                        amt = len(res)
                        if amt == 0:
                            embed = discord.Embed(
                                title="Quotes Error",
                                description=f"There does not exist any quote for the user \"{name}\"",
                                color=0xFF0000)
                            await ctx.send(embed=embed)
                            raise discord.ext.commands.errors.BadArgument

                        # checks if the index exists
                        if member is not None:
                            c.execute("SELECT Quote, Name, CreatedAt, QuoteID FROM Quotes WHERE UniqueMemberID=? AND DiscordGuildID=? ORDER BY QuoteID LIMIT 1 OFFSET ?", (uniqueID, guild_id, index))
                        else:
                            c.execute("SELECT Quote, Name, CreatedAt, QuoteID FROM Quotes WHERE Name LIKE ? AND DiscordGuildID=? ORDER BY QuoteID LIMIT 1 OFFSET ?", (f"%{name}%", guild_id, index))
                        res = c.fetchone()
                        if res is None:
                            embed = discord.Embed(
                                title="Quotes Error",
                                description=f"There does not exist a quote with that index for the user \"{name}\". "
                                            f"Keep index between `0` and `{amt}`",
                                color=0xFF0000)
                            await ctx.send(embed=embed)
                            raise discord.ext.commands.errors.BadArgument
                        await send_quote(ctx, res[0], res[2], res[1], res[3])

                    except ValueError:
                        # Is the quote a command or a new quote to add
                        if quote.lower().split(" ")[0] == "all":
                            # show all quotes from name
                            quote_list = ""

                            # executes query to get all quotes
                            if member is not None:
                                c.execute("SELECT Quote, Name, CreatedAt, QuoteID FROM Quotes WHERE UniqueMemberID=? AND DiscordGuildID=? ORDER BY QuoteID", (uniqueID, guild_id))
                            else:
                                c.execute("SELECT Quote, Name, CreatedAt, QuoteID FROM Quotes WHERE Name LIKE ? AND DiscordGuildID=? ORDER BY QuoteID", (f"%{name}%", guild_id))
                            res = c.fetchall()

                            # If there are no quotes for the given person;
                            if len(res) == 0:
                                embed = discord.Embed(title="Quotes Error", description=f"{name} doesn't have any quotes yet.", color=0xFF0000)
                                await ctx.send(embed=embed)
                                raise discord.ext.commands.errors.BadArgument

                            i = 0
                            for row in res:
                                quote_to_add = row[0].replace("*", "").replace("_", "").replace("~", "").replace("\\", "").replace("`", "")
                                if len(quote_to_add) > 150:
                                    quote_to_add = quote_to_add[:150] + "**[...]**"
                                quote_list += f"\n**#{i}:** {quote_to_add} `[ID: {row[3]}]`"
                                i += 1

                            # better splitting method
                            remaining_quotes = quote_list
                            embeds_to_send = []
                            message_count = 1
                            page_count = 1

                            quoted_name = name
                            if member is not None:
                                quoted_name = member.name
                            while len(remaining_quotes) > 0:
                                # split quotes into multiple chunks of max 6000 chars
                                if len(remaining_quotes) >= 5900:
                                    rind = remaining_quotes.rindex("\n", 0, 5900)
                                else:
                                    rind = len(remaining_quotes)
                                single_msg = remaining_quotes[0:rind]
                                remaining_quotes = remaining_quotes[rind:]
                                embed = discord.Embed(title=f"All quotes from {quoted_name}", description=f"`Message {message_count}`", color=0x404648)
                                message_count += 1
                                embeds_to_send.append(embed)
                                while len(single_msg) > 0:
                                    # split quotes into multiple fields of max 1000 chars
                                    if len(single_msg) >= 1000:
                                        rind2 = single_msg.rindex("\n", 0, 1000)
                                        if rind2 == 0:
                                            # one quote is more than 1000 chars
                                            rind2 = single_msg.rindex(" ", 0, 1000)
                                    else:
                                        rind2 = len(single_msg)
                                    embed.add_field(name=f"Page {page_count}", value=single_msg[0:rind2])
                                    single_msg = single_msg[rind2:]
                                    page_count += 1

                            for e in embeds_to_send:
                                # sends all embeds messages
                                await ctx.send(embed=e)

                        elif quote.lower().split(" ")[0] == "del":  # Command to delete quotes
                            if not await self.bot.is_owner(ctx.author):
                                raise discord.ext.commands.errors.NotOwner
                            try:
                                quote_id = int(quote.lower().split(" ")[1])
                                try:
                                    c.execute("DELETE FROM Quotes WHERE QuoteID=?", (quote_id,))
                                    conn.commit()

                                    await ctx.send(f"Deleted quote with quote ID {quote_id}.")
                                except IndexError:
                                    await ctx.send("No name with that index.")
                            except (IndexError, ValueError):
                                await ctx.send("You forgot to add an index.")
                        else:  # If the quote is a new quote to add
                            if len(quote) > 500 and not await self.bot.is_owner(ctx.author):
                                embed = discord.Embed(
                                    title="Quote Error",
                                    description="This quote exceeds the max_length length of 500 chars. Ping Mark if you want the quote added.",
                                    color=0xFF0000)
                                await ctx.send(embed=embed)
                                raise discord.ext.commands.errors.NotOwner

                            if not isascii(quote) and not await self.bot.is_owner(ctx.author):
                                embed = discord.Embed(
                                    title="Quote Error",
                                    description="This quote contains too many non-ascii characters. Ping Mark if you want the quote added.",
                                    color=0xFF0000)
                                await ctx.send(embed=embed)
                                raise discord.ext.commands.errors.BadArgument

                            # corrects some values
                            if uniqueID == -1:
                                uniqueID = None
                                quoted_name = name
                            else:
                                quoted_name = member.name
                            addedByUniqueID = handySQL.get_uniqueMemberID(conn, ctx.message.author.id, guild_id)

                            sql = """   INSERT INTO Quotes(Quote, Name, UniqueMemberID, AddedByUniqueMemberID, DiscordGuildID)
                                        VALUES (?,?,?,?,?)"""
                            c.execute(sql, (quote, quoted_name, uniqueID, addedByUniqueID, guild_id))
                            conn.commit()

                            embed = discord.Embed(title="Added Quote", description=f"Added quote for {name}", color=0x00FF00)
                            await ctx.send(embed=embed)
        else:
            # If $quote is written on its own, send a random quote from any user
            c.execute("SELECT Quote, QuoteID, Name, CreatedAt FROM Quotes WHERE DiscordGuildID=? ORDER BY RANDOM() LIMIT 1", (ctx.message.guild.id,))
            res = c.fetchone()
            if res is None:
                embed = discord.Embed(title="Quote Error", description="There are no quotes on this server yet.", color=0xFF0000)
                await ctx.send(embed=embed)
                raise discord.ext.commands.errors.BadArgument
            await send_quote(ctx, res[0], res[3], res[2], res[1])

    async def user_checkup(self, guild_id, name):
        # If the guild doesnt exist in quotes yet
        if str(guild_id) not in self.quotes:
            self.quotes[str(guild_id)] = {}

        # If the user doesnt exist in quotes yet
        if str(name) not in self.quotes[str(guild_id)]:
            self.quotes[str(guild_id)][name] = []


def setup(bot):
    bot.add_cog(Quote(bot))
