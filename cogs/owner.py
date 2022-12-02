import asyncio
import random
import sqlite3
import time
from enum import Enum
from sqlite3 import Error

import discord
from discord.ext import commands
from tabulate import tabulate

from helper.sql import SQLFunctions


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
        return "<:blue_box:944974657013047328>" * bars + "<:grey_box:944973724371779594>" * (max_length - bars)  # First is blue square, second is grey
    elif failed:
        return "<:red_box:944974688516440114>"*bars  # Red square
    else:
        return "<:green_box:944973724803817522>"*bars  # Green square


class IDType(Enum):
    USER = 1
    ROLE = 2
    CHANNEL = 3
    GUILD = 4


class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()

        temp_count_channel_id = SQLFunctions.get_config("CountChannelID", self.conn)
        self.count_channel_id = temp_count_channel_id[0] if len(temp_count_channel_id) > 0 else 996746797236105236
        temp_follow = SQLFunctions.get_config("FollowID", self.conn)
        self.follow_id = temp_follow[0] if len(temp_follow) > 0 else None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id == self.count_channel_id and message.author.id in [self.bot.owner_id, self.follow_id]:
            try:
                count = int(message.content)
                await message.channel.send(f"{count+1}")
            except ValueError:
                pass

    @commands.is_owner()
    @commands.guild_only()
    @commands.command(usage="follow [member | channel]")
    async def follow(self, ctx: commands.Context, user: discord.Member | discord.TextChannel | discord.Thread | None):
        if user and isinstance(user, discord.Member):
            SQLFunctions.insert_or_update_config("FollowID", user.id, self.conn)
            self.follow_id = user.id
            await ctx.send(f"Following {user.mention}")
            return
        
        if user and isinstance(user, discord.abc.Messageable):
            SQLFunctions.insert_or_update_config("CountChannelID", user.id, self.conn)
            self.count_channel_id = user.id
            await ctx.send(f"Counting in <#{self.count_channel_id}>")
            return

        following = SQLFunctions.get_config("FollowID", self.conn)
        if len(following) == 0:
            await ctx.send("Not following anyone yet.")
        else:
            await ctx.send(f"Following <@{following[0]}>")

    @commands.is_owner()
    @commands.group(usage="perm <command>", invoke_without_command=True)
    async def perm(self, ctx, command=None):
        """
        Can be used to edit or view permissions for a command.
        For more information view the `add` subcommand.
        Permissions: Owner
        """
        if ctx.invoked_subcommand is None:
            if command is None:
                await ctx.reply("ERROR! No command to view given.")
                raise commands.errors.BadArgument()
            if command.lower() not in [com.name.lower() for com in self.bot.commands]:
                await ctx.reply("ERROR! Command not found. Did you maybe mistype a subcommand?")
                raise commands.errors.BadArgument()
            command_level = SQLFunctions.get_all_command_levels(command.lower(), self.conn)
            embed = discord.Embed(
                description=f"Dynamic permissions for `{command.lower()}`:",
                color=discord.Color.blue()
            )
            user_msg = "\n".join(f"* {k}: {v}" for k, v in command_level.user_levels.items())
            role_msg = "\n".join(f"* {k}: {v}" for k, v in command_level.role_levels.items())
            channel_msg = "\n".join(f"* {k}: {v}" for k, v in command_level.channel_levels.items())
            guild_msg = "\n".join(f"* {k}: {v}" for k, v in command_level.guild_levels.items())
            embed.add_field(name="User", value=f"```md\n{user_msg} ```")
            embed.add_field(name="Role", value=f"```md\n{role_msg} ```")
            embed.add_field(name="\u200b", value="\u200b", inline=False)
            embed.add_field(name="Channel", value=f"```md\n{channel_msg} ```")
            embed.add_field(name="Guild", value=f"```md\n{guild_msg} ```")
            await ctx.reply(embed=embed)

    @commands.is_owner()
    @perm.command(usage="add <command name> <object ID> <permission Level [-1|0|1]>", name="add", aliases=["addPerm", "change"])
    async def addPerm(self, ctx, command_name=None, object_id=None, permission_level=None):
        """
        Sets the permission for a command name and the given ID.
        0: default value
        -1: command is disabled for that ID
        1: command is enabled for that ID
        Hierarchy is as follows: USER > ROLE > CHANNEL > GUILD
        For roles, if any of the roles allow the command, the user can use the command. \
        Additionally when adding roles, one can do simply do `&23123...` without the `<@>` stuff, not to ping \
        by accident. User, channels and guilds can be added by simply putting in the ID.
        Permissions: Owner
        """
        if command_name is None:
            await ctx.reply("ERROR! No command name given.")
            raise commands.errors.BadArgument()
        if object_id is None:
            await ctx.reply("ERROR! No ID given.")
            raise commands.errors.BadArgument()

        # to handle what type of object ID we are given
        try:
            if "&" in object_id:
                object_id = int(object_id.replace("<@", "").replace("&", "").replace(">", "").replace("!", ""))
                object_type = IDType.ROLE
            elif "@" in object_id:
                object_id = int(object_id.replace("<@", "").replace("!", "").replace(">", ""))
                object_type = IDType.USER
            elif "#" in object_id:
                object_id = int(object_id.replace("<#", "").replace(">", ""))
                object_type = IDType.CHANNEL
            else:
                object_id = int(object_id)
                discord_object = self.bot.get_guild(object_id)
                if discord_object is None:
                    discord_object = self.bot.get_channel(object_id)
                    if discord_object is None:
                        discord_object = self.bot.get_user(object_id)
                        if discord_object is None:
                            await ctx.reply("ERROR! No object was found with the given ID.")
                            raise commands.errors.BadArgument()
                        else:
                            object_type = IDType.USER
                    else:
                        object_type = IDType.CHANNEL
                else:
                    object_type = IDType.GUILD

        except ValueError:
            await ctx.reply("ERROR! Incorrect ID given. Either mention or simply write the ID.")
            raise commands.errors.BadArgument()
        if permission_level is None:
            await ctx.reply("ERROR! No permission level given.")
            raise commands.errors.BadArgument()
        try:
            permission_level = int(permission_level)
        except ValueError:
            await ctx.reply("ERROR! The given permission level is not an int.")
            raise commands.errors.BadArgument()
        if command_name.lower() not in [com.name.lower() for com in self.bot.commands]:
            await ctx.reply("ERROR! No command with that name found.")
            raise commands.errors.BadArgument()

        SQLFunctions.insert_or_update_command_level(command_name.lower(), object_id, permission_level, object_type.name, self.conn)

        embed = discord.Embed(description=f"Successfully changed permissions for `{command_name.lower()}` with level `{permission_level}` for "
                                          f"`{object_type.name}` with ID `{object_id}`",
                              color=discord.Color.green())
        await ctx.reply(embed=embed)

    @commands.is_owner()
    @commands.command(usage="sql <command>")
    async def sql(self, ctx, *, sql):
        """
        Use SQL
        Permissions: Owner
        """
        conn = self.conn
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        start_time = time.perf_counter()
        sql = sql.replace("insert", "insert or ignore").replace("INSERT", "INSERT OR IGNORE")
        error = False
        try:
            c.execute(sql)
        except Error as e:
            await ctx.send(str(e))
            error = True
        finally:
            conn.commit()
        if error:
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

    @commands.is_owner()
    @commands.command(usage="bully <user>")
    async def bully(self, ctx, user=None):
        """
        Bully a user by pinging that person in random intervals, then instantly deleting that message again.
        Permissions: Owner
        """
        await ctx.message.delete()
        if user is None:
            await ctx.send("No user")
            raise commands.errors.NotOwner
        for i in range(10):
            await asyncio.sleep(random.randint(10, 100))
            msg = await ctx.send(user)
            await msg.delete()

    @commands.is_owner()
    @commands.command(usage="loops")
    async def loops(self, ctx):
        """
        Displays all running background tasks
        Permissions: Owner
        """
        all_loops = {
            "Lecture Updates Loop": self.bot.get_cog("Task").heartbeat(),
            "Git Backup Loop": self.bot.get_cog("Statistics").heartbeat(),
            "Voice XP track Loop": self.bot.get_cog("Voice").heartbeat(),
            "Events Updates": self.bot.get_cog("Information").heartbeat(),
            "AoC Tracker": self.bot.get_cog("AdventOfCode").heartbeat(),
        }

        msg = ""
        for name in all_loops.keys():
            if all_loops[name]:
                msg += f"\n**{name}:** <a:checkmark:944970382522351627>"
            else:
                msg += f"\n**{name}:** <a:cross:944970382694314044>"
        await ctx.send(msg)

    @commands.is_owner()
    @commands.command(usage="loading")
    async def loading(self, ctx):
        """
        Plays a little loading animation in a message.
        Permissions: Owner
        """
        msg = await ctx.send("Loading:\n0% | " + loading_bar(0))
        for i in range(1, 10):
            await msg.edit(
                content=("Loading:\n" + f"{random.randint(i * 10, i * 10 + 5)}% | " + loading_bar(i)))
            await asyncio.sleep(0.75)
        await msg.edit(content=("Loading: DONE\n" + "100% | " + loading_bar(10, 10, False)))

    @commands.is_owner()
    @commands.command(usage="restart")
    async def restart(self, ctx):
        """
        Exits the current process and hopes it will be restarted automatically.
        Permissions: Owner
        """
        await ctx.send("Restarting...")
        exit()

    @commands.is_owner()
    @commands.command(usage="react <message_id> <reaction>")
    async def react(self, ctx, message_id, reaction):
        """
        React to a message using the bot.
        Permissions: Owner
        """
        message = await ctx.fetch_message(int(message_id))
        await message.add_reaction(reaction)

    @commands.is_owner()
    @commands.command(usage="spam")
    async def spam(self, ctx):
        """
        Sends close to the maximum allowed characters on Discord in one single message
        Permissions: Owner
        """
        spam = "\n" * 1900
        embed = discord.Embed(title="." + "\n" * 250 + ".", description="." + "\n" * 2000 + ".")
        embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
        embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
        embed.add_field(name=".\n.", value="." + "\n" * 1000 + ".")
        embed.add_field(name=".\n.", value="." + "\n" * 700 + ".")
        await ctx.send(f"\"{spam}\"", embed=embed)
        await ctx.send(f"{len(spam) + len(embed)} chars")

    @commands.is_owner()
    @commands.command(aliases=["send", "repeatme", "echo"], usage="say [count] <msg>")
    async def say(self, ctx, count="", *, cont):
        """
        Repeats a message. If given, repeats a specific amount of times
        Permissions: Owner
        """
        if count.isnumeric():
            amt = int(count)
            for _ in range(amt):
                await ctx.send(cont)
        else:
            await ctx.send(f"{count} {cont}")


async def setup(bot):
    await bot.add_cog(Owner(bot))
