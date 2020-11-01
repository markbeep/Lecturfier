import discord
from discord.ext import commands
import datetime
import psutil
import time
import random
import asyncio
from sympy.solvers import solve
from sympy import symbols, simplify
import multiprocessing
import json
from pytz import timezone
import traceback
import os
import string


class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.script_start = 0
        self.clap_counter = 0
        self.time = 0
        self.simplified = ""
        self.newcomers = {}
        self.ta_request = {}
        self.TIME_TO_WAIT = 20 * 3600  # hours to wait between reps
        self.blocked_users = [767034445093273620, 739915006396596354, 766978544156409867, 766972914867634187, 766943366217990164, 769542250635460649]
        self.quotes_filepath = "data/quotes.json"
        self.reputation_filepath = "data/reputation.json"

        with open(self.quotes_filepath, "r") as f:
            self.quotes = json.load(f)

        with open(self.reputation_filepath, "r") as f:
            self.reputation = json.load(f)


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

        # To get a quote you can just type `-name`
        if message.content.startswith("-"):
            try:
                random.seed(time.time())
                name = message.content.replace("-", "").lower()
                rand_quote = random.choice(self.quotes[str(message.guild.id)][name])
                await self.send_quote(message.channel, rand_quote[1], rand_quote[0], name)
            except IndexError:
                print("Didn't find that user to send a quote from")
            except KeyError:
                print("User doesn't exist")
        if message.content.startswith("+rep"):
            await self.rep(message)

    async def rep(self, message):

        if message.author.id in self.blocked_users:
            await message.channel.send(f"{message.author.mention} this discord account is blocked from using +rep.")
            return

        args = message.content.split(" ")
        try:
            if len(args) == 1:  # If there's only the command:
                await self.send_reputations(message, message.author)

            elif len(args) == 2:  # If there's only the command a mention
                u_id = args[1].replace("<@", "").replace(">", "").replace("!", "")
                member = message.guild.get_member(int(u_id))
                await self.send_reputations(message, member)

            else:  # If the message is long enough, add it as a reputation
                # check if it is a mention
                u_id = args[1].replace("<@", "").replace(">", "").replace("!", "")
                member = message.guild.get_member(int(u_id))

                if member.id == message.author.id:
                    raise ValueError

                # checks if the message chars are valid
                if not await self.valid_chars_checker(message.content):
                    raise ValueError

                # check if the user exists
                await self.rep_checkup(message.guild.id, member.id)
                await self.rep_checkup(message.guild.id, message.author.id)

                # Add reputation to user
                time_valid = await self.add_rep(message, member, message.author)
                if time_valid:
                    embed = discord.Embed(title="Added +rep", description=f"Added +rep to {member.display_name}", color=discord.Color.green())
                    if len(args) > 2:
                        embed.add_field(name="Comment:", value=f"```{' '.join(args[2:])}```")
                    embed.set_author(name=str(message.author))
                    msg = await message.channel.send(embed=embed)
                    await asyncio.sleep(10)
                    await message.delete()

                else:
                    sendTime = self.reputation[str(message.guild.id)]['last_rep_time'][str(message.author.id)] + self.TIME_TO_WAIT
                    sendTime = datetime.datetime.fromtimestamp(sendTime).strftime("%A at %H:%M")
                    embed = discord.Embed(title="Error", description=f"You've repped too recently. You can rep again on {sendTime}.",
                                          color=discord.Color.red())
                    msg = await message.channel.send(embed=embed)
                    await asyncio.sleep(10)
                    await msg.delete()
                    await message.delete()

        except ValueError:
            embed = discord.Embed(title="Error", description="Only mention one user, don't mention yourself, only use printable ascii characters, and keep it under 40 characters.", color=discord.Color.red())
            embed.add_field(name="Example", value="+rep <@755781649643470868> helped with Eprog")
            msg = await message.channel.send(embed=embed)

            await asyncio.sleep(10)
            await msg.delete()
            await message.delete()

    async def valid_chars_checker(self, message_content):
        valid_chars = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', "ä", "ü", "ö", "Ä", "Ü", "Ö", '!', '"', '#', '$', '%', '&', "'", '(', ')', '*', '+', ',', '-', '.', '/', ':', ';', '<', '=', '>', '?', '@', '[', ']', '^', '_', '{', '|', '}', '~', ' ', '\t', '\n', '\r', '\x0b', '\x0c']
        for letter in message_content:
            if letter not in valid_chars:
                return False
        return True

    async def send_reputations(self, message, member):
        await self.rep_checkup(message.guild.id, member.id)
        reputation_msg = ""
        for rep in self.reputation[str(message.guild.id)]["rep"][str(member.id)]:
            reputation_msg += f"+ {rep}\n"
        if len(reputation_msg) == 0:
           reputation_msg = "--- it's pretty empty here, go help some people out"
        msg = f"```diff\nReputations: {member.display_name}\n__________________________\n{reputation_msg}```"
        await message.channel.send(msg)

    async def add_rep(self, message, member, author):
        """
        Adds the reputation to the file
        """
        if self.reputation[str(message.guild.id)]["last_rep_time"][str(author.id)] + self.TIME_TO_WAIT > time.time():
            return False

        self.reputation[str(message.guild.id)]["last_rep_time"][str(author.id)] = time.time()
        msg = message.content.split(" ")
        if len(msg) > 2:
            self.reputation[str(message.guild.id)]["rep"][str(member.id)].append(" ".join(msg[2:]))

        # SAVE FILE
        try:
            with open(self.reputation_filepath, "w") as f:
                json.dump(self.reputation, f, indent=2)
            print("SAVED REPUTATION")
        except Exception:
            user = self.bot.get_user(205704051856244736)
            await user.send(f"Saving REPUTATION file failed:\n{traceback.format_exc()}")
        return True

    async def rep_checkup(self, guild_id, name):
        # If the guild doesn't exist in reputation yet
        if str(guild_id) not in self.reputation:
            self.reputation[str(guild_id)] = {}

        # If the categories don't exist in reputation yet
        if "rep" not in self.reputation[str(guild_id)]:
            self.reputation[str(guild_id)]["rep"] = {}
            self.reputation[str(guild_id)]["last_rep_time"] = {}

        # If the user doesn't exist in reputation yet
        if str(name) not in self.reputation[str(guild_id)]["rep"]:
            self.reputation[str(guild_id)]["rep"][str(name)] = []
            self.reputation[str(guild_id)]["last_rep_time"][str(name)] = 0


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):

        if user.bot:
            return
        # If the reaction giver is one of the newcomers
        if user.id in self.newcomers:
            if reaction.message.id == self.newcomers[user.id]:
                if str(reaction) == "<:bach:764174568000192552>":
                    role = discord.Object(767315361443741717)
                    await user.add_roles(role, reason="Reaction role")
                    print(f"Added External role to {str(user)}.")
                    embed = discord.Embed(title="External role added",
                                          description=f"Added **External** role to {str(user)}", color=0xa52222)
                elif str(reaction) == "✏":
                    role = discord.Object(747786383317532823)
                    await user.add_roles(role, reason="Reaction role")
                    print(f"Added Student role to {str(user)}.")
                    embed = discord.Embed(title="Student role added",
                                          description=f"Added **Student** role to {str(user)}", color=0xff6c00)
                elif str(reaction) == "🧑‍🏫":
                    await reaction.clear()
                    channel = self.bot.get_channel(747768907992924192)
                    embed = discord.Embed(title="TA REQUEST", description=f"{str(user)} requests to be a TA\n"
                                                                          f"<:checkmark:769279808244809798> to accept\n"
                                                                          f"<:xmark:769279807916998728> to decline",
                                          color=discord.Color.gold())
                    ta_msg = await channel.send(embed=embed)
                    await ta_msg.add_reaction("<:checkmark:769279808244809798>")
                    await ta_msg.add_reaction("<:xmark:769279807916998728>")
                    self.ta_request[ta_msg.id] = user.id
                    return
                else:
                    return

                self.newcomers.pop(user.id, None)
                await reaction.message.channel.send(embed=embed)
                await reaction.message.delete()

        if reaction.message.id in self.ta_request:
            ta_user = self.bot.get_user(self.ta_request[reaction.message.id])
            if str(reaction) == "<:checkmark:769279808244809798>":
                embed = discord.Embed(title="Accepted TA Role", description=f"Added **TA** role to {str(ta_user)}",
                                      color=discord.Color.green())
                role = discord.Object(767084137361440819)
                await user.add_roles(role, reason="Accepted TA role")

            elif str(reaction) == "<:xmark:769279807916998728>":
                embed = discord.Embed(title="Rejected TA Role",
                                      description=f"Did **not** add TA role to {str(ta_user)}",
                                      color=discord.Color.red())
            else:
                return

            await reaction.message.channel.send(embed=embed)
            await reaction.message.delete()
            self.ta_request.pop(reaction.message.id, None)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = self.bot.get_channel(747794480517873685)
        await self.send_welcome_message(channel, member)

    async def loading_bar(self, bars, max=None, failed=None):
        bars = round(bars)
        if max is None:
            max = 10
        if failed is None:
            return "<:blue_box:764901467097792522>" * bars + "<:grey_box:764901465592037388>" * (max - bars)  # First is blue square, second is grey
        elif failed:
            return "<:red_box:764901465872662528>"*bars  # Red square
        else:
            return "<:green_box:764901465948684289>"*bars  # Green square

    @commands.command()
    async def loading(self, ctx):
        if await self.bot.is_owner(ctx.author):
            msg = await ctx.send("Loading:\n0% | " + await self.loading_bar(0))
            for i in range(1, 10):
                await msg.edit(content=("Loading:\n" + f"{random.randint(i*10,i*10+5)}% | " + await self.loading_bar(i)))
                await asyncio.sleep(0.75)
            await msg.edit(content=("Loading: DONE\n" + "100% | " + await self.loading_bar(10, 10, False)))

    @commands.command(aliases=["halp", "h", "halpp", "helpp"])
    async def help(self, ctx):
        await ctx.author.send("👌")
        msg = await ctx.channel.send("Sent dm")
        await asyncio.sleep(7)
        await msg.delete()
        await ctx.author.send("https://giphy.com/gifs/lol-vine-deez-nuts-CYU3D3bQnlLIk")
        await asyncio.sleep(10)
        await ctx.author.send("""Lol there's not much you can do with this bot.
Idk try one of the following commands:
$help
$info
$hangman
$calc <input>
$ping
$quote <name>
$minesweeper
$statistics""")

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
    @commands.has_permissions(administrator=True)
    async def ban(self, ctx, person):
        await ctx.send(f"Banning {person}...")
        await asyncio.sleep(10)
        await ctx.send("Was justa prank brudi")

    @commands.command()
    async def calc(self, ctx, num1=None):
        if "iq" in ctx.message.content.lower():
            await ctx.send(f"Stop asking for your fucking IQ. Nobody cares about your {random.randint(1,10)} IQ")
            return
        await ctx.send(f"{ctx.message.author.mention}: I guess {random.randrange(-1000000, 1000000)}. Could be wrong tho...")

    @commands.command(aliases=["send", "repeatme"])
    async def say(self, ctx, *, cont):
        """
        Repeats a message
        """
        if await self.bot.is_owner(ctx.author):
            await ctx.send(cont)

    def simp(self, eq):
        eq = simplify(eq)

    @commands.command()
    async def xxx_solve(self, ctx, *num1):
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
            print(fixed)

            variables = []
            for l in list(fixed):
                if l.isalpha() and symbols(l) not in variables:
                    variables.append(symbols(l))

            solution = ""
            for v in variables:
                print(v)
                solved = solve(fixed, v)
                print(solved)
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
        embed = discord.Embed(title="Pong! 🏓", description=f"🌐 Ping: `{round(self.bot.latency * 1000)}` ms")
        await ctx.send(embed=embed)

    async def send_quote(self, ctx, quote, date, name, index=None):
        embed = discord.Embed(description=quote, color=0x404648)
        footer_txt = ""
        if index is not None:
            footer_txt += f"| Index: {index}"
        embed.set_footer(text=f"-{name}, {date}" + footer_txt)
        await ctx.send(embed=embed)

    @commands.command()
    async def quote(self, ctx, name=None, *quote):
        guild_id = str(ctx.message.guild.id)
        if name is not None:
            if name == "names":
                if guild_id not in self.quotes:
                    await ctx.send("There are no quotes on this server yet.")
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
                    return
                name = name.lower()
                if len(quote) > 0:
                    await self.user_checkup(guild_id, name)
                    try:
                        # Checks if the quote is a quote index
                        index = int(quote)
                        await self.send_quote(ctx, self.quotes[guild_id][name][index][1], self.quotes[guild_id][name][index][0], name, index)

                    except ValueError:
                        # Is the quote a command or a new quote to add
                        if quote.lower() == "all":
                            # show all quotes from name
                            quote_list = ""

                            for i in range(len(self.quotes[guild_id][name])):
                                quote_list += f"**{[i]}:** {self.quotes[guild_id][name][i][1]}\n"

                            # If there are no quotes for the given person;
                            if len(quote_list) == 0:
                                await ctx.send(f"{name} doesn't have any quotes yet.")
                                return

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
                                    msg += line + "\n"
                                else:
                                    embed.add_field(name=f"Page {counter}", value=msg)
                                    msg_length += len(msg)
                                    msg = line
                                    counter += 1
                            embed.add_field(name=f"Page {counter}", value=msg)

                            await ctx.send(embed=embed)
                        elif quote.lower().split(" ")[0] == "del":  # Command to delete quotes
                            if not await self.bot.is_owner(ctx.author):
                                return
                            try:
                                index = int(quote.lower().split(" ")[1])
                                try:
                                    self.quotes[guild_id][name].pop(index)

                                    # SAVE FILE
                                    try:
                                        with open(self.quotes_filepath, "w") as f:
                                            json.dump(self.quotes, f, indent=2)
                                        print("SAVED QUOTES")
                                    except Exception:
                                        user = self.bot.get_user(205704051856244736)
                                        await user.send(f"Saving QUOTES file failed:\n{traceback.format_exc()}")

                                    await ctx.send(f"Deleted quote with index {index}.")
                                except IndexError:
                                    await ctx.send("No name with that index.")
                            except (IndexError, ValueError):
                                await ctx.send("You forgot to add an index.")
                        else:  # If the quote is a new quote to add
                            date = datetime.datetime.now(timezone("Europe/Zurich")).strftime("%d/%m/%Y")

                            if len(quote) > 300 and not await self.bot.is_owner(ctx.author):
                                await ctx.send("This quote exceeds the max length of 300 chars. DM Mark if you want the quote added.")
                                return

                            self.quotes[guild_id][name].append([date, quote])

                            # SAVE FILE
                            try:
                                with open(self.quotes_filepath, "w") as f:
                                    json.dump(self.quotes, f, indent=2)
                                print("SAVED QUOTES")
                            except Exception:
                                user = self.bot.get_user(205704051856244736)
                                await user.send(f"Saving QUOTES file failed:\n{traceback.format_exc()}")

                            await ctx.send(f"Added quote for {name}")
                    except IndexError:
                        await ctx.send(f"{name} doesn't have a quote with that index.")
                else:
                    try:
                        random.seed(time.time())
                        rand_quote = random.choice(self.quotes[guild_id][name])
                        await self.send_quote(ctx, rand_quote[1], rand_quote[0], name)
                    except (KeyError, IndexError):
                        await ctx.send(f"{name} doesn't have any quotes yet.")
        else:  # If $quote is written on its own, send a random quote from any user
            c = 0  # Counter: So the bot doesnt loop too much in case there's no non-empty quote for some reason
            while True:
                try:
                    random.seed(time.time() + c)
                    rand_name = random.choice(list(self.quotes[guild_id].keys()))
                    rand_quote = random.choice(self.quotes[guild_id][rand_name])
                    await self.send_quote(ctx, rand_quote[1], rand_quote[0], rand_name)
                    break
                except IndexError:
                    c += 1
                    print("YEEEEET")
                    if c >= 10:
                        await ctx.send("No quotes found.")
                        break

    async def user_checkup(self, guild_id, name):
        # If the guild doesnt exist in quotes yet
        if str(guild_id) not in self.quotes:
            self.quotes[str(guild_id)] = {}

        # If the user doesnt exist in quotes yet
        if str(name) not in self.quotes[str(guild_id)]:
            self.quotes[str(guild_id)][name] = []

    @commands.command()
    async def spam_till_youre_dead(self, ctx):
        if await self.bot.is_owner(ctx.author):
            spam = "\n"*1900
            embed = discord.Embed(title="." + "\n"*250 + ".", description="." + "\n"*2000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 700 + ".")
            await ctx.send(f"\"{spam}\"", embed=embed)
            await ctx.send(f"{len(spam) + len(embed)} chars")

    @commands.command()
    async def reboot(self, ctx):
        if await self.bot.is_owner(ctx.author):
            await ctx.send("Rebooting...")
            os.system('reboot now')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def testWelcome(self, ctx):
        await self.send_welcome_message(ctx, ctx.author)

    async def send_welcome_message(self, channel, user):
        msg = f"Welcome {user.mention}! Head to <#769261792491995176> to read " \
              f"through the few rules we have on this server. " \
              f"Then press one of the following reactions.\n\n" \
              f"✏   if you're a **D-INFK** student.\n" \
              f"<:bach:764174568000192552>   if you're external.\n" \
              f"🧑‍🏫   if you're a TA (needs to be confirmed by an admin).\n\n" \
              f"**YOUR EMAIL ADDRESS FOR DISCORD NEEDS TO BE VERIFIED FOR YOU TO BE ABLE TO CHAT AND PARTICIPATE ON THIS SERVER**"
        embed = discord.Embed(title="**WELCOME!**", description=msg, color=0xadd8e6)
        embed.set_thumbnail(url=user.avatar_url)
        message = await channel.send(user.mention, embed=embed)
        self.newcomers[user.id] = message.id
        await message.add_reaction("✏")
        await message.add_reaction("<:bach:764174568000192552>")
        await message.add_reaction("🧑‍🏫")

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