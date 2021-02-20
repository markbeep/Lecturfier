import discord
from discord.ext import commands
from datetime import datetime
import time
import asyncio
from emoji import demojize
import json
from helper.git_backup import gitpush
from helper import handySQL


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
            try:
                await ctx.message.add_reaction("<:ERROR:792154973559455774>")
            except discord.errors.NotFound:
                pass
            print(error)

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
        # Adds the message to the DB
        handySQL.create_message_entry(conn, message, message.channel, message.guild)
        try:
            # This is in case a message is a direct message
            guild_obj = message.guild
        except AttributeError:
            guild_obj = None

        SUBJECT_ID = 0

        # Increments sent message count
        result = handySQL.increment_message_statistic(conn, message.author, guild_obj, SUBJECT_ID, "MessageSentCount", "UserMessageStatistic")
        if not result[0]:
            print(f"ERROR! MessageSentCount: {result[2]} | UserID: {message.author.id}")

        # Makes it better to work with the message
        msg = demojize(message.content)

        # Increments character count
        result = handySQL.increment_message_statistic(conn, message.author, guild_obj, SUBJECT_ID, "CharacterCount", "UserMessageStatistic", len(msg))
        if not result[0]:
            print(f"ERROR! CharacterCount: {result[2]} | UserID: {message.author.id}")

        # Increments word count
        result = handySQL.increment_message_statistic(conn, message.author, guild_obj, SUBJECT_ID, "WordCount", "UserMessageStatistic",
                                                      len(msg.split(" ")))
        if not result[0]:
            print(f"ERROR! WordCount: {result[2]} | UserID: {message.author.id}")

        # Increments emoji count
        if ":" in msg:
            result = handySQL.increment_message_statistic(conn, message.author, guild_obj, SUBJECT_ID, "EmojiCount", "UserMessageStatistic",
                                                          (msg.count(":") // 2))
            if not result[0]:
                print(f"ERROR! EmojiCount: {result[2]} | UserID: {message.author.id}")

        # Increments spoiler count
        if "||" in msg:
            result = handySQL.increment_message_statistic(conn, message.author, guild_obj, SUBJECT_ID, "SpoilerCount", "UserMessageStatistic",
                                                          (msg.count("||") // 2))
            if not result[0]:
                print(f"ERROR! SpoilerCount: {result[2]} | UserID: {message.author.id}")

        # File Statistics
        if len(message.attachments) > 0:
            # Increments files sent count
            result = handySQL.increment_message_statistic(conn, message.author, guild_obj, SUBJECT_ID, "FileSentCount", "UserMessageStatistic",
                                                          len(message.attachments))
            if not result[0]:
                print(f"ERROR! FileSentCount: {result[2]} | UserID: {message.author.id}")

            file_sizes = 0
            images_amt = 0
            for f in message.attachments:
                file_sizes += f.size
                if f.height is not None and f.height > 0:
                    images_amt += 1

            # Increments total file size count
            result = handySQL.increment_message_statistic(conn, message.author, guild_obj, SUBJECT_ID, "FileTotalSize", "UserMessageStatistic",
                                                          file_sizes)
            if not result[0]:
                print(f"ERROR! FileSentCount: {result[2]} | UserID: {message.author.id}")

            # Increments images sent count
            result = handySQL.increment_message_statistic(conn, message.author, guild_obj, SUBJECT_ID, "ImageCount", "UserMessageStatistic",
                                                          images_amt)
            if not result[0]:
                print(f"ERROR! ImageCount: {result[2]} | UserID: {message.author.id}")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        # Update messages to be "deleted"
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE DiscordMessages SET IsDeleted=1, DeletedAt=? WHERE DiscordMessageID=?", (datetime.now(), message.id))
        conn.commit()

        try:
            # This is in case a message is a direct message
            guild_obj = message.guild
        except AttributeError:
            guild_obj = None

        SUBJECT_ID = 0

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
        c = conn.cursor()
        c.execute("SELECT IsEdited FROM DiscordMessages WHERE DiscordMessageID=? ORDER BY IsEdited DESC", (message.id,))
        result = c.fetchone()
        if result is not None:
            IsEdited = result[0]
            handySQL.create_message_entry(conn, message, message.channel, message.guild, IsEdited + 1)

        try:
            # This is in case a message is a direct message
            guild_obj = message.guild
        except AttributeError:
            guild_obj = None

        SUBJECT_ID = 0

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

        SUBJECT_ID = 0

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

        SUBJECT_ID = 0

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
