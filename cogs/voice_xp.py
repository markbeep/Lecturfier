import json
import math
import discord
from discord.ext import commands
import random
import asyncio
from helper.log import log


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


# TODO: check for bugs
class VoiceXp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.counter = 0
        self.levels_filepath = "./data/levels.json"
        with open(self.levels_filepath) as f:
            self.levels = json.load(f)

        bot.loop.create_task(self.background_loop())

    @commands.Cog.listener()
    async def on_message(self, message):
        # add xp to user
        try:
            if str(message.guild.id) in self.levels and self.levels[str(message.guild.id)]["on"]:
                await self.add_xp(message.guild.id, message.author, 3, 5)
        except AttributeError:
            pass

    async def background_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await self.give_users_xp(9, 12)
            await asyncio.sleep(10)

            if self.counter == 5:
                self.counter = 0
                with open(self.levels_filepath, "w") as f:
                    json.dump(self.levels, f, indent=2)
                log("SAVED LEVELS", "XP")
            self.counter += 1

    async def give_users_xp(self, amount_min, amount_max):
        """
        Function that gives each member in the voice channel XP that is not muted or afk
        :param amount_min: minimum random xp to give
        :param amount_max: maximum random xp to give
        :return: None
        """
        for guild_id in self.levels.keys():
            # Goes through every guild in the levels.json file
            if not self.levels[str(guild_id)]["on"]:
                log(f"{guild_id} does not have levels activated", "XP")
                continue
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                log(f"{guild_id} does not exist anymore. Skipping...", "XP")
                continue

            log(f"Checking voice channels of guild: {guild_id} | # of vc: {len(guild.voice_channels)}", "XP")
            for v_ch in guild.voice_channels:
                # Goes through every voice channel on that specific server
                for u in v_ch.members:
                    # Goes through every member in that voice channel
                    if u.voice.afk or u.bot or u.voice.self_mute or u.voice.self_deaf:
                        log(f"User is afk or muted: {u.name}", "XP")
                        pass
                    else:
                        await self.add_xp(guild_id, u, amount_min, amount_max)

        await asyncio.sleep(10)

    async def add_xp(self, guild_id, user, amount_min, amount_max):
        try:
            self.levels[str(guild_id)][str(user.id)] += random.randrange(amount_min, amount_max)
        except KeyError:
            # If there is a KeyError, it means the user doesn't exist yet and it creates a new entry
            log(f"Creating new entry for {user.name} and adding xp", "XP")
            self.levels[str(guild_id)][str(user.id)] = random.randrange(amount_min, amount_max)

    @commands.command()
    async def rank(self, ctx, user=None):
        if str(ctx.message.guild.id) in self.levels and not self.levels[str(ctx.message.guild.id)]["on"]:
            await ctx.send(f"{ctx.message.author.mention}, `levels` are turned off on this server! *(If you just turned them on, wait 10 seconds)*")
            return
        if user is None:
            u_id = str(ctx.message.author.id)
        else:
            u_id = user.replace("<@", "").replace(">", "").replace("!", "")
        try:
            level = levefier(self.levels[str(ctx.message.guild.id)][u_id])
            member = ctx.message.guild.get_member(int(u_id))
            pre_level = round(self.levels[str(ctx.message.guild.id)][u_id] - xpfier(level))
            aft_level = round(xpfier(level + 1) - xpfier(level))
            if user is None:
                await ctx.send(f"{ctx.message.author.mention}, your current level is `{level}` with `{pre_level}` / `{aft_level}` xp.")
            else:
                await ctx.send(f"{member.display_name}'s level is `{level}` with `{pre_level}` / `{aft_level}` xp.")
        except KeyError:
            await ctx.send(f"{ctx.message.author.mention}, invalid mention or user ID. Can't display rank for that user.")

    @commands.command(aliases=["lb", "ranks"])
    async def leaderboard(self, ctx):
        async with ctx.typing():
            try:
                """
                Creates a list with sorted dicts
                """
                temp = {}
                for user in self.levels[str(ctx.message.guild.id)].keys():
                    if user != "on" and user != "do_not_track":
                        temp[user] = self.levels[str(ctx.message.guild.id)][user]
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
                        # 60 xp
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
        if state is None:
            if str(ctx.message.guild.id) in self.levels and self.levels[str(ctx.message.guild.id)]["on"]:
                await ctx.send("Levels are `ON` on this server!")
            else:
                await ctx.send("Levels are `OFF` on this server!")
            return
        if state.lower() == "on":
            if str(ctx.message.guild.id) in self.levels:
                self.levels[str(ctx.message.guild.id)]["on"] = True
            else:
                self.levels[str(ctx.message.guild.id)] = {"on": True}
            await ctx.send("Levels are now `ON` on this server!")
            log(f"Levels are now ON on guild: {ctx.message.guild.id}", "XP")
        elif state.lower() == "off":
            if str(ctx.message.guild.id) in self.levels:
                self.levels[str(ctx.message.guild.id)]["on"] = False
            else:
                self.levels[str(ctx.message.guild.id)] = {"on": False}
            await ctx.send("Levels are now `OFF` on this server!")
            log(f"Levels are now OFF on guild: {ctx.message.guild.id}", "XP")
        else:
            await ctx.send("Please state whether you want to turn levels `ON` or `OFF`.")
            return
        with open(self.levels_filepath, "w") as f:
            json.dump(self.levels, f, indent=2)


def setup(bot):
    bot.add_cog(VoiceXp(bot))
