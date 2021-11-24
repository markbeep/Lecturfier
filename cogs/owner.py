import asyncio
import os
import random
import sqlite3
import time
from datetime import datetime
from enum import Enum
from sqlite3 import Error

import discord
from discord.ext import commands
from pytz import timezone
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
        return "<:blue_box:764901467097792522>" * bars + "<:grey_box:764901465592037388>" * (max_length - bars)  # First is blue square, second is grey
    elif failed:
        return "<:red_box:764901465872662528>"*bars  # Red square
    else:
        return "<:green_box:764901465948684289>"*bars  # Green square


class IDType(Enum):
    USER = 1
    ROLE = 2
    CHANNEL = 3
    GUILD = 4


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()

        # gets the button value to watch
        self.watch_button_value = SQLFunctions.get_config("ButtonValue", self.conn)
        if len(self.watch_button_value) == 0:
            self.watch_button_value = 1e6
        else:
            self.watch_button_value = self.watch_button_value[0]
        self.sent_message = False
        self.old_value = 1e6  # to ignore fake buttons we store the last value

    @commands.Cog.listener()
    async def on_message_edit(self, before, message):
        if message.author.id == 778731540359675904:
            if len(message.components) > 0:
                message = await message.channel.fetch_message(message.id)
                action_row = message.components[0]
                if len(action_row.components) == 0:
                    return
                button = action_row.components[0]
                button_value = button.label
                if button_value.isnumeric():
                    button_value = int(button_value)
                    if not self.sent_message and button_value >= self.watch_button_value:
                        user = self.bot.get_user(205704051856244736)
                        embed = discord.Embed(
                            title="BUTTON ABOVE SCORE",
                            description=f"Watching Score: `{self.watch_button_value}`\n"
                                        f"Button Value: `{button_value}`\n"
                                        f"Channel: <#{message.channel.id}>\n"
                                        f"Message Link: [Click Here](https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id})",
                            color=discord.Color.gold()
                        )
                        for i in range(3):
                            await user.send(embed=embed)
                        self.sent_message = True
                    elif button_value < self.old_value:
                        # the button was clicked and the score went down
                        dt = datetime.fromtimestamp(time.time() + 60 * (self.watch_button_value - button_value), tz=timezone("Europe/Zurich"))
                        self.sent_message = False
                        user = self.bot.get_user(205704051856244736)
                        embed = discord.Embed(
                            title="Button was clicked.",
                            description=f"Watching Score: `{self.watch_button_value}`\n"
                                        f"Button Value: `{button_value}`\n"
                                        f"Channel: <#{message.channel.id}>\n"
                                        f"Message Link: [Click Here](https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id})\n"
                                        f"Button is at desired value at `{dt.strftime('%H:%M on %a. %d.%m.%Y')}`",
                            color=discord.Color.red()
                        )
                        await user.send(embed=embed)

                    self.old_value = button_value

    @commands.is_owner()
    @commands.command()
    async def watch(self, ctx, val=None):
        await ctx.message.delete()
        if val is None:
            # yes if we're tracking, no if we're at default value
            if self.watch_button_value < 1e6:
                await ctx.send(f"{self.watch_button_value} | {self.sent_message}", delete_after=5)
            else:
                await ctx.send("no", delete_after=5)
        else:
            if not val.isnumeric():
                await ctx.send("not int", delete_after=5)
                raise discord.ext.commands.errors.BadArgument
            # saves the value to watch into config
            SQLFunctions.insert_or_update_config("ButtonValue", int(val), self.conn)
            self.watch_button_value = int(val)
            self.old_value = 1e6
            self.sent_message = False
            await ctx.send("ok", delete_after=5)

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
                raise discord.ext.commands.BadArgument
            if command.lower() not in [com.name.lower() for com in self.bot.commands]:
                await ctx.reply("ERROR! Command not found. Did you maybe mistype a subcommand?")
                raise discord.ext.commands.BadArgument
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
            raise discord.ext.commands.BadArgument
        if object_id is None:
            await ctx.reply("ERROR! No ID given.")
            raise discord.ext.commands.BadArgument

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
                            raise discord.ext.commands.BadArgument
                        else:
                            object_type = IDType.USER
                    else:
                        object_type = IDType.CHANNEL
                else:
                    object_type = IDType.GUILD

        except ValueError:
            await ctx.reply("ERROR! Incorrect ID given. Either mention or simply write the ID.")
            raise discord.ext.commands.BadArgument
        if permission_level is None:
            await ctx.reply("ERROR! No permission level given.")
            raise discord.ext.commands.BadArgument
        try:
            permission_level = int(permission_level)
        except ValueError:
            await ctx.reply("ERROR! The given permission level is not an int.")
            raise discord.ext.commands.BadArgument
        if command_name.lower() not in [com.name.lower() for com in self.bot.commands]:
            await ctx.reply("ERROR! No command with that name found.")
            raise discord.ext.commands.BadArgument

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
            raise discord.ext.commands.errors.NotOwner
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
            "Lecture Updates Loop": self.bot.get_cog("Updates").heartbeat(),
            "Git Backup Loop": self.bot.get_cog("Statistics").heartbeat(),
            "Voice XP track Loop": self.bot.get_cog("Voice").heartbeat(),
            "COVID Web Scraper": self.bot.get_cog("Games").heartbeat(),
            "Events Updates": self.bot.get_cog("Information").heartbeat()
        }

        msg = ""
        for name in all_loops.keys():
            if all_loops[name]:
                msg += f"\n**{name}:** <:checkmark:776717335242211329>"
            else:
                msg += f"\n**{name}:** <:xmark:776717315139698720>"
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
    @commands.command(usage="reboot")
    async def reboot(self, ctx):
        """
        Uses `reboot now` in the command line. Restarts the current device if it runs on linux.
        Permissions: Owner
        """
        await ctx.send("Rebooting...")
        os.system('reboot now')  # Only works on linux (saved me a few times)

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
    async def say(self, ctx, count=None, *, cont):
        """
        Repeats a message. If given, repeats a specific amount of times
        Permissions: Owner
        """
        try:
            amt = int(count)
            for i in range(amt):
                await ctx.send(cont)
        except ValueError:
            await ctx.send(f"{count} {cont}")


def setup(bot):
    bot.add_cog(Owner(bot))
