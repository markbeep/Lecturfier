import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
from pytz import timezone
import time
from helper.lecture_scraper.scrape import scraper
import json
import traceback
from helper.log import log
from helper.sql import SQLFunctions


async def create_lecture_embed(subject_name, stream_url, zoom_url, subject_website_url, subject_room=None, color=discord.colour.Color.light_gray()):
    embed = discord.Embed(title=f"Lecture Starting: {subject_name}", color=color, timestamp=datetime.now(timezone("Europe/Zurich")))
    if stream_url is not None:
        stream_url = f"[Click Here]({stream_url})"
    if subject_website_url is not None:
        subject_website_url = f"[Click Here]({subject_website_url})"
    if zoom_url is not None:
        zoom_url = f"[Click Here]({zoom_url})"

    embed.description = f"**Stream URL:** {stream_url}\n" \
                        f"**Zoom URL:** {zoom_url}\n" \
                        f"**Subject Room:** {subject_room}\n" \
                        f"**Subject Website URL:** {subject_website_url}"
    return embed


def get_formatted_time(rem):
    if rem < 3600:
        return f"{round(rem/60)}M"
    if rem < 86400:
        hours = rem//3600
        return f"{hours}H {get_formatted_time(rem-hours*3600)}"
    days = rem//86400
    return f"{days}D {get_formatted_time(rem-days*86400)}"


def get_month_day(dt, weekday):
    days_until = (weekday - dt.weekday()) % 7
    day = dt + timedelta(days_until)
    return day


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
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()
        # WE CURRENTLY DON'T RUN THE BACKGROUND LOOP FOR LECTURE UPDATES
        # self.background_loop.start()
        self.current_activity = ""
        self.sent_updates = False

    def heartbeat(self):
        return self.background_loop.is_running()

    def get_task(self):
        return self.background_loop

    def get_time_till_next_lesson(self):
        dt = datetime.now()
        minute = dt.hour
        hour = dt.hour
        day = dt.weekday()
        conn = self.conn
        c = conn.cursor()

        # Display lectures that are about to start
        greater_sign = ">"
        if minute < 15:
            greater_sign = ">="

        sql = f"""  SELECT S.SubjectAbbreviation, WD.DayID, WD.TimeFrom
                    FROM WeekDayTimes WD
                    INNER JOIN Subjects S on WD.SubjectID = S.SubjectID
                    WHERE WD.TimeFrom {greater_sign}? AND WD.DayID==? OR WD.DayID>?
                    ORDER BY WD.DayID, WD.TimeFrom"""
        c.execute(sql, (hour, day, day))
        result = c.fetchone()
        if result is None:
            # Probably weekend or friday, so no results
            c.execute(sql, (0, 0, 0))
            result = c.fetchone()
            if result is None:
                return "No Lesson"

        # Calculate remaining time
        subjectName = result[0]
        date_of_subject = get_month_day(dt, int(result[1]))
        subjectHour = int(result[2])
        td = datetime(date_of_subject.year, date_of_subject.month, date_of_subject.day, subjectHour, 15) - dt
        rem = int(td.total_seconds())
        return f"{subjectName} in {get_formatted_time(rem)}"

    @tasks.loop(seconds=10)
    async def background_loop(self):
        await self.bot.wait_until_ready()
        try:
            # Check what lectures are starting
            minute = datetime.now().minute
            if not self.sent_updates and minute <= 5:
                self.sent_updates = True
                subject = self.get_starting_subject()
                if subject is not None:
                    await self.send_lecture_start(
                        subject["SubjectName"],
                        subject["SubjectLink"],
                        subject["StreamLink"],
                        self.channel_to_post,
                        759615935496847412,  # Role to ping
                        subject["ZoomLink"],
                        subject["OnSiteLocation"])
                    # Send in #lecture-distractions without ping
                    await self.send_lecture_start(
                        subject["SubjectName"],
                        subject["SubjectLink"],
                        subject["StreamLink"],
                        755339832917491722,
                        0,  # Role to ping
                        subject["ZoomLink"],
                        subject["OnSiteLocation"])
                    # send in #lecture-questions without ping
                    await self.send_lecture_start(
                        subject["SubjectName"],
                        subject["SubjectLink"],
                        subject["StreamLink"],
                        813397356837863454,
                        0,  # Role to ping
                        subject["ZoomLink"],
                        subject["OnSiteLocation"])
            if minute > 5:
                self.sent_updates = False

            # Update activity status:
            # Disabled because semester 2 is over -------------------
            """time_till_next = self.get_time_till_next_lesson()
            if time_till_next != self.current_activity:
                await self.bot.change_presence(activity=discord.Activity(name=time_till_next, type=discord.ActivityType.watching))"""

        except AttributeError as e:
            print(f"ERROR in Lecture Updates Loop! Probably wrong channel ID | {e}")
        except Exception:
            await asyncio.sleep(10)
            user = self.bot.get_user(self.bot.owner_id)
            await user.send(f"Error in background loop: {traceback.format_exc()}")
            log(f"Error in background loop self.bot.py: {traceback.format_exc()}", "BACKGROUND")

    @commands.command(usage="testLecture <subject_id> <channel_id> <role_id>")
    @commands.is_owner()
    async def testLecture(self, ctx, subject_id=None, channel_id=None, role_id=0, stream_url=None):
        """
        Test the embed message for starting lectures
        Permissions: Owner
        """
        # Input/Error catching
        if channel_id is None:
            await ctx.send("ERROR! Not enough parameters: `$testLecture <subjectID> <channelID> [streamURL] [roleID to ping]`")
            raise discord.ext.commands.CommandError
        try:
            channel = self.bot.get_channel(int(channel_id))
            channel_id = int(channel_id)
        except ValueError:
            await ctx.send("ERROR! `channel_id` needs to be an integer")
            raise discord.ext.commands.CommandError
        if channel is None:
            await ctx.send("ERROR! Can't retreive channel with that channel ID")
            raise discord.ext.commands.CommandError

        c = self.conn.cursor()
        c.execute("SELECT SubjectID, SubjectName, SubjectLink FROM Subjects WHERE SubjectID=? LIMIT 1", (subject_id,))
        subject = c.fetchone()
        if subject is None:
            await ctx.send("ERROR! That SubjectID does not exist in the DB")
            raise discord.ext.commands.CommandError
        try:
            await self.send_lecture_start(subject[1], subject[2], stream_url, channel_id=channel_id, role_id=role_id)
        except Exception as e:
            await ctx.send(f"ERROR! Can't send embed message:\n`{e}`")

    def get_starting_subject(self, semester=2):
        c = self.conn.cursor()
        sql = """   SELECT WD.SubjectID, S.SubjectName, S.SubjectLink, WD.StreamLink, WD.ZoomLink, WD.OnSiteLocation
                    FROM WeekDayTimes WD
                    INNER JOIN Subjects S on WD.SubjectID=S.SubjectID
                    WHERE WD.DayID=? AND WD.TimeFROM=? AND S.SubjectSemester=?"""
        day = datetime.now().weekday()
        hour = datetime.now().hour
        c.execute(sql, (day, hour, semester))
        row = c.fetchone()
        if row is None:
            return None
        return {"SubjectID": row[0], "SubjectName": row[1], "SubjectLink": row[2], "StreamLink": row[3], "ZoomLink": row[4], "OnSiteLocation": row[5]}

    async def send_lecture_start(self, subject_name, website_url, stream_url, channel_id, role_id, zoom_url=None, subject_room=None):
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            raise discord.ext.commands.CommandError("Invalid ChannelID")
        embed = await create_lecture_embed(subject_name, stream_url, zoom_url, website_url, subject_room)
        ping_msg = f"<@&{role_id}>"
        if role_id == 0:
            ping_msg = ""
        await channel.send(ping_msg, embed=embed)

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
                            user = self.bot.get_user(self.bot.owner_id)
                            await user.send(f"Lesson: {lesson}\nError: KeyError\nChanges: `{changes}`")
                        if correct_changes["event"] == "other":
                            embed = discord.Embed(title=f"{lesson} has been changed!",
                                                  description=f"[Click here to get to {lesson}'s website]({lecture_urls[lesson]}).",
                                                  timestamp=datetime.utcfromtimestamp(time.time()), color=color)
                            if self.send_message_to_finn:
                                users = [self.bot.owner_id, 304014259975880704]  # 304014259975880704
                            else:
                                users = [self.bot.owner_id]
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
                            if send_ping:
                                msg = await channel.send("<@&759615935496847412>", embed=embed)
                            else:
                                msg = await channel.send(embed=embed)
                            await msg.publish()
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
                                msg = await channel.send("<@&759615935496847412>", embed=embed)
                            else:
                                msg = await channel.send(embed=embed)
                            await msg.publish()
                            send_ping = False
            except Exception:
                user = self.bot.get_user(self.bot.owner_id)
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

    def all_times(self, schedule):
        times = []
        for subject in self.schedule:
            for time_text in self.schedule[subject]:
                times.append(time_text)
        return times


def setup(bot):
    bot.add_cog(Updates(bot))
