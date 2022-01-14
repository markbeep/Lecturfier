import asyncio
import math
import random
import time
from datetime import datetime
from enum import Enum

import discord
from discord.ext import commands, menus
from discord.ext.commands.cooldowns import BucketType
from discord_components import (Button, ButtonStyle, DiscordComponents,
                                Interaction, InteractionType)
from pytz import timezone

from helper.sql import SQLFunctions


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
    embed.set_footer(text=f"-{quote.Name}, {dt} | Quote ID: {quote.QuoteID} | Elo: {round(quote.Elo)}")
    await channel.send(embed=embed)


class Winner(Enum):
    First = 1
    Second = 2
    Draw = 3


def determine_k_value(rating) -> int:
    if rating < 600:
        return 40
    if rating < 1200:
        return 32
    if rating < 1600:
        return 24
    return 16


def calculate_elo(elo1, elo2, winner: Winner) -> tuple[int, int]:
    """
    Calculates the new Elos depending on who won.
    https://metinmediamath.wordpress.com/2013/11/27/how-to-calculate-the-elo-rating-including-example/
    """
    t_rating1 = 10 ** (elo1 / 400)
    t_rating2 = 10 ** (elo2 / 400)
    expected_score1 = t_rating1 / (t_rating1 + t_rating2)
    expected_score2 = t_rating2 / (t_rating1 + t_rating2)
    if winner == Winner.First:
        act_score1 = 1
        act_score2 = 0
    elif winner == Winner.Draw:
        act_score1 = 0.5
        act_score2 = 0.5
    else:
        act_score1 = 0
        act_score2 = 1
    updated_elo1 = elo1 + determine_k_value(elo1) * (act_score1 - expected_score1)
    updated_elo2 = elo2 + determine_k_value(elo2) * (act_score2 - expected_score2)
    if updated_elo1 < 0:
        updated_elo1 = 0
    if updated_elo2 < 0:
        updated_elo2 = 0
    return updated_elo1, updated_elo2


def set_new_elo(score1, score2, quote1: SQLFunctions.Quote, quote2: SQLFunctions.Quote, conn) -> tuple[int, int]:
    if score1 == score2:  # draw
        current_elo1, current_elo2 = quote1.Elo, quote2.Elo
        for _ in range(score1 + score2):
            current_elo1, current_elo2 = calculate_elo(current_elo1, current_elo2, Winner.Draw)
        SQLFunctions.update_quote_battle(quote1.QuoteID, quote1.AmountBattled + score1 + score2, quote1.AmountWon + score1, current_elo1, conn)
        SQLFunctions.update_quote_battle(quote2.QuoteID, quote2.AmountBattled + score1 + score2, quote2.AmountWon + score2, current_elo2, conn)
        return current_elo1, current_elo2
    if score1 > score2:  # first quote won
        diff = score1 - score2
        current_elo1, current_elo2 = quote1.Elo, quote2.Elo
        for _ in range(diff):
            current_elo1, current_elo2 = calculate_elo(current_elo1, current_elo2, Winner.First)
        SQLFunctions.update_quote_battle(quote1.QuoteID, quote1.AmountBattled + score1 + score2, quote1.AmountWon + score1, current_elo1, conn)
        SQLFunctions.update_quote_battle(quote2.QuoteID, quote2.AmountBattled + score1 + score2, quote2.AmountWon + score2, current_elo2, conn)
        return current_elo1, current_elo2
    # second quote won
    diff = score2 - score1
    current_elo1, current_elo2 = quote1.Elo, quote2.Elo
    for _ in range(diff):
        current_elo1, current_elo2 = calculate_elo(current_elo1, current_elo2, Winner.Second)
    SQLFunctions.update_quote_battle(quote1.QuoteID, quote1.AmountBattled + score1 + score2, quote1.AmountWon + score1, current_elo1, conn)
    SQLFunctions.update_quote_battle(quote2.QuoteID, quote2.AmountBattled + score1 + score2, quote2.AmountWon + score2, current_elo2, conn)
    return current_elo1, current_elo2


class Battle:
    def __init__(self, embed: discord.Embed, components: list[list[Button]], quote1: SQLFunctions.Quote, quote2: SQLFunctions.Quote, rank1: int,
                 rank2: int, pause: bool):
        self.embed = embed
        self.components = components
        self.quote1 = quote1
        self.quote2 = quote2
        self.rank1 = rank1
        self.rank2 = rank2
        self.pause = pause  # True if the battle didnt start immediately
        self.message: discord.Message = None

    def add_message(self, message: discord.Message):
        self.message = message

    def __repr__(self):
        return f"{self.quote1.QuoteID} : {self.quote2.QuoteID}"


def recover_quote_battle(message: discord.Message, conn) -> Battle:
    embed = message.embeds[0]
    name1 = embed.fields[0].name
    quote1_id = int(name1.split(" | ")[1].replace("ID: ", ""))
    name2 = embed.fields[1].name
    quote2_id = int(name2.split(" | ")[1].replace("ID: ", ""))
    quote1 = SQLFunctions.get_quote(quote1_id, message.guild.id, conn)
    quote2 = SQLFunctions.get_quote(quote2_id, message.guild.id, conn)
    battle = Battle(
        embed=embed,
        components=[],
        quote1=quote1,
        quote2=quote2,
        rank1=-1,
        rank2=-2,
        pause=True
    )
    battle.add_message(message)
    return battle


class Quote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.time = 0
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()
        self.battle_scores = {}  # message id and score of the battle as a tuple
        self.voted_users = {}  # dict with lists of users that voted on a battle
        channel_id = SQLFunctions.get_config("QuoteBattleChannel")
        if len(channel_id) > 0:
            channel_id = channel_id[0]
        else:
            channel_id = -1
        self.battle_channel = self.bot.get_channel(channel_id)
        self.active_battles = []  # current active quote battles

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

    @commands.Cog.listener()
    async def on_button_click(self, res: Interaction):
        if res.component.id in ["1", "2", "3"]:
            found_battle = None
            # True if the message hasnt been edited in a while
            battle_deactivated = res.message.edited_at is None or datetime.timestamp(res.message.edited_at) + 15 < datetime.timestamp(
                datetime.utcnow())
            if res.message.id not in self.battle_scores or res.message.id not in self.voted_users or battle_deactivated:
                # the message ID is not in any of dicts => battle isn't active right now
                # if the battle exists in self.active_battles, start the battle, else its simply a lost battle
                for b in self.active_battles:
                    if res.message.id == b.message.id:
                        found_battle = b
                if not found_battle:  # probably a lost battle, so we recover it
                    found_battle = recover_quote_battle(res.message, self.conn)
                # we only set new empty battle scores if the battle is not in cache
                if res.message.id not in self.battle_scores or res.message.id not in self.voted_users:
                    self.init_battle_dict(res.message, found_battle)
                print("Reactivated battle: ", found_battle)

            # the battle is ongoing, so add the vote where it belongs
            for i in range(5):  # incase of an error, we try at max 5 times again
                try:
                    if res.component.id == "3":
                        await res.respond(type=InteractionType.ChannelMessageWithSource,
                                          content="You selected the bin button. The bin simply starts the battle countdown if it hasn't "
                                                  "yet so you don't have to vote if both quotes are crap.")
                    elif res.user.id in self.voted_users[res.message.id]:
                        await res.respond(type=InteractionType.ChannelMessageWithSource,
                                          content="You already voted on this battle. You can't vote twice.\n"
                                                  "*If this battle is bugged, try the button in ~10 seconds again. That should reactivate it again.*")
                    else:
                        self.battle_scores[res.message.id][int(res.component.id) - 1] += 1  # increments the score
                        self.voted_users[res.message.id].append(res.user.id)
                        member = res.message.guild.get_member(res.user.id)
                        if member is None:
                            member = await res.message.guild.fetch_member(res.user.id)
                        SQLFunctions.update_statistics(member, 0, self.conn, vote_count=1)
                        await res.respond(type=InteractionType.ChannelMessageWithSource, content=f"Successfully voted for option {res.component.id}")
                    if found_battle:  # if this was a recovered battle, start it
                        await self.handle_battle(res.message.channel, found_battle, 20)
                    break
                except discord.errors.DiscordServerError:
                    battle = found_battle
                    if res.message.id in self.active_battles:
                        battle = self.active_battles[res.message.id]
                    print(f"Got a DiscordServerError caught during a quote battle on battle. COUNT: {i}\n"
                          f"\t--- {battle}")
                    await asyncio.sleep(random.randrange(i * 10, i * 20))
                except discord.errors.HTTPException:
                    battle = found_battle
                    if res.message.id in self.active_battles:
                        battle = self.active_battles[res.message.id]
                    print(f"Got a HTTPException which was caught during a quote battle on battle. COUNT: {i}\n"
                          f"\t--- {battle}")
                    await asyncio.sleep(random.randrange(5, 8))
                except KeyError:
                    if not res.responded:
                        await res.respond(type=InteractionType.ChannelMessageWithSource,
                                          content="The battle you voted on seems to have already ended.")

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
            # we check the aliases of that name
            aliases = SQLFunctions.get_quote_aliases(self.conn)
            for a in aliases.keys():
                if a.lower() == name.lower():
                    name = aliases[a]
                    break
            # if there is only a name/ID given, send a random quote from that user
            if len(quote) == 0:

                q = None
                try:
                    quote_id = int(name)
                    # tries to first query if its a quote ID
                    q = SQLFunctions.get_quote(quote_id, guild_id=ctx.message.guild.id, conn=self.conn)
                except ValueError:
                    pass
                if q is None:  # its not a valid quote ID in this case
                    # if its a user ID, gets a random quote from the user with that ID
                    name = name.replace("<@", "").replace(">", "").replace("!", "")
                    discord_member = None
                    if name.isnumeric():
                        discord_member = ctx.message.guild.get_member(int(name))
                    if discord_member is not None:  # we have a quote by a discord user
                        member = SQLFunctions.get_or_create_discord_member(discord_member, 0, self.conn)
                        quotes = SQLFunctions.get_quotes(unique_member_id=member.UniqueMemberID, guild_id=ctx.message.guild.id, conn=self.conn,
                                                         random=True)
                    else:  # its a quote by a non-discord user
                        quotes = SQLFunctions.get_quotes(name=name, guild_id=ctx.message.guild.id, conn=self.conn, random=True)
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
                        quotes = SQLFunctions.get_quotes(discord_user_id=int(user_id), guild_id=ctx.message.guild.id, conn=self.conn)
                    else:
                        quotes = SQLFunctions.get_quotes(name=name, guild_id=ctx.message.guild.id, conn=self.conn)
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
                    return []
                discord_member = all_discord_members[0]
                uniqueIDs.append(discord_member.UniqueMemberID)
                return discord_member, uniqueIDs

        # Not a discord member ID
        # We make a list of all uniqueIDs with the matching name)
        all_discord_members = SQLFunctions.get_members_by_name(username, channel.guild.id, conn=self.conn)
        uniqueIDs = [m.UniqueMemberID for m in all_discord_members]

        return None, uniqueIDs

    async def add_quote(self, username, message: discord.Message, quote, quoteAdder: discord.Member = None, reactionQuote=False,
                        discord_member: discord.Member = None):
        username = username.replace("<@", "").replace(">", "").replace("!", "")
        channel = message.channel
        member = None
        if quoteAdder is None:
            quoteAdder = message.author

        if username.isnumeric() and discord_member is None:
            discord_member = message.guild.get_member(int(username))

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
        if discord_member is not None:  # that username is a discord user ID
            member = SQLFunctions.get_or_create_discord_member(discord_member, conn=self.conn)
            quoted_name = discord_member.name
            uniqueID = member.UniqueMemberID
        else:
            quoted_name = username

        addedBy = SQLFunctions.get_or_create_discord_member(quoteAdder, conn=self.conn)

        # checks if its a self quote
        if addedBy.UniqueMemberID == uniqueID:
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

        aliases = SQLFunctions.get_quote_aliases(self.conn)
        for a in aliases.keys():
            if a.lower() == quoted_name.lower():
                quoted_name = aliases[a]
                break

        # checks if the quote exists already
        if uniqueID is None:
            res = SQLFunctions.get_quotes(quote=quote, guild_id=channel.guild.id, name=quoted_name)
        else:
            res = SQLFunctions.get_quotes(quote=quote, guild_id=channel.guild.id, unique_member_id=uniqueID)
        if len(res) > 0:
            embed = discord.Embed(
                title="Quote Error",
                description="This quote has been added already.",
                color=0xFF0000)
            if not reactionQuote:
                await channel.send(content=quoteAdder.mention, embed=embed, delete_after=5)
            raise discord.ext.commands.errors.BadArgument

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
            total_quotes, total_names, total_voted_on = SQLFunctions.get_quote_stats(ctx.message.guild.id, self.conn)

            embed = discord.Embed(
                title="All Quotes Stats",
                description="You didn't specify what user to get quotes off. So here are some stats."
            )
            embed.add_field(name="Total Quotes", value=total_quotes)
            embed.add_field(name="Total Names", value=total_names)
            if total_quotes == 0:  # just to avoid a DivByZero if there are 0 quotes
                total_quotes = 1
            embed.add_field(name="Voted On", value=f"{total_voted_on} / {total_quotes} ({round(100 * total_voted_on / total_quotes, 1)}%)")
            await ctx.message.reply(embed=embed)
            return
        # we check the aliases of that name
        aliases = SQLFunctions.get_quote_aliases(self.conn)
        for a in aliases.keys():
            if a.lower() == user.lower():
                user = aliases[a]
                break
        await self.get_all_quotes(ctx, user)

    async def get_all_quotes(self, ctx, user):

        member = None
        user = user.replace("<@", "").replace(">", "").replace("!", "")
        if user.isnumeric():
            discord_member = ctx.message.guild.get_member(int(user))
            member = SQLFunctions.get_or_create_discord_member(discord_member, 0, self.conn)

        quote_list = ""

        # executes query to get all quotes
        if member is not None:
            all_quotes = SQLFunctions.get_quotes(unique_member_id=member.UniqueMemberID, guild_id=ctx.message.guild.id, conn=self.conn)
        else:
            all_quotes = SQLFunctions.get_quotes(name=user, guild_id=ctx.message.guild.id, conn=self.conn)

        # If there are no quotes for the given person;
        if len(all_quotes) == 0:
            embed = discord.Embed(title="Quotes Error", description=f"{user} doesn't have any quotes yet.", color=0xFF0000)
            await ctx.send(embed=embed)
            raise discord.ext.commands.errors.BadArgument

        pages = create_pages(all_quotes)

        p = Pages(self.bot, ctx, pages, ctx.message.author.id, f"All quotes from {all_quotes[0].Name}", 180)
        if len(pages) > 1:
            await p.handle_pages()
        else:
            await ctx.message.delete(delay=120)
            await ctx.send(embed=p.create_embed(), delete_after=120)

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
        quotes_to_remove = SQLFunctions.get_quotes_to_remove(ctx.message.guild.id, self.conn) \
            + SQLFunctions.get_quotes_to_remove_name(ctx.message.guild.id, self.conn)
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
        quotes_to_remove = SQLFunctions.get_quotes_to_remove(ctx.message.guild.id, self.conn) \
            + SQLFunctions.get_quotes_to_remove_name(ctx.message.guild.id, self.conn)

        # fetches each quote and adds it to a page
        # 1 quote per page
        pages = []
        while len(quotes_to_remove) > 0:
            quote = quotes_to_remove.pop()
            # userID, quoteID, quote, reporterID, name, reason
            user_id = None
            if quote.Quote.Member:
                user_id = quote.Quote.Member.DiscordUserID
            pages.append([
                user_id,
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

    @commands.guild_only()
    @quote.command(usage="search <part of quote>")
    async def search(self, ctx, *, args):
        quotes = SQLFunctions.get_quotes(guild_id=ctx.message.guild.id, quote=args, conn=self.conn)
        quotes_list = ""
        i = 1
        for q in quotes:
            idx = q.QuoteText.lower().find(args.lower())
            formatted_quote = q.QuoteText[:idx] + f"**{q.QuoteText[idx: idx + len(args)]}**" + q.QuoteText[idx + len(args):]
            quotes_list += f"\n**{i}**: {formatted_quote} `[{q.QuoteID}]`"
            i += 1
            # creates the pages
        pages = []
        while len(quotes_list) > 0:
            # split quotes into multiple fields of max 1000 chars
            if len(quotes_list) >= 1000:
                rind2 = quotes_list.rindex("\n", 0, 1000)
                if rind2 == 0:
                    # one quote is more than 1000 chars
                    rind2 = quotes_list.rindex(" ", 0, 1000)
                    if rind2 == 0:
                        # the quote is longer than 1000 chars and has no spaces
                        rind2 = 1000
            else:
                rind2 = len(quotes_list)
            pages.append(quotes_list[0:rind2])
            quotes_list = quotes_list[rind2:]
        if len(args) > 200:
            args = args[:200] + "[...]"
        if len(pages) == 0:
            embed = discord.Embed(title="No Matching Quotes Found",
                                  description=f"Tag:\n```{args.replace('```', '')}```",
                                  color=discord.Color.red())
            await ctx.reply(embed=embed)
            raise discord.ext.commands.BadArgument
        qm = Pages(
            self.bot,
            ctx,
            pages,
            ctx.message.author.id,
            f"Quotes containing string: {args}")
        await qm.handle_pages()

    @commands.is_owner()
    @quote.command(name="delete", aliases=["del"], usage="delete <Quote ID>")
    async def delete_quote(self, ctx, quoteID=None):
        """
        Deletes the quote with the given ID.
        Permissions: Owner
        """
        if quoteID is None:
            await ctx.send("No quote ID given.")
            raise discord.ext.commands.BadArgument
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

    def pick_top_quotes(self, quotes) -> tuple[tuple[int, SQLFunctions.Quote], tuple[int, SQLFunctions.Quote]]:
        """
        Picks two quotes that are at the top of the leaderboards
        85% to pick 2 top 10 quotes
        10% to pick a top 50 quote
        5% to pick some other quote
        """
        n = len(quotes)
        chance_for_first = 0.85
        chance_for_second = 0.10
        first_cat = 20  # amount in first category
        second_cat = 80  # amount in second category
        chance_for_rest = 1 - chance_for_first - chance_for_second
        """
        The min/max methods make sure that there are the same amount of weights
        as there are quotes.
        min(n, 10) = n if n<10, else it's just 10
        min(max(0, n-10)) = 0 if n<10, else = n-10 if n<40, else its 40
        max(0, n-50) = 0 if n<50, else it's =n-50
        """
        quote_weights = [chance_for_first / first_cat for _ in range(min(n, first_cat))] + \
                        [chance_for_second / second_cat for _ in range(min(max(0, n - first_cat), second_cat))] + \
                        [chance_for_rest / (n - first_cat - second_cat) for _ in range(max(0, n - first_cat - second_cat))]
        return self.pick_random_quotes(quotes, quote_weights)

    def pick_random_quotes(self, quotes, quote_weights) -> tuple[tuple[int, SQLFunctions.Quote], tuple[int, SQLFunctions.Quote]]:
        """
        Picks two random quotes and assumes the given quotes list is order by rank.
        :returns Two tuples each including the rank of the quote and the quote object itself.
        """
        # Re-raffles until we have two unique quotes
        quotes_with_rank = [(i + 1, quotes[i]) for i in range(len(quotes))]
        while True:
            two_random_quotes = random.choices(quotes_with_rank, weights=quote_weights, k=2)
            (rank1, quote1) = two_random_quotes[0]
            (rank2, quote2) = two_random_quotes[1]
            if quote1.Name == "test" or quote2.Name == "test":
                continue
            for b in self.active_battles:  # if one of the quotes is already in a battle, continue
                if b.quote1.QuoteID in [quote1.QuoteID, quote2.QuoteID] or b.quote2.QuoteID in [quote1.QuoteID, quote2.QuoteID]:
                    continue
            if quote1.QuoteID != quote2.QuoteID:
                break
        return (rank1, quote1), (rank2, quote2)

    @commands.guild_only()
    @commands.is_owner()
    @quote.command(aliases=["sb"])
    async def startBattle(self, ctx, count=None):
        if count is None:
            count = 3
        elif not count.isnumeric():
            await ctx.reply("The given count needs to be numeric.")
            raise discord.ext.commands.BadArgument
        count = int(count)
        for _ in range(count):
            battle = self.init_battle_message(ctx.channel)
            msg = await ctx.send(embed=battle.embed, components=battle.components)
            battle.add_message(msg)

    def get_rank_of_quote(self, quote_id: int, guild_id: int):
        """
        Gets the rank of a quote. Not the most efficient so should be avoided to be used a lot.
        """
        quotes = SQLFunctions.get_quotes(guild_id=guild_id, conn=self.conn, rank_by_elo=True)
        i = 1
        for q in quotes:
            if q.QuoteID == quote_id:
                return i
            i += 1
        return -1

    def init_battle_message(self, channel, time_for_battle=0) -> Battle:
        quotes = SQLFunctions.get_quotes(conn=self.conn, guild_id=channel.guild.id, rank_by_elo=True)
        random.seed()

        PAUSE = time_for_battle == 0  # true if this battle doesnt start immediatly

        if not PAUSE:
            embed = discord.Embed(
                description=f"Choose the better quote using the buttons. Battle ends after {time_for_battle} seconds.\nVotes: 0",
                color=discord.Color.gold()
            )
        else:
            embed = discord.Embed(
                description=f"Choose the better quote using the buttons. Battle countdown starts once somebody votes.\nVotes: 0",
                color=discord.Color.random()
            )

        if random.random() <= 0.1:  # there's a 5% chance for a top battle to show up
            embed.title = "TOP QUOTE BATTLE"
            (rank1, quote1), (rank2, quote2) = self.pick_top_quotes(quotes)
            embed.set_thumbnail(url="https://media4.giphy.com/media/LO8oXHPum0xworIyk4/giphy.gif")
        else:
            embed.title = "Epic Quote Battle"
            min_battles = 99999
            max_battles = 0
            for q in quotes:
                min_battles = min(q.AmountBattled, min_battles)
                max_battles = max(q.AmountBattled, max_battles)
            # Tokens is what is used to give weights to quotes so quotes that have been shown less are more likely to be shown
            tokens = max_battles - min_battles + 1
            quote_weights = [tokens - x.AmountBattled for x in quotes]
            (rank1, quote1), (rank2, quote2) = self.pick_random_quotes(quotes, quote_weights)

        quote1_text = quote1.QuoteText
        quote2_text = quote2.QuoteText
        if len(quote1_text) > 1000:
            quote1_text = quote1_text[:1000] + " **[...]**"
        if len(quote2_text) > 1000:
            quote2_text = quote2_text[:1000] + " **[...]**"

        embed.add_field(name=f"1️⃣ | ID: {quote1.QuoteID} | Name: {quote1.Name}", value=quote1_text, inline=False)
        embed.add_field(name=f"2️⃣ | ID: {quote2.QuoteID} | Name: {quote2.Name}", value=quote2_text, inline=False)
        embed.set_footer(text="The bin button simply starts the battle if it hasn't started yet.")
        components = [[
            Button(style=ButtonStyle.blue, emoji="1️⃣", id="1"),
            Button(style=ButtonStyle.blue, emoji="2️⃣", id="2"),
            Button(style=ButtonStyle.grey, emoji="🗑️", id="3")
        ]]
        battle = Battle(
            embed=embed,
            components=components,
            quote1=quote1,
            quote2=quote2,
            rank1=rank1,
            rank2=rank2,
            pause=PAUSE
        )
        return battle

    def init_battle_dict(self, msg, battle):
        self.active_battles.append(battle)
        battle.add_message(msg)
        self.voted_users[msg.id] = []
        self.battle_scores[msg.id] = [0, 0]

    async def handle_battle(self, channel: discord.TextChannel, battle: Battle, time_for_battle=30, user_message=None):
        """
        Handles the whole quote battle including picking the quotes, sending the message,
        editing it and deleting the messages afterwards.
        """
        if battle.message is None:
            raise Exception("Message is unassigned for battle")

        quote1 = battle.quote1
        quote2 = battle.quote2
        embed = battle.embed
        rank1 = battle.rank1
        rank2 = battle.rank2
        elo1 = quote1.Elo
        elo2 = quote2.Elo
        msg = battle.message

        if battle.pause:  # the battle was paused, so we have to get the new ranks of the quotes incase they changed
            rank1 = self.get_rank_of_quote(quote1.QuoteID, channel.guild.id)
            rank2 = self.get_rank_of_quote(quote2.QuoteID, channel.guild.id)

        start_time = time.time()
        while start_time + time_for_battle > time.time():
            embed.description = f"Choose the better quote using the buttons. Battle ending in {int(start_time + time_for_battle - time.time())} seconds.\nVotes: {len(self.voted_users[msg.id])}"
            await msg.edit(embed=embed)
            await asyncio.sleep(5)

        embed = discord.Embed(
            title=embed.title + " Over",
            description=f"Quote Battle over. There were {len(self.voted_users[msg.id])} intense battles.",
            color=discord.Color.gold()
        )

        score1, score2 = self.battle_scores[msg.id]
        new_elo1, new_elo2 = set_new_elo(score1, score2, quote1, quote2, self.conn)

        # gets the new ranks
        quotes = SQLFunctions.get_quotes(conn=self.conn, guild_id=channel.guild.id, rank_by_elo=True)
        new_rank1 = 0
        new_rank2 = 0
        for i, q in enumerate(quotes):
            if q.QuoteID == quote1.QuoteID:
                new_rank1 = i + 1
            elif q.QuoteID == quote2.QuoteID:
                new_rank2 = i + 1
            if new_rank1 != 0 and new_rank2 != 0:
                break

        quote1_text = quote1.QuoteText
        quote2_text = quote2.QuoteText
        if len(quote1_text) > 1000:
            quote1_text = quote1_text[:1000] + " **[...]**"
        if len(quote2_text) > 1000:
            quote2_text = quote2_text[:1000] + " **[...]**"

        # remove all entries that were created again
        if battle in self.active_battles:
            self.active_battles.remove(battle)
        self.voted_users.pop(msg.id)
        self.battle_scores.pop(msg.id)

        embed.add_field(name=f"1️⃣ | ID: {quote1.QuoteID} | Name: {quote1.Name} | Wins: {score1} | Rank: {rank1} → {new_rank1} | Elo: {round(elo1)} → {round(new_elo1)}",
                        value=quote1_text, inline=False)
        embed.add_field(name=f"2️⃣ | ID: {quote2.QuoteID} | Name: {quote2.Name} | Wins: {score2} | Rank: {rank2} → {new_rank2} | Elo: {round(elo2)} → {round(new_elo2)}",
                        value=quote2_text, inline=False)
        await msg.edit(embed=embed, components=[])

        try:
            await msg.delete(delay=60)
        except (discord.NotFound, discord.Forbidden):
            pass
        if user_message is not None:
            try:
                await user_message.delete(delay=60)
            except (discord.NotFound, discord.Forbidden):
                pass

        # automatically sends the battle again once it ends if its in the battle channel
        if self.battle_channel is not None and channel.id == self.battle_channel.id:
            battle = self.init_battle_message(channel)
            for _ in range(10):
                try:
                    msg = await channel.send(embed=battle.embed, components=battle.components)
                    break
                except discord.errors.DiscordServerError:
                    await asyncio.sleep(5)
            battle.add_message(msg)

    @commands.cooldown(4, 15, BucketType.channel)
    @commands.guild_only()
    @quote.command(aliases=["b"], usage="battle")
    async def battle(self, ctx):
        """
        Picks two random quotes and allows users to vote on which quote they find better. \
        Each vote from a user counts as a win for that quote and immediately takes effect.
        """
        battle = self.init_battle_message(ctx.channel, 30)
        msg: discord.Message = await ctx.send(embed=battle.embed, components=battle.components)
        self.init_battle_dict(msg, battle)
        await self.handle_battle(ctx.channel, battle, 30, ctx.message)

    @commands.guild_only()
    @quote.command(aliases=["lb", "top"], usage="leaderboard [user ID | mention]")
    async def leaderboard(self, ctx, user=None):
        if user is None:
            title = "Quote Leaderboard"
            quotes = SQLFunctions.get_quotes(guild_id=ctx.message.guild.id, rank_by_elo=True)
        else:
            user_id: str = user.replace("<@", "").replace(">", "").replace("!", "")
            if not user_id.isnumeric():
                await ctx.reply(f"Did not find a user with the given ID/mention.")
                raise discord.ext.commands.errors.BadArgument
            quotes = SQLFunctions.get_quotes(guild_id=ctx.message.guild.id, rank_by_elo=True, discord_user_id=int(user_id))
            if len(quotes) == 0:
                await ctx.reply(f"Did not find any quotes from the given user.")
                raise discord.ext.commands.errors.BadArgument
            title = f"Quote Leaderboard from {quotes[0].Name}"
        qm = Pages(self.bot, ctx, create_pages(quotes), ctx.message.author.id, title)
        await qm.handle_pages()

    @commands.guild_only()
    @quote.group(aliases=["f", "favorite", "favourite", "favourites"], usage="favorites", invoke_without_command=True)
    async def favorites(self, ctx):
        """
        Used to store and view your favorite quotes. Check out the subcommands `add` and `remove` to add some favorite quotes.
        """
        if ctx.invoked_subcommand is not None:
            return
        quotes = SQLFunctions.get_favorite_quotes_of_user(ctx.author, self.conn)
        # If there are no quotes for the given person;
        if len(quotes) == 0:
            embed = discord.Embed(
                title="Quotes Error",
                description=f"You don't have any favorite quotes yet.\nCheck out the subcommand `add` to add your first favorite command!",
                color=discord.Color.red())
            embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
            await ctx.send(embed=embed)
            raise discord.ext.commands.errors.BadArgument

        pages = create_pages(quotes)
        qm = Pages(self.bot, ctx, pages, ctx.author.id, "Favorite Quotes")
        await qm.handle_pages()

    @commands.guild_only()
    @favorites.command(name="add", aliases=["a"], usage="add <quote ID>")
    async def add_favorite(self, ctx, quote_id=None):
        """
        Add a quote to your personal quote favorites! Quote ID needs to be a valid \
        quote and an integer of course.
        """
        # Input parsing
        if quote_id is None:
            embed = discord.Embed(description=f"No Quote ID given as parameter.", color=discord.Color.red())
            embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
            await ctx.reply(embed=embed)
            raise discord.ext.commands.errors.BadArgument
        if not quote_id.isnumeric():
            embed = discord.Embed(description=f"The given Quote ID is not an int!", color=discord.Color.red())
            embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
            await ctx.reply(embed=embed)
            raise discord.ext.commands.errors.BadArgument
        quote_id = int(quote_id)

        # if the quote ID even exists
        quote = SQLFunctions.get_quote(quote_id, ctx.message.guild.id, self.conn)
        if quote is None:
            embed = discord.Embed(description=f"Quote ID `{quote_id}` does not exist!", color=discord.Color.red())
            embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
            await ctx.reply(embed=embed)
            raise discord.ext.commands.errors.BadArgument

        # if the quote ID was already favoritted by this user
        quotes = SQLFunctions.get_favorite_quotes_of_user(ctx.author, self.conn)
        for q in quotes:
            if q.QuoteID == quote_id:
                embed = discord.Embed(description=f"You already favorited the quote with ID `{quote_id}`!", color=discord.Color.red())
                embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
                await ctx.reply(embed=embed)
                raise discord.ext.commands.errors.BadArgument

        # add favorite
        SQLFunctions.add_favorite_quote(ctx.author, quote_id, self.conn)
        embed = discord.Embed(description=f"Successfully favorited quote ID `{quote_id}` by {quote.Name}!", color=discord.Color.green())
        embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
        await ctx.reply(embed=embed)

    @commands.guild_only()
    @favorites.command(name="remove", aliases=["delete", "del", "r"], usage="remove <quote ID>")
    async def remove_favorite(self, ctx, quote_id=None):
        """
        Remove a quote from your personal quote favorites! Quote ID needs to be a valid \
        quote and an integer of course.
        """
        # Input parsing
        if quote_id is None:
            embed = discord.Embed(description=f"No Quote ID given as parameter.", color=discord.Color.red())
            embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
            await ctx.reply(embed=embed)
            raise discord.ext.commands.errors.BadArgument
        if not quote_id.isnumeric():
            embed = discord.Embed(description=f"The given Quote ID is not an int!", color=discord.Color.red())
            embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
            await ctx.reply(embed=embed)
            raise discord.ext.commands.errors.BadArgument
        quote_id = int(quote_id)

        # if the quote ID even exists
        quote = SQLFunctions.get_quote(quote_id, ctx.message.guild.id, self.conn)
        if quote is None:
            embed = discord.Embed(description=f"Quote ID `{quote_id}` does not exist!", color=discord.Color.red())
            embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
            await ctx.reply(embed=embed)
            raise discord.ext.commands.errors.BadArgument

        # checks if the quote was ever favorited
        quotes = SQLFunctions.get_favorite_quotes_of_user(ctx.author, self.conn)
        for q in quotes:
            if q.QuoteID == quote_id:
                break
        else:
            # Quote wasn't favorited
            embed = discord.Embed(description=f"Quote with ID `{quote_id}` was never favorited!", color=discord.Color.red())
            embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
            await ctx.reply(embed=embed)
            raise discord.ext.commands.errors.BadArgument

        # remove favorite
        SQLFunctions.remove_favorite_quote(ctx.author, quote_id, self.conn)
        embed = discord.Embed(description=f"Successfully unfavorited quote ID `{quote_id}`!", color=discord.Color.blurple())
        embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Quote(bot))


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
        embed = discord.Embed(title="Quotes to Remove", description=f"Page {page_number + 1}/{len(self.pages)}", color=0x00003f)
        userID, quoteID, quote, reporterID, name, reason = self.pages[page_number]
        if len(reason) > 700:
            reason = reason[:700] + "..."
        elif reason == "":
            reason = "*No reason was given.*"
        if userID is not None:
            embed.add_field(name=f"ID: {quoteID} | {name}",
                            value=f"Discord User: <@{userID}>\nReported by: <@{reporterID}>\n**Quote:**\n{quote}\n**Reason:**\n{reason}")
        else:
            embed.add_field(name=f"ID: {quoteID} | {name}", value=f"Reported by: <@{reporterID}>\n**Quote:**\n{quote}\n**Reason:**\n{reason}")
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
        embed.add_field(name="Quote", value=quote)
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


def create_pages(quotes: list[SQLFunctions.Quote]) -> list[str]:
    quotes_list = ""
    i = 1
    for q in quotes:
        quote_to_add = q.QuoteText.replace("*", "").replace("~", "").replace("\\", "").replace("`", "").replace("||", "")
        if quote_to_add.count("\n") > 2:
            # makes multiline quotes not fill too many lines
            split_lines = quote_to_add.split("\n")
            quote_to_add = "\n".join(split_lines[:2]) + "\n **[...]**"
        if len(quote_to_add) > 150:
            quote_to_add = quote_to_add[:150] + "**[...]**"
        quotes_list += f"\n**{i}**: {quote_to_add} `[{q.QuoteID}][Elo: {round(q.Elo)}]`"
        i += 1
    # creates the pages
    pages = []
    while len(quotes_list) > 0:
        # split quotes into multiple fields of max 1000 chars
        if len(quotes_list) >= 1000:
            rind2 = quotes_list.rindex("\n", 0, 1000)
            if rind2 == 0:
                # one quote is more than 1000 chars
                rind2 = quotes_list.rindex(" ", 0, 1000)
                if rind2 == 0:
                    # the quote is longer than 1000 chars and has no spaces
                    rind2 = 1000
        else:
            rind2 = len(quotes_list)
        pages.append(quotes_list[0:rind2])
        quotes_list = quotes_list[rind2:]
    return pages


class Pages:
    def __init__(self, bot: discord.Client, ctx: discord.ext.commands.Context, pages: list, user_id: int, embed_title: str, seconds=60, description=""):
        self.bot = bot  # bot object required so we can wait for the button click
        self.ctx = ctx  # so that we can remove the original message in the end
        self.page_count = 0  # current page
        self.pages = pages  # list of strings
        self.start_time = time.time()
        self.user_id = user_id  # the user ID that can change the pages
        self.embed_title = embed_title  # the title of each page
        self.seconds = seconds  # time in seconds to wait until we delete the message
        self.message = None  # the quotes message sent by the bot
        self.description = description  # description of the embed

    async def handle_pages(self):
        """
        The meat of the pages which handles what shall be done depending
        on what button was pressed. This sits in a while loop until the time
        of self.seconds passes.
        """
        self.message = await self.send_initial_message()
        while True:
            # waits for a button click event
            try:
                # We add a timeout so that the message still gets deleted
                # even if nobody presses any button
                res = await self.bot.wait_for("button_click", timeout=self.seconds)
            except asyncio.TimeoutError:
                break
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
                    await res.respond(type=InteractionType.ChannelMessageWithSource,
                                      content="Sorry got a little error. Simply press the button again.")
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
        if self.page_count == len(self.pages) - 1:  # we are on the last page
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
        if (len(self.description) > 0):
            embed.description = self.description
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
