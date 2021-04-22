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
from helper import handySQL, image2queue as im2q
from sqlite3 import Error
import sqlite3
from tabulate import tabulate
from PIL import Image
import PIL
import io
from discord.ext.commands.cooldowns import BucketType


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


def modifiers(img: im2q.PixPlace, mods: tuple) -> int:
    drawn = 0
    start = 0
    end = 0
    for i in range(len(mods)):
        m = mods[i]
        last = i == len(mods)-1
        if m.startswith("p"):  # percent start
            if not last:
                if mods[i+1].isnumeric():
                    start = int(mods[i+1])
                    i += 1
        if m.startswith("e"):  # percent end
            if not last:
                if mods[i+1].isnumeric():
                    end = int(mods[i+1])
                    i += 1
        elif m.startswith("f"):  # flip
            img.flip()
        elif m.startswith("c"):  # center
            img.center_first()
        elif m.startswith("l"):  # low to high def
            img.low_to_high_res()

    if start != 0 or end != 0:
        print(start, end)
        if start != 0 != end:
            drawn = img.perc_to_perc(start, end)
        elif start != 0:
            drawn = img.resume_progress(start)
        else:
            img.end_at(end)
    return drawn


async def create_buffer(ctx, x1, x2, y1, y2):
    async with aiohttp.ClientSession() as cs:
        async with cs.get(ctx.message.attachments[0].url) as r:
            buffer = io.BytesIO(await r.read())
    im = Image.open(buffer)
    x1 = int(x1)
    x2 = int(x2)
    y1 = int(y1)
    y2 = int(y2)
    width, height = im.size
    if x2 - x1 != width or y2 - y1 != height:
        im = im.resize((x2 - x1, y2 - y1), PIL.Image.NEAREST)
        buff = io.BytesIO()
        im.save(buff, format="PNG")
        buff.seek(0)
        return buff
    buffer.seek(0)
    return buffer


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "./data/discord.db"
        self.conn = handySQL.create_connection(self.db_path)
        self.cancel_all = False
        self.cancel_draws = []
        self.pause_draws = False
        self.progress = {}
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
        if ID not in self.progress:
            return "Project has no info"
        prog = self.progress[ID]
        topX, topY = prog["img"].top_left_corner
        botX, botY = prog["img"].bot_right_corner
        pix_drawn = prog["count"]
        pix_total = prog["img"].size
        return f"ID: {ID}\n" \
               f"X: {topX} | Y: {topY}\n" \
               f"Width: {botX - topX} | Height: {botY - topY}\n" \
               f"Pixel Total: {pix_total}\n" \
               f"Pixels to draw: {pix_total-pix_drawn}\n" \
               f"Pixels drawn: {pix_drawn}\n" \
               f"{loading_bar_draw(pix_drawn, pix_total)}  {round(100 * pix_drawn / pix_total, 2)}%\n" \
               f"Time Remaining: {round((pix_total - pix_drawn) * len(self.progress) / 60, 2)} mins\n" \
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

    @commands.is_owner()
    @commands.group(aliases=["d"], usage="draw <command> <x1> <x2> <y1> <y2> <step> <color/channel> [delete_messages: y/n]", invoke_without_command=True)
    async def draw(self, ctx, command=None, x1=None):
        """
        Draws a picture using Battle's place command.
        Commands:
        - `image <x1> <x2> <y1> <y2> [step] [updates channel]`
        - `multi <x1> <x2> <y1> <y2> [step] [updates channel]`
        - `save [clear]`
        - `cancel`: Cancels all currently going on drawings.
        - `pause`: Pauses all drawings
        Permissions: Owner
        """
        if ctx.invoked_subcommand is None:
            if command is None:
                await ctx.send("No command given")
                raise discord.ext.commands.errors.BadArgument
            elif command == "pause":
                self.pause_draws = not self.pause_draws
                await ctx.send(f"Pause draws: {self.pause_draws}")
            elif command == "cancel":
                if x1 is None:
                    self.cancel_all = True
                    self.progress = {}
                else:
                    self.cancel_draws.append(x1)
                return
            else:
                await ctx.send("Command not found. Right now only `cancel`, `image` and `square` exist.")

    @commands.is_owner()
    @draw.command(aliases=["i"], usage="image <x1> <x2> <y1> <y2> {mods}")
    async def image(self, ctx, x1=None, x2=None, y1=None, y2=None, *mods):
        """
        `x1`: x to start
        `x2`: x to stop
        `y1`: y to start
        `y2`: y to stop
        **Modifiers:**
        `p <int>`: Percentage to start at
        `e <int>`: Percentage to stop image at
        `f`: Flip queue order
        `c`: Center to out draw order
        `l`: Low to High Def draw order
        Permissions: Owner
        """
        if len(ctx.message.attachments) == 0:
            await ctx.send("No image given")
            raise discord.ext.commands.errors.BadArgument
        try:
            buffer = await create_buffer(ctx, x1, x2, y1, y2)
        except ValueError:
            await ctx.send("Not all coordinates given.")
            raise discord.ext.commands.errors.BadArgument

        self.cancel_all = False

        # id to stop specific draw
        ID = str(random.randint(1000, 10000))

        img = im2q.PixPlace(buffer, ID)
        drawn = modifiers(img, mods)
        pixels_queue = img.get_queue()

        self.progress[ID] = {
            "count": drawn,
            "img": img,
            "queue": pixels_queue
        }

        embed = discord.Embed(title="Started Drawing", description=self.draw_desc(ID))
        await ctx.send(embed=embed)

        # draws the pixels
        while len(pixels_queue) > 0:
            if self.cancel_all or str(ID) in self.cancel_draws:
                await ctx.send(f"Canceled Project {ID}.")
                if ID in self.progress:
                    self.progress.pop(ID)
                if ID in self.cancel_draws:
                    self.cancel_draws.pop(self.cancel_draws.index(ID))
                raise discord.ext.commands.errors.BadArgument
            if self.pause_draws:
                await asyncio.sleep(10)
                continue
            pix = pixels_queue[0]
            pX = pix[0]
            pY = pix[1]
            pHex = rgb2hex(pix[2], pix[3], pix[4])
            try:
                await ctx.send(f".place setpixel {pX} {pY} {pHex} | PROJECT {ID}")
                self.progress[ID]["count"] += 1
                pixels_queue.pop(0)
            except Exception:
                await asyncio.sleep(5)

        # Removes the project from the current active projects
        self.progress.pop(ID)

    @commands.guild_only()
    @commands.cooldown(1, 30, BucketType.guild)
    @draw.command(aliases=["m"], usage="multi <x1> <x2> <y1> <y2> {mods}")
    async def multi(self, ctx, x1=None, x2=None, y1=None, y2=None, *mods):
        """
        Creates a txt file for setmultiplepixels and sends it via DMs.
        `x1`: x to start
        `x2`: x to stop
        `y1`: y to start
        `y2`: y to stop
        **Modifiers:**
        `p <int>`: Percentage to start at
        `e <int>`: Percentage to stop image at
        `f`: Flip queue order
        `c`: Center to out draw order
        `l`: Low to High Def draw order
        """
        if len(ctx.message.attachments) == 0:
            await ctx.send("No image given")
            raise discord.ext.commands.errors.BadArgument
        try:
            buffer = await create_buffer(ctx, x1, x2, y1, y2)
        except ValueError:
            await ctx.send("Not all coordinates given.")

        img = im2q.PixPlace(buffer, "multi")
        modifiers(img, mods)
        pixels_queue = img.get_queue()

        # makes txt files instead
        file_count = 0
        files = []
        while len(pixels_queue) > 0:
            file_count += 1
            content = ""
            pixels_added = 0
            for i in range(80000):
                if len(pixels_queue) == 0:
                    break
                pix = pixels_queue.pop(0)
                pX = pix[0]
                pY = pix[1]
                pHex = rgb2hex(pix[2], pix[3], pix[4])
                content += f"{pX} {pY} {pHex}"
                if len(pixels_queue) != 0:
                    content += "|"
                pixels_added += 1
            filename = f"{file_count}-{pixels_added}.txt"
            files.append(filename)
            with open(filename, "a") as f:
                f.write(content)

        for f in files:
            file = discord.File(f)
            await ctx.author.send(f, file=file)
            os.remove(f)
        await ctx.author.send("Done")
        return

    @draw.command(usage="progress <ID>", aliases=["prog"])
    async def progress(self, ctx, ID=None):
        if ID is None or ID not in self.progress:
            keys = ""
            for k in self.progress.keys():
                keys += f"\n- `{k}` {round(self.progress[k]['count']*100/self.progress[k]['img'].size, 2)}%"
            await ctx.send(f"Project IDs | Count:{len(self.progress)} | Paused: {self.pause_draws}{keys}")
            return
        embed = discord.Embed(
            title=f"Drawing Progress | Project {ID}",
            description=self.draw_desc(ID)
        )
        await ctx.send(embed=embed)

    @commands.is_owner()
    @draw.command(usage="preview <ID>")
    async def preview(self, ctx, ID=None):
        if ID is None or ID not in self.progress:
            await ctx.send("Unknown ID given")
        else:
            if len(ctx.message.attachments) == 0:
                await ctx.send("No image given. You need to send the place image.")
                raise discord.ext.commands.errors.BadArgument
            async with aiohttp.ClientSession() as cs:
                async with cs.get(ctx.message.attachments[0].url) as r:
                    buffer = io.BytesIO(await r.read())
            async with ctx.typing():
                img = self.progress[ID]["img"]
                img.add_place(buffer)
                gif = img.create_gif()
                file = discord.File(fp=gif, filename="prev.gif")
            await ctx.send(file=file)


    @commands.is_owner()
    @draw.command()
    async def save(self, ctx, on="n"):
        # saves the new image if needed
        msg = ""
        if len(ctx.message.attachments) != 0:
            async with aiohttp.ClientSession() as cs:
                async with cs.get(ctx.message.attachments[0].url) as r:
                    buffer = io.BytesIO(await r.read())
            self.image = im = Image.open(buffer)
            im.save("place.png", "PNG")
            msg = "Successfully updated place.png"

        if on.startswith("c") or on.startswith("n"):
            self.image = None
            await ctx.send(f"{msg}\nTurned `OFF` image protection.")
        else:
            self.image = Image.open("place.png")
            await ctx.send(f"{msg}\nTurned `ON` image protection.")

    @commands.is_owner()
    @draw.command(aliases=["mismatches", "mis"])
    async def mismatch(self, ctx, color_to_check=""):
        if len(ctx.message.attachments) == 0:
            await ctx.send("No image given")
            raise discord.ext.commands.errors.BadArgument
        fp = "place.png"
        if not os.path.isfile(fp):
            fp = "placeOFF.png"
            if not os.path.isfile(fp):
                await ctx.send("No image to compare to")
                raise discord.ext.commands.errors.BadArgument
        save_pixels = Image.open(fp).convert("RGBA").load()
        async with aiohttp.ClientSession() as cs:
            async with cs.get(ctx.message.attachments[0].url) as r:
                buffer = io.BytesIO(await r.read())
        place_pixels = Image.open(buffer).convert("RGBA").load()

        im, count = self.find_mismatches(save_pixels, place_pixels, color_to_check)

        im.save("mismatches.png", "PNG")
        file = discord.File("mismatches.png")
        await ctx.send(f"Found {count} mismatches:", file=file)

    def find_mismatches(self, save_pixels, place_pixels, color_to_check=""):
        im = Image.new(mode="RGBA", size=(1000, 1000), color=(0, 0, 0, 0))
        pixels = im.load()
        count = 0
        for x in range(1000):
            for y in range(1000):
                r, g, b, a = save_pixels[x, y]
                if a != 0:
                    rp, gp, bp, ap = place_pixels[x, y]
                    if color_to_check.replace("#", "") == rgb2hex(rp, gp, bp).replace("#", "") or color_to_check == "" and (r, g, b, a) != (rp, gp, bp, ap):
                        count += 1
                        pixels[x, y] = (r, g, b, a)
        return im, count

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
