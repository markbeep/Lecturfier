import discord
from discord.ext import commands
from datetime import datetime

from discord.ext.commands import has_permissions
from pytz import timezone
import psutil
import time
import random
import string
import hashlib
from helper.lecture_scraper import scraper_test
from discord.ext.commands.cooldowns import BucketType
from helper import handySQL
from calendar import monthrange
import asyncio


def get_formatted_time(rem):
    if rem < 0:
        return f"*Passed*"
    if rem < 3600:
        return f"{round(rem / 60)} minutes"
    if rem < 86400:
        hours = rem // 3600
        return f"{int(hours)} hours {get_formatted_time(rem - hours * 3600)}"
    days = rem // 86400
    return f"{int(days)} days {get_formatted_time(rem - days * 86400)}"


def format_input_date(date, time_inp):
    # Splits the date either on . or -
    res = date.split(".")
    if len(res) < 3:
        res = date.split("-")
    if len(res) < 3:
        return False
    date_dict = {}
    try:
        date_dict["day"] = int(res[0])
        date_dict["month"] = int(res[1])
        date_dict["year"] = int(res[2])
        if not is_valid_date(date_dict, time_inp):
            return False
        return date_dict
    except ValueError:
        return False


def is_valid_date(date, time_inp):
    # checks if a date hasnt passed yet
    cur_year = datetime.now().year
    cur_month = datetime.now().month
    cur_day = datetime.now().day
    if date["year"] < cur_year:
        # Year is passed
        if cur_year + 5 >= date["year"] + 2000 >= cur_year:
            date["year"] = date["year"]+2000
        else:
            return False
    if date["year"] == cur_year:
        if date["month"] < cur_month or date["month"] > 12:
            return False
        if date["month"] == cur_month:
            try:
                max_days = monthrange(date["year"], date["month"])[1]
            except ValueError:
                return False
            if date["day"] == cur_day:
                if not format_input_time(time_inp):
                    return False
            if date["day"] < cur_day > max_days:
                return False
    if date["year"] > cur_year + 5:
        return False
    return True


def format_input_time(time_inp):
    # Splits the time on :
    res = time_inp.split(":")
    if len(res) < 2:
        return False
    time_dict = {}
    try:
        time_dict["hour"] = int(res[0])
        time_dict["minute"] = int(res[1])
        if is_valid_time(time_dict):
            return time_dict
        return False
    except ValueError:
        return False


def is_valid_time(time_dict):
    # checks if a time hasnt passed yet
    cur_hour = datetime.now().hour
    cur_minute = datetime.now().minute
    if 0 <= time_dict["hour"] < 24 and 0 <= time_dict["minute"] < 60:
        if time_dict["hour"] == cur_hour:
            return cur_minute < time_dict["minute"]
        return True
    return False


def starting_in(string_date):
    dt = datetime.strptime(string_date, "%Y-%m-%d %H:%M:%S")
    delta = dt - datetime.now()
    return get_formatted_time(delta.total_seconds())


def add_event_fields(embed, ID, name, host, joined_users, date, start, created, desc):
    """
    Adds all the necessary fields to an embed message for a specific event
    :param embed:
    :param ID:
    :param name:
    :param host:
    :param joined_users:
    :param date:
    :param start:
    :param created:
    :param desc:
    :return:
    """
    embed.add_field(name="**Event ID**", value=ID)
    embed.add_field(name="Event Name", value=name)
    embed.add_field(name="Host", value=f"<@{host}>")
    embed.add_field(name="Joined Users", value=joined_users)
    embed.add_field(name="Event Date", value=format_date_string(date))
    embed.add_field(name="Starting in", value=starting_in(start))
    embed.add_field(name="Created", value=format_date_string(created))
    embed.add_field(name="Event Description", value=desc)


def format_date_string(dt):
    return datetime.strptime(str(dt), "%Y-%m-%d %H:%M:%S").strftime("%H:%M on %d.%b %Y")


def get_event_details(c, event_id, guild_id=None):
    # guild_id is only given if its important to limit events to a guild
    if guild_id is not None:
        sql = """   SELECT E.EventName, E.EventCreatedAt, E.EventStartingAt, E.EventDescription, DM.DiscordUserID, E.EventID, E.UpdatedMessageID, E.UpdatedChannelID
                    FROM Events E
                    INNER JOIN DiscordMembers DM on E.UniqueMemberID = DM.UniqueMemberID
                    WHERE E.EventID=? AND DM.DiscordGuildID=?"""
        c.execute(sql, (event_id, guild_id))
    else:
        sql = """   SELECT E.EventName, E.EventCreatedAt, E.EventStartingAt, E.EventDescription, DM.DiscordUserID, E.EventID, E.UpdatedMessageID, E.UpdatedChannelID
                    FROM Events E
                    INNER JOIN DiscordMembers DM on E.UniqueMemberID = DM.UniqueMemberID
                    WHERE E.EventID=?"""
        c.execute(sql, (event_id,))
    res = c.fetchone()
    return res


def create_event_embed(c, res):
    # Creates joined user table
    sql = """   SELECT D.DiscordUserID
                FROM EventJoinedUsers E 
                INNER JOIN DiscordMembers D on D.UniqueMemberID = E.UniqueMemberID
                WHERE E.EventID=?"""
    c.execute(sql, (res[5],))
    users = c.fetchall()
    joined_users_msg = f"Total: {len(users)}"
    counter = 1
    for row in users:
        if counter > 5:
            joined_users_msg += "\n> . . ."
            break
        joined_users_msg += f"\n> <@{row[0]}>"
        counter += 1

    # Creates and returns the embed message
    embed = discord.Embed(title="Updating Event View", color=0xFCF4A3)
    embed.set_footer(text=f"Join this event with $event join {res[5]}")
    add_event_fields(embed, res[5], res[0], res[4], joined_users_msg, res[2], res[2], res[1], res[3])
    return embed


async def check_join_leave_condition(c, command, conn, ctx, event_name, guild_id):
    """
    Used for the event join and leave commands to check whether the event exists and there only exists one result
    """
    if event_name is None:
        await ctx.send(
            f"ERROR! {ctx.message.author.mention}, you did not specify what event to {command}. Check `$help event` to get more "
            f"info about the event command.", delete_after=10)
        await ctx.message.delete(delay=10)
        raise discord.ext.commands.errors.BadArgument
    sql = """   SELECT E.EventID, E.EventName
                FROM Events E
                INNER JOIN DiscordMembers D on D.UniqueMemberID = E.UniqueMemberID
                WHERE (E.EventName LIKE ? OR E.EventID=?) AND D.DiscordGuildID=? AND E.IsDone=0"""
    c.execute(sql, (f"%{event_name}%", event_name, guild_id))
    event_result = c.fetchall()
    if len(event_result) == 0:
        await ctx.send(f"ERROR! {ctx.message.author.mention}, could not find an upcoming event with that name/ID.", delete_after=10)
        await ctx.message.delete(delay=10)
        raise discord.ext.commands.errors.BadArgument
    event_result = event_result[0]
    # Checks if the user already joined the event
    uniqueID = handySQL.get_uniqueMemberID(conn, ctx.message.author.id, guild_id)
    c.execute("SELECT IsHost FROM EventJoinedUsers WHERE EventID=? AND UniqueMemberID=?", (event_result[0], uniqueID))
    res = c.fetchone()
    return event_result, res, uniqueID


class Information(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.script_start = time.time()
        self.db_path = "./data/discord.db"
        self.time_heartbeat = 0
        self.conn = handySQL.create_connection(self.db_path)
        self.task = self.bot.loop.create_task(self.background_events())

    def get_connection(self):
        """
        Retreives the current database connection
        :return: Database Connection
        """
        if self.conn is None:
            self.conn = handySQL.create_connection(self.db_path)
        c = self.conn.cursor()
        c.execute('PRAGMA foreign_keys = ON;')
        self.conn.commit()
        c.close()
        return self.conn

    def heartbeat(self):
        return self.time_heartbeat

    def get_task(self):
        return self.task

    async def background_events(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.time_heartbeat = time.time()
            await asyncio.sleep(20)
            conn = self.get_connection()
            c = conn.cursor()

            # iterates through all update messages
            c.execute("SELECT EventID, UpdatedMessageID, UpdatedChannelID, EventStartingAt FROM Events WHERE IsDone=0")
            result = c.fetchall()
            dt = str(datetime.now(timezone("Europe/Zurich")))
            for row in result:
                if row[1] is not None and row[2] is not None:
                    try:
                        # updates the event message
                        channel = self.bot.get_channel(int(row[2]))
                        msg = await channel.fetch_message(int(row[1]))
                        res = get_event_details(c, row[0], channel.guild.id)
                        embed = create_event_embed(c, res)
                        await msg.edit(embed=embed)
                    except discord.NotFound:
                        continue

                # ping users if event starts
                if row[3] < dt:
                    # gets the users to ping
                    sql = """   SELECT D.DiscordUserID
                                FROM EventJoinedUsers E 
                                INNER JOIN DiscordMembers D on D.UniqueMemberID = E.UniqueMemberID
                                WHERE E.EventID=?"""
                    c.execute(sql, (row[0],))
                    result = c.fetchall()

                    # creates the embed for the starting event
                    # E.EventName, E.EventCreatedAt, E.EventStartingAt, E.EventDescription, DM.DiscordUserID, E.EventID, E.UpdatedMessageID, E.UpdatedChannelID
                    event_res = get_event_details(c, row[0])
                    embed = discord.Embed(
                        title="Event Starting!",
                        description=f"`{event_res[0]}` is starting! Here just a few details of the event:",
                        color=0xFCF4A3)
                    embed.add_field(name="Event ID", value=row[0])
                    embed.add_field(name="Host", value=f"<@{event_res[4]}>")
                    embed.add_field(name="Description", value=event_res[3])

                    for user_row in result:
                        user = self.bot.get_user(user_row[0])
                        if user is None:
                            print(f"Did not find user with ID {user_row[0]}")
                            continue
                        try:
                            await user.send(embed=embed)
                        except discord.Forbidden:
                            print(f"Can't dm {user.name}")

            # Marks all older events as done
            c.execute("Update Events SET IsDone=1 WHERE EventStartingAt < ?", (dt,))
            conn.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        self.script_start = time.time()

    @commands.cooldown(2, 10, BucketType.user)
    @commands.command(aliases=["terms"], usage="$terminology [word]")
    async def terminology(self, ctx, word=None):
        """
        Fetches the terms from the PPROG site. This command has been neglected \
        as it barely serves a purpose.
        """
        async with ctx.typing():
            terms = await scraper_test.terminology()
            if word is None:
                embed = discord.Embed(title="PPROG Terminology")
                cont = ""
                for key in terms.keys():
                    cont += f"**- {key}:** {terms[key]}\n"
                if len(cont) > 2000:
                    index = cont.rindex("\n", 0, 1900)
                    cont = cont[0:index]
                    cont += "\n..."
                embed.description = cont
                embed.set_footer(text="URL=https://cgl.ethz.ch/teaching/parallelprog21/pages/terminology.html")
                await ctx.send(embed=embed)
            else:
                if word in terms.keys():
                    cont = f"**{word}**:\n{terms[word]}"
                    embed = discord.Embed(title="PPROG Terminology", description=cont)
                    embed.set_footer(text="URL=https://cgl.ethz.ch/teaching/parallelprog21/pages/terminology.html")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("Couldn't find word. soz...")

    @commands.cooldown(4, 10, BucketType.user)
    @commands.command(usage="guild")
    async def guild(self, ctx):
        """
        Used to display information about the server.
        """
        guild = ctx.message.guild
        embed = discord.Embed(title=f"Guild Statistics", color=discord.colour.Color.dark_blue())
        embed.add_field(name="Categories", value=f"Server Name:\n"
                                                 f"Server ID:\n"
                                                 f"Member Count:\n"
                                                 f"Categories:\n"
                                                 f"Text Channels:\n"
                                                 f"Voice Channels:\n"
                                                 f"Emoji Count / Max emojis:\n"
                                                 f"Owner:\n"
                                                 f"Roles:")
        embed.add_field(name="Values", value=f"{guild.name}\n"
                                             f"{guild.id}\n"
                                             f"{guild.member_count}\n"
                                             f"{len(guild.categories)}\n"
                                             f"{len(guild.text_channels)}\n"
                                             f"{len(guild.voice_channels)}\n"
                                             f"{len(guild.emojis)} / {guild.emoji_limit}\n"
                                             f"{guild.owner.mention}\n"
                                             f"{len(guild.roles)}")
        await ctx.send(embed=embed)

    @commands.cooldown(4, 10, BucketType.user)
    @commands.command(aliases=["source", "code"], usage="info")
    async def info(self, ctx):
        """
        Sends some info about the bot.
        """
        async with ctx.typing():
            b_time = time_up(time.time() - self.script_start)  # uptime of the script
            s_time = time_up(seconds_elapsed())  # uptime of the pc
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory()

            cont = f"**Instance uptime: **`{b_time}`\n" \
                   f"**Computer uptime: **`{s_time}`\n" \
                   f"**CPU: **`{round(cpu)}%` | **RAM: **`{round(ram.percent)}%`\n" \
                   f"**Discord.py Version:** `{discord.__version__}`\n" \
                   f"**Bot source code:** [Click here for source code](https://github.com/markbeep/Lecturfier)"
            embed = discord.Embed(title="Bot Information:", description=cont, color=0xD7D7D7,
                                  timestamp=datetime.now(timezone("Europe/Zurich")))
            embed.set_footer(text=f"Called by {ctx.author.display_name}")
            embed.set_thumbnail(url=self.bot.user.avatar_url)
            embed.set_author(name=self.bot.user.display_name, icon_url=self.bot.user.avatar_url)
        await ctx.send(embed=embed)

    @commands.cooldown(4, 10, BucketType.user)
    @commands.command(usage="token")
    async def token(self, ctx):
        """
        Sends a bot token.
        """
        token = random_string(24) + "." + random_string(6) + "." + random_string(27)
        embed = discord.Embed(title="Bot Token", description=f"||`{token}`||")
        await ctx.send(embed=embed)

    @commands.cooldown(4, 10, BucketType.user)
    @commands.command(aliases=["pong", "ding", "pingpong"], usage="ping")
    async def ping(self, ctx):
        """
        Check the ping of the bot
        """
        title = "Pong!"
        if "pong" in ctx.message.content.lower():
            title = "Ping!"
        if "pong" in ctx.message.content.lower() and "ping" in ctx.message.content.lower():
            title = "Ding?"
        if "ding" in ctx.message.content.lower():
            title = "*slap!*"

        embed = discord.Embed(
            title=f"{title} 🏓",
            description=f"🌐 Ping: \n"
                        f"❤ HEARTBEAT:")

        start = time.perf_counter()
        ping = await ctx.send(embed=embed)
        end = time.perf_counter()
        embed = discord.Embed(
            title=f"{title} 🏓",
            description=f"🌐 Ping: `{round((end - start) * 1000)}` ms\n"
                        f"❤ HEARTBEAT: `{round(self.bot.latency * 1000)}` ms")
        await ping.edit(embed=embed)

    @commands.cooldown(4, 10, BucketType.user)
    @commands.command(aliases=["cypher"], usage="cipher <amount to displace> <msg>")
    async def cipher(self, ctx, amount=None, *msg):
        """
        This is Caesar's cipher, but instead of only using the alphabet, it uses all printable characters.
        Negative values are allowed and can be used to decipher messages.
        """
        printable = list(string.printable)
        printable = printable[0:-5]
        if len(msg) == 0:
            await ctx.send("No message specified.")
            raise discord.ext.commands.errors.BadArgument
        try:
            amount = int(amount)
        except ValueError:
            await ctx.send("Amount is not an int.")
            raise discord.ext.commands.errors.BadArgument
        msg = " ".join(msg)
        encoded_msg = ""
        amount = amount % len(printable)
        for letter in msg:
            index = printable.index(letter) + amount
            if index >= len(printable) - 1:
                index = index - (len(printable))
            encoded_msg += printable[index]

        await ctx.send(f"```{encoded_msg}```")

    @commands.cooldown(4, 10, BucketType.user)
    @commands.command(usage="hash <OpenSSL algo> <msg>")
    async def hash(self, ctx, algo=None, *msg):
        """
        Hash a message using an OpenSSL algorithm (sha256 for example).
        """
        if algo is None:
            await ctx.send("No Algorithm given. `$hash <OPENSSL algo> <msg>`")
            raise discord.ext.commands.errors.BadArgument
        try:
            joined_msg = " ".join(msg)
            msg = joined_msg.encode('UTF-8')
            h = hashlib.new(algo)
            h.update(msg)
            output = h.hexdigest()
            embed = discord.Embed(
                title=f"**Hashed message using {algo.lower()}**",
                colour=0x000000
            )
            embed.add_field(name="Input:", value=f"{joined_msg}", inline=False)
            embed.add_field(name="Output:", value=f"`{output}`", inline=False)
            await ctx.send(embed=embed)
        except ValueError:
            await ctx.send("Invalid hash type. Most OpenSSL algorithms are supported. Usage: `$hash <hash algo> <msg>`")
            raise discord.ext.commands.errors.BadArgument

    @commands.group(aliases=["events"], usage="event [add/view/edit/delete/join/leave] [event name/event ID] [date] [time] [description]", invoke_without_command=True)
    async def event(self, ctx, command=None):
        """
        The event command is used to keep track of upcoming events. Each user can add a maximum of two events.

        Command specific help pages have been moved to their own pages with viewable with `{prefix}event <subcommand>`.
        """
        conn = self.get_connection()
        c = conn.cursor()
        try:
            guild_id = ctx.message.guild.id
            guild_name = ctx.message.guild.name
        except AttributeError:
            guild_id = 0
            guild_name = "Direct Message"

        if command is None:
            # list all upcoming events sorted by upcoming order
            sql = """   SELECT E.EventName, E.EventStartingAt, E.EventID
                        FROM Events E
                        INNER JOIN DiscordMembers DM on DM.UniqueMemberID = E.UniqueMemberID
                        WHERE DM.DiscordGuildID=? AND IsDone=0
                        ORDER BY E.EventStartingAt"""
            c.execute(sql, (guild_id,))
            results = c.fetchall()
            i = 0
            embed = discord.Embed(title=f"Upcoming Events On {guild_name}", color=0xFCF4A3)
            embed.set_footer(text="$event view <ID> to get more details about an event")
            for e in results:
                if i == 10:
                    # a max of 10 events are shown
                    break
                dt = datetime.strptime(e[1], "%Y-%m-%d %H:%M:%S")
                form_time = starting_in(e[1])
                embed.add_field(name=f"**ID:** {e[2]}\n**Name:** {e[0]}", value=f"**At:** {dt}\n**In:** {form_time}", inline=False)
                i += 1
            if len(results) == 0:
                embed.description = "-- There are no upcoming events --"
            await ctx.send(embed=embed)
        elif ctx.invoked_subcommand is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, the command you used is not recognized. Check `$help event` to get more "
                           f"info about the event command.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

    @event.command(usage="add <event name> <date> <event time> [description]")
    async def add(self, ctx, event_name=None, date=None, event_time=None, *, event_info="*[n/a]*"):
        """
        This command is used to add custom events.

        __**Parameters:**__
        **- event name:** Required. The name of the event. If multiple words, it needs to be in quotation marks. *Maximum 50 characters.*
        **- date:** Required. The start date of the event. The format is `DD.MM.YYYY` or `DD.MM.YY` or `DD-MM-YYYY` or `DD-MM-YY`.
        **- time:** Required. The starting time of the event. The format needs to be `HH:MM`.
        **- description:** Optional. Description to describe your event in more detail (what to prepare, who to contact, etc.). *Maximum 700 characters.*

        Some examples:
        - `{prefix}event add "My Birthday" 13.03.2022 00:00 This day is my birthday hehe :)`
        - `{prefix}event add 420BlazeIt 20.4.21 4:20 Send me a dm if you wanna join this event!`
        """
        conn = self.get_connection()
        c = conn.cursor()
        try:
            guild_id = ctx.message.guild.id
        except AttributeError:
            guild_id = 0

        # check if uniquememberid already exists in db
        uniqueID = handySQL.get_uniqueMemberID(conn, ctx.message.author.id, guild_id)
        c.execute("SELECT EventName FROM Events WHERE UniqueMemberID=? AND IsDone=0", (uniqueID,))
        result = c.fetchall()
        if len(result) < 2:
            # add the event to the db
            # Make sure the inputs are correct
            if event_name is None or date is None or event_time is None:
                await ctx.send("ERROR! Incorrect arguments given. Check `$help event` to get more "
                               f"info about the event command.", delete_after=10)
                await ctx.message.delete(delay=10)
                raise discord.ext.commands.errors.BadArgument
            date = format_input_date(date, event_time)
            if not date:
                await ctx.send(
                    "ERROR! Incorrect date format given or date is passed. Should be `DD.MM.YYYY` or `DD-MM-YYYY`. Check `$help event` to get more "
                    f"info about the event command. Event has to start minimum the next minute.", delete_after=10)
                await ctx.message.delete(delay=10)
                raise discord.ext.commands.errors.BadArgument
            event_time = format_input_time(event_time)
            if not event_time:
                await ctx.send("ERROR! Incorrect time format given. Should be `HH:MM`. Check `$help event` to get more "
                               f"info about the event command.", delete_after=10)
                await ctx.message.delete(delay=10)
                raise discord.ext.commands.errors.BadArgument
            # Adds the entry to the sql db
            event_description = event_info
            if len(event_description) > 700:
                event_description = event_description[0: 700] + "..."
            if len(event_name) > 50:
                event_name = event_name[0: 50] + "..."

            try:
                dt = datetime(date["year"], date["month"], date["day"], event_time["hour"], event_time["minute"])
            except ValueError:
                await ctx.send(
                    "ERROR! Incorrect date format given or date is passed. Should be `DD.MM.YYYY` or `DD-MM-YYYY`. Check `$help event` to get more "
                    f"info about the event command.", delete_after=10)
                await ctx.message.delete(delay=10)
                raise discord.ext.commands.errors.BadArgument

            # Inserts event into event database
            c.execute("INSERT INTO Events(EventName, EventCreatedAt, EventStartingAt, EventDescription, UniqueMemberID) VALUES (?,?,?,?,?)",
                      (event_name, str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")), str(dt), event_description, uniqueID))
            conn.commit()

            # Inserts user as host to EventJoinedUsers for the newly added event
            row_id = c.lastrowid
            c.execute("SELECT EventID FROM Events WHERE ROWID=?", (row_id,))
            event_id = c.fetchone()[0]
            c.execute("INSERT INTO EventJoinedUsers(EventID, UniqueMemberID, IsHost) VALUES (?,?,?)", (event_id, uniqueID, 1))
            conn.commit()

            # Creates and sends the embed message
            embed = discord.Embed(title="Added New Event", color=0xFCF4A3)
            embed.add_field(name="Event ID", value=event_id)
            embed.add_field(name="Event Name", value=event_name, inline=False)
            embed.add_field(name="Event Host", value=ctx.message.author.mention, inline=False)
            embed.add_field(name="Event Date", value=format_date_string(dt), inline=False)
            embed.add_field(name="Event Description", value=event_description, inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("ERROR! Each member can only add **two** events. (Might get changed in the future)", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

    @event.command(usage="view <event name / ID>")
    async def view(self, ctx, event_name=None):
        """
        View existing events with more detail using this command.

        The event name parameter can either be a search term (meaning all fitting events will be displayed) or \
        a specific event ID to only show a single event. If multiple events are shown, they are ordered so that \
        events closest to starting are at the top.
        """
        conn = self.get_connection()
        c = conn.cursor()
        try:
            guild_id = ctx.message.guild.id
        except AttributeError:
            guild_id = 0

        if event_name is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you did not specify what event to view. Check `$help event` to get more "
                           f"info about the event command.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        else:
            try:
                # checks if the inputted value is an integer and maby an eventID
                int(event_name)
                sql = """   SELECT E.EventName, E.EventCreatedAt, E.EventStartingAt, E.EventDescription, DM.DiscordUserID, E.EventID
                            FROM Events E
                            INNER JOIN DiscordMembers DM on E.UniqueMemberID = DM.UniqueMemberID
                            WHERE E.EventID=? AND DM.DiscordGuildID=?
                            ORDER BY IsDone, E.EventStartingAt"""
                c.execute(sql, (event_name, guild_id))
                results = c.fetchall()
                if len(results) == 0:
                    raise ValueError
            except ValueError:
                sql = """   SELECT E.EventName, E.EventCreatedAt, E.EventStartingAt, E.EventDescription, DM.DiscordUserID, E.EventID
                            FROM Events E
                            INNER JOIN DiscordMembers DM on E.UniqueMemberID = DM.UniqueMemberID
                            WHERE E.EventName LIKE ? AND DM.DiscordGuildID=?
                            ORDER BY IsDone, E.EventStartingAt"""
                c.execute(sql, (f"%{event_name}%", guild_id))
                results = c.fetchall()
            if len(results) == 0:
                await ctx.send("ERROR! There is no event with a similar name. Simply type `$event` to get a list of upcoming events.",
                               delete_after=10)
                await ctx.message.delete(delay=10)
                raise discord.ext.commands.errors.BadArgument
            embed = discord.Embed(title="Indepth Event View", color=0xFCF4A3)
            embed.set_footer(text="Join an event with $event join <ID>")
            if len(results) > 2:
                embed.add_field(name="NOTICE",
                                value="*There are more than 2 matches with that event name. Only showing the two closest matching events.*",
                                inline=False)
                embed.add_field(name="\u200b", value="``` ```", inline=False)
            i = 1
            MAX_EVENTS = 2  # max amount of events to send per view command
            for e in results:
                # creates a list of all joined members
                sql = """   SELECT D.DiscordUserID
                            FROM EventJoinedUsers E 
                            INNER JOIN DiscordMembers D on D.UniqueMemberID = E.UniqueMemberID
                            WHERE E.EventID=?"""
                c.execute(sql, (e[5],))
                res = c.fetchall()
                joined_users_msg = f"Total: {len(res)}"
                counter = 1
                for row in res:
                    joined_users_msg += f"\n> <@{row[0]}>"
                    if counter >= 5:
                        joined_users_msg += "\n> . . ."
                        break
                    counter += 1

                # Adds the fields to an event
                add_event_fields(embed, e[5], e[0], e[4], joined_users_msg, e[2], e[2], e[1], e[3])

                # if not last field, add a spacer
                if i < MAX_EVENTS and i < len(results):
                    embed.add_field(name="\u200b", value="``` ```", inline=False)
                i += 1
                if i > MAX_EVENTS:
                    break
            await ctx.send(embed=embed)

    @event.command(usage="delete <event ID>")
    async def delete(self, ctx, event_name=None):
        """
        Delete your own events using this command.

        Event ID has to be a valid ID of one of your own events. You cannot delete \
        other people's events.
        """
        conn = self.get_connection()
        c = conn.cursor()
        try:
            guild_id = ctx.message.guild.id
        except AttributeError:
            guild_id = 0

        # delete the entry
        uniqueID = handySQL.get_uniqueMemberID(conn, ctx.message.author.id, guild_id)
        if event_name is None:
            event_name = ""
        c.execute("SELECT EventName FROM Events WHERE UniqueMemberID=? AND EventID = ?", (uniqueID, event_name))
        result = c.fetchall()
        if len(result) == 0:
            await ctx.send(f"ERROR! No event found with the ID `{event_name}` which you are the host of.")
            raise discord.ext.commands.errors.BadArgument
        c.execute("DELETE FROM Events WHERE UniqueMemberID=? AND EventID=?", (uniqueID, event_name))
        conn.commit()
        embed = discord.Embed(title="Deleted Event",
                              description=f"**Name of deleted event:** {result[0][0]}\n"
                                          f"**Event host:** {ctx.message.author.mention}",
                              color=0xFCF4A3)
        await ctx.send(embed=embed)

    @event.command(usage="join <event name / ID>")
    async def join(self, ctx, event_name=None):
        """
        Joins an event using the event name or ID.
        When joining with the event name the first matching event is chosen. \
        To make sure you join the right event, use the ID.

        Examples:
        - `{prefix}event join 420BlazeIt`
        - `{prefix}event join 42`
        """
        conn = self.get_connection()
        c = conn.cursor()
        try:
            guild_id = ctx.message.guild.id
        except AttributeError:
            guild_id = 0

        event_result, res, uniqueID = await check_join_leave_condition(c, "join", conn, ctx, event_name, guild_id)

        # Joining part
        if res is not None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you already joined the event `{event_result[1]}`.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        # Joins the user to the event
        c.execute("INSERT INTO EventJoinedUsers(EventID, UniqueMemberID) VALUES (?,?)", (event_result[0], uniqueID))
        conn.commit()
        embed = discord.Embed(
            title="Joined Event",
            description=f"Added {ctx.message.author.mention} to event `{event_result[1]}`."
                        f"You can leave the event with `$event leave {event_result[0]}`",
            color=0xFCF4A3)
        await ctx.send(embed=embed)

    @event.command(usage="leave <event name / ID>")
    async def leave(self, ctx, event_name=None):
        """
        Leaves an event using the event name or ID.
        When leaving with the event name the first matching event is chosen. \
        To make sure you leave the right event, use the ID.

        Examples:
        - `{prefix}event leave 420BlazeIt`
        - `{prefix}event leave 42`
        """
        conn = self.get_connection()
        c = conn.cursor()
        try:
            guild_id = ctx.message.guild.id
        except AttributeError:
            guild_id = 0

        event_result, res, uniqueID = await check_join_leave_condition(c, "leave", conn, ctx, event_name, guild_id)

        # Leaving part
        if res is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you can't leave an event you haven't even joined yet. "
                           f"The event in question: `{event_result[1]}`.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        # Removes the user from that event
        c.execute("DELETE FROM EventJoinedUsers WHERE EventID=? AND UniqueMemberID=?", (event_result[0], uniqueID))
        conn.commit()

        embed = discord.Embed(
            title="Left Event",
            description=f"Removed {ctx.message.author.mention} from event `{event_result[1]}`."
                        f"You can rejoin the event with `$event join {event_result[0]}`",
            color=0xffa500)
        await ctx.send(embed=embed)

    @event.command(usage="update <event ID>")
    @has_permissions(kick_members=True)
    async def update(self, ctx, event_name=None):
        """
        Creates an updating event message, which constantly gets updated with \
        the joined members and the remaining time to start.

        There can only be a single updated message for each event. If the command \
        is called again, the older message will simply be deleted.

        Permissions: kick_members
        """
        conn = self.get_connection()
        c = conn.cursor()
        try:
            guild_id = ctx.message.guild.id
        except AttributeError:
            guild_id = 0

        # Sends a message that gets update
        if guild_id == 0:
            await ctx.send("Can't send an updating event messagee in direct messages.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        if event_name is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you did not specify what event to create an updating message for.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        # Checks if the Event exists
        res = get_event_details(c, event_name, guild_id)
        if res is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, could not find an event with that ID.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        # Checks if there already exists an updating message, if there does, deletes old one
        if res[6] is not None:
            try:
                channel = self.bot.get_channel(int(res[7]))
                msg_to_delete = await channel.fetch_message(int(res[6]))
                await msg_to_delete.delete()
            except discord.NotFound:
                pass

        # Creates embed and sends the message
        embed = create_event_embed(c, res)
        msg = await ctx.send(embed=embed)

        c.execute("UPDATE Events SET UpdatedMessageID=?, UpdatedChannelID=? WHERE EventID=?", (msg.id, msg.channel.id, event_name))
        conn.commit()
        await ctx.send("Successfully added updating event to DB.", delete_after=3)
        await ctx.message.delete()


def setup(bot):
    bot.add_cog(Information(bot))


def time_up(t):
    if t <= 60:
        return f"{int(t)} seconds"
    elif 3600 > t > 60:
        minutes = t // 60
        seconds = t % 60
        return f"{int(minutes)} minutes and {int(seconds)} seconds"
    elif t >= 3600:
        hours = t // 3600  # Seconds divided by 3600 gives amount of hours
        minutes = (t % 3600) // 60  # The remaining seconds are looked at to see how many minutes they make up
        seconds = (t % 3600) - minutes * 60  # Amount of minutes remaining minus the seconds the minutes "take up"
        if hours >= 24:
            days = hours // 24
            hours = hours % 24
            return f"{int(days)} days, {int(hours)} hours, {int(minutes)} minutes and {int(seconds)} seconds"
        else:
            return f"{int(hours)} hours, {int(minutes)} minutes and {int(seconds)} seconds"


def seconds_elapsed():
    now = datetime.now()
    current_timestamp = time.mktime(now.timetuple())
    return current_timestamp - psutil.boot_time()


def random_string(n):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))
