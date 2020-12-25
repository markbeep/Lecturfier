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
from helper.git_backup import gitpush


# TODO make on_message_delete and on_reaction_add raw
# labels: STATISTICS
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
            "msgs_during_ep",           # DONE
            "msgs_during_dm",           # DONE
            "msgs_during_la",           # DONE
            "msgs_during_ad",           # DONE
            "reactions_added",          # DONE
            "files_sent",               # DONE
            "gifs_sent",                # DONE
            "reactions_received",       # DONE
            "commands_used"             # Only Lecturfier

        ]
        self.checks_full_name = {
            "messages_sent": "Messages sent",
            "messages_deleted": "Messages deleted",
            "messages_edited": "Messages edited",
            "chars_sent": "Characters sent",
            "words_sent": "Words sent",
            "spoilers": "Spoilers sent",
            "emojis": "Emojis used",
            "files_sent": "Files sent",
            "gifs_sent": "GIFs sent",
            "reactions_received": "Reactions received",
            "commands_used": "Bot usage",
            "msgs_during_lecture": "Messages / lectures",
            "msgs_during_ep": "Messages / EProg",
            "msgs_during_dm": "Messages / DiscMat",
            "msgs_during_la": "Messages / LinAlg",
            "msgs_during_ad": "Messages / AnD",
            "reactions_added": "Reactions added"
        }
        self.lesson_times = {
            "ep":
                {
                    "Tue": [10, 12],
                    "Fri": [8, 10]
                 },
            "dm":
                {
                    "Tue": [12, 14],
                    "Wed": [12, 14]
                },
            "la":
                {
                    "Wed": [10, 12],
                    "Fri": [10, 12]
                },
            "ad":
                {
                    "Thu": [14, 17]
                }
        }
        self.bot_uptime_path = "./data/bot_uptime.json"
        with open(self.bot_uptime_path, "r") as f:
            self.bot_uptime = json.load(f)
        self.statistics_filepath = "./data/statistics.json"
        with open(self.statistics_filepath, "r") as f:
            self.statistics = json.load(f)
        self.waiting = False
        self.time_counter = 0  # So statistics dont get saved every few seconds, and instead only every 2 mins
        self.notice_message = 0  # The message that notifies others about joining the spam channel
        self.recent_message = []
        self.bot_changed_to_yesterday = {}
        self.time_heartbeat = 0
        self.task = self.bot.loop.create_task(self.background_save_statistics())

    def heartbeat(self):
        return self.time_heartbeat

    def get_task(self):
        return self.task

    async def background_save_statistics(self):
        sent_file = False
        await self.bot.wait_until_ready()
        start_time = time.perf_counter()
        while not self.bot.is_closed():
            self.time_heartbeat = time.time()
            if self.time_counter >= 6:  # Saves the statistics file every minute
                self.time_counter = 0
                try:
                    with open(self.statistics_filepath, "w") as f:
                        json.dump(self.statistics, f, indent=2)
                    log("SAVED STATISTICS", "STATISTICS")
                    with open(self.bot_uptime_path, "w") as f:
                        json.dump(self.bot_uptime, f, indent=2)
                    log("SAVED BOT UPTIME", "UPTIME")
                except Exception:
                    user = self.bot.get_user(205704051856244736)
                    await user.send(f"Saving files failed:\n{traceback.format_exc()}")
            else:
                self.time_counter += 1
            if not sent_file and datetime.now().hour % 2 == 0:  # Backs up all files every 2 hours
                # Backs the data files up to github
                with open("./data/settings.json", "r") as f:
                    settings = json.load(f)
                if settings["upload to git"]:
                    sent_file = True
                    output = gitpush("./data")
                    user = self.bot.get_user(205704051856244736)
                    await user.send("Updated GIT\n"
                                    f"Commit: `{output[0]}`\n"
                                    f"Push: `{output[1]}`")
            if datetime.now().hour % 2 != 0:
                sent_file = False

            await asyncio.sleep(10)
            time_taken = time.perf_counter() - start_time

            await self.is_bot_running(747752542741725244, time_taken)
            await self.is_bot_running(237607896626495498, time_taken)
            start_time = time.perf_counter()

    async def is_bot_running(self, guild_id, time_taken):
        guild = self.bot.get_guild(guild_id)
        hour_min = datetime.now(timezone("Europe/Zurich")).strftime("%H:%M")
        day = datetime.now(timezone("Europe/Zurich")).strftime("%w")
        if guild is not None:
            for u in guild.members:
                if str(u.status) != "offline":
                    await self.add_uptime(guild_id, u.id, hour_min, day, time_taken)

    async def add_uptime(self, guild_id, bot_id, hour_min, day, time_taken):
        guild_id = str(guild_id)
        bot_id = str(bot_id)
        if guild_id not in self.bot_uptime:
            self.bot_uptime[guild_id] = {}
        if bot_id not in self.bot_uptime[guild_id]:
            self.bot_uptime[guild_id][bot_id] = {"day": time_taken, "yesterday": 0, "week": time_taken, "past_week": 0, "total": time_taken, "start": time.time()}
        self.bot_uptime[guild_id][bot_id]["day"] += time_taken
        self.bot_uptime[guild_id][bot_id]["week"] += time_taken
        self.bot_uptime[guild_id][bot_id]["total"] += time_taken

        if bot_id in self.bot_changed_to_yesterday and self.bot_changed_to_yesterday[bot_id] > time.time() - 300:
            pass
        elif hour_min == "23:59":
            if day == "0":  # if sunday
                self.bot_uptime[guild_id][bot_id]["past_week"] = self.bot_uptime[guild_id][bot_id]["week"]
                self.bot_uptime[guild_id][bot_id]["week"] = 0
            self.bot_uptime[guild_id][bot_id]["yesterday"] = self.bot_uptime[guild_id][bot_id]["day"]
            self.bot_uptime[guild_id][bot_id]["day"] = 0
            self.bot_changed_to_yesterday[bot_id] = time.time()

    async def get_uptime(self, guild_id, bot_id, data_range):
        guild_id = str(guild_id)
        bot_id = str(bot_id)
        if guild_id not in self.bot_uptime or bot_id not in self.bot_uptime[guild_id]:
            return 0
        if data_range not in self.bot_uptime[guild_id][bot_id]:
            self.bot_uptime[guild_id][bot_id][data_range] = 0
        return self.bot_uptime[guild_id][bot_id][data_range]

    @commands.command()
    async def uptime(self, ctx, bot=None):
        if bot is None:
            await ctx.send("No bot specified.")
        else:
            try:
                memberconverter = discord.ext.commands.MemberConverter()
                user = await memberconverter.convert(ctx, bot)
            except discord.ext.commands.errors.BadArgument:
                await ctx.send(f"{ctx.message.author.mention}, that is not a user. Mention a user or bot for this command to work.")
                raise discord.ext.commands.errors.BadArgument

            lecturfier_start_time = time.time() - await self.get_uptime(ctx.message.guild.id, self.bot.user.id, "start")
            lecturfier_total = round((float(await self.get_uptime(ctx.message.guild.id, self.bot.user.id, "total")) / lecturfier_start_time) * 100, 2)
            if lecturfier_total > 100:
                lecturfier_total = 100

            bot_yesterday = round(float(await self.get_uptime(ctx.message.guild.id, user.id, "yesterday")) / 864, 2)
            bot_week = round(float(await self.get_uptime(ctx.message.guild.id, user.id, "past_week")) / 6048, 2)
            bot_start_time = time.time() - await self.get_uptime(ctx.message.guild.id, user.id, "start")
            bot_total = round((float(await self.get_uptime(ctx.message.guild.id, user.id, "total")) / bot_start_time) * 100, 2)
            if bot_total > 100:
                bot_total = 100
            embed = discord.Embed(title=f"Bot Uptime",
                                  description=f"**{user.display_name}**\n"
                                              f"Total: {bot_total}%\n"
                                              f"Last Week: {bot_week}%\n"
                                              f"Yesterday: {bot_yesterday}%",
                                  color=discord.Color.blue())
            embed.set_footer(text=f"Accuracy: {lecturfier_total}%")
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if "is not found" in str(error):
            return
        if ctx.message.author.bot:
            return
        else:
            self.recent_message.append(ctx.message.author.id)
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
            self.statistics[str(ctx.message.guild.id)]["commands_used"][str(ctx.message.author.id)] += 1

    @commands.Cog.listener()
    async def on_ready(self):
        self.script_start = time.time()

    # TODO Find out why stats doesnt always work
    @commands.Cog.listener()
    async def on_message(self, message):
        if "@everyone" in message.content.lower():
            return
        if message.author.bot:
            return
        try:
            if message.author.id in self.recent_message:
                return
            self.recent_message.append(message.author.id)

            await self.user_checkup(message)

            msg = demojize(message.content)
            self.statistics[str(message.guild.id)]["messages_sent"][str(message.author.id)] += 1
            self.statistics[str(message.guild.id)]["chars_sent"][str(message.author.id)] += len(msg)
            self.statistics[str(message.guild.id)]["words_sent"][str(message.author.id)] += len(msg.split(" "))

            # Amount of emojis in a message
            emoji_amt = msg.count(":") // 2
            if emoji_amt > 5:
                emoji_amt = 5
            self.statistics[str(message.guild.id)]["emojis"][str(message.author.id)] += emoji_amt

            # Amount of spoilers in a message
            spoiler_amt = msg.count("||") // 2
            if spoiler_amt > 5:
                spoiler_amt = 5
            self.statistics[str(message.guild.id)]["spoilers"][str(message.author.id)] += spoiler_amt

            self.statistics[str(message.guild.id)]["gifs_sent"][str(message.author.id)] += msg.count("giphy") + msg.count("tenor") + msg.count(".gif")

            if len(message.attachments) > 0:
                self.statistics[str(message.guild.id)]["files_sent"][str(message.author.id)] += len(message.attachments)

            cur_time = datetime.now(timezone("Europe/Zurich")).strftime("%a:%H").split(":")

            for key in self.lesson_times.keys():
                if cur_time[0] in self.lesson_times[key]:
                    if self.lesson_times[key][cur_time[0]][0] <= int(cur_time[1]) <= self.lesson_times[key][cur_time[0]][1]:
                        self.statistics[str(message.guild.id)][f"msgs_during_{key}"][str(message.author.id)] += 1
                        self.statistics[str(message.guild.id)]["msgs_during_lecture"][str(message.author.id)] += 1

            await asyncio.sleep(5)
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
                raise discord.ext.commands.errors.BadArgument
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


def setup(bot):
    bot.add_cog(Statistics(bot))
