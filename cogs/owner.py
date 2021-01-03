import discord
from PIL.Image import Image
from discord.ext import commands
import random
import asyncio
import inspect
from nudenet import NudeClassifierLite
from PIL import Image
import requests
from io import BytesIO
import os
import time
from cogs import admin, hangman, help, updates, minesweeper, owner, player, quote, reputation, statistics, voice


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == 755781649643470868:
            return
        if message.channel.id == 00:  # turned it off
            try:
                msg = ""
                time_taken = 0
                url_list = []
                for i in range(len(message.attachments)):
                    if message.attachments[i].height is not None:
                        # The file is an image
                        url_list.append(message.attachments[i].url)
                temp_message_content = message.content
                while "http" in temp_message_content:
                    url = await self.get_link(temp_message_content)
                    url_list.append(url)
                    temp_message_content = temp_message_content.replace(url, "")

                if len(url_list) == 0:
                    return
                msg_info = await self.nsfw_check_message(url_list)
                msg += msg_info[0]
                time_taken += msg_info[1]

                if len(msg) > 0:
                    await message.channel.send(f"\n{message.author.mention}\n{msg}"
                                               f"\n`Seconds taken: {time_taken}`")
            except KeyError:
                raise discord.ext.commands.errors.BadArgument

    async def get_link(self, message_content):
        message_content = " " + message_content + " "
        if "http" in message_content:
            for i in range(message_content.index("http"), len(message_content)):
                if message_content[i] == " " or message_content[i] == "\n":
                    url = message_content[message_content.index("http"): i]
                    url = url.replace("<", "").replace(">", "")
                    return url
        else:
            return None

    async def nsfw_check_message(self, url):
        msg = ""
        output = await self.nsfw_check(url)
        result = output['result']
        filenames = output['filename']
        for i in range(len(filenames)):
            msg += f"Image nsfw score: {int(round(result[filenames[i]]['unsafe'] *  100))}% | <{url[i]}>\n"
        return msg, round(output['time_taken'], 2)

    async def nsfw_check(self, url):
        start = time.perf_counter()

        file_names = []
        for u in url:
            # downloads the images
            response = requests.get(u, verify=False)
            img = Image.open(BytesIO(response.content))

            # gives a random filename and saves the image
            filename = f"{random.randint(1, 1000000)}.png"
            img.save(filename, format="png")
            file_names.append(filename)

        # classifies the image to get the nude amount
        classifier = NudeClassifierLite()
        result = classifier.classify(file_names)

        for fn in file_names:
            # removes the image again
            os.remove(fn)

        time_taken = time.perf_counter() - start
        return {"filename": file_names, "result": result, "time_taken": time_taken}

    async def loading_bar(self, bars, max_length=None, failed=None):
        bars = round(bars)
        if max_length is None:
            max_length = 10
        if failed is None:
            return "<:blue_box:764901467097792522>" * bars + "<:grey_box:764901465592037388>" * (max_length - bars)  # First is blue square, second is grey
        elif failed:
            return "<:red_box:764901465872662528>"*bars  # Red square
        else:
            return "<:green_box:764901465948684289>"*bars  # Green square

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
                "Statistics file save Loop": self.bot.get_cog("Statistics").heartbeat(),
                "Voice XP track Loop": self.bot.get_cog("Voice").heartbeat(),
                "COVID Web Scraper": self.bot.get_cog("Player").heartbeat()
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
            msg = await ctx.send("Loading:\n0% | " + await self.loading_bar(0))
            for i in range(1, 10):
                await msg.edit(
                    content=("Loading:\n" + f"{random.randint(i * 10, i * 10 + 5)}% | " + await self.loading_bar(i)))
                await asyncio.sleep(0.75)
            await msg.edit(content=("Loading: DONE\n" + "100% | " + await self.loading_bar(10, 10, False)))
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
