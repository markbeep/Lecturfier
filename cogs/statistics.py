import discord
from discord.ext import commands
from discord.ext.commands import CommandOnCooldown
from datetime import datetime
import time
import asyncio
from emoji import demojize
import json
from helper.git_backup import gitpush
from helper import handySQL
from discord.ext.commands.cooldowns import BucketType


def is_in(word, list_to_check):
    for v in list_to_check:
        if word.lower() == v.lower():
            return v
    return False


class Statistics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.script_start = 0
        self.waiting = False
        self.time_counter = 0  # So statistics dont get saved every few seconds, and instead only every 2 mins
        self.bot_changed_to_yesterday = {}
        self.time_heartbeat = 0
        self.db_path = "./data/discord.db"
        self.conn = handySQL.create_connection(self.db_path)
        self.task = self.bot.loop.create_task(self.background_git_backup())

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

    async def background_git_backup(self):
        sent_file = False
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.time_heartbeat = time.time()

            # Backs up all files every 2 hours
            if not sent_file and datetime.now().hour % 2 == 0:
                # Backs the data files up to github
                with open("./data/settings.json", "r") as f:
                    settings = json.load(f)
                if settings["upload to git"]:
                    sent_file = True
                    output = gitpush("./data")
                    user = self.bot.get_user(self.bot.owner_id)
                    await user.send("Updated GIT\n"
                                    f"Commit: `{output[0]}`\n"
                                    f"Push: `{output[1]}`")
            if datetime.now().hour % 2 != 0:
                sent_file = False

            await asyncio.sleep(10)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if "is not found" in str(error):
            return
        if ctx.message.author.bot:
            return
        else:
            if isinstance(error, CommandOnCooldown):
                embed = discord.Embed(description=str(error), color=0x8F0000)
                await ctx.send(embed=embed, delete_after=3)
            try:
                await ctx.message.add_reaction("<:ERROR:792154973559455774>")
            except discord.errors.NotFound:
                pass
            print(f"ERROR: {str(error)}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.message.author.bot:
            return
        else:
            try:
                await ctx.message.add_reaction("<:checkmark:776717335242211329>")
            except discord.errors.NotFound:
                pass

    @commands.Cog.listener()
    async def on_ready(self):
        self.script_start = time.time()

    @commands.Cog.listener()
    async def on_message(self, message):
        # Creates a connection with the DB
        conn = self.get_connection()
        try:
            # This is in case a message is a direct message
            guild_obj = message.guild
        except AttributeError:
            guild_obj = None

        SUBJECT_ID = self.get_current_subject_id()
        # Makes it better to work with the message
        msg = demojize(message.content)

        char_count = len(msg)
        word_count = len(msg.split(" "))
        emoji_count = msg.count(":") // 2
        spoiler_count = msg.count("||") // 2

        # File Statistics
        files_amount = 0
        file_sizes = 0
        images_amt = 0
        for f in message.attachments:
            file_sizes += f.size
            if f.height is not None and f.height > 0:
                images_amt += 1

        uniqueID = handySQL.get_or_create_member(conn, message.author, guild_obj)

        c = conn.cursor()
        c.execute(f"SELECT * FROM UserMessageStatistic WHERE UniqueMemberID=? AND SubjectID=?", (uniqueID, SUBJECT_ID))
        if c.fetchone() is None:
            result = handySQL.create_message_statistic_entry(conn, message.author, guild_obj, SUBJECT_ID, "UserMessageStatistic")
            if not result[0]:
                return
        values = (char_count, word_count, spoiler_count, emoji_count, files_amount, file_sizes, images_amt, uniqueID, SUBJECT_ID)
        sql = """   UPDATE UserMessageStatistic
                    SET MessageSentCount=MessageSentCount+1,
                        CharacterCount=CharacterCount+?,
                        WordCount=WordCount+?,
                        SpoilerCount=SpoilerCount+?,
                        EmojiCount=EmojiCount+?,
                        FileSentCount=FileSentCount+?,
                        FileTotalSize=FileTotalSize+?,
                        ImageCount=ImageCount+?
                    WHERE UniqueMemberID=? AND SubjectID=?"""
        c.execute(sql, values)
        conn.commit()

    def get_current_subject_id(self, semester=2):
        conn = self.get_connection()
        c = conn.cursor()
        sql = """   SELECT WD.SubjectID
                    FROM WeekDayTimes WD
                    INNER JOIN Subject S on WD.SubjectID=S.SubjectID
                    WHERE WD.DayID=? AND WD.TimeFROM<=? AND WD.TimeTo>? AND S.SubjectSemester=?"""
        day = datetime.now().weekday()
        hour = datetime.now().hour
        c.execute(sql, (day, hour, hour, semester))
        row = c.fetchone()
        if row is None:
            return 0
        return row[0]

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        # Update messages to be "deleted"
        conn = self.get_connection()

        try:
            # This is in case a message is a direct message
            guild_obj = message.guild
        except AttributeError:
            guild_obj = None

        SUBJECT_ID = self.get_current_subject_id()

        # Increments deleted message count
        result = handySQL.increment_message_statistic(conn, message.author, guild_obj, SUBJECT_ID, "MessageDeletedCount", "UserMessageStatistic")
        if not result[0]:
            print(f"ERROR! MessageDeletedCount: {result[2]} | UserID: {message.author.id}")

    @commands.Cog.listener()
    async def on_message_edit(self, before, message):
        # Adds the edited message to the table
        if before.content == message.content:
            return
        conn = self.get_connection()

        try:
            # This is in case a message is a direct message
            guild_obj = message.guild
        except AttributeError:
            guild_obj = None

        SUBJECT_ID = self.get_current_subject_id()

        # Increments edited message count
        result = handySQL.increment_message_statistic(conn, message.author, guild_obj, SUBJECT_ID, "MessageEditedCount", "UserMessageStatistic")
        if not result[0]:
            print(f"ERROR! MessageEditedCount: {result[2]} | UserID: {message.author.id}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        conn = self.get_connection()

        try:
            # This is in case a message is a direct message
            guild_obj = reaction.message.guild
        except AttributeError:
            guild_obj = None

        SUBJECT_ID = self.get_current_subject_id()

        # Increments added reaction count for reaction giver
        result = handySQL.increment_message_statistic(conn, user, guild_obj, SUBJECT_ID, "ReactionAddedCount", "UserReactionStatistic")
        if not result[0]:
            print(f"ERROR! ReactionAddedCount: {result[2]} | UserID: {user.id}")

        # User can't up the statistic on his own message
        if user.id == reaction.message.author.id:
            return

        # Increments gotten reaction count for reaction receiver
        result = handySQL.increment_message_statistic(conn, reaction.message.author, guild_obj, SUBJECT_ID, "GottenReactionCount",
                                                      "UserReactionStatistic")
        if not result[0]:
            print(f"ERROR! GottenReactionCount: {result[2]} | UserID: {user.id}")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        conn = self.get_connection()

        try:
            # This is in case a message is a direct message
            guild_obj = reaction.message.guild
        except AttributeError:
            guild_obj = None

        SUBJECT_ID = self.get_current_subject_id()

        # Increments removed reaction count for reaction giver
        result = handySQL.increment_message_statistic(conn, user, guild_obj, SUBJECT_ID, "ReactionRemovedCount", "UserReactionStatistic")
        if not result[0]:
            print(f"ERROR! ReactionRemovedCount: {result[2]} | UserID: {user.id}")

        # User can't up the statistic on his own message
        if user.id == reaction.message.author.id:
            return

        # Increments removed gotten reaction count for reaction receiver
        result = handySQL.increment_message_statistic(conn, reaction.message.author, guild_obj, SUBJECT_ID, "GottenReactionRemovedCount",
                                                      "UserReactionStatistic")
        if not result[0]:
            print(f"ERROR! GottenReactionRemovedCount: {result[2]} | UserID: {user.id}")

    async def create_embed(self, display_name, guild_id, user_id, message_columns, reaction_columns):
        embed = discord.Embed(title=f"Statistics for {display_name}")
        conn = self.get_connection()
        c = conn.cursor()
        uniqueID = handySQL.get_uniqueMemberID(conn, user_id, guild_id)
        for column in message_columns:
            sql = f"""  SELECT UniqueMemberID, SUM({column}) as sm
                        FROM UserMessageStatistic
                        GROUP BY UniqueMemberID
                        ORDER BY sm DESC"""
            rank = 0
            val = None
            for row in c.execute(sql):
                rank += 1
                if row[0] == uniqueID:
                    val = row[1]
                    break
            if val is None:
                continue
            if column == "FileTotalSize":
                val = round(val / 1000000.0, 2)
                val = f"{val} MB"
            embed.add_field(name=column, value=f"{val} *({rank}.)*\n")
        for column in reaction_columns:
            sql = f"""  SELECT UniqueMemberID, SUM({column}) as sm
                        FROM UserReactionStatistic
                        GROUP BY UniqueMemberID
                        ORDER BY sm DESC"""
            rank = 0
            val = None
            for row in c.execute(sql):
                rank += 1
                if row[0] == uniqueID:
                    val = row[1]
                    break
            if val is None:
                continue
            embed.add_field(name=column, value=f"{val} *({rank}.)*\n")
        return embed

    async def get_rows(self, column, table, guild_id, limit):
        conn = self.get_connection()
        sql = f"""  SELECT dm.DiscordUserID, SUM({column}) as sm
                    FROM {table} as ums
                    INNER JOIN DiscordMembers as dm on dm.UniqueMemberID=ums.UniqueMemberID
                    INNER JOIN DiscordUsers DU on dm.DiscordUserID = DU.DiscordUserID
                    WHERE dm.DiscordGuildID=? AND DU.IsBot=0
                    GROUP BY ums.UniqueMemberID
                    ORDER BY sm DESC
                    LIMIT ?"""
        result = conn.execute(sql, (guild_id, limit))
        rows = result.fetchall()
        return rows

    async def get_top_users(self, guild_id, message_columns=(), reaction_columns=(), name="Top User Statistics", limit=3):
        embed = discord.Embed(title=name)
        for column in message_columns:
            rows = await self.get_rows(column, "UserMessageStatistic", guild_id, limit)
            if rows is None:
                continue
            lb_msg = ""
            for i in range(len(rows)):
                val = rows[i][1]
                if column == "FileTotalSize":
                    val = round(val / 1000000.0, 2)
                    val = f"{val} MB"
                lb_msg += f"**{i+1}.** <@!{rows[i][0]}> *({val})*\n"
            embed.add_field(name=column, value=lb_msg)
        for column in reaction_columns:
            rows = await self.get_rows(column, "UserReactionStatistic", guild_id, limit)
            if rows is None:
                continue
            lb_msg = ""
            for i in range(len(rows)):
                lb_msg += f"**{i + 1}.** <@!{rows[i][0]}> *({rows[i][1]})*\n"
            embed.add_field(name=column, value=lb_msg)
        return embed

    @commands.cooldown(4, 10, BucketType.user)
    @commands.command(aliases=["stats"], usage="statistics [user]")
    async def statistics(self, ctx, user=None):
        """
        Used to call the statistics page of a user or of the server.
        The user parameter can be another user or "top" to get the top three users \
        of each category.
        """
        message_columns = [
            "MessageSentCount",
            "MessageDeletedCount",
            "MessageEditedCount",
            "CharacterCount",
            "WordCount",
            "SpoilerCount",
            "EmojiCount",
            "FileSentCount",
            "FileTotalSize",
            "ImageCount"
        ]
        reaction_columns = [
            "ReactionAddedCount",
            "ReactionRemovedCount",
            "GottenReactionCount",
            "GottenReactionRemovedCount"
        ]

        try:
            guild_id = ctx.message.guild.id
        except AttributeError:
            guild_id = 0

        if user is not None:
            user_message_val = is_in(user, message_columns)
            user_reaction_val = is_in(user, reaction_columns)

        if user is None:
            embed = await self.create_embed(ctx.message.author.display_name, guild_id, ctx.message.author.id, message_columns, reaction_columns)
            await ctx.send(embed=embed)
        elif user == "top":
            embed = await self.get_top_users(guild_id, message_columns, reaction_columns)
            await ctx.send(embed=embed)
        elif user_message_val:
            embed = await self.get_top_users(guild_id, (user_message_val,), (), f"Top {user}", 10)
            await ctx.send(embed=embed)
        elif user_reaction_val:
            embed = await self.get_top_users(guild_id, (), (user_reaction_val,), f"Top {user}", 10)
            await ctx.send(embed=embed)
        else:
            try:
                memberconverter = discord.ext.commands.MemberConverter()
                user = await memberconverter.convert(ctx, user)
            except discord.ext.commands.errors.BadArgument:
                await ctx.send("Invalid user. Mention the user for this to work.")
                raise discord.ext.commands.errors.BadArgument
            embed = await self.create_embed(user.display_name, guild_id, user.id, message_columns, reaction_columns)
            await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Statistics(bot))
