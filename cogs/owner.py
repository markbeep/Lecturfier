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
            else:
                await ctx.send("Unknown file")
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
                "COVID Web Scraper": self.bot.get_cog("Games").heartbeat()
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
