import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from pytz import timezone
import time
from helper.lecture_scraper.scrape import scraper
import json
import traceback
from helper.log import log


class Updates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open("./data/schedule.json", "r") as f:
            self.schedule = json.load(f)
        with open("./data/settings.json", "r") as f:
            self.settings = json.load(f)
        self.channel_to_post = self.settings[self.settings["channel_to_post"]]
        self.test_livestream_message = self.settings["test_livestream_message"]
        self.send_message_to_finn = self.settings["send_message_to_finn"]
        self.lecture_updater_version = "v2.4"

        self.time_heartbeat = 0

        self.bot.loop.create_task(self.background_loop())

    def heartbeat(self):
        return self.time_heartbeat

    async def background_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                channel = self.bot.get_channel(self.channel_to_post)
                cur_time = datetime.now(timezone("Europe/Zurich")).strftime("%a:%H:%M")
                self.time_heartbeat = time.time()
                if self.test_livestream_message:
                    cur_time = "test"
                if int(datetime.now(timezone("Europe/Zurich")).strftime("%M")) % 10 == 0:  # Only check updates every 10 minutes
                    await self.check_updates(channel, cur_time, self.lecture_updater_version)
                if cur_time in self.all_times(self.schedule):
                    await self.send_livestream(cur_time, channel, self.lecture_updater_version)
                await asyncio.sleep(40)
            except Exception:
                user = self.bot.get_user(205704051856244736)
                await user.send(f"Error in background loop: {traceback.format_exc()}")
                log(f"Error in background loop self.bot.py: {traceback.format_exc()}", "BACKGROUND")
                await asyncio.sleep(10)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def edit(self, ctx, id: int = None, link=None):
        try:
            await ctx.message.delete()
            if id is None or link is None:
                msg = await ctx.send("No link sent")
                await asyncio.sleep(7)
                await msg.delete()
                return
            room = self.get_room(link)
            message = await ctx.channel.fetch_message(id)
            title = message.embeds[0].title
            embed = discord.Embed(title=f"{title} is starting soon!",
                                  description=f"**Lecture is in {room}**\n[**>> Click here to view the livestream <<**]({link})\n---------------------\n",
                                  timestamp=datetime.fromtimestamp(time.time()), color=discord.Color.light_grey())
            embed.set_footer(text="(Edited)")
            await message.edit(embed=embed)
        except Exception:
            user = self.bot.get_user(205704051856244736)
            await user.send(f"No lesson error: {traceback.format_exc()}")

    async def check_updates(self, channel, cur_time, version):
        start = time.time()
        scraped_info = scraper()
        changes = scraped_info[0]
        lecture_urls = scraped_info[1]
        send_ping = True
        for lesson in changes.keys():
            try:
                if len(changes[lesson]) > 0:
                    for i in range(len(changes[lesson])):

                        # EMBED COLOR
                        color = discord.Color.lighter_grey()
                        if lesson == "Introduction to Programming":
                            color = discord.Color.blue()
                        elif lesson == "Discrete Mathematics":
                            color = discord.Color.purple()
                        elif lesson == "Linear Algebra":
                            color = discord.Color.gold()
                        elif lesson == "Algorithms and Data Structures":
                            color = discord.Color.magenta()

                        try:
                            correct_changes = changes[lesson][i]
                        except KeyError as e:
                            correct_changes = changes[lesson]
                            user = self.bot.get_user(205704051856244736)
                            await user.send(f"Lesson: {lesson}\nError: KeyError\nChanges: `{changes}`")
                        if correct_changes["event"] == "other":
                            embed = discord.Embed(title=f"{lesson} has been changed!",
                                                  description=f"[Click here to get to {lesson}'s website]({lecture_urls[lesson]}).",
                                                  timestamp=datetime.utcfromtimestamp(time.time()), color=color)
                            if self.send_message_to_finn:
                                users = [205704051856244736, 304014259975880704]  # 304014259975880704
                            else:
                                users = [205704051856244736]
                            for u_id in users:
                                user = self.bot.get_user(u_id)
                                await user.send(embed=embed)

                        elif correct_changes["event"] == "edit":
                            log(f"{lesson} was changed", "LESSON")
                            title = f"There has been an edit on __{lesson}__"
                            description = f"""**OLD**:
        {self.format_exercise(correct_changes["content"]["old"])}

        **NEW**:
        {self.format_exercise((correct_changes["content"]["new"]), correct_changes["content"]["keys"])}"""
                            embed = discord.Embed(title=title, description=description,
                                                  timestamp=datetime.utcfromtimestamp(time.time()), color=color)
                            embed.set_footer(
                                text=f"{version} | This message took {round(time.time() - start, 2)} seconds to send")
                            await channel.send(embed=embed)
                            if send_ping:
                                await channel.send("<@&759615935496847412>", embed=embed)
                            else:
                                await channel.send(embed=embed)
                            send_ping = False

                        elif correct_changes["event"] == "new":
                            log(f"{lesson} got an new update", "LESSON")
                            title = f"Something new was added on __{lesson}__"
                            description = f"""**NEW**:\n{self.format_exercise(correct_changes["content"])}"""
                            embed = discord.Embed(title=title, description=description,
                                                  timestamp=datetime.utcfromtimestamp(time.time()), color=color)
                            embed.set_footer(
                                text=f"{version} | This message took {round(time.time() - start, 2)} seconds to send")
                            if send_ping:
                                await channel.send("<@&759615935496847412>", embed=embed)
                            else:
                                await channel.send(embed=embed)
                            send_ping = False
            except Exception:
                user = self.bot.get_user(205704051856244736)
                await user.send(f"Lesson{lesson}\nError: {traceback.format_exc()}")

    def format_exercise(self, version, edited_keys=None):
        topics = {"name": "Name", "date": "Date", "abgabe_date": "Submission Date", "links": "Link"}
        formatted_text = ""
        for key in version:
            if edited_keys is not None and key in edited_keys:
                formatted_text += f"__{topics[key]}: {self.check_link(key, version[key])}__\n"
            else:
                formatted_text += f"{topics[key]}: {self.check_link(key, version[key])}\n"
        return formatted_text

    def check_link(self, key, data):
        if key == "links":
            text = ""
            for diff_url in range(len(data)):
                text += f"[Click Here for {data[diff_url]['text']}]({data[diff_url]['url'].replace(' ', '%20')})\n"
            return text
        else:
            return data

    async def send_livestream(self, cur_time: str, channel, version):
        color = discord.Color.lighter_grey()
        log("Sending Embed Message for livestream.", "LIVESTREAM")
        link = ""
        name = ""
        website_url = ""
        if cur_time in self.schedule['eprog']:  # Eprog
            link = self.schedule['eprog'][cur_time]
            website_url = self.schedule['eprog']['url']
            name = "Introduction to Programming"
            color = discord.Color.blue()
        elif cur_time in self.schedule['diskmat']:  # diskmat
            link = self.schedule['diskmat'][cur_time]
            website_url = self.schedule['diskmat']['url']
            name = "Discrete Mathematics"
            color = discord.Color.purple()
        elif cur_time in self.schedule['linalg']:  # linalg
            link = self.schedule['linalg'][cur_time]
            website_url = self.schedule['linalg']['url']
            name = "Linear Algebra"
            color = discord.Color.gold()
        elif cur_time in self.schedule['and']:  # AnD
            link = self.schedule['and'][cur_time]
            website_url = self.schedule['and']['url']
            name = "Algorithms and Data Structures"
            color = discord.Color.magenta()
        elif cur_time in self.schedule['test']:  # TEST
            link = self.schedule['test'][cur_time]
            website_url = self.schedule['test']['url']
            name = "< Test Message >"

        room = self.get_room(link)
        embed = discord.Embed(title=f"{name} is starting soon!",
                              description=f"**Lecture is in {room}**\n[**>> Click here to view the lecture <<**]({link})\n---------------------\n[*Link to Website*]({website_url})",
                              timestamp=datetime.utcfromtimestamp(time.time()), color=color)
        embed.set_footer(text=f"{version}")
        await channel.send("<@&759615935496847412>", embed=embed)

        await asyncio.sleep(40)  # So it doesnt send the stream twice in a minute

    def all_times(self, schedule):
        times = []
        for subject in self.schedule:
            for time_text in self.schedule[subject]:
                times.append(time_text)
        return times

    def get_room(self, link):
        if "zoom" in link:
            room = "Zoomland"
        elif "ethz" in link:
            link = link[46:-5]
            room = link[link.index("/") + 1:].replace("-", " ").upper()
        else:
            room = "(N/A)"

        return room


def setup(bot):
    bot.add_cog(Updates(bot))
