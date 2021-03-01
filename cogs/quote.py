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


async def send_quote(ctx, quote, date, name, index=None):
    embed = discord.Embed(description=quote, color=0x404648)
    footer_txt = ""
    if index is not None:
        footer_txt += f"| Index: {index}"
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

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        # To get a quote you can just type `-name`
        if message.content.startswith("-"):
            name = "NONE"
            try:
                random.seed(time.time())
                name = message.content.replace("-", "").lower()
                rand_quote = random.choice(self.quotes[str(message.guild.id)][name])
                await send_quote(message.channel, rand_quote[1], rand_quote[0], name)
            except IndexError:
                log(f"Did not find quote from user: {name}", "QUOTE")
            except KeyError:
                log(f"Name does not exist in database: {name}", "QUOTE")

    @commands.cooldown(4, 10, BucketType.user)
    @commands.command(aliases=["q", "quotes"], usage="quote [user] [quote/command] [index]")
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
        guild_id = str(ctx.message.guild.id)
        if name is not None:
            if name == "names":
                if guild_id not in self.quotes:
                    await ctx.send("There are no quotes on this server yet.")
                    raise discord.ext.commands.errors.BadArgument
                else:
                    all_names = "Everybody with a quote as of now:\n"
                    for n in self.quotes[guild_id].keys():
                        all_names += f"-{n}\n"
                    embed = discord.Embed(title=name, description=all_names, color=0x404648)
                    await ctx.send(embed=embed)
            else:
                quote = " ".join(quote)
                try:
                    memberconverter = discord.ext.commands.MemberConverter()
                    name = await memberconverter.convert(ctx, name)
                    name = name.name
                except discord.ext.commands.errors.BadArgument:
                    name = str(name)
                if "@" in name or "@" in quote:
                    await ctx.send("Quotes can't contain `@` in names (unless they are mentions) or in the quote.")
                    raise discord.ext.commands.errors.BadArgument
                name = name.lower()

                # checks if the name is an alias
                for key in self.aliases.keys():
                    for alias in self.aliases[key]:
                        if alias == name:
                            name = key
                if len(quote) > 0:
                    await self.user_checkup(guild_id, name)
                    try:
                        # Checks if the quote is a quote index
                        index = int(quote)
                        await send_quote(ctx, self.quotes[guild_id][name][index][1],
                                         self.quotes[guild_id][name][index][0], name, index)

                    except ValueError:
                        # Is the quote a command or a new quote to add
                        if quote.lower() == "all":
                            # show all quotes from name
                            quote_list = ""

                            for i in range(len(self.quotes[guild_id][name])):
                                quote_to_add = self.quotes[guild_id][name][i][1].replace("*", "").replace("_", "").replace("~", "").replace("\\", "").replace("`", "")
                                quote_list += f"\n**{[i]}:** {quote_to_add}"

                            # If there are no quotes for the given person;
                            if len(quote_list) == 0:
                                await ctx.send(f"{name} doesn't have any quotes yet.")
                                raise discord.ext.commands.errors.BadArgument

                            embed = discord.Embed(title=f"All quotes from {name}", color=0x404648)
                            # if the quote is too long:
                            splitted_lines = quote_list.split("\n")
                            msg = ""
                            counter = 1
                            msg_length = 0
                            for line in splitted_lines:
                                if msg_length >= 5000:
                                    await ctx.send(embed=embed)
                                    embed = discord.Embed(color=0x404648)
                                    msg_length = 0
                                    msg = ""
                                if len(line) + len(msg) < 1000:
                                    msg += "\n" + line
                                else:
                                    embed.add_field(name=f"Page {counter}", value=msg)
                                    msg_length += len(msg)
                                    msg = line
                                    counter += 1
                            embed.add_field(name=f"Page {counter}", value=msg)

                            await ctx.send(embed=embed)
                        elif quote.lower().split(" ")[0] == "del":  # Command to delete quotes
                            if not await self.bot.is_owner(ctx.author):
                                raise discord.ext.commands.errors.NotOwner
                            try:
                                index = int(quote.lower().split(" ")[1])
                                try:
                                    self.quotes[guild_id][name].pop(index)

                                    # SAVE FILE
                                    with open(self.quotes_filepath, "w") as f:
                                        json.dump(self.quotes, f, indent=2)
                                    log("SAVED QUOTES", "QUOTES")

                                    await ctx.send(f"Deleted quote with index {index}.")
                                except IndexError:
                                    await ctx.send("No name with that index.")
                            except (IndexError, ValueError):
                                await ctx.send("You forgot to add an index.")
                        else:  # If the quote is a new quote to add
                            date = datetime.datetime.now(timezone("Europe/Zurich")).strftime("%d/%m/%Y")

                            if len(quote) > 500 and not await self.bot.is_owner(ctx.author):
                                await ctx.send(
                                    "This quote exceeds the max_length length of 500 chars. DM Mark if you want the quote added.")
                                raise discord.ext.commands.errors.NotOwner

                            self.quotes[guild_id][name].append([date, quote])

                            # SAVE FILE
                            try:
                                with open(self.quotes_filepath, "w") as f:
                                    json.dump(self.quotes, f, indent=2)
                                log(f"Added quote for {name}", "QUOTES")
                                log("SAVED QUOTES", "QUOTES")
                            except Exception:
                                log(f"Saving QUOTES file failed:\n{traceback.format_exc()}", "QUOTES")
                                user = self.bot.get_user(self.bot.owner_id)
                                await user.send(f"Saving QUOTES file failed:\n{traceback.format_exc()}")

                            await ctx.send(f"Added quote for {name}")
                    except IndexError:
                        await ctx.send(f"{name} doesn't have a quote with that index.")
                        raise discord.ext.commands.errors.BadArgument
                else:
                    try:
                        random.seed(time.time())
                        rand_quote = random.choice(self.quotes[guild_id][name])
                        await send_quote(ctx, rand_quote[1], rand_quote[0], name)
                    except (KeyError, IndexError):
                        await ctx.send(f"{name} doesn't have any quotes yet.")
                        raise discord.ext.commands.errors.BadArgument
        else:  # If $quote is written on its own, send a random quote from any user
            c = 0  # Counter: So the bot doesnt loop too much in case there's no non-empty quote for some reason
            while True:
                try:
                    random.seed(time.time() + c)
                    rand_name = random.choice(list(self.quotes[guild_id].keys()))
                    rand_quote = random.choice(self.quotes[guild_id][rand_name])
                    await send_quote(ctx, rand_quote[1], rand_quote[0], rand_name)
                    break
                except IndexError:
                    c += 1
                    if c >= 10:
                        await ctx.send("No quotes found.")
                        raise discord.ext.commands.errors.BadArgument
                except KeyError:
                    await ctx.send("There are no quotes on this server yet.")
                    raise discord.ext.commands.errors.BadArgument

    async def user_checkup(self, guild_id, name):
        # If the guild doesnt exist in quotes yet
        if str(guild_id) not in self.quotes:
            self.quotes[str(guild_id)] = {}

        # If the user doesnt exist in quotes yet
        if str(name) not in self.quotes[str(guild_id)]:
            self.quotes[str(guild_id)][name] = []


def setup(bot):
    bot.add_cog(Quote(bot))
