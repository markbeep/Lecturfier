from datetime import datetime
import aiohttp
import discord
from discord.ext import commands
import random
import asyncio
import inspect
import os
import time
from cogs import admin, hangman, help, updates, minesweeper, owner, games, quote, reputation, statistics, voice
import json
from helper import handySQL
from sqlite3 import Error
import sqlite3
from tabulate import tabulate
from PIL import Image
import PIL
import io


def rgb2hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)


def loading_bar_draw(a, b):
    prog = int(10*a/b)
    return "<:green_box:764901465948684289>"*prog + (10-prog)*"<:grey_box:764901465592037388>"


def isascii(s):
    total = 0
    for t in s:
        q = len(t.encode('utf-8'))
        if q > 2:
            total += q
    return total < 300


def loading_bar(bars, max_length=None, failed=None):
    bars = round(bars)
    if max_length is None:
        max_length = 10
    if failed is None:
        return "<:blue_box:764901467097792522>" * bars + "<:grey_box:764901465592037388>" * (max_length - bars)  # First is blue square, second is grey
    elif failed:
        return "<:red_box:764901465872662528>"*bars  # Red square
    else:
        return "<:green_box:764901465948684289>"*bars  # Green square


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "./data/discord.db"
        self.conn = handySQL.create_connection(self.db_path)
        self.cancel_all = False
        self.cancel_draws = []
        self.progress = {}
        try:
            self.image = Image.open("place.png")
        except FileNotFoundError:
            self.image = None

    def get_connection(self):
        """
        Retreives the current database connection
        :return: Database Connection
        """

        if self.conn is None:
            self.conn = handySQL.create_connection(self.db_path)
        return self.conn

    def draw_desc(self, ID):
        try:
            index = int(ID)
        except ValueError:
            index = "n/a"
        if index not in self.progress:
            return "Project has no info"
        prog = self.progress[index]
        topleft = prog[2]
        bottomright = prog[3]
        step = prog[4]
        if len(topleft) == 0:
            topX = 0
            topY = 0
        else:
            topX = topleft[0]
            topY = topleft[1]
        if len(bottomright) == 0:
            botX = 0
            botY = 0
        else:
            botX = bottomright[0]
            botY = bottomright[1]
        return f"ID: {ID}\n" \
               f"X: {topX} | Y: {topY} | Step: {step}\n" \
               f"Width: {botX - topX} | Height: {botY - topY}\n" \
               f"Pixel Total: {prog[1]}\n" \
               f"Pixels to draw: {prog[1]-prog[0]}\n" \
               f"Pixels drawn: {prog[0]}\n" \
               f"{loading_bar_draw(prog[0], prog[1])}  {round(100 * prog[0] / prog[1], 2)}%\n" \
               f"Time Remaining: {round((prog[1] - prog[0]) * len(self.progress) / 60, 2)} mins\n" \
               f"`.place zoom {topX} {topY} {min(max(botX - topX, botY - topY), 250)}` to see the progress.\n"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:  # ignores itself
            return

        # fights against people trying to ruin my images hehe ;)
        if message.content.startswith(".place setpixel ") and self.image is not None:
            cont = message.content.split(" ")
            try:
                x = int(cont[2])
                y = int(cont[3])
            except ValueError:
                return
            r, g, b, a = self.image.getpixel((x, y))
            if a != 0:
                color = rgb2hex(r, g, b)
                if color != cont[4].lower():
                    channel = self.bot.get_channel(819966095070330950)
                    if channel is None:
                        channel = self.bot.get_channel(402563165247766528)
                    await channel.send(f".place setpixel {x} {y} {color} | COUNTERING {message.author.name}")

    @commands.command(usage="sql <command>")
    async def sql(self, ctx, *, sql):
        """
        Use SQL
        Permissions: Owner
        """
        if len(sql) > 0 and sql[0] == "table":
            file = discord.File("./images/sql_table.png")
            await ctx.send(file=file)
            return
        if await self.bot.is_owner(ctx.author):
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            start_time = time.perf_counter()
            sql = sql.replace("INSERT", "INSERT OR IGNORE").replace("insert", "insert or ignore")
            try:
                c.execute(sql)
                conn.commit()
            except Error as e:
                await ctx.send(e)
                return
            rows = c.fetchall()
            if rows is None:
                await ctx.send("Rows is a None Object. Might have failed getting a connection to the DB?")
                return
            if len(rows) > 0:
                header = list(dict(rows[0]).keys())
                values = []
                for r in rows:
                    values.append(list(dict(r).values()))
                table = tabulate(values, header, tablefmt="plain")
                table = table.replace("```", "")
                row_count = len(rows)
            else:
                table = "Execution finished without errors."
                row_count = c.rowcount
            cont = f"```\nRows affected: {row_count}\n" \
                   f"Time taken: {round((time.perf_counter()-start_time)*1000, 2)} ms\n" \
                   f"{table}```"
            if len(cont) > 2000:
                index = cont.rindex("\n", 0, 1900)
                cont = cont[0:index] + "\n  ...```"
            await ctx.send(cont)
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="moveToDB <file>")
    async def moveToDB(self, ctx, file=""):
        """
        Used to move data from json files to the database
        Permissions: Owner
        """
        conn = self.get_connection()
        if await self.bot.is_owner(ctx.author):
            if file == "levels":
                with open("./data/levels.json", "r") as f:
                    levels = json.load(f)
                for guild_id in levels:
                    count = 0
                    guild_obj = self.bot.get_guild(int(guild_id))
                    if guild_obj is None:
                        print(f"Didn't find Guild with ID: {guild_id}")
                        continue
                    for member_id in levels[guild_id]:
                        if member_id == "on":
                            continue
                        member_obj = guild_obj.get_member(int(member_id))
                        if member_obj is None:
                            print(f"Didn't find Member with ID: {member_id}")
                            continue

                        handySQL.create_voice_level_entry(conn, member_obj, guild_obj)
                        uniqueID = handySQL.get_uniqueMemberID(conn, member_id, guild_id)
                        conn.execute("UPDATE VoiceLevels SET ExperienceAmount=? WHERE UniqueMemberID=?", (levels[guild_id][member_id], uniqueID))
                        conn.commit()
                        count += 1
                    await ctx.send(f"{count} successful DB entry transfers on guild `{guild_obj.name}`")
            elif file == "covid":
                with open("./data/covid_points.json", "r") as f:
                    covid = json.load(f)
                for guild in covid:
                    count = 0
                    guild_obj = self.bot.get_guild(int(guild))
                    if guild_obj is None:
                        print(f"Didn't find Guild with ID: {guild}")
                        continue
                    for member in covid[guild]:
                        member_obj = guild_obj.get_member(int(member))
                        if member_obj is None:
                            print(f"Didn't find Member with ID: {member}")
                            continue
                        handySQL.create_covid_guessing_entry(conn, member_obj, guild_obj)
                        uniqueID = handySQL.get_uniqueMemberID(conn, member, guild)
                        total = int(covid[guild][member][1])
                        guessCount = covid[guild][member][2]
                        conn.execute("UPDATE CovidGuessing SET TotalPointsAmount=?, GuessCount=? WHERE UniqueMemberID=?", (total, guessCount, uniqueID))
                        conn.commit()
                        count += 1
                    await ctx.send(f"{count} successful DB entry transfers on guild `{guild_obj.name}`")
            elif file == "statistics":
                with open("./data/statistics.json", "r") as f:
                    statistics = json.load(f)
                for guild in statistics:
                    guild_obj = self.bot.get_guild(int(guild))
                    if guild_obj is None:
                        print(f"Didn't find Guild with ID: {guild}")
                        continue
                    count = 0
                    for member in statistics[guild]["messages_sent"]:
                        member_obj = guild_obj.get_member(int(member))
                        if member_obj is None:
                            print(f"Didn't find Member with ID: {member}")
                            continue
                        # Create DB entries
                        msg_result = handySQL.create_message_statistic_entry(conn, member_obj, guild_obj, 0, "UserMessageStatistic")
                        reaction_result = handySQL.create_message_statistic_entry(conn, member_obj, guild_obj, 0, "UserReactionStatistic")
                        uniqueID = handySQL.get_uniqueMemberID(conn, member, guild)
                        sql = """   UPDATE UserMessageStatistic
                                    SET
                                        MessageSentCount=?,
                                        MessageDeletedCount=?,
                                        MessageEditedCount=?,
                                        CharacterCount=?,
                                        WordCount=?,
                                        SpoilerCount=?,
                                        EmojiCount=?,
                                        FileSentCount=?
                                    WHERE UniqueMemberID=? AND SubjectID=0
                                    """
                        s = statistics[guild]
                        for v in ("messages_sent", "messages_deleted", "messages_edited", "chars_sent", "words_sent", "spoilers", "emojis", "files_sent", "reactions_added", "reactions_received"):
                            if member not in s[v]:
                                s[v][member] = 0
                        conn.execute(sql, (
                            s["messages_sent"][member],
                            s["messages_deleted"][member],
                            s["messages_edited"][member],
                            s["chars_sent"][member],
                            s["words_sent"][member],
                            s["spoilers"][member],
                            s["emojis"][member],
                            s["files_sent"][member],
                            uniqueID
                        ))
                        sql = """   UPDATE UserReactionStatistic
                                    SET
                                        ReactionAddedCount=?,
                                        GottenReactionCount=?
                                    WHERE UniqueMemberID=? AND SubjectID=0"""
                        conn.execute(sql, (
                            s["reactions_added"][member],
                            s["reactions_received"][member],
                            uniqueID
                        ))
                        conn.commit()
                        if not msg_result[0]:
                            print(f"Message {msg_result[2]}")
                        if not reaction_result[0]:
                            print(f"Reaction {reaction_result[2]}")
                        if reaction_result[0] and msg_result[0]:
                            count += 1
                    await ctx.send(f"{count} successful DB entry transfers on guild `{guild_obj.name}`")
            elif file == "reputations":
                with open("./data/reputation.json", "r") as f:
                    reputations = json.load(f)
                for guild in reputations:
                    guild_obj = self.bot.get_guild(int(guild))
                    if guild_obj is None:
                        print(f"Didn't find Guild with ID: {guild}")
                        continue
                    count = 0
                    for member in reputations[guild]["rep"]:
                        member_obj = guild_obj.get_member(int(member))
                        if member_obj is None:
                            print(f"Didn't find Member with ID: {member}")
                            continue
                        for message in reputations[guild]["rep"][member]:
                            sql = """   INSERT INTO Reputations(
                                            UniqueMemberID,
                                            ReputationMessage,
                                            IsPositive)
                                        VALUES (?,?,?)"""
                            uniqueID = handySQL.get_or_create_member(conn, member_obj, guild_obj)
                            # Check if the rep is positive
                            if message.startswith("-"):
                                isPositive = 0
                            else:
                                isPositive = 1
                            conn.execute(sql, (uniqueID, message, isPositive))
                            conn.commit()
                            count += 1
                    await ctx.send(f"{count} successful DB entry transfers on guild `{guild_obj.name}`")
            elif file == "quotes":
                with open("./data/quotes.json", "r") as f:
                    quotes = json.load(f)
                for guild_id in quotes:
                    finished = []
                    total_count = 0
                    count = 0
                    guild_obj = self.bot.get_guild(int(guild_id))
                    if guild_obj is None:
                        print(f"Didn't find Guild with ID: {guild_id}")
                        continue
                    for name in quotes[guild_id]:
                        if len(quotes[guild_id][name]) == 0:
                            continue
                        try:
                            member = discord.utils.find(lambda m: m.name.lower() == name, guild_obj.members)
                        except discord.ext.commands.errors.UserNotFound:
                            member = None
                        uniqueID = None
                        quoted_name = name
                        if member is not None:
                            uniqueID = handySQL.get_uniqueMemberID(conn, member.id, guild_id)
                            quoted_name = member.name
                        for q in quotes[guild_id][name]:
                            if not isascii(q[1]):
                                continue
                            date = datetime.strptime(q[0], "%d/%m/%Y").strftime("%Y-%m-%d %H:%M:%S")
                            sql = """   INSERT INTO Quotes(Quote, Name, UniqueMemberID, DiscordGuildID, CreatedAt)
                                        VALUES(?,?,?,?,?)"""
                            conn.execute(sql, (q[1], quoted_name, uniqueID, guild_id, date))
                            conn.commit()
                            count += 1
                            total_count += 1
                        finished.append(quoted_name)

                        if count >= 200:
                            await ctx.send(f"{count} successful DB entry transfers for names:\n`{', '.join(finished)}`")
                            finished = []
                            count = 0
                    if len(finished) > 0:
                        await ctx.send(f"{count} successful DB entry transfers for names:\n`{', '.join(finished)}`")
                    await ctx.send(f"{total_count} successful DB entry transfers on guild `{guild_obj.name}`")

            else:
                await ctx.send("Unknown file")
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.group(usage="draw <command> <x1> <x2> <y1> <y2> <step> <color/channel> [delete_messages: y/n]", invoke_without_command=True)
    async def draw(self, ctx, command=None, x1=None, x2=None, y1=None, y2=None, step=1, color="#FFFFFF"):
        """
        Draws a picture using Battle's place command.
        Commands:
        - `image <x1> <x2> <y1> <y2> [step] [updates channel]`
        - `save [clear]`
        - `cancel`: Cancels all currently going on drawings.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            if ctx.invoked_subcommand is None:
                if command is None:
                    await ctx.send("No command given")
                    raise discord.ext.commands.errors.BadArgument
                elif command == "cancel":
                    if x1 is None:
                        self.cancel_all = True
                    else:
                        self.cancel_draws.append(x1)
                    return
                elif command == "image":
                    if len(ctx.message.attachments) == 0:
                        await ctx.send("No image given")
                        raise discord.ext.commands.errors.BadArgument
                    async with aiohttp.ClientSession() as cs:
                        async with cs.get(ctx.message.attachments[0].url) as r:
                            buffer = io.BytesIO(await r.read())
                    im = Image.open(buffer)
                    x1 = int(x1)
                    x2 = int(x2)
                    y1 = int(y1)
                    y2 = int(y2)
                    im = im.resize((x2-x1, y2-y1), PIL.Image.NEAREST)
                    width, height = im.size
                    pixels = im.convert('RGBA').load()
                    odd = False
                    self.cancel_all = False
                    total_pixels = 0

                    # to get the top left most coordinate and bot right most to look at
                    botX = 0
                    botY = 0
                    topX = x2
                    topY = y2

                    # id to stop specific draw
                    ID = random.randint(1000, 10000)

                    prepare_queue = []
                    pixels_queue = []

                    # count image beforehand
                    for x in range(0, width, step):
                        if odd and step > 1:
                            start = step//2
                            odd = False
                        else:
                            start = 0
                            odd = True
                        for y in range(start, height, step):
                            r, g, b, a = pixels[x, y]
                            if a != 0:
                                topX = min(topX, x)
                                topY = min(topY, y)
                                total_pixels += 1
                                prepare_queue.append([x, y, rgb2hex(r, g, b)])
                                botY = max(y, botY)
                                botX = max(x, botX)

                    # reorders the pixel placement so every 100th pixel gets drawn first
                    for i in range(100):
                        cur = i
                        while cur < len(prepare_queue):
                            pixels_queue.append(prepare_queue[cur])
                            cur += 100

                    topleft = (x1+topX, y1+topY)
                    bottomright = (x1+botX, y1+botY)

                    self.progress[ID] = [0, len(pixels_queue), topleft, bottomright, step]

                    # Get channel
                    try:
                        channel = self.bot.get_channel(int(color))
                        if channel is None:
                            raise ValueError
                    except ValueError:
                        channel = ctx.channel

                    embed = discord.Embed(title="Started Drawing", description=self.draw_desc(ID))
                    await channel.send(embed=embed)

                    # draws the pixels
                    while len(pixels_queue) > 0:
                        if self.cancel_all or str(ID) in self.cancel_draws:
                            await ctx.send(f"Canceled Project {ID}.")
                            self.cancel_draws.pop(self.cancel_draws.index(str(ID)))
                            self.progress.pop(ID)
                            raise discord.ext.commands.errors.BadArgument
                        pix = pixels_queue[0]
                        pX = pix[0]
                        pY = pix[1]
                        pHex = pix[2]
                        try:
                            await ctx.send(f".place setpixel {pX} {pY} {pHex} | PROJECT {ID}")
                            self.progress[ID][0] += 1
                            pixels_queue.pop(0)
                        except Exception:
                            await asyncio.sleep(5)

                    # Removes the project from the current active projects
                    self.progress.pop(ID)
                elif command == "save":

                    if x1 is not None and x1.lower() == "clear":
                        self.image = None
                        try:
                            os.remove("place.png")
                        except FileNotFoundError:
                            pass
                        await ctx.send("Cleared image to keep track of")
                        return

                    if len(ctx.message.attachments) == 0:
                        await ctx.send("No image given")
                        raise discord.ext.commands.errors.BadArgument
                    async with aiohttp.ClientSession() as cs:
                        async with cs.get(ctx.message.attachments[0].url) as r:
                            buffer = io.BytesIO(await r.read())

                    self.image = im = Image.open(buffer)
                    im.save("place.png", "PNG")
                    await ctx.send("Successfully updated place.png")

                else:
                    await ctx.send("Command not found. Right now only `cancel`, `image` and `square` exist.")
        else:
            raise discord.ext.commands.errors.NotOwner

    @draw.command(usage="progress <ID>", aliases=["prog"])
    async def progress(self, ctx, ID=None):
        if ID is None or int(ID) not in self.progress:
            keys = ""
            for k in self.progress.keys():
                keys += f"- `{k}`"
            await ctx.send(f"Project IDs | Count:{len(self.progress)}\n{keys}")
            return
        embed = discord.Embed(
            title=f"Drawing Progress | Project {ID}",
            description=self.draw_desc(ID)
        )
        await ctx.send(embed=embed)

    @commands.command(usage="bully <user>")
    async def bully(self, ctx, user=None):
        """
        Bully a user by pinging that person in random intervals, then instantly deleting that message again.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            await ctx.message.delete()
            if user is None:
                await ctx.send("No user")
                raise discord.ext.commands.errors.NotOwner
            for i in range(10):
                await asyncio.sleep(random.randint(10, 100))
                msg = await ctx.send(user)
                await msg.delete()
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="inspect <cmd>")
    async def inspect(self, ctx, cmd="minesweeper"):
        """
        Used to send the code of any given command. **Does not work yet.**
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            source_code = inspect.getsource(minesweeper.Minesweeper)
            await ctx.send(f"```python\n"
                           f"{source_code}\n"
                           f"```")
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="loops")
    async def loops(self, ctx):
        """
        Displays all running background tasks
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            all_loops = {
                "Lecture Updates Loop": self.bot.get_cog("Updates").heartbeat(),
                "Git Backup Loop": self.bot.get_cog("Statistics").heartbeat(),
                "Voice XP track Loop": self.bot.get_cog("Voice").heartbeat(),
                "COVID Web Scraper": self.bot.get_cog("Games").heartbeat(),
                "Events Updates": self.bot.get_cog("Information").heartbeat()
            }

            msg = ""
            cur_time = time.time()
            for name in all_loops.keys():
                if all_loops[name]:
                    msg += f"\n**{name}:** <:checkmark:776717335242211329>"
                else:
                    msg += f"\n**{name}:** <:xmark:776717315139698720>"
            await ctx.send(msg)
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="loading")
    async def loading(self, ctx):
        """
        Plays a little loading animation in a message.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            msg = await ctx.send("Loading:\n0% | " + loading_bar(0))
            for i in range(1, 10):
                await msg.edit(
                    content=("Loading:\n" + f"{random.randint(i * 10, i * 10 + 5)}% | " + loading_bar(i)))
                await asyncio.sleep(0.75)
            await msg.edit(content=("Loading: DONE\n" + "100% | " + loading_bar(10, 10, False)))
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="reboot")
    async def reboot(self, ctx):
        """
        Uses `reboot now` in the command line. Restarts the current device if it runs on linux.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            await ctx.send("Rebooting...")
            os.system('reboot now')  # Only works on linux (saved me a few times)
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="react <message_id> <reaction>")
    async def react(self, ctx, message_id, reaction):
        """
        React to a message using the bot.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            message = await ctx.fetch_message(int(message_id))
            await message.add_reaction(reaction)
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="spam")
    async def spam(self, ctx):
        """
        Sends close to the maximum allowed characters on Discord in one single message
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            spam = "\n" * 1900
            embed = discord.Embed(title="." + "\n" * 250 + ".", description="." + "\n" * 2000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
            embed.add_field(name=".\n.", value="." + "\n" * 700 + ".")
            await ctx.send(f"\"{spam}\"", embed=embed)
            await ctx.send(f"{len(spam) + len(embed)} chars")
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(aliases=["send", "repeatme", "echo"], usage="say [count] <msg>")
    async def say(self, ctx, count=None, *, cont):
        """
        Repeats a message. If given, repeats a specific amount of times
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            try:
                amt = int(count)
                for i in range(amt):
                    await ctx.send(cont)
            except ValueError:
                await ctx.send(f"{count} {cont}")
        else:
            raise discord.ext.commands.errors.NotOwner


def setup(bot):
    bot.add_cog(Owner(bot))
