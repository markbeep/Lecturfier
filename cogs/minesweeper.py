import discord
from discord.ext import commands
import random
import time
import asyncio

class Minesweeper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sending = False

    async def bomb_placer(self, size:int, mines:int):
        mine_field = []
        if size < 2:
            size = 2
        if mines < 1:
            mines = 1
        if mines > size**2 - 1:
            mines = size**2 - 1

        for i in range(size):
            xx_mine_field = []
            for j in range(size):
                xx_mine_field.append(0)
            mine_field.append(xx_mine_field)

        i = 1
        rand_counter = 0
        while i <= mines:
            random.seed(time.time() + rand_counter)
            row_index = random.randrange(size)
            random.seed(time.time() + 1 + rand_counter)
            column_index = random.randrange(size)
            rand_counter += 1
            if mine_field[row_index][column_index] == "x":
                continue
            else:
                mine_field[row_index][column_index] = "x"
                i += 1
        return [mine_field, size, mines]

    async def bomb_counter(self, mine_field):
        for y in range(len(mine_field)):
            for x in range(len(mine_field)):
                if mine_field[y][x] == 0:
                    bomb_count = 0
                    for i in range(-1, 2):
                        for j in range(-1, 2):
                            try:
                                if y - i < 0 or x - j < 0:
                                    pass
                                elif mine_field[y-i][x-j] == "x":
                                    bomb_count += 1
                            except IndexError:
                                continue
                    mine_field[y][x] = bomb_count

        return mine_field

    async def minesweeper_text_format(self, text):
        text = text.replace("x", "🟥")
        text = text.replace("0", ":zero:")
        text = text.replace("1", ":one:")
        text = text.replace("2", ":two:")
        text = text.replace("3", ":three:")
        text = text.replace("4", ":four:")
        text = text.replace("5", ":five:")
        text = text.replace("6", ":six:")
        text = text.replace("7", ":seven:")
        text = text.replace("8", ":eight:")
        text = text.replace("9", ":nine:")
        return text

    async def uncover_field(self, field):
        rand_counter = 0
        while True:
            random.seed(time.time() + rand_counter)
            row_index = random.randrange(len(field))
            random.seed(time.time() + 1 + rand_counter)
            column_index = random.randrange(len(field))
            rand_counter += 1
            if field[row_index][column_index] != "x":
                field[row_index][column_index] = f"{field[row_index][column_index]}f"
                break
        return field

    @commands.command(aliases=["ms"], usage="minesweeper [size] [amount of mines]")
    async def minesweeper(self, ctx, size="10", mines="10"):
        """
        Sends a minefield from the nice nostalgic minesweeper game in Discord-style. Each box is a spoiler that contains \
        either a number or a bomb. If you want to retry a minefield, you need to go out and into a channel to hide the \
        spoilers again.

        The maximum size of a minefield is 20 x 20 squares. Any more and discord completely messes it up.

        You can also use one of the three presets to create a field with pre-made rules using either "beginner", \
        "intermediate" or "expert" as the size keyword.
        """
        if self.sending:
            await asyncio.sleep(1)
            await ctx.send("❗❗ Already sending a mine field. Hold on ❗❗", delete_after=7)
            await ctx.message.delete()
            raise discord.ext.commands.errors.BadArgument

        self.sending = True
        try:
            size = int(size)
            mines = int(mines)
            if size > 20:
                await ctx.send("Too big of a mine field to send on discord. Keep it under 20.", delete_after=7)
                await ctx.message.delete()
                self.sending = False
                raise discord.ext.commands.errors.BadArgument

        except ValueError:
            try:
                if size.lower() == "beginner":
                    size = random.randrange(8, 11)
                    mines = 10
                elif size.lower() == "intermediate":
                    size = random.randrange(13, 17)
                    mines = 40
                elif size.lower() == "expert":
                    size = random.randrange(21, 22)
                    mines = 99
                else:
                    raise ValueError
            except (ValueError, AttributeError):
                await ctx.send("Wrong input. Use `$minesweeper <size> <mines>`", delete_after=7)
                await ctx.message.delete()
                self.sending = False
                raise discord.ext.commands.errors.BadArgument
        placed_bombs = await self.bomb_placer(size=int(size), mines=int(mines))
        mine_field = placed_bombs[0]
        corrected_size = placed_bombs[1]
        corrected_mines = placed_bombs[2]

        mine_field = await self.bomb_counter(mine_field)
        final_message = f"__Size: {corrected_size} | Mines: {corrected_mines}__"

        mine_field = await self.uncover_field(mine_field)
        split_messages = []
        for row in mine_field:
            row_string = ""
            for i in row:
                if "f" in str(i):
                    row_string += i.replace('f', '')
                else:
                    row_string += f"||{i}||"
            if len(await self.minesweeper_text_format(final_message) + await self.minesweeper_text_format(row_string)) > 850:
                msg = await self.minesweeper_text_format(final_message)
                await ctx.send(msg)
                final_message = row_string
            else:
                final_message += "\n" + row_string

        try:
            final_message = await self.minesweeper_text_format(final_message)
            self.sending = False
            if len(final_message) <= 1:
                return
            await ctx.send(final_message)
        except discord.errors.HTTPException:
            await ctx.send("Too big of a mine field to send on discord.")
            raise discord.ext.commands.errors.BadArgument


def setup(bot):
    bot.add_cog(Minesweeper(bot))