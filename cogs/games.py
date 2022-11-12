import asyncio
import io
import time
from datetime import datetime
from types import new_class

import aiohttp
import discord
from bs4 import BeautifulSoup as bs
from colorthief import ColorThief
from discord.ext import commands, tasks
from discord.ext.commands.cooldowns import BucketType
from PIL import UnidentifiedImageError
from pytz import timezone

from helper.log import log
from helper.sql import SQLFunctions


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.clap_counter = 0
        self.time = 0

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.content.lower().replace("!", "") == "hello there <@755781649643470868>":
            await message.channel.send(f"General Kenobi {message.author.mention}")
        if time.time() - self.time > 10:
            self.clap_counter = 0
        if "👏" in message.content:
            await message.add_reaction("👏")
            self.clap_counter += 1
            self.time = time.time()
            if self.clap_counter >= 3:
                self.clap_counter = 0
                await message.channel.send("👏\n👏\n👏")

async def setup(bot):
    await bot.add_cog(Games(bot))
