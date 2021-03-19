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


def draw_desc(topleft, step, xMax, yMax, amt_of_pixels, transparent, total_pixels, delta_pixels, delta_time):
    remaining_pixels = total_pixels - amt_of_pixels
    if len(topleft) == 0:
        x1 = 0
        y1 = 0
    else:
        x1 = topleft[0]
        y1 = topleft[1]
    if delta_time > 2:
        rem_time = round(remaining_pixels*delta_pixels/(delta_time*60), 2)
    else:
        rem_time = "∞"
    return f"X: {x1} | Y: {y1} | Step: {step}\n" \
           f"Width: {xMax-x1} | Height: {yMax-y1}\n" \
           f"Pixel Total: {total_pixels}\n" \
           f"Pixels to draw: {remaining_pixels}\n" \
           f"Pixels drawn: {amt_of_pixels}\n"\
           f"Transparent: {transparent}\n"\
           f"{loading_bar_draw(amt_of_pixels, total_pixels)}  {round(100 * amt_of_pixels / total_pixels, 2)}%\n" \
           f"Time Remaining: {rem_time} mins\n" \
           f"`dev.place zoom {x1} {y1} {max(xMax-x1, yMax-y1)}` to see the progress."


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "./data/discord.db"
        self.conn = handySQL.create_connection(self.db_path)
        self.cancel_draw = False

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
        if message.author.id == 755781649643470868:
            return

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
                table = tabulate(values, header, tablefmt="presto")
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
            else:
                await ctx.send("Unknown file")
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="draw <command> <x1> <x2> <y1> <y2> <step> <color/channel>")
    async def draw(self, ctx, command=None, x1=None, x2=None, y1=None, y2=None, step=1, color="#FFFFFF"):
        """
        Draws a picture using battle's place command.
        Commands:
        - image: Draws the attached image and automatically resizes the image to the given dimensions. Channel ID is optional to send the progress \
        in a separate channel.
        - box: Draws a one color box with the given dimensions. Color has to be in format #FFFFFF.
        - cancel: Cancels all currently going on drawings.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            if command is None:
                await ctx.send("No command given")
                raise discord.ext.commands.errors.BadArgument
            elif command == "cancel":
                self.cancel_draw = True
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
                im = im.resize((x2+1-x1, y2+1-y1), PIL.Image.NEAREST)
                xMax, yMax = im.size
                pixels = im.convert('RGBA').load()
                curX = x1
                odd = False
                msgs = []
                self.cancel_draw = False
                amt_of_pixels = 0
                transparent = 0  # amount of transparent/skipped pixels
                total_pixels = 0
                topleft = ()
                countX = 0
                countY = 0

                # count pixels beforehand
                for x in range(0, xMax, step):
                    if odd and step > 1:
                        start = step+int(step/2)
                        odd = False
                    else:
                        start = step
                        odd = True
                    for y in range(start, yMax, step):
                        r, g, b, a = pixels[x, y]
                        if a != 0:
                            if len(topleft) == 0:
                                topleft = (x, y)
                            total_pixels += 1
                            countY = y
                            countX = x

                # Get channel
                try:
                    channel = self.bot.get_channel(int(color))
                    if channel is None:
                        raise ValueError
                except ValueError:
                    channel = ctx.channel

                # Timer
                pixel_clock = 0
                cur_time = time.time()

                # Creates embed to see overview of image
                desc = draw_desc(topleft, step, countX, countY, amt_of_pixels, transparent, total_pixels, amt_of_pixels-pixel_clock, time.time()-cur_time)
                embed = discord.Embed(title="Drawing Image", description=desc)
                prog_msg = await channel.send(embed=embed)
                for x in range(0, xMax, step):
                    if odd and step > 1:
                        start = int(step/2)
                        curY = y1 + int(step/2)
                        odd = False
                    else:
                        start = 0
                        curY = y1
                        odd = True
                    for y in range(start, yMax, step):
                        if self.cancel_draw:
                            await ctx.send("Canceling draw")
                            desc = draw_desc(topleft, step, countX, countY, amt_of_pixels, transparent, total_pixels, amt_of_pixels-pixel_clock, time.time()-cur_time)
                            embed = discord.Embed(title="CANCELED Drawing Image", description=desc, color=0xFF0000)
                            await prog_msg.edit(embed=embed)
                            if len(msgs) > 0:
                                await ctx.channel.delete_messages(msgs)
                            raise discord.ext.commands.errors.BadArgument
                        r, g, b, a = pixels[x, y]
                        hex_color = rgb2hex(r, g, b)

                        # ignores black pixels / acts like they are transparent
                        if a != 0:
                            msgs.append(await ctx.send(f"dev.place setpixel {curX} {curY} {hex_color}"))
                            amt_of_pixels += 1
                        else:
                            transparent += 1
                        if len(msgs) >= 20:
                            await ctx.channel.delete_messages(msgs)
                            msgs = []
                            desc = draw_desc(topleft, step, countX, countY, amt_of_pixels, transparent, total_pixels, amt_of_pixels - pixel_clock,
                                             time.time() - cur_time)
                            pixel_clock = amt_of_pixels
                            cur_time = time.time()
                            embed = discord.Embed(title="Drawing Image", description=desc)
                            await prog_msg.edit(embed=embed)
                        curY += step
                    curX += step
                if len(msgs) > 0:
                    await ctx.channel.delete_messages(msgs)
                desc = draw_desc(topleft, step, countX, countY, amt_of_pixels, transparent, total_pixels, amt_of_pixels-pixel_clock, time.time()-cur_time)
                embed = discord.Embed(title="DONE Drawing Image", description=desc, color=0x00FF00)
                await prog_msg.edit(embed=embed)

            elif command == "square":
                try:
                    if x1 is None or x2 is None or y1 is None or y2 is None:
                        raise discord.ext.commands.errors.BadArgument
                    x1 = int(x1)
                    x2 = int(x2)
                    y1 = int(y1)
                    y2 = int(y2)
                except (ValueError, discord.ext.commands.errors.BadArgument):
                    await ctx.send("Incorrect arguments. `draw <x1/cancel> <x2> <y1> <y2> [color in # hex] [step]`")
                msgs = []
                self.cancel_draw = False
                odd = False
                y1_start = y1
                for x in range(x1, x2, step):
                    # alternating placing pattern to fill a space faster
                    if odd and step > 1:
                        y1_start = y1+int(step/2)
                        odd = False
                    elif step > 1:
                        y1_start = y1
                        odd = True

                    for y in range(y1_start, y2, step):
                        if self.cancel_draw:
                            await ctx.send("Canceling draw")
                            raise discord.ext.commands.errors.BadArgument
                        msgs.append(await ctx.send(f"dev.place setpixel {x} {y} {color}"))
                        if len(msgs) >= 20:
                            await ctx.channel.delete_messages(msgs)
                            msgs = []
                if len(msgs) > 0:
                    await ctx.channel.delete_messages(msgs)

            else:
                await ctx.send("Command not found. Right now only `cancel`, `image` and `square` exist.")
        else:
            raise discord.ext.commands.errors.NotOwner

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
                seconds_elapsed = cur_time - all_loops[name]
                if seconds_elapsed <= 120:
                    msg += f"\n**{name}:** <:checkmark:776717335242211329> | Last Heartbeat: `{int(round(seconds_elapsed))}` seconds ago"
                elif all_loops[name] == 0:
                    msg += f"\n**{name}:** <:xmark:776717315139698720> | Last Heartbeat: **background task never even started**"
                else:
                    msg += f"\n**{name}:** <:xmark:776717315139698720> | Last Heartbeat: `{int(round(seconds_elapsed))}` seconds ago"
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

    @commands.command(aliases=["send", "repeatme", "echo"], usage="say <msg>")
    async def say(self, ctx, *, cont):
        """
        Repeats a message
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            await ctx.send(cont)
        else:
            raise discord.ext.commands.errors.NotOwner


def setup(bot):
    bot.add_cog(Owner(bot))
