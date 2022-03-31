import asyncio
import io
import os
import random

import aiohttp
import discord
import PIL
from discord.ext import commands, tasks
from discord.ext.commands.cooldowns import BucketType
from PIL import Image, ImageDraw, ImageFont

from helper import image2queue as im2q
from helper.sql import SQLFunctions


def rgb2hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)


def loading_bar_draw(a, b):
    prog = int(10 * a / b)
    return "<:green_box:944973724803817522>" * prog + (10 - prog) * "<:grey_box:944973724371779594>"


def modifiers(img: im2q.PixPlace, mods: tuple) -> int:
    drawn = 0
    start = -1
    end = -1
    for i in range(len(mods)):
        m = mods[i]
        last = i == len(mods) - 1
        if m.startswith("p"):  # percent start
            if not last:
                if mods[i + 1].isnumeric():
                    start = int(mods[i + 1])
                    i += 1
        if m.startswith("e"):  # percent end
            if not last:
                if mods[i + 1].isnumeric():
                    end = int(mods[i + 1])
                    i += 1
        elif m.startswith("f"):  # flip
            img.flip()
        elif m.startswith("c"):  # center
            img.center_first()
        elif m.startswith("r"):  # low to high def
            img.low_to_high_res()
        elif m.startswith("l"):  # left to right
            img.left_to_right()

    if start != -1 or end != -1:
        print("Modifiers", start, end)
        if start != -1 != end:
            drawn = img.perc_to_perc(start, end)
        elif start != -1:
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


def is_valid_msg(msg):
    filt = "!\"#$%&'()*+, -./:;<=>?@[\\]^_`{|}~ "
    if len(msg) > 200 or len(msg) < 15:
        return False
    count = 0
    for c in msg:
        if c in filt:
            count += 1
    if count / len(msg) > 0.7:
        return False
    return True


class Draw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cancel_all = False
        self.cancel_draws = []
        self.pause_draws = False
        self.progress = {}
        self.image = None
        self.queue = []
        self.background_draw.start()
        self.db_path = "./data/discord.db"
        self.place_path = "./place/"
        self.conn = SQLFunctions.connect()

        self.LINE_HEIGHT = 62  # amount of lines which fit on the place canvas
        self.CHAR_WIDTH = 166  # amount of chars which fit in a line on the place canvas
        self.font = ImageFont.truetype("./data/nk57-monospace-cd-rg.ttf", 12)
        self.userToCopyTextFrom = -1
        self.last_line = SQLFunctions.get_config("Draw_Last_Line", self.conn)
        if len(self.last_line) == 0:
            self.last_line = 0
        else:
            self.last_line = self.last_line[0]
        self.last_char = SQLFunctions.get_config("Draw_Last_Char", self.conn)
        if len(self.last_char) == 0:
            self.last_char = 0
        else:
            self.last_char = self.last_char[0]

    def get_task(self):
        self.pause_draws = True
        return self.background_draw

    @tasks.loop(seconds=5)
    async def background_draw(self):
        await self.bot.wait_until_ready()
        # opens and readies all the files
        imgs = self.get_all_queues(self.place_path)
        for im in imgs:
            if im.fp not in self.progress:
                start = SQLFunctions.get_config(f"Start_{im.fp}", self.conn)
                if len(start) == 0:
                    start = 0
                else:
                    start = start[0]
                self.progress[im.fp] = {
                    "count": start,
                    "img": im,
                    "queue": im.get_queue()
                }
                self.queue.append({
                    "ID": im.fp,
                    "size": im.size,
                    "img": im,
                    "queue": im.get_queue()
                })

        channelID = SQLFunctions.get_config("PlaceChannel", self.conn)
        if len(channelID) == 0:
            channelID = 819966095070330950
        else:
            channelID = channelID[0]
        channel = self.bot.get_channel(channelID)
        if channel is None:
            channel = self.bot.get_channel(402551175272202252)  # fallback test channel

        # keeps going through all lists
        while len(self.queue) > 0 and not self.pause_draws:
            drawing = self.queue[0]
            start = SQLFunctions.get_config(f"Start_{drawing['ID']}", self.conn)
            end = SQLFunctions.get_config(f"End_{drawing['ID']}", self.conn)
            if len(start) == 0:
                start = 0
            else:
                start = start[0]
            if len(end) == 0:
                end = drawing["img"].size
            else:
                end = end[0]
            done = await self.draw_pixels(drawing["ID"], channel, start, end)
            if done:
                self.remove_drawing(drawing["ID"])

    def remove_drawing(self, ID):
        # removes the drawing from the sql table
        SQLFunctions.delete_config(f"%{ID}", self.conn)
        # removes it from the queue and progress bar
        if ID in self.progress:
            self.progress.pop(ID)
            self.queue.pop(0)
        while ID in self.cancel_draws:
            self.cancel_draws.remove(ID)
        os.remove(f"{self.place_path}{ID}.npy")

    def get_all_queues(self, dir="./"):
        q = []
        for filename in os.listdir(dir):
            if filename.endswith(".npy"):
                img = im2q.PixPlace(filename.replace(".npy", ""), "q", setup=False)
                img.load_array(os.path.join(dir, filename))
                q.append(img)
        return q

    async def draw_pixels(self, ID, channel, start, end) -> bool:
        pixels_queue = self.progress[ID]["queue"][start:end]
        # draws the pixels
        while len(pixels_queue) > 0:
            if self.cancel_all or str(ID) in self.cancel_draws:
                await channel.send(f"Canceled Project {ID}.")
                return True
            if self.pause_draws:
                return False
            pix = pixels_queue[0]
            pX = pix[0]
            pY = pix[1]
            pHex = rgb2hex(pix[2], pix[3], pix[4])
            try:
                await channel.send(f".place setpixel {pX} {pY} {pHex} | PROJECT {ID}")
                self.progress[ID]["count"] += 1
                pixels_queue.pop(0)
                if self.progress[ID]["count"] % 10 == 0:
                    SQLFunctions.insert_or_update_config(f"Start_{ID}", self.progress[ID]["count"], self.conn)
            except Exception:
                await asyncio.sleep(5)
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
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

        if message.author.id == self.userToCopyTextFrom and message.channel.id != 813430350965375046 and is_valid_msg(message.content):
            if len(self.queue) > 50:
                return
            pil_img, self.last_line, self.last_char = self.draw_text(message.content, self.last_line, self.last_char)
            SQLFunctions.insert_or_update_config("Draw_Last_Line", self.last_line, self.conn)
            SQLFunctions.insert_or_update_config("Draw_Last_Char", self.last_char, self.conn)
            # id to stop specific draw
            ID = str(random.randint(1000, 10000))
            img = im2q.PixPlace(ID, ID, False, pil_img=pil_img)
            img.left_to_right()
            self.handle_image(img, 0, ID)

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
               f"Pixels to draw: {pix_total - pix_drawn}\n" \
               f"Pixels drawn: {pix_drawn}\n" \
               f"{loading_bar_draw(pix_drawn, pix_total)}  {round(100 * pix_drawn / pix_total, 2)}%\n" \
               f"Time Remaining: {round((pix_total - pix_drawn) * len(self.progress) / 60, 2)} mins\n" \
               f"`.place zoom {topX} {topY} {min(max(botX - topX, botY - topY), 250)}` to see the progress.\n"

    @commands.is_owner()
    @commands.group(aliases=["d"], usage="draw <command> <x1> <x2> <y1> <y2> <step> <color/channel> [delete_messages: y/n]",
                    invoke_without_command=True)
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
                    for d in self.queue:
                        self.remove_drawing(d["ID"])
                else:
                    self.cancel_draws.append(x1)
                    self.remove_drawing(x1)
            else:
                await ctx.send("Command not found. Right now only `cancel`, `image` and `square` exist.")

    def handle_image(self, img: im2q, drawn: int, ID: str):
        self.progress[ID] = {
            "count": drawn,
            "img": img,
            "queue": img.get_queue()
        }
        self.queue.append({
            "ID": ID,
            "size": img.size,
            "img": img,
            "queue": img.get_queue()
        })

        SQLFunctions.insert_or_update_config(f"Start_{ID}", 0, self.conn)
        SQLFunctions.insert_or_update_config(f"End_{ID}", img.size, self.conn)

        # saves the img as a numpy file so it can easily be reload when the bot restarts
        img.save_array(f"{self.place_path}{ID}")

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
        `r`: "Random" order
        `l`: Left to right draw order
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

        self.handle_image(img, drawn, ID)

        embed = discord.Embed(title="Started Drawing", description=self.draw_desc(ID))
        await ctx.send(embed=embed)

    @commands.is_owner()
    @draw.command(aliases=["t"], usage="text")
    async def text(self, ctx):
        """
        Reads in pixels from a setpixel txt file
        """
        if len(ctx.message.attachments) == 0:
            await ctx.send("No text file given")
            raise discord.ext.commands.errors.BadArgument
        async with aiohttp.ClientSession() as cs:
            async with cs.get(ctx.message.attachments[0].url) as r:
                setpixels_file = await r.text()

        self.cancel_all = False

        # id to stop specific draw
        ID = str(random.randint(1000, 10000))

        img = im2q.PixPlace(ID, ID, setup=False, setpixels=setpixels_file)

        self.handle_image(img, 0, ID)

        embed = discord.Embed(title="Started Drawing", description=self.draw_desc(ID))
        await ctx.send(embed=embed)

    @commands.is_owner()
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
    async def progress(self, ctx, ID=""):
        if "comp" not in ID and (ID == "" or ID not in self.progress):
            keys = ""
            rank = 1
            total_pix = 0
            for k in self.queue:
                time_to_start = total_pix // 60
                current_amount = self.progress[k["ID"]]["count"]
                img_total = k["img"].size
                percentage = round(current_amount * 100 / img_total, 2)
                total_pix += img_total - current_amount
                keys += f"`{rank}:` ID: {k['ID']}\n" \
                        f"---**Starting in:** {time_to_start}mins\n" \
                        f"---**Progress:** {percentage}%\n" \
                        f"---**Duration:** {img_total - current_amount} pixels | {(img_total - current_amount) // 60}mins\n" \
                        f"---**Finished in:** {total_pix // 60}mins\n"
                rank += 1
            if len(keys) > 2000:
                await ctx.send("Too many projects currently in work. Use `$d prog compact` to get a compact view.")
                return
            await ctx.send(f"Project IDs | Count:{len(self.progress)} | Paused: {self.pause_draws}\n{keys}")
            return
        if "comp" in ID.lower():  # compact view to send a lot of projects easier
            total_pix = 0
            id_list = []
            for k in self.queue:
                total_pix += k["img"].size
                id_list.append(k["ID"])
            id_msg = f"`n: {len(self.queue)}`\n" + ", ".join(id_list)
            if len(id_msg) > 2000:
                id_msg = id_msg[:2000] + "**[...]**"
            embed = discord.Embed(title="Compact Projects", description=id_msg)
            embed.add_field(name="Time", value=f"All projects finished in `{total_pix // 60}` mins")
            await ctx.send(embed=embed)
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
            async with ctx.typing():
                img = self.progress[ID]["img"]
                gif = await img.create_gif()
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
                    if color_to_check.replace("#", "") == rgb2hex(rp, gp, bp).replace("#", "") or color_to_check == "" and (r, g, b, a) != (
                            rp, gp, bp, ap):
                        count += 1
                        pixels[x, y] = (r, g, b, a)
        return im, count

    def draw_text(self, text, last_line, last_char) -> tuple[Image.Image, int, int]:
        img = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        text = " | " + text.replace("\n", " ")

        # splits the text into lines
        lines, last_char = self.write_lines(text, last_char)

        # draws the lines
        while len(lines) > 0:
            empty_lines = ["" for _ in range(last_line)]

            if len(lines) > self.LINE_HEIGHT - last_line:
                li = lines[:self.LINE_HEIGHT - last_line]
                lines = lines[self.LINE_HEIGHT - last_line:]
            else:
                li = lines
                lines = []

            last_line = (last_line + len(li)) % self.LINE_HEIGHT

            text = "\n".join(empty_lines + li)
            r = random.randrange  # for readability on the next line
            d.text((0, 0), text, fill=(r(256), r(256), r(256), 255), font=self.font)

        if last_char > 0:
            last_line -= 1
        return img, last_line, last_char

    def write_lines(self, text: str, last_char: int) -> tuple[list[str], int]:
        """Last char is the last character of the last line

        Args:
            text (str): The string which should be split into lines
            last_char (int): The last character of the last line

        Returns:
            (list[str], int): A list with all the lines and an int where the last character was placed.
        """
        lines = []
        while len(text) > 0:
            t = " " * last_char  # we add spaces to move the text to the right by enough
            chars_added = 0  # amount of characters added to the line

            # if the text is too long to add to the line, we cut it so it fits perfectly
            if len(text) > self.CHAR_WIDTH - last_char:
                t += text[:self.CHAR_WIDTH - last_char]
                chars_added = len(text[:self.CHAR_WIDTH - last_char])
                text = text[self.CHAR_WIDTH - last_char:]
            else:
                t += text
                chars_added = len(text)
                text = ""

            last_char = (last_char + chars_added) % self.CHAR_WIDTH
            lines.append(t)

        return lines, last_char


def setup(bot):
    bot.add_cog(Draw(bot))
