import json
import math
import discord
from discord.ext import commands
import random
import asyncio


def xpfier(n):
    return round((n/0.0002725)**1.15)


def levefier(xp):
    return math.floor(xp**(1/1.15) * 0.0002725)


def number_split(num):
    number = ""
    i = 0
    for n in list(str(num))[::-1]:
        if i % 3 == 0 and i != 0:
            number = "'" + number
        number = str(n) + number
        i += 1
    return number

# TODO: Change xp background task into multiple functions
# TODO: create a new level graph function
# TODO: make xp be checked more frequently, to have it more accurately time
# TODO: check for bugs
class VoiceXp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.levels_filepath = "./data/levels.json"
        with open(self.levels_filepath) as f:
            self.ignore_channels = json.load(f)

        bot.loop.create_task(self.background_loop())

    async def background_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await self.check_users()

    async def check_users(self):
            print("Starting background loop")
            with open(self.levels_filepath, "r") as f:
                det = json.load(f)
            for guild_id in det.keys():
                if not det[str(guild_id)]["on"]:
                    continue
                guild = self.bot.get_guild(int(guild_id))
                if guild is None:
                    continue

                for v_ch in guild.voice_channels:
                    for u in v_ch.members:
                        print(f"-Checking user: {u.name}")
                        if u.voice.afk or u.bot or u.voice.self_mute or u.voice.self_deaf:
                            pass
                        else:
                            try:
                                pre_level = levefier(det[str(guild_id)][str(u.id)])
                                det[str(guild_id)][str(u.id)] += random.randrange(180, 220)
                                print(f"Giving {u.name} xp")
                                aft_level = levefier(det[str(guild_id)][str(u.id)])

                            except KeyError:
                                print(f"Giving {u.name} xp")
                                det[str(guild_id)][str(u.id)] = random.randrange(180, 220)

            with open(self.levels_filepath, "w") as f:
                json.dump(det, f, indent=2)

            await asyncio.sleep(120)

    @commands.command()
    async def rank(self, ctx):
        with open(self.levels_filepath, "r") as f:
            levels = json.load(f)
        try:
            if str(ctx.message.guild.id) in levels and levels[str(ctx.message.guild.id)]["on"]:
                level = levefier(levels[str(ctx.message.guild.id)][str(ctx.message.author.id)])
                await ctx.send(
                    f"{ctx.message.author.mention}, your current level is `{level}` with `{round(levels[str(ctx.message.guild.id)][str(ctx.message.author.id)] - xpfier(level))}` / `{round(xpfier(level + 1) - xpfier(level))}` xp")
            else:
                raise KeyError
        except KeyError:
            await ctx.send(
                f"{ctx.message.author.mention}, `levels` are turned off on this server! *(If you just turned them on, wait a minute)*")

    @commands.command(aliases=["lb", "ranks"])
    async def leaderboard(self, ctx):
        async with ctx.typing():
            try:
                with open(self.levels_filepath, "r") as f:
                    det = json.load(f)

                """
                Creates a list with sorted dicts
                """
                temp = {}
                for user in det[str(ctx.message.guild.id)].keys():
                    if user != "on" and user != "do_not_track":
                        temp[user] = det[str(ctx.message.guild.id)][user]
                temp = sorted(temp.items(), key=lambda v: v[1])

                """
                Creates the message content
                """
                i = 1
                cont = ""
                for profile in temp[::-1]:
                    member = ctx.message.guild.get_member(int(profile[0]))
                    if member is None:
                        pass
                    else:
                        if i == 1:
                            cont += "<:gold:413030003639582731>"
                        elif i == 2:
                            cont += "<:silver:413030018881552384>"
                        elif i == 3:
                            cont += "<:bronze:413030030076149776>"
                        else:
                            cont += "<:invisible:413030446327267328>"
                        member = member.display_name
                        cont += f"**{i}.** __{member}__: **Level {levefier(profile[1])}** (*{number_split(profile[1])} xp | {round(profile[1] / 6000)} hours*)\n\n"
                        i += 1
                        if i >= 11:
                            break
                embed = discord.Embed(
                    title=f"Top Levels of: **{ctx.message.guild.name}** <a:upvoteparrot:412336233105326091>",
                    description=cont, color=0x00FF00)
            except KeyError:
                embed = discord.Embed(title=f"Error", description="This server has no levels yet", color=0xFF0000)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def levels(self, ctx, state=None):
        with open(self.levels_filepath, "r") as f:
            levels = json.load(f)
        if state is None:
            if str(ctx.message.guild.id) in levels and levels[str(ctx.message.guild.id)]["on"]:
                await ctx.send("Levels are `ON` on this server!")
            else:
                await ctx.send("Levels are `OFF` on this server!")
            return
        if state.lower() == "on":
            if str(ctx.message.guild.id) in levels:
                levels[str(ctx.message.guild.id)]["on"] = True
            else:
                levels[str(ctx.message.guild.id)] = {"on": True}
            await ctx.send("Levels are now `ON` on this server!")
        elif state.lower() == "off":
            if str(ctx.message.guild.id) in levels:
                levels[str(ctx.message.guild.id)]["on"] = False
            else:
                levels[str(ctx.message.guild.id)] = {"on": False}
            await ctx.send("Levels are now `OFF` on this server!")
        else:
            await ctx.send("Please state whether you want to turn levels `ON` or `OFF`.")
        with open(self.levels_filepath, "w") as f:
            json.dump(levels, f, indent=2)

def setup(bot):
    bot.add_cog(VoiceXp(bot))
