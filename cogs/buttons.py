import discord
from discord.ext import commands
from discord_components import *
import time
import asyncio
import tabulate


class Buttons(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["calc"], usage="calculator")
    async def calculator(self, ctx):
        c = Calculator(self.bot, ctx, 180)
        await c.handle_calculator()

    @commands.command()
    async def select(self, ctx, *options):
        components = []
        selects = []
        count = {}
        total = 0
        if len(options) > 100:
            await ctx.reply("Max of 100 options allowed")
            raise discord.ext.commands.BadArgument
        elif len(options) == 0:
            await ctx.reply("Not enough options given.")
            raise discord.ext.commands.BadArgument

        amount_added = 0
        for opt in options:
            if opt in count.keys():
                continue
            opt = opt.replace("@", "").replace("&", "")
            if len(opt) == 0:
                continue
            selects.append(SelectOption(label=opt, value=opt))
            count[opt] = 0
            amount_added += 1
            if amount_added == 25:
                components.append(Select(placeholder="Select an option", options=selects))
                selects = []
                amount_added = 0
        if amount_added > 0:
            components.append(Select(placeholder="Select an option", options=selects))

        components.append(Button(label=f"Voted: {total}", style=ButtonStyle.random_color(), disabled=True))

        def create_vote(c: dict):
            return f"```\n{tabulate.tabulate(c.items(), tablefmt='psql')}```"

        msg = await ctx.reply(
            f"**Select one of the options below**\n{create_vote(count)}",
            components=components
        )

        while True:
            try:
                res: Interaction = await self.bot.wait_for("select_option", check=None, timeout=30)
                if res is None or res.component is None:
                    continue
                name = res.component[0].label
                count[name] += 1
                total += 1
                await res.respond(type=4, content=f"You selected {name}")
                components[len(components)-1] = Button(label=f"Voted: {total}", style=ButtonStyle.random_color(), disabled=True)
                await msg.edit(
                    f"**Select one of the options below**\n{create_vote(count)}",
                    components=components
                )
            except asyncio.TimeoutError:
                for i in range(len(components)-1):
                    components[i] = Select(placeholder="Select an option", options=[SelectOption(label="no", value="no")], disabled=True)
                await msg.edit(
                    f"**Selection menu closed**\n{create_vote(count)}",
                    components=components
                )
                break


def setup(bot):
    bot.add_cog(Buttons(bot))


class Calculator:
    def __init__(self, bot, ctx, seconds=60):
        self.equation = ""
        self.previous_answer = 0
        self.operator = ""
        self.bot = bot
        self.ctx = ctx
        self.time = time.time()
        self.seconds = seconds
        self.message = None
        self.open_parenth_count = 0

    async def handle_calculator(self):
        self.message = await self.send_initial_message()
        while time.time() < self.time + self.seconds:
            res = await self.bot.wait_for("button_click")
            if res.message is not None and type(res.component) != type(list) and res.message.id == self.message.id:
                if res.user.id == self.ctx.message.author.id:
                    label = res.component.label
                    if label in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "x", "/", "+", "-", "^"]:
                        if self.equation == "N/A":
                            self.equation = label
                        else:
                            self.equation = f"{self.equation}{label}"
                    elif label == "DEL":
                        if self.equation == "N/A" or len(self.equation) <= 1:
                            self.equation = ""
                        elif len(self.equation) >= 3 and self.equation[-3:] == "ANS":
                            # Removes ANS if its the last thing
                            self.equation = self.equation[:-3]
                        else:
                            self.equation = self.equation[:-1]
                    elif label in ["(", ")"]:
                        self.equation = f"{self.equation}{label}"
                        if label == "(":
                            self.open_parenth_count += 1
                        else:
                            self.open_parenth_count -= 1
                    elif label == "ANS":
                        self.equation = f"{self.equation}{label}"
                    elif label == "=":
                        try:
                            self.equation = self.equation.replace("x", "*").replace("ANS", str(self.previous_answer)).replace("^", "**")
                            result = eval(self.equation)
                            self.equation = str(result)
                            self.previous_answer = result
                        except (ZeroDivisionError, SyntaxError):
                            self.equation = "N/A"
                    elif label == "AC":
                        self.equation = ""
                    elif label == "OFF":
                        break
                    elif label == ".":
                        self.equation = f"{self.equation}{label}"
                    await self.update_message()
                    try:
                        await res.respond(type=InteractionType.UpdateMessage, components=self.get_components())
                    except discord.errors.NotFound:
                        continue
                else:
                    await res.respond(type=InteractionType.ChannelMessageWithSource, content="The calculator wasn't called by you.")
        try:
            await self.ctx.message.delete()
        except discord.errors.NotFound:
            pass
        await self.message.delete()

    async def update_message(self):
        await self.message.edit(embed=self.create_embed())

    def get_components(self) -> list:
        components = [
            [
                Button(style=ButtonStyle.grey, label="7"),
                Button(style=ButtonStyle.grey, label="8"),
                Button(style=ButtonStyle.grey, label="9"),
                Button(style=ButtonStyle.grey, label="DEL"),
                Button(style=ButtonStyle.grey, label="AC")
            ],
            [
                Button(style=ButtonStyle.grey, label="4"),
                Button(style=ButtonStyle.grey, label="5"),
                Button(style=ButtonStyle.grey, label="6"),
                Button(style=ButtonStyle.grey, label="x"),
                Button(style=ButtonStyle.grey, label="/")
            ],
            [
                Button(style=ButtonStyle.grey, label="1"),
                Button(style=ButtonStyle.grey, label="2"),
                Button(style=ButtonStyle.grey, label="3"),
                Button(style=ButtonStyle.grey, label="+"),
                Button(style=ButtonStyle.grey, label="-")
            ],
            [
                Button(style=ButtonStyle.grey, label="0"),
                Button(style=ButtonStyle.grey, label="."),
                Button(style=ButtonStyle.grey, label="("),
                Button(style=ButtonStyle.grey, label=")"),
                Button(style=ButtonStyle.grey, label="=")
            ],
            [
                Button(style=ButtonStyle.grey, label="ANS"),
                Button(style=ButtonStyle.red, label="OFF")
            ]
        ]
        # checks if the operators can be used
        if len(self.equation) == 0 or self.equation[-1] in ["x", "/", "(", ".", "+", "-", "^"]:
            components[1][3:] = [
                Button(style=ButtonStyle.grey, label="x", disabled=True),
                Button(style=ButtonStyle.grey, label="/", disabled=True)
            ]
            components[3][1] = Button(style=ButtonStyle.grey, label=".", disabled=True)
        # when to allow + -
        if len(self.equation) > 0 and self.equation[-1] in ["x", "/", "(", ".", "^"]:
            components[2][3:] = [
                Button(style=ButtonStyle.grey, label="+", disabled=True),
                Button(style=ButtonStyle.grey, label="-", disabled=True)
            ]
        # when to allow ANS and opening bracket
        if len(self.equation) > 0 and self.equation[-1] in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "S"]:
            components[4][0] = Button(style=ButtonStyle.grey, label="ANS", disabled=True)
            components[3][2] = Button(style=ButtonStyle.grey, label="(", disabled=True)

        # makes the closing parentheses red if a closing bracket is needed
        if self.open_parenth_count > 0:
            components[3][3] = Button(style=ButtonStyle.red, label=")")
        # when to disable the closing bracket
        if self.open_parenth_count == 0 or (len(self.equation) > 0 and self.equation[-1] in ["(", "x", "/", ".", "+", "-", "^"]):
            components[3][3] = Button(style=ButtonStyle.grey, label=")", disabled=True)

        # when to disable numbers
        if len(self.equation) > 0 and self.equation[-1] in ["S", ")"]:
            components[0][:3] = [
                Button(style=ButtonStyle.grey, label="7", disabled=True),
                Button(style=ButtonStyle.grey, label="8", disabled=True),
                Button(style=ButtonStyle.grey, label="9", disabled=True),
            ]
            components[1][:3] = [
                Button(style=ButtonStyle.grey, label="4", disabled=True),
                Button(style=ButtonStyle.grey, label="5", disabled=True),
                Button(style=ButtonStyle.grey, label="6", disabled=True),
            ]
            components[2][:3] = [
                Button(style=ButtonStyle.grey, label="1", disabled=True),
                Button(style=ButtonStyle.grey, label="2", disabled=True),
                Button(style=ButtonStyle.grey, label="3", disabled=True),
            ]

        # check if its possible to even compute the equation
        try:
            self.equation.replace("x", "*").replace("ANS", str(self.previous_answer)).replace("^", "**")
        except (SyntaxError, ZeroDivisionError):
            components[3][4] = Button(style=ButtonStyle.red, label="=", disabled=True)

        return components

    def create_embed(self):
        embed = discord.Embed()
        embed.set_author(name=str(self.ctx.message.author), icon_url=self.ctx.message.author.avatar_url)
        field_value = self.equation
        if len(field_value) < 42:
            field_value += " "*(42 - len(field_value))
        if len(field_value) > 1000:
            field_value = "N/A"
        embed.add_field(name="Calculator", value=f"```\n{field_value}\n```")
        return embed

    async def send_initial_message(self) -> discord.Message:
        return await self.ctx.send(embed=self.create_embed(), components=self.get_components())