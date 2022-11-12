import os
import subprocess
from itertools import chain
from threading import Thread
import json
import discord
from discord.ext import commands
import asyncio


if os.name == "nt":
    FILENAME = "./a.exe"
else:
    FILENAME = "./a.out"

AMAZON_ID = 963682692732428330
SECONDS = 20


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.battle_channel = self.bot.get_channel(819966095070330950)
        if self.battle_channel is None:
            self.battle_channel = self.bot.get_channel(944968090490380321)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.content.startswith(str(self.bot.user.id)) and message.author.id == AMAZON_ID:
            me, filler, game_object = message.content.split("|")
            game_object = json.loads(game_object)
            t = Thread(target=run, args=[self.battle_channel, game_object, asyncio.get_event_loop()])
            t.start()

    @commands.command()
    @commands.is_owner()
    async def play(self, ctx, enemy: str = None):
        """
        Plays a game of Amazon against the enemy
        """
        if enemy is None:
            await ctx.reply("No enemy id given")
            return
        await ctx.send(f"<@{AMAZON_ID}>|start|{enemy}")


async def setup(bot):
    await bot.add_cog(Admin(bot))


def run(channel: discord.TextChannel, game_object: dict, loop):
    flattened = chain.from_iterable(game_object["board"])
    res = subprocess.check_output([FILENAME, str(SECONDS), str(game_object["turn"]), *[str(x) for x in flattened]])
    res = res.decode("utf-8").replace("\r", "").split("\n")
    res = [x for x in res if len(x) > 5][-1]
    v = res.split(" ")
    confidence = round(200*(float(v[7])-0.5))
    asyncio.run_coroutine_threadsafe(channel.send(f"<@{AMAZON_ID}>|play|{game_object['id']}|{v[0]},{v[1]}|{v[2]},{v[3]}|{v[4]},{v[5]}| "
                                                  f"simulations: {v[6]} | confidence: {confidence} |t1 `{v[8]}`|t2 `{v[9]}`|c1 `{v[10]}`|c2 `{v[11]}`|w `{v[12]}`"), loop)
