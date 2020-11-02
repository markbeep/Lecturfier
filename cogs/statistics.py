import discord
from discord.ext import commands
from datetime import datetime
from pytz import timezone
import time
import asyncio
import json
from emoji import demojize
import traceback
from helper.log import log


class Statistics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.script_start = 0
        self.checks = [
            "messages_sent",            # DONE
            "messages_deleted",         # DONE
            "messages_edited",          # DONE
            "chars_sent",               # DONE
            "words_sent",               # DONE
            "spoilers",                 # DONE
            "emojis",                   # DONE
            "msgs_during_lecture",      # DONE
            "reactions_added",          # DONE
            "files_sent",               # DONE
            "gifs_sent",                # DONE
            "reactions_received",       # DONE
            "commands_used"             # Only Lecturfier till now

        ]
        self.checks_full_name = {
            "messages_sent": "Messages sent",
            "messages_deleted": "Messages deleted",
            "messages_edited": "Messages edited",
            "chars_sent": "Characters sent",
            "words_sent": "Words sent",
            "spoilers": "Spoilers sent",
            "emojis": "Emojis used",
            "msgs_during_lecture": "Messages sent during lectures",
            "reactions_added": "Reactions added",
            "files_sent": "Files sent",
            "gifs_sent": "GIFs sent",
            "reactions_received": "Reactions received",
            "commands_used": "Bot Commands used"

        }
        self.lesson_times = {
            "Tue": [10, 14],
            "Wed": [10, 14],
            "Thu": [14, 17],
            "Fri": [8, 12]
        }

        self.statistics_filepath = "./data/statistics.json"
        with open(self.statistics_filepath, "r") as f:
            self.statistics = json.load(f)
        with open("./data/ignored_channels.json") as f:
            self.ignore_channels = json.load(f)

        # self.spam_channel_times = ["Tue:11:45", "Fri:09:45", "Fri:09:45", "Wed:13:45", "Wed:11:45", "Fri:11:45", "Thu:16:45"]
        self.time_of_msg = time.time()
        self.waiting = False
        self.time_counter = 0  # So statistics dont get saved every few seconds, and instead only every 2 mins
        self.notice_message = 0  # The message that notifies others about joining the spam channel
        self.recent_message = []

        bot.loop.create_task(self.background_loop())

    async def background_loop(self):
        sent_file = False
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            if self.time_counter >= 5:
                self.time_counter = 0
                try:
                    with open(self.statistics_filepath, "w") as f:
                        json.dump(self.statistics, f, indent=2)
                    log("SAVED STATISTICS", "STATISTICS")
                except Exception:
                    user = self.bot.get_user(205704051856244736)
                    await user.send(f"Saving STATISTICS file failed:\n{traceback.format_exc()}")
            if not sent_file and datetime.now().hour % 2 == 0:
                sent_file = True
                user = self.bot.get_user(205704051856244736)
                await user.send("Statistics loop is working")
            if datetime.now().hour % 2 != 0:
                sent_file = False

            #  await self.spam_channel()

            await asyncio.sleep(20)
            self.time_counter += 1

    @commands.Cog.listener()
    async def on_ready(self):
        self.script_start = time.time()

    @commands.Cog.listener()
    async def on_message(self, message):
        if "@everyone" in message.content.lower():
            return
        if message.author.bot:
            return
        try:
            if message.author.id in self.recent_message:
                return
            if message.channel.id in self.ignore_channels:
                return
            self.recent_message.append(message.author.id)

            await self.user_checkup(message)

            msg = demojize(message.content)

            if message.content.startswith("$") or message.content.startswith("\\") or message.content.startswith(";"):
                self.statistics[str(message.guild.id)]["commands_used"][str(message.author.id)] += 1

            self.statistics[str(message.guild.id)]["messages_sent"][str(message.author.id)] += 1
            self.statistics[str(message.guild.id)]["chars_sent"][str(message.author.id)] += len(msg)
            self.statistics[str(message.guild.id)]["words_sent"][str(message.author.id)] += len(msg.split(" "))
            emoji_amt = msg.count(":") // 2
            if emoji_amt > 5:
                emoji_amt = 5
            self.statistics[str(message.guild.id)]["emojis"][str(message.author.id)] += emoji_amt
            spoiler_amt = msg.count("||") // 2
            if spoiler_amt > 5:
                spoiler_amt = 5
            self.statistics[str(message.guild.id)]["spoilers"][str(message.author.id)] += spoiler_amt
            self.statistics[str(message.guild.id)]["gifs_sent"][str(message.author.id)] += msg.count("giphy") + msg.count("tenor") + msg.count(".gif")

            if len(message.attachments) > 0:
                self.statistics[str(message.guild.id)]["files_sent"][str(message.author.id)] += len(message.attachments)

            cur_time = datetime.now(timezone("Europe/Zurich")).strftime("%a:%H").split(":")
            if cur_time[0] in self.lesson_times:
                if self.lesson_times[cur_time[0]][0] <= int(cur_time[1]) <= self.lesson_times[cur_time[0]][1]:
                    self.statistics[str(message.guild.id)]["msgs_during_lecture"][str(message.author.id)] += 1

            await asyncio.sleep(2)
            self.recent_message.pop(self.recent_message.index(message.author.id))
        except AttributeError:
            user = self.bot.get_user(205704051856244736)
            await user.send("AttributeError for on_message")

    async def user_checkup(self, message=None, reaction=None, user=None):
        if message is not None and user is None:
            author_id = message.author.id
        if reaction is not None:
            message = reaction.message
            author_id = user.id
        if user is not None:
            author_id = user.id

        # If the guild doesnt exist in statistics yet
        if str(message.guild.id) not in self.statistics:
            self.statistics[str(message.guild.id)] = {}

        # If the check doesnt exist in statistics yet
        for check in self.checks:
            if check not in self.statistics[str(message.guild.id)]:
                self.statistics[str(message.guild.id)][check] = {}

        # If the user doesnt exist in statistics yet
        for check in self.checks:
            if str(author_id) not in self.statistics[str(message.guild.id)][check]:
                self.statistics[str(message.guild.id)][check][str(author_id)] = 0

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        try:
            if message.author.bot:
                return
            await self.user_checkup(message)
            self.statistics[str(message.guild.id)]["messages_deleted"][str(message.author.id)] += 1
            dm_users = [205704051856244736, 190550937264324608, 252091777115226114]
            for u_id in dm_users:
                user = self.bot.get_user(u_id)
                embed = discord.Embed(title=f"Deleted Message from {message.author}", description=message.content)
                await user.send(embed=embed)
        except AttributeError:
            user = self.bot.get_user(205704051856244736)
            await user.send("AttributeError for message delete")

    @commands.Cog.listener()
    async def on_message_edit(self, before, message):
        try:
            if message.author.bot:
                return
            await self.user_checkup(message)
            self.statistics[str(message.guild.id)]["messages_edited"][str(message.author.id)] += 1
        except AttributeError:
            user = self.bot.get_user(205704051856244736)
            await user.send("AttributeError for message edit")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        try:
            # Reactions added
            if user.bot or reaction.message.author.bot:
                return
            await self.user_checkup(reaction=reaction, user=user)
            self.statistics[str(reaction.message.guild.id)]["reactions_added"][str(user.id)] += 1

            # Reactions on own message
            if reaction.message.author.id == user.id:
                return
            await self.user_checkup(message=reaction.message)
            self.statistics[str(reaction.message.guild.id)]["reactions_received"][str(reaction.message.author.id)] += 1
        except AttributeError:
            user = self.bot.get_user(205704051856244736)
            await user.send("AttributeError for reaction add")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        try:
            if user.bot:
                return
            # Reactions added
            await self.user_checkup(reaction=reaction, user=user)
            self.statistics[str(reaction.message.guild.id)]["reactions_added"][str(user.id)] -= 1
            if self.statistics[str(reaction.message.guild.id)]["reactions_added"][str(user.id)] < 0:
                self.statistics[str(reaction.message.guild.id)]["reactions_added"][str(user.id)] = 0

            # Reactions on own message
            if reaction.message.author.id == user.id:
                return
            await self.user_checkup(message=reaction.message)
            self.statistics[str(reaction.message.guild.id)]["reactions_received"][str(reaction.message.author.id)] -= 1
            if self.statistics[str(reaction.message.guild.id)]["reactions_received"][str(reaction.message.author.id)] < 0:
                self.statistics[str(reaction.message.guild.id)]["reactions_received"][str(reaction.message.author.id)] = 0
        except AttributeError:
            user = self.bot.get_user(205704051856244736)
            await user.send("AttributeError for reaction remove")

    @commands.command(aliases=["stats"])
    @commands.has_permissions(administrator=True)
    async def statistics(self, ctx, user=None):
        """
        Used to call a statistics page
        :param ctx: Message context
        :param user: Either no input, "top" or @user
        :return: nothing
        """
        if user is None:
            await self.user_checkup(message=ctx.message)
            embed = discord.Embed(title=f"Statistics for {ctx.message.author.display_name}")
            for c in self.checks:
                sort = sorted(self.statistics[str(ctx.message.guild.id)][c].items(), key=lambda x: x[1], reverse=True)
                rank = 1
                for i in sort:
                    if str(ctx.message.author.id) in i:
                        break
                    else:
                        rank += 1
                embed.add_field(name=self.checks_full_name[c], value=f"*{self.statistics[str(ctx.message.guild.id)][c][str(ctx.message.author.id)]} ({rank}.)*\n")
            await ctx.send(embed=embed)

        elif user == "top":
            sort = {}
            embed = discord.Embed(title="Top User Statistics")
            for c in self.checks:
                users = []
                sort[c] = sorted(self.statistics[str(ctx.message.guild.id)][c].items(), key=lambda x: x[1],
                                 reverse=True)
                for k in sort[c]:
                    u_obj = ctx.message.guild.get_member(int(k[0]))
                    users.append([str(u_obj.display_name), k[1]])
                    if len(users) == 3:
                        break
                embed.add_field(name=self.checks_full_name[c], value=f"**1.** {users[0][0]} *({users[0][1]})*\n"
                                                                     f"**2.** {users[1][0]} *({users[1][1]})*\n"
                                                                     f"**3.** {users[2][0]} *({users[2][1]})*")
            await ctx.send(embed=embed)
        else:
            try:
                memberconverter = discord.ext.commands.MemberConverter()
                user = await memberconverter.convert(ctx, user)
            except discord.ext.commands.errors.BadArgument:
                await ctx.send("Invalid user. Mention the user for this to work.")
                return
            await self.user_checkup(message=ctx.message, user=user)
            embed = discord.Embed(title=f"Statistics for {user.display_name}")
            for c in self.checks:
                sort = sorted(self.statistics[str(ctx.message.guild.id)][c].items(), key=lambda x: x[1], reverse=True)
                rank = 1
                for i in sort:
                    if str(user.id) in i:
                        break
                    else:
                        rank += 1
                embed.add_field(name=self.checks_full_name[c],
                                value=f"*{self.statistics[str(ctx.message.guild.id)][c][str(user.id)]} ({rank}.)*\n")
            await ctx.send(embed=embed)


    """
    async def spam_channel(self):
        guild_id = 747752542741725244
        spam_channel_id = 765571174775914517
        lecture_channel_id = 755339832917491722
        time_to_keep_channel_open = 900  # 900 seconds for 15 minutes

        role = self.bot.get_guild(guild_id).default_role
        cur_time = datetime.now(timezone("Europe/Zurich")).strftime("%a:%H:%M")

        if cur_time in self.spam_channel_times and not self.waiting:
            self.time_of_msg = time.time()
            self.waiting = True
            channel = self.bot.get_channel(spam_channel_id)  # spam channel
            lecture = self.bot.get_channel(lecture_channel_id)  # lecture discussions channel
            await channel.send("." + "\n" * 40 + "❗❗ Let the spam begin ❗❗\n" + "<a:partypoop:412336219175780353>" * 10)
            await channel.set_permissions(role, send_messages=True, read_messages=True)
            self.notice_message = await lecture.send(f"❗❗ If you wanna spam, head to <#{channel.id}> ❗❗")

        elif self.waiting and time.time() - self.time_of_msg > time_to_keep_channel_open:
            self.waiting = False
            channel = self.bot.get_channel(spam_channel_id)  # spam channel
            await channel.set_permissions(role, send_messages=False)
            await channel.send("." + "\n" * 40 + "Alright spamming is over. See you once the next lecture derails!")
            await self.notice_message.delete()
            await asyncio.sleep(10)
            await channel.set_permissions(role, read_messages=False)
    """

def setup(bot):
    bot.add_cog(Statistics(bot))