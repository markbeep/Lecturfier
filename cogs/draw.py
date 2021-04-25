import aiohttp
import discord
from discord.ext import commands, tasks
import random
import asyncio
import os
from helper import handySQL, image2queue as im2q
from PIL import Image
import PIL
import io
from discord.ext.commands.cooldowns import BucketType


def rgb2hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)


def loading_bar_draw(a, b):
    prog = int(10*a/b)
    return "<:green_box:764901465948684289>"*prog + (10-prog)*"<:grey_box:764901465592037388>"


def modifiers(img: im2q.PixPlace, mods: tuple) -> int:
    drawn = 0
    start = -1
    end = -1
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

    if start != -1 or end != -1:
        print("Modfiers", start, end)
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
        self.conn = handySQL.create_connection(self.db_path)

    def get_task(self):
        self.pause_draws = True
        return self.background_draw

    def get_connection(self):
        """
        Retreives the current database connection
        :return: Database Connection
        """

        if self.conn is None:
            self.conn = handySQL.create_connection(self.db_path)
        return self.conn

    @tasks.loop(seconds=5)
    async def background_draw(self):
        await self.bot.wait_until_ready()

        conn = self.get_connection()
        c = conn.cursor()

        # opens and readies all the files
        imgs = self.get_all_queues(self.place_path)
        for im in imgs:
            if im.fp not in self.progress:
                c.execute("SELECT ConfigValue FROM Config WHERE ConfigKey LIKE ?", (f"Start_{im.fp}",))
                start = c.fetchone()
                if start is None:
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

        c.execute("SELECT ConfigValue FROM Config WHERE ConfigKey LIKE 'PlaceChannel'")
        channelID = c.fetchone()
        if channelID is None:
            channelID = 819966095070330950
        else:
            channelID = channelID[0]
        channel = self.bot.get_channel(channelID)

        # keeps going through all lists
        while len(self.queue) > 0 and not self.pause_draws:
            drawing = self.queue[0]
            c.execute("SELECT ConfigValue FROM Config WHERE ConfigKey LIKE ?", (f"Start_{drawing['ID']}",))
            start = c.fetchone()
            c.execute("SELECT ConfigValue FROM Config WHERE ConfigKey LIKE ?", (f"End_{drawing['ID']}",))
            end = c.fetchone()
            if start is None:
                start = 0
            else:
                start = start[0]
            if end is None:
                end = drawing["img"].size
            else:
                end = end[0]

            done = await self.draw_pixels(drawing["ID"], channel, start, end)

            print(done)
            if done:
                self.remove_drawing(drawing["ID"])

    def remove_drawing(self, ID):
        conn = self.get_connection()
        # removes the drawing from the sql table
        conn.execute("DELETE FROM Config WHERE ConfigKey LIKE ?", (f"%{ID}",))
        conn.commit()
        # removes it from the queue and progress bar
        if ID in self.progress:
            self.progress.pop(ID)
            self.queue.pop(0)
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
        conn = self.get_connection()
        c = conn.cursor()
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
                    c.execute("UPDATE Config SET ConfigValue=? WHERE ConfigKey LIKE ?", (self.progress[ID]["count"], f"Start_{ID}"))
                    conn.commit()
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
                else:
                    self.cancel_draws.append(x1)
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

        conn = self.get_connection()
        conn.execute("INSERT INTO Config(ConfigKey, ConfigValue) VALUES (?, ?)", (f"Start_{ID}", 0))
        conn.execute("INSERT INTO Config(ConfigKey, ConfigValue) VALUES (?, ?)", (f"End_{ID}", img.size))
        conn.commit()

        # saves the img as a numpy file so it can easily be reload when the bot restarts
        img.save_array(f"{self.place_path}{ID}")

        embed = discord.Embed(title="Started Drawing", description=self.draw_desc(ID))
        await ctx.send(embed=embed)

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
            rank = 1
            total_pix = 0
            for k in self.queue:
                time_to_start = total_pix // 60
                current_amount = self.progress[k["ID"]]["count"]
                img_total = k["img"].size
                percentage = round(current_amount * 100 / img_total, 2)
                total_pix += img_total-current_amount
                keys += f"`{rank}:` ID: {k['ID']}\n" \
                        f"---**Starting in:** {time_to_start}mins\n" \
                        f"---**Progress:** {percentage}%\n" \
                        f"---**Duration:** {img_total-current_amount} pixels | {(img_total-current_amount)//60}mins\n" \
                        f"---**Finished in:** {total_pix // 60}mins\n"
                rank += 1
            await ctx.send(f"Project IDs | Count:{len(self.progress)} | Paused: {self.pause_draws}\n{keys}")
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


def setup(bot):
    bot.add_cog(Draw(bot))