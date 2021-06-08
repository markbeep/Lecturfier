import discord
from discord.ext import commands, tasks
from discord.ext.commands import CommandOnCooldown
from datetime import datetime
import time
import asyncio
from emoji import demojize
import json
from helper.git_backup import gitpush
from discord.ext.commands.cooldowns import BucketType
from helper.sql import SQLFunctions
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
        self.db_path = "./data/discord.db"
        self.background_git_backup.start()
        self.sent_file = False
        self.current_subject = [-1, 0]

    def heartbeat(self):
        return self.background_git_backup.is_running()

    def get_task(self):
        return self.background_git_backup

    @tasks.loop(seconds=10)
    async def background_git_backup(self):
        await self.bot.wait_until_ready()

        # Backs up all files every 2 hours
        if not self.sent_file and datetime.now().hour % 2 == 0:
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
            self.sent_file = False

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
        # only count stats in servers
        if message.guild is None:
            return

        SUBJECT_ID = self.get_current_subject()
        print("SUBJECT ID", SUBJECT_ID)
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

        SQLFunctions.update_statistics(message.author,
                                       SUBJECT_ID,
                                       messages_sent=1,
                                       characters_sent=char_count,
                                       words_sent=word_count,
                                       spoilers_sent=spoiler_count,
                                       emojis_sent=emoji_count,
                                       files_sent=files_amount,
                                       file_size_sent=file_sizes,
                                       images_sent=images_amt)

    def get_current_subject(self, semester=2) -> int:
        """
        Minor cache system to only make a subject query if it's a new minute
        Returns the current subject ID
        """
        minute = datetime.now().minute
        if self.current_subject[0] != minute:
            subject_id = SQLFunctions.get_current_subject_id(semester)
            self.current_subject = [minute, subject_id]
        return self.current_subject[1]

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None:
            return
        SUBJECT_ID = self.get_current_subject()
        SQLFunctions.update_statistics(message.member, SUBJECT_ID, messages_deleted=1)

    @commands.Cog.listener()
    async def on_message_edit(self, before, message):
        # Adds the edited message to the table
        if message.guild is None:
            return

        # gets the char difference between the two messages
        b_cont = before.content
        a_cont = message.content
        before_char_count = len(b_cont)
        before_word_count = len(b_cont.split(" "))
        before_emoji_count = b_cont.count(":") // 2
        before_spoiler_count = b_cont.count("||") // 2
        after_char_count = len(a_cont)
        after_word_count = len(a_cont.split(" "))
        after_emoji_count = a_cont.count(":") // 2
        after_spoiler_count = a_cont.count("||") // 2

        SUBJECT_ID = self.get_current_subject()
        SQLFunctions.update_statistics(message.author,
                                       SUBJECT_ID,
                                       messages_edited=1,
                                       characters_sent=after_char_count - before_char_count,
                                       words_sent=after_word_count - before_word_count,
                                       emojis_sent=after_emoji_count - before_emoji_count,
                                       spoilers_sent=after_spoiler_count - before_spoiler_count)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, member):
        if reaction.message.guild is None:
            return
        SUBJECT_ID = self.get_current_subject()
        SQLFunctions.update_statistics(member, SUBJECT_ID, reactions_added=1)
        if member.id == reaction.message.author.id:
            return
        SQLFunctions.update_statistics(reaction.message.author, SUBJECT_ID, reactions_received=1)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, member):
        if reaction.message.guild is None:
            return
        SUBJECT_ID = self.get_current_subject()
        SQLFunctions.update_statistics(member, SUBJECT_ID, reactions_removed=1)
        if member.id == reaction.message.author.id:
            return
        SQLFunctions.update_statistics(reaction.message.author, SUBJECT_ID, reactions_taken_away=1)

    async def create_embed(self, display_name, guild_id, user_id, message_columns, reaction_columns):
        embed = discord.Embed(title=f"Statistics for {display_name}")
        conn = self.get_connection()
        c = conn.cursor()
        uniqueID = handySQL.get_uniqueMemberID(conn, user_id, guild_id)
        for column in message_columns:
            sql = f"""  SELECT ums.UniqueMemberID, SUM({column}) as sm
                        FROM UserMessageStatistic ums
                        INNER JOIN DiscordMembers as dm on dm.UniqueMemberID=ums.UniqueMemberID
                        INNER JOIN DiscordUsers DU on dm.DiscordUserID = DU.DiscordUserID
                        WHERE DU.IsBot=0
                        GROUP BY ums.UniqueMemberID
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
            sql = f"""  SELECT ums.UniqueMemberID, SUM({column}) as sm
                        FROM UserReactionStatistic ums
                        INNER JOIN DiscordMembers as dm on dm.UniqueMemberID=ums.UniqueMemberID
                        INNER JOIN DiscordUsers DU on dm.DiscordUserID = DU.DiscordUserID
                        WHERE DU.IsBot=0
                        GROUP BY ums.UniqueMemberID
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
                lb_msg += f"**{i + 1}.** <@!{rows[i][0]}> *({val})*\n"
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

        SQLFunctions.get_statistic_rows()
        return

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
