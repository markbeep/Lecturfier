import asyncio
import math
import random
import time
from sqlite3 import Error
import discord
from discord.ext import commands
from helper import handySQL


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

        self.db_path = "./data/discord.db"
        self.conn = handySQL.create_connection(self.db_path)
        self.time_heartbeat = 0

        self.task = self.bot.loop.create_task(self.background_save_levels())

    def heartbeat(self):
        return self.time_heartbeat

    def get_task(self):
        return self.task

    def get_connection(self):
        """
        Retreives the current database connection
        :return: Database Connection
        """
        if self.conn is None:
            self.conn = handySQL.create_connection(self.db_path)
        return self.conn

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        # add xp to user
        await self.add_xp(message.guild, message.author, 3, 5)

    async def background_save_levels(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.time_heartbeat = time.time()
            await self.give_users_xp(9, 12)
            await asyncio.sleep(10)

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
                        await self.add_xp(guild, u, amount_min, amount_max)

    async def add_xp(self, guild, user, amount_min, amount_max):
        """
        Adds xp to a specific user in that guild
        :param guild:
        :param user:
        :param amount_min:
        :param amount_max:
        :return:
        """
        conn = self.get_connection()
        if conn is not None:
            rand_amount = random.randrange(1, 10)

            # Creates new voice level entry
            handySQL.create_voice_level_entry(conn, user, guild)
            if guild is None:
                guild_id = 0
            else:
                guild_id = guild.id

            # Retreives the UniqueMemberID
            uniqueMemberID = handySQL.get_uniqueMemberID(conn, user.id, guild_id)

            sql = f"""UPDATE VoiceLevels SET ExperienceAmount = ExperienceAmount + {rand_amount} WHERE UniqueMemberID=?"""
            c = conn.cursor()
            c.execute(sql, (uniqueMemberID,))
            conn.commit()
        else:
            print("ERROR! conn was a None type")

    @commands.command(usage="rank [user]")
    async def rank(self, ctx, user=None):
        """
        This command sends the users voice XP rank. If no user is defined, the command user's rank is sent.
        """
        if user is None:
            u_id = str(ctx.message.author.id)
        else:
            member = ctx.message.guild.get_member_named(user)
            if member is None:
                u_id = user.replace("<@", "").replace(">", "").replace("!", "")
            else:
                u_id = member.id

        # Query User experience
        conn = self.get_connection()
        try:
            c = conn.cursor()
            if ctx.message.guild is None:
                guild_id = 0
            else:
                guild_id = ctx.message.guild.id
            sql = """SELECT ExperienceAmount FROM VoiceLevels INNER JOIN DiscordMembers DM on DM.UniqueMemberID=VoiceLevels.UniqueMemberID
                            WHERE DM.DiscordUserID=? AND DM.DiscordGuildID=?"""
            c.execute(sql, (u_id, guild_id))
            line = c.fetchone()
            if line is None:
                await ctx.send(f"{ctx.message.author.mention}, invalid mention or user ID. Can't display rank for that user.")
                raise ValueError
            try:
                experience = int(line[0])
            except ValueError as e:
                await ctx.send(f"There was a lil' problem:\n`{e}`")
                raise ValueError
        except Error as e:
            await ctx.send(f"There was a lil' problem:\n`{e}`")
            raise ValueError

        level = levefier(experience)
        pre_level = round(experience - xpfier(level))
        aft_level = round(xpfier(level + 1) - xpfier(level))
        embed = discord.Embed(title="Voice Level", description=f"User: <@!{u_id}>\n"
                                                               f"Current Level: `{level}`\n"
                                                               f"Level XP: `{pre_level}` / `{aft_level}`\n"
                                                               f"Total XP: `{number_split(experience)}`\n"
                                                               f"Estimated Hours: `{round(experience / 3600, 1)}`", color=0x00FF00)
        await ctx.send(embed=embed)

    @commands.command(aliases=["lb", "ranks"], usage="leaderboard")
    async def leaderboard(self, ctx):
        """
        This command sends the top 10 users with the most voice XP on this server.
        """
        conn = self.get_connection()
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
                            cont += "<:gold:413030003639582731>"
                        elif i == 2:
                            cont += "<:silver:413030018881552384>"
                        elif i == 3:
                            cont += "<:bronze:413030030076149776>"
                        else:
                            cont += "<:invisible:413030446327267328>"

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
                    title=f"Top Levels of: **{guild_name}** <a:upvoteparrot:412336233105326091>",
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
