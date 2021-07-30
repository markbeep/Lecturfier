import asyncio
import math
import discord
from discord.ext import commands, menus
import datetime
import json
from pytz import timezone
from discord.ext.commands.cooldowns import BucketType
from helper.sql import SQLFunctions
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


async def send_quote(channel: discord.channel, quote: SQLFunctions.Quote):
    embed = discord.Embed(description=quote.QuoteText, color=0x404648)
    local_tz = timezone("Europe/Zurich")
    dt = quote.CreatedAt.astimezone(local_tz).strftime("%d.%b %Y").lstrip("0")
    embed.set_footer(text=f"-{quote.Name}, {dt} | Quote ID: {quote.QuoteID}")
    await channel.send(embed=embed)


class Quote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.time = 0
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()

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

            blocked_channels = SQLFunctions.get_config("BlockedQuoteChannel", self.conn)
            if channel.id in blocked_channels:
                print("Blocked Quote Channel. Ignoring quote.")
                return

            await self.add_quote(username=user, message=message, quote=message.content, quoteAdder=quoteAdder, reactionQuote=True)

    @commands.cooldown(4, 10, BucketType.user)
    @commands.guild_only()
    @commands.group(aliases=["q", "quotes"], usage="quote [user [quote/index]]", invoke_without_command=True)
    async def quote(self, ctx, name=None, *, quote=""):
        """
        Sends a completely random quote from the server if all parameters are empty. \
        If only a name is given, it sends a random quote from that user.

        Some examples:
        `$quote`   - sends a random quote from any user
        `$quote ueli`   - sends a random quote from the user ueli
        `$quote ueli haHaa`   - adds "haHaa" as a quote to the user ueli
        `$quote ueli all`   - displays all quotes from the user ueli
        `$quote ueli 23`   - displays the 23rd indexed quote from the user ueli
        `$quote names`   - displays all names that have a quote
        """
        if ctx.invoked_subcommand is not None:
            return

        # if message is a reply, add the replied message as a quote
        reply = ctx.message.reference
        if reply is not None and name is None and len(quote) == 0:
            reply_message = await ctx.message.channel.fetch_message(reply.message_id)
            name = str(reply_message.author.id)
            quote = reply_message.content
            await self.add_quote(username=name, message=reply_message, quote=quote, quoteAdder=ctx.message.author)
            return

        if name is None:  # no user is given, so send a random quote
            # If $quote is written on its own, send a random quote from any user
            quote = SQLFunctions.get_quote(-1, guild_id=ctx.message.guild.id, conn=self.conn, random=True)
            if quote is None:
                embed = discord.Embed(title="Quote Error", description="There are no quotes on this server yet.", color=0xFF0000)
                await ctx.send(embed=embed)
                raise discord.ext.commands.errors.BadArgument
            await send_quote(ctx, quote)

        else:  # there's a user given
            # if there is only a name/ID given, send a random quote from that user
            if len(quote) == 0:

                q = None
                try:
                    quote_id = int(name.replace("<@", "").replace(">", "").replace("!", ""))
                    # tries to first query if its a quote ID
                    q = SQLFunctions.get_quote(quote_id, guild_id=ctx.message.guild.id, conn=self.conn)
                except ValueError:
                    pass
                if q is None:  # its not a valid quote ID in this case
                    # if its a user ID, gets a random quote from the user with that ID
                    member, multUniqueIDs = await self.get_quote_members(ctx, name)
                    if member is not None:
                        quotes = SQLFunctions.get_quotes_by_user(unique_member_id=member.UniqueMemberID, guild_id=ctx.message.guild.id, conn=self.conn, random=True)
                    else:
                        quotes = SQLFunctions.get_quotes_by_user(name=name, guild_id=ctx.message.guild.id, conn=self.conn, random=True)
                    if len(quotes) == 0:
                        q = None
                    else:
                        q = quotes[0]
                if q is None:
                    # userID has no quote on this server
                    embed = discord.Embed(title="Quotes", description=f"No quote found from user or with ID `{name}`")
                    await ctx.send(embed=embed)
                    raise discord.ext.commands.errors.BadArgument

                await send_quote(ctx, q)
                return

            else:
                # if theres something behind the name

                # if its an index behind the user
                if quote.isnumeric():
                    index = int(quote)
                    user_id = name.replace("<@", "").replace(">", "").replace("!", "")
                    if user_id.isnumeric():
                        quotes = SQLFunctions.get_quotes_by_user(discord_user_id=int(user_id), guild_id=ctx.message.guild.id, conn=self.conn)
                    else:
                        quotes = SQLFunctions.get_quotes_by_user(name=name, guild_id=ctx.message.guild.id, conn=self.conn)
                    if len(quotes) == 0:
                        embed = discord.Embed(
                            title="Quotes Error",
                            description=f"There does not exist any quote for the user `{name}`",
                            color=0xFF0000)
                        await ctx.send(embed=embed)
                        raise discord.ext.commands.errors.BadArgument
                    if index < 0 or index >= len(quotes):
                        embed = discord.Embed(
                            title="Quotes Error",
                            description=f"There does not exist a quote with that index for the user \"{name}\". "
                                        f"Keep the index between `0 <= index < {len(quotes)}`.",
                            color=0xFF0000)
                        await ctx.send(embed=embed)
                        raise discord.ext.commands.errors.BadArgument
                    q = quotes[index]
                    await send_quote(ctx.channel, q)

                else:  # its a new quote to add
                    if quote.lower().split(" ")[0] == "all":
                        await self.get_all_quotes(ctx, name)
                        return

                    await self.add_quote(username=name, quote=quote, message=ctx.message)

    async def get_quote_members(self, channel: discord.TextChannel, username: str) -> (SQLFunctions.DiscordMember, list[int]):
        uniqueIDs = []  # list of all matching uniqueIDs

        user_id = username.replace("<@", "").replace(">", "").replace("!", "")
        if user_id.isnumeric():
            member = channel.guild.get_member(int(user_id))
            if member is not None:
                all_discord_members = SQLFunctions.get_members_by_name("none", channel.guild.id, discord_user_id=member.id, conn=self.conn)
                if len(all_discord_members) == 0:
                    return None, []
                discord_member = all_discord_members[0]
                uniqueIDs.append(discord_member.UniqueMemberID)
                return discord_member, uniqueIDs

        # Not a discord member ID
        # We make a list of all uniqueIDs with the matching name)
        all_discord_members = SQLFunctions.get_members_by_name(username, channel.guild.id, conn=self.conn)
        uniqueIDs = [m.UniqueMemberID for m in all_discord_members]
        discord_member = None

        return discord_member, uniqueIDs

    async def add_quote(self, username, message: discord.Message, quote, quoteAdder: discord.Member = None, reactionQuote=False):
        username = username.replace("<@", "").replace(">", "").replace("!", "")
        channel = message.channel
        if quoteAdder is None:
            quoteAdder = message.author

        member, multipleUniqueIDs = await self.get_quote_members(channel, username)

        # Some error messages ------------------------------
        # If the quote is too long
        if len(quote) > 500 and not await self.bot.is_owner(quoteAdder):
            embed = discord.Embed(
                title="Quote Error",
                description="This quote exceeds the max_length length of 500 chars. Ping Mark if you want the quote added.",
                color=0xFF0000)
            if reactionQuote:
                try:
                    await message.add_reaction("<:tooLongQuote:852876951407820820>")
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
                    await message.add_reaction("<:tooLongQuote:852876951407820820>")
                except discord.errors.Forbidden:
                    pass
            else:
                await channel.send(content=quoteAdder.mention, embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument

        blocked_ids = SQLFunctions.get_config("BlockQuote", self.conn)

        # If the user is blocked from adding quotes
        if quoteAdder.id in blocked_ids:
            embed = discord.Embed(
                title="Quote Error",
                description="You are blocked from adding new quotes. Possible reasons include adding too many fake quotes or "
                            "simply spamming the quote command.",
                color=0xFF0000)
            if reactionQuote:
                try:
                    await message.add_reaction("<:blockedFromQuoting:840988109578698782>")
                except discord.errors.Forbidden:
                    pass
            else:
                await channel.send(content=quoteAdder.mention, embed=embed, delete_after=5)
                await message.delete(delay=2)
            raise discord.ext.commands.errors.BadArgument

        uniqueID = None
        if member is None:  # that username is not a discord username or has no uniqueID
            quoted_name = username
            # is it a DiscordUserID though?
            if username.isnumeric():
                quoted_member = channel.guild.get_member(int(username))
                member = SQLFunctions.get_or_create_discord_member(quoted_member, conn=self.conn)
                quoted_name = quoted_member.name
        else:
            quoted_name = member.User.DisplayName
            uniqueID = multipleUniqueIDs[0]
        addedBy = SQLFunctions.get_or_create_discord_member(quoteAdder, conn=self.conn)

        # checks if its a self quote
        if addedBy.UniqueMemberID in multipleUniqueIDs:
            embed = discord.Embed(
                title="Quote Error",
                description="You can't quote yourself. That's pretty lame.",
                color=0xFF0000)
            embed.set_footer(text="(Or your username is the same as the person you're trying to quote.)")
            if reactionQuote:
                try:
                    await message.add_reaction("<:selfQuote:852877064515092520>")
                except discord.errors.Forbidden:
                    pass
            else:
                await channel.send(content=quoteAdder.mention, embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument

        # checks if the quote exists already
        if uniqueID is None:
            res = SQLFunctions.get_quotes_by_user(quote=quote, guild_id=channel.guild.id, name=username)
        else:
            res = SQLFunctions.get_quotes_by_user(quote=quote, guild_id=channel.guild.id, unique_member_id=uniqueID)
        if len(res) > 0:
            embed = discord.Embed(
                title="Quote Error",
                description="This quote has been added already.",
                color=0xFF0000)
            if not reactionQuote:
                await channel.send(content=quoteAdder.mention, embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument

        aliases = SQLFunctions.get_quote_aliases(self.conn)
        for a in aliases.keys():
            if a.lower() == quoted_name.lower():
                quoted_name = a
                break

        quote_object: SQLFunctions.Quote = SQLFunctions.add_quote(quote, quoted_name, member, addedBy, channel.guild.id)
        quoteID = "n/a"
        if quote_object is not None:
            quoteID = quote_object.QuoteID

        if reactionQuote:
            try:
                await message.add_reaction("<:addedQuote:840985556304265237>")
            except discord.errors.NotFound:
                pass

        embed = discord.Embed(title="Added Quote", description=f"Added quote for {quoted_name}\nQuoteID: `{quoteID}`", color=0x00FF00)

        if reactionQuote:
            await message.reply(embed=embed, mention_author=False)
        else:
            await channel.send(embed=embed)

    @commands.guild_only()
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
            total_quotes, total_names = SQLFunctions.get_quote_stats(self.conn)

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
    async def report(self, ctx, quoteID=None, *, reason=""):
        """
        Report quotes which should be deleted. This makes deleting quotes a lot easier \
        and more organized. Additionally ping @mark so he knows a quote was reported.
        """
        if ctx.invoked_subcommand is not None:
            return
        print(f"{reason=}")
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

        # check if quote ID is a valid ID
        quote = SQLFunctions.get_quote(quote_ID=quoteID, guild_id=ctx.message.guild.id, conn=self.conn)
        if quote is None:
            embed = discord.Embed(
                title="Quotes Error",
                description=f"The given quote ID can't be assigned to a valid quote. Did you type the right ID?",
                color=0xFF0000)
            await ctx.send(embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument

        # check if quote ID is already listed in db
        quotes_to_remove = SQLFunctions.get_quotes_to_remove(self.conn)
        for q in quotes_to_remove:
            if quote.QuoteID == q.Quote.QuoteID:
                embed = discord.Embed(
                    title="Quotes Error",
                    description=f"The given quote ID is already listed in the quotes to remove list.",
                    color=0xFF0000)
                await ctx.send(embed=embed, delete_after=5)
                raise discord.ext.commands.errors.BadArgument
        
        # At this point we have a valid Quote ID, so add it to the database
        member = SQLFunctions.get_or_create_discord_member(ctx.message.author, conn=self.conn)
        SQLFunctions.insert_quote_to_remove(quoteID, reason, member, self.conn)
        embed = discord.Embed(
            title="Added Quote Report",
            description=f"Succesfully requested quote {quoteID} to be deleted.",
            color=0x00FF00)
        await ctx.send(embed=embed, delete_after=5)

    @commands.is_owner()
    @commands.guild_only()
    @report.command(aliases=["show", "all"], usage="showReports")
    async def showReports(self, ctx):
        """
        Shows all reported quotes in an easy to use fashion.
        Permissions: Owner
        """
        # get all the reports
        quotes_to_remove = SQLFunctions.get_quotes_to_remove(self.conn)

        # fetches each quote and adds it to a page
        # 1 quote per page
        pages = []
        while len(quotes_to_remove) > 0:
            quote = quotes_to_remove.pop()
            # userID, quoteID, quote, reporterID, name, reason
            pages.append([
                quote.Quote.Member.DiscordUserID,
                quote.Quote.QuoteID,
                quote.Quote.QuoteText,
                quote.Reporter.DiscordUserID,
                quote.Quote.Name,
                quote.Reason
            ])

        # should have a list of page lists, each with a max of 10 elements
        # in each page element we have user ID, quoute ID and the quote itself
        if len(pages) == 0:
            await ctx.send("There are no reported quotes to remove.")
            return
        
        m = QuotesToRemove(pages, self.conn)
        await m.start(ctx=ctx, channel=ctx.channel)

    async def get_all_quotes(self, ctx, user):
        member, multUniqueIDs = await self.get_quote_members(ctx.message.channel, user)

        quote_list = ""

        # executes query to get all quotes
        if member is not None:
            all_quotes = SQLFunctions.get_quotes_by_user(unique_member_id=member.UniqueMemberID, guild_id=ctx.message.guild.id, conn=self.conn)
        else:
            all_quotes = SQLFunctions.get_quotes_by_user(name=user, guild_id=ctx.message.guild.id, conn=self.conn)

        # If there are no quotes for the given person;
        if len(all_quotes) == 0:
            embed = discord.Embed(title="Quotes Error", description=f"{user} doesn't have any quotes yet.", color=0xFF0000)
            await ctx.send(embed=embed)
            raise discord.ext.commands.errors.BadArgument

        i = 0
        for quote in all_quotes:
            quote_to_add = quote.QuoteText.replace("*", "").replace("~", "").replace("\\", "").replace("`", "")
            if quote_to_add.count("\n") > 2:
                # makes multiline quotes not fill too many lines
                split_lines = quote_to_add.split("\n")
                quote_to_add = "\n".join(split_lines[:2]) + "\n **[...]**"
            if len(quote_to_add) > 150:
                quote_to_add = quote_to_add[:150] + "**[...]**"
            quote_list += f"\n**#{i}:** {quote_to_add} `[ID: {quote.QuoteID}]`"
            i += 1

        # splits the messages into different pages by character length
        pages = []

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

        p = Pages(self.bot, ctx, pages, ctx.message.author.id, f"All quotes from {all_quotes[0].Name}", 180)
        if len(pages) > 1:
            await p.handle_pages()
        else:
            await ctx.message.delete(delay=120)
            await ctx.send(embed=p.create_embed(), delete_after=120)

    @commands.is_owner()
    @quote.command(name="delete", aliases=["del"], usage="delete <Quote ID>")
    async def delete_quote(self, ctx, quoteID=None):
        """
        Deletes the quote with the given ID.
        Permissions: Owner
        """
        try:
            quote_id = int(quoteID)
            try:
                SQLFunctions.delete_quote(quoteID, self.conn)

                await ctx.send(f"Deleted quote with quote ID {quote_id}.")
            except IndexError:
                await ctx.send("No name with that index.")
        except (IndexError, ValueError):
            await ctx.send("You forgot to add an index.")

    @commands.guild_only()
    @quote.command(name="names", aliases=["name"], usage="names")
    async def quote_names(self, ctx):
        """
        Lists all names/discord id's that have at least one quote.
        It's sorted by amount of quotes each user has in descending order.
        """
        quoted_names = SQLFunctions.get_quoted_names(ctx.message.guild, self.conn)

        # If there are no quotes on the server
        if len(quoted_names) == 0:
            embed = discord.Embed(title="Quote Error", description="There are no quotes on this server yet.", color=0xFF0000)
            await ctx.send(embed=embed)
            raise discord.ext.commands.errors.BadArgument

        MAX_FIELDS = 21
        per_field = math.ceil(len(quoted_names) / MAX_FIELDS)  # the amount of names per field to have a max of 21 fields

        # create mention message to cache the mentions for the watching discord users
        mention_message = ""
        messages_to_send = []
        for name in quoted_names:
            if len(mention_message) > 1970:
                messages_to_send.append(mention_message)
                mention_message = ""
            if name.member is not None:
                mention_message += f"<@{name.member.DiscordUserID}> "
        if len(mention_message) > 0:
            messages_to_send.append(mention_message)

        # splits the names into the given amount of MAX_FIELDS
        names_message = ""
        for name in quoted_names:
            name_to_use = name.quote.Name
            if name.member is not None:
                name_to_use = f"<@{name.member.DiscordUserID}>"
            names_message += f"-{name_to_use} `({name.total_quotes} quotes)`\n"

        # splits the messages into sub 2000 char chunks
        pages = []
        while len(names_message) > 1000:
            index = names_message.rindex("\n", 0, 1000)
            pages.append(names_message[:index])
            names_message = names_message[index:]
        if len(names_message) > 0:
            pages.append(names_message)

        # sends the initial message, then edits it to a mention message and deletes it afterwards
        for m in messages_to_send:
            msg = await ctx.send("mentions go brrrrrrr <a:partypoop:412336219175780353>")
            await msg.edit(content=m)
            await msg.delete()

        p = Pages(self.bot, ctx, pages, ctx.message.author.id, "All Quote Names")
        if len(pages) > 1:
            await p.handle_pages()
        else:
            await ctx.send(embed=p.create_embed(), delete_after=60)
            await ctx.message.delete(delay=60)


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
        userID, quoteID, quote, reporterID, name, reason = self.pages[page_number]
        if len(reason) > 700:
            reason = reason[:700] + "..."
        elif reason == "":
            reason = "*No reason was given.*"
        if userID is not None:
            embed.add_field(name=f"ID: {quoteID} | {name}", value=f"Discord User: <@{userID}>\nReported by: <@{reporterID}>\n**Quote:**\n{quote}\n**Reason:**\n{reason}")
        else:
            embed.add_field(name=f"ID: {quoteID} | {name}", value="Reported by: <@{reporterID}>\n**Quote:**\n{quote}\n**Reason:**\n{reason}")
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
        userID, quoteID, quote, reporterID, name, reason = self.pages[self.page_count]
        SQLFunctions.delete_quote(quoteID, self.conn)
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
        userID, quoteID, quote, reporterID, name, reason = self.pages[self.page_count]
        SQLFunctions.delete_quote_to_remove(quoteID, self.conn)
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
            try:
                # We add a timeout so that the message still gets deleted
                # even if nobody presses any button
                res = await self.bot.wait_for("button_click", timeout=10)
            except asyncio.TimeoutError:
                continue
            if res.message is not None and res.message.id == self.message.id:
                try:
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
                        await res.respond(type=InteractionType.UpdateMessage, components=self.get_components(), embed=self.create_embed())
                    else:
                        await res.respond(type=InteractionType.ChannelMessageWithSource, content="This page wasn't called by you.")
                except AttributeError:
                    await res.respond(type=InteractionType.ChannelMessageWithSource, content="Sorry got a little error. Simply press the button again.")
        try:
            await self.ctx.message.delete()
        except discord.errors.NotFound:
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
            components[1] = Button(style=ButtonStyle.grey, label="<", disabled=True)

        return [components]

    def create_embed(self) -> discord.Embed:
        """
        Creates a discord embed with the given self.embed_title as
        the title and the page depending on the current page we're on.
        """
        embed = discord.Embed(title=self.embed_title, color=0x404648)
        embed.add_field(name=f"Page {self.page_count + 1} / {len(self.pages)}", value=self.pages[self.page_count])
        embed.set_author(name=str(self.ctx.message.author), icon_url=self.ctx.message.author.avatar_url)
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
