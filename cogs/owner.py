from datetime import datetime
import discord
from discord.ext import commands
import random
import asyncio
import os
import time
import json
from helper.sql import SQLFunctions
from sqlite3 import Error
import sqlite3
from tabulate import tabulate


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
        self.conn = SQLFunctions.connect()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:  # ignores itself
            return

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
