import asyncio
import time
import traceback
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from pytz import timezone

from helper.lecture_scraper.scrape import scraper
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
        self.send_message_to_finn = False
        self.lecture_updater_version = "v1.0"
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()
        self.channel_to_post = SQLFunctions.get_config("channel_to_post_updates", self.conn)
        self.background_loop.start()
        self.current_activity = ""
        self.sent_updates = {1: False, 2: False, 3: False, 4: False, 5: False, 6: False}
        self.lecture_updates_role_ids = {
            "first": 885810281358446623,
            "second": 885810349121622056,
            "third": 885810401969831978
        }
        self.sent_website_updates = False

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
            # Find out what semesters are currently going on
            # Only works for the 3 bachelor years as of now
            month = datetime.now().month
            if 9 <= month <= 12:
                semesters = [1, 3, 5]
            elif 2 <= month <= 6:
                semesters = [2, 4, 6]
            else:
                print("No subjects going on right now. So skipping the loop completely.")
                return

            # Check what lectures are starting
            dt = datetime.now(timezone("Europe/Zurich"))
            minute = dt.minute
            for sem in semesters:
                if not self.sent_updates[sem] and minute <= 5:
                    role_id = 0
                    if sem in [1, 2]:
                        role_id = self.lecture_updates_role_ids["first"]
                    elif sem in [3, 4]:
                        role_id = self.lecture_updates_role_ids["second"]
                    elif sem in [5, 6]:
                        role_id = self.lecture_updates_role_ids["third"]
                    subject = SQLFunctions.get_starting_subject(sem, self.conn, dt.weekday(), dt.hour)
                    if subject is not None:
                        await self.send_lecture_start(
                            subject_name=subject.name,
                            website_url=subject.website_link,
                            stream_url=subject.stream_link,
                            channel_id=756391202546384927,  # lecture updates channel,
                            role_id=role_id,
                            zoom_url=subject.zoom_link,
                            subject_room=subject.on_site_location
                        )
                        self.sent_updates[sem] = True
            if minute > 5:
                self.sent_updates = {1: False, 2: False, 3: False, 4: False, 5: False, 6: False}

            if not self.sent_website_updates and minute % 10 == 0:
                exercise_update_channel = self.bot.get_channel(756391202546384927)  # lecture updates channel
                if exercise_update_channel is None:
                    exercise_update_channel = self.bot.get_channel(402563165247766528)  # channel on bot testing server
                if exercise_update_channel is not None:
                    await self.check_updates(exercise_update_channel, self.lecture_updater_version)
                self.sent_website_updates = True
            elif minute % 10 != 0:
                self.sent_website_updates = False

        except AttributeError as e:
            print(f"ERROR in Lecture Updates Loop! Probably wrong channel ID | {e}")
        except Exception:
            await asyncio.sleep(10)
            user = self.bot.get_user(self.bot.owner_id)
            await user.send(f"Error in background loop: {traceback.format_exc()}")
            log(f"Error in background loop self.bot.py: {traceback.format_exc()}", "BACKGROUND")

    @commands.is_owner()
    @commands.command(usage="testLecture <semester> <day> <hour> [role ID to ping]")
    async def testLecture(self, ctx, semester=None, day=None, hour=None, role_id=0):
        """
        Test the embed message for starting lectures
        Permissions: Owner
        """
        # Input/Error catching
        if day is None or hour is None:
            await ctx.reply("ERROR! Not enough parameters. You need `<semester> <day> <hour> [role ID to ping]`.")
            raise discord.ext.commands.CommandError
        try:
            semester = int(semester)
            day = int(day)
            hour = int(hour)
        except ValueError:
            await ctx.reply("ERROR! Semester, day and hour need to be integers.")
            raise discord.ext.commands.BadArgument

        subject: SQLFunctions.Subject = SQLFunctions.get_starting_subject(semester, self.conn, day, hour)
        if subject is None:
            await ctx.reply("No subject starting at that time.")
            return
        try:
            await self.send_lecture_start(
                subject_name=subject.name,
                website_url=subject.website_link,
                stream_url=subject.stream_link,
                channel_id=756391202546384927,  # lecture updates channel,
                role_id=role_id,
                zoom_url=subject.zoom_link,
                subject_room=subject.on_site_location
            )
        except Exception as e:
            await ctx.reply(f"ERROR! Can't send embed message:\n`{e}`")

    @commands.is_owner()
    @commands.command(usage="addLecture", aliases=["addlecture"])
    async def addLecture(self, ctx):
        """
        Allows the addition of new lecture times to the databse with a guided system.
        Permissions: Owner
        """
        await ctx.reply("What is the subject full name? Type `stop` anytime to cancel the adding of the lecture.")

        def check(m):
            return m.author == ctx.message.author and m.channel == ctx.channel

        try:
            msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=30)
            if msg.content.lower() == "stop":
                await ctx.reply("Adding subject canceled.")
                return
            subject_name = msg.content

            await msg.reply("What is the subject abbreviation?")
            msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=30)
            if msg.content.lower() == "stop":
                await ctx.reply("Adding subject canceled.")
                return
            subject_abbreviation = msg.content

            for i in range(5):
                await msg.reply("What semester is the subject in?")
                msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=30)
                if msg.content.lower() == "stop":
                    await ctx.reply("Adding subject canceled.")
                    return
                try:
                    subject_semester = int(msg.content)
                    break
                except ValueError:
                    await msg.reply(f"The given value is not an integer. {5-i-1} retries remaining:")
            else:
                await ctx.reply("Adding subject canceled.")
                return

            await msg.reply("What is the subject website link? `-` or `0` to skip.")
            msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=30)
            if msg.content.lower() == "stop":
                await ctx.reply("Adding subject canceled.")
                return
            subject_website = msg.content
            if msg.content in ["-", "0"]:
                subject_website = None

            for i in range(5):
                await msg.reply("What days is the lecture on? Separated by **space** and using integers. Any numbers under 0 or above 6 are ignored."
                                "\n```\nMonday: 0\nTuesday: 1\nWednesday: 2\nThursday: 3\nFriday: 4```")
                msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=30)
                if msg.content.lower() == "stop":
                    await ctx.reply("Adding subject canceled.")
                    return
                try:
                    subject_days = [int(x) for x in msg.content.split(" ") if x != "" and 0 <= int(x) <= 6]
                    break
                except ValueError:
                    await msg.reply(f"The given values are not all integers. {5 - i - 1} retries remaining:")
            else:
                await ctx.reply("Adding subject canceled.")
                return

            weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            subject_times = []
            for day in subject_days:
                for i in range(5):
                    try:
                        # Starting time of lecture
                        await msg.reply(f"At what hour does the lecture start on {weekday_names[day]}?")
                        msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=30)
                        if msg.content.lower() == "stop":
                            await ctx.reply("Adding subject canceled.")
                            return
                        hour_start = int(msg.content)

                        # Ending time of lecture
                        await msg.reply(f"At what hour does the lecture end on {weekday_names[day]}?")
                        msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=30)
                        if msg.content.lower() == "stop":
                            await ctx.reply("Adding subject canceled.")
                            return
                        hour_end = int(msg.content)
                    except ValueError:
                        await msg.reply(f"The given value is not an integer. Restarting questions for this day. {5 - i - 1} retries remaining:")
                        continue

                    # Zoom link
                    await msg.reply("What is the subject zoom link? `-` or `0` to skip.")
                    msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=30)
                    if msg.content.lower() == "stop":
                        await ctx.reply("Adding subject canceled.")
                        return
                    zoom_link = msg.content
                    if msg.content.lower() in ["-", "0"]:
                        zoom_link = None

                    # Stream Link
                    await msg.reply("What is the subject stream link? `-` or `0` to skip.")
                    msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=30)
                    if msg.content.lower() == "stop":
                        await ctx.reply("Adding subject canceled.")
                        return
                    stream_link = msg.content
                    if msg.content.lower() in ["-", "0"]:
                        stream_link = None

                    # On Site location
                    await msg.reply("What is the on site location of the subject? `-` or `0` to skip.")
                    msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=30)
                    if msg.content.lower() == "stop":
                        await ctx.reply("Adding subject canceled.")
                        return
                    on_site_location = msg.content
                    if msg.content.lower() in ["-", "0"]:
                        on_site_location = None

                    subject_times.append([day, hour_start, hour_end, zoom_link, stream_link, on_site_location])
                    break
                else:
                    await ctx.reply("Adding subject canceled.")
                    return

            for lecture in subject_times:
                dayID = lecture[0]
                start_hour = lecture[1]
                end_hour = lecture[2]
                zoom_link = lecture[3]
                stream_link = lecture[4]
                on_site_location = lecture[5]
                SQLFunctions.update_or_insert_weekdaytime(
                    name=subject_name,
                    abbreviation=subject_abbreviation,
                    link=subject_website,
                    zoom_link=zoom_link,
                    stream_link=stream_link,
                    on_site_location=on_site_location,
                    semester=subject_semester,
                    starting_hour=start_hour,
                    ending_hour=end_hour,
                    day=dayID,
                    conn=self.conn
                )
            await ctx.reply("Succesfully added the subject times!")

        except asyncio.TimeoutError:
            await ctx.reply("You took too long to respond. You have 30 seconds to respond.")
            raise discord.ext.commands.BadArgument

    async def send_lecture_start(self, subject_name, website_url, stream_url, channel_id, role_id, zoom_url=None, subject_room=None):
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = self.bot.get_channel(402563165247766528)  # bot testing channel
        embed = await create_lecture_embed(subject_name, stream_url, zoom_url, website_url, subject_room)
        ping_msg = f"<@&{role_id}>"
        if role_id == 0:
            ping_msg = ""
        await channel.send(ping_msg, embed=embed)

    async def check_updates(self, channel: discord.TextChannel, version):
        start = time.time()
        scraped_info = scraper()
        changes = scraped_info[0]
        lecture_urls = scraped_info[1]
        send_ping = True
        ping_msg = f"<@&{self.lecture_updates_role_ids['first']}>"
        for lesson in changes.keys():
            try:
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
                    except KeyError:
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

                    elif correct_changes["event"] == "edit":  # EDITS
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

                        msg = await channel.send(embed=embed)
                        await msg.edit(content=ping_msg)
                        try:
                            await msg.publish()
                        except discord.Forbidden:
                            pass
                        send_ping = False

                    elif correct_changes["event"] == "new":
                        log(f"{lesson} got a new update", "LESSON")
                        title = f"Something new was added on __{lesson}__"
                        description = f"""**NEW**:\n{self.format_exercise(correct_changes["content"])}"""
                        embed = discord.Embed(title=title, description=description,
                                              timestamp=datetime.utcfromtimestamp(time.time()), color=color)
                        embed.set_footer(
                            text=f"{version} | This message took {round(time.time() - start, 2)} seconds to send")
                        if send_ping:
                            msg = await channel.send(ping_msg, embed=embed)
                        else:
                            msg = await channel.send(embed=embed)
                            await msg.edit(content=ping_msg)
                        try:
                            await msg.publish()
                        except discord.Forbidden:
                            pass
                        send_ping = False

                        start = time.time()
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


def setup(bot):
    bot.add_cog(Updates(bot))
