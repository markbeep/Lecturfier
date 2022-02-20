import math
import random
from sqlite3 import Error

import discord
from discord.ext import commands, tasks
from discord.ext.commands.cooldowns import BucketType

from helper.sql import SQLFunctions


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


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = SQLFunctions.connect()
        self.background_save_levels.start()

    def heartbeat(self):
        return self.background_save_levels.is_running()

    def get_task(self):
        return self.background_save_levels

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return
        # add xp to user
        await self.add_xp(message.author, 3, 5)

    @tasks.loop(seconds=10)
    async def background_save_levels(self):
        await self.bot.wait_until_ready()
        await self.give_users_xp(9, 12)

    async def give_users_xp(self, amount_min, amount_max):
        """
        Function that gives each member in the voice channel XP that is not muted or afk
        :param amount_min: minimum random xp to give
        :param amount_max: maximum random xp to give
        :return: None
        """
        for guild in self.bot.guilds:
            # Goes through every guild the bot is on
            for v_ch in guild.voice_channels:
                # Goes through every voice channel on that specific server
                for u in v_ch.members:
                    # Goes through every member in that voice channel
                    # If the user is afk, a bot or muted
                    if not (u.voice.afk or u.bot or u.voice.self_mute or u.voice.self_deaf or u.voice.mute):
                        await self.add_xp(u, amount_min, amount_max)

    async def add_xp(self, member: discord.Member, amount_min, amount_max):
        """
        Adds xp to a specific user in that guild
        :param member:
        :param amount_min:
        :param amount_max:
        :return:
        """
        rand_amount = random.randrange(amount_min, amount_max)

        SQLFunctions.insert_or_update_voice_level(
            member, rand_amount, self.conn)

    @commands.cooldown(4, 10, BucketType.user)
    @commands.guild_only()
    @commands.command(usage="rank [user]")
    async def rank(self, ctx, user=None):
        """
        This command sends the users voice XP rank. If no user is defined, the command user's rank is sent.
        """
        if user is None:
            member = ctx.message.author
        else:
            user_id = user.replace(
                "<@", "").replace(">", "").replace("!", "")
            member = None
            if user_id.isnumeric():
                member = ctx.message.guild.get_member(int(user_id))

        if member is None:
            await ctx.send(f"{ctx.message.author.mention}, invalid mention or user ID. Can't display rank for that user.")
            raise ValueError

        # Query User experience
        voice_level = SQLFunctions.get_voice_level(member, self.conn)

        level = levefier(voice_level.experience)
        pre_level = round(voice_level.experience - xpfier(level))
        aft_level = round(xpfier(level + 1) - xpfier(level))
        embed = discord.Embed(title="Voice Level", description=f"User: <@!{voice_level.member.DiscordUserID}>\n"
                                                               f"Current Level: `{level}`\n"
                                                               f"Level XP: `{pre_level}` / `{aft_level}`\n"
                                                               f"Total XP: `{number_split(voice_level.experience)}`\n"
                                                               f"Estimated Hours: `{round(voice_level.experience / 3600, 1)}`", color=0x00FF00)
        await ctx.send(embed=embed)

    @commands.cooldown(2, 10, BucketType.user)
    @commands.command(aliases=["lb", "ranks"], usage="leaderboard")
    async def leaderboard(self, ctx):
        """
        This command sends the top 10 users with the most voice XP on this server.
        """
        conn = self.conn
        if conn is not None:
            c = conn.cursor()
            try:
                async with ctx.typing():
                    if ctx.message.guild is None:
                        guild_id = 0
                    else:
                        guild_id = ctx.message.guild.id
                    sql = """SELECT DiscordUserID, ExperienceAmount
                                    FROM VoiceLevels
                                    INNER JOIN DiscordMembers ON VoiceLevels.UniqueMemberID=DiscordMembers.UniqueMemberID
                                    WHERE DiscordGuildID=?
                                    ORDER BY ExperienceAmount DESC"""
                    c.execute(sql, (guild_id,))
                    rows = c.fetchall()

                    # Creates the message content
                    i = 1
                    cont = ""
                    for user in rows:
                        if i == 1:
                            cont += "<:gold:944970589158920222>"
                        elif i == 2:
                            cont += "<:silver:944970589133766717>"
                        elif i == 3:
                            cont += "<:bronze:944970589481869352>"
                        else:
                            cont += "<:invisible:944970589196652564>"

                        # 1 xp / second
                        cont += f"**{i}.** <@!{user[0]}> | **Level {levefier(user[1])}** (*{number_split(user[1])} xp | {round(user[1] / 3600, 1)} hours*)\n\n"
                        i += 1
                        if i >= 11:
                            break
                try:
                    guild_name = ctx.message.guild.name
                except AttributeError:
                    guild_name = "DM Channel"
                embed = discord.Embed(
                    title=f"Top Levels of: **{guild_name}** <a:partyparrot:944970381951897650>",
                    description=cont, color=0x00FF00)
                await ctx.send(embed=embed)
            except Error as e:
                await ctx.send(f"There was a lil' problem:\n`{e}`")
                raise ValueError
        else:
            await ctx.send("There was a lil' problem. Couldn't connect to the DB")
            raise ValueError


def setup(bot):
    bot.add_cog(Voice(bot))
