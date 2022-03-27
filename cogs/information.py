import math
import random
import string
import time
from calendar import monthrange
from datetime import date, datetime

# AoC Imports
import aiohttp
import json
from cogs.quote import Pages
import os

import discord
import psutil
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
from discord.ext.commands.cooldowns import BucketType
from pytz import timezone

from helper.sql import SQLFunctions


def get_formatted_time(rem):
    if rem < 0:
        return f"*Passed*"
    if rem < 60:
        return f"{round(rem)} seconds"
    if rem < 3600:
        minutes = rem // 60
        return f"{int(minutes)} minutes {get_formatted_time(rem - minutes * 60)}"
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


def starting_in(dt: datetime):
    delta = dt - datetime.now()
    return get_formatted_time(delta.total_seconds())


def format_date_string(dt: datetime):
    return dt.strftime("%H:%M on %d.%b %Y")


def create_event_embed(event: SQLFunctions.Event, joined_members: list):
    # Creates joined user table
    joined_users_msg = f"Total: {len(joined_members)}"
    counter = 1
    for member in joined_members:
        if counter > 5:
            joined_users_msg += "\n> . . ."
            break
        joined_users_msg += f"\n> <@{member.DiscordUserID}>"
        counter += 1
    # Creates and returns the embed message
    embed = discord.Embed(title="Updating Event View", color=0xFCF4A3)
    embed.set_footer(text=f"Join this event with $event join {event.EventID}")
    add_event_fields(embed, event, joined_users_msg)
    return embed


def add_event_fields(embed, event, joined_users_msg):
    embed.add_field(name="**Event ID**", value=event.EventID)
    embed.add_field(name="Event Name", value=event.EventName)
    embed.add_field(name="Host", value=f"<@{event.DiscordMember.DiscordUserID}>")
    embed.add_field(name="Joined Users", value=joined_users_msg)
    embed.add_field(name="Event Date", value=format_date_string(event.EventStartingAt))
    embed.add_field(name="Starting in", value=starting_in(event.EventStartingAt))
    embed.add_field(name="Created", value=format_date_string(event.EventCreatedAt))
    embed.add_field(name="Event Description", value=event.EventDescription)


class Information(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.script_start = time.time()
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()
        self.background_events.start()
        # emote used for adding users to an event
        self.emote = "<a:greenverify:949669955413114960>"

    def heartbeat(self):
        return self.background_events.is_running()

    def get_task(self):
        return self.background_events

    @tasks.loop(seconds=20)
    async def background_events(self):
        await self.bot.wait_until_ready()
        # iterates through all events to update the event messages
        results = SQLFunctions.get_events(self.conn, is_done=False)
        current_time = datetime.now()
        for event in results:
            joined_members = SQLFunctions.get_event_joined_users(event, self.conn)
            if event.UpdatedChannelID is not None and event.UpdatedMessageID is not None:
                try:
                    # fetches the event channel and event
                    # in case of an error updating is simply skipped
                    channel = self.bot.get_channel(event.UpdatedChannelID)
                    if channel is None or channel.guild is None:  # channel is not visible to the bot or it's a private channel
                        continue
                    msg = await channel.fetch_message(event.UpdatedMessageID)
                    embed = create_event_embed(event, joined_members)
                    await msg.edit(embed=embed)
                except (discord.NotFound, discord.errors.Forbidden):
                    print(f"Have no access to the events update message for the event with ID {event.EventID}.")
                    continue
            # ping users if event starts
            if event.EventStartingAt <= current_time:
                # creates the embed for the starting event
                embed = discord.Embed(
                    title="Event Starting!",
                    description=f"`{event.EventName}` is starting! Here just a few details of the event:",
                    color=0xFCF4A3)
                embed.add_field(name="Event ID", value=event.EventID)
                embed.add_field(name="Host", value=f"<@{event.DiscordMember.DiscordUserID}>")
                embed.add_field(name="Description", value=event.EventDescription)

                for member in joined_members:
                    user = self.bot.get_user(member.DiscordUserID)
                    if user is None:
                        print(f"Did not find user with ID {member.DiscordUserID}")
                        continue
                    try:
                        await user.send(embed=embed)
                    except discord.Forbidden:
                        print(f"Can't dm {user.name}")
        # Marks all older events as done
        SQLFunctions.mark_events_done(current_time, conn=self.conn)

    @commands.Cog.listener()
    async def on_ready(self):
        self.script_start = time.time()

    async def join_leave_event(self, member, guild_id, command, message_id=None, event_id=None) -> SQLFunctions.Event:
        event_results = SQLFunctions.get_events(self.conn, guild_id=guild_id)
        for e in event_results:
            if e.UpdatedMessageID == message_id or e.EventID == event_id:
                event = e
                break
        else:  # no matching event was found otherwise
            return False
        # check if the user already joined the event
        joined_members = SQLFunctions.get_event_joined_users(event=event, conn=self.conn)
        joined = True
        for m in joined_members:
            if m.DiscordUserID == member.id:
                discord_member: SQLFunctions.DiscordMember = m
                break
        else:
            joined = False
        if command == "join" and not joined:
            # Adds the user to the event
            sql_member = SQLFunctions.get_or_create_discord_member(member)
            SQLFunctions.add_member_to_event(event, sql_member, self.conn)
        elif command == "leave" and joined:
            # Removes the user from the event
            SQLFunctions.remove_member_from_event(event, discord_member, self.conn)
        else:
            return False
        try:
            await self.set_event_channel_perms(member, event.SpecificChannelID, command)
        except discord.Forbidden:
            pass
        return event

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.channel_id is None or payload.member is None or payload.message_id is None:
            return
        # return if its the bot itself
        if payload.member.bot:
            return
        if self.emote in str(payload.emoji):
            event = await self.join_leave_event(payload.member, payload.guild_id, "join", message_id=payload.message_id)
            SQLFunctions.logger.debug(f"Member {str(payload.member)} joining Event: {event}")
            if not event:
                return
            try:
                await payload.member.send(f"Added you to the event **{event.EventName}**")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.channel_id is None or payload.user_id is None:
            return
        # return if its the bot itself
        if payload.user_id == self.bot.user.id:
            return
        if self.emote in str(payload.emoji):
            guild = self.bot.get_guild(payload.guild_id)
            if guild is None:
                return
            member = guild.get_member(payload.user_id)
            if member is None:
                return
            event = await self.join_leave_event(member, payload.guild_id, "leave", message_id=payload.message_id)
            SQLFunctions.logger.debug(f"Member {str(member)} leaving Event: {event}")
            if not event:
                return
            try:
                user = self.bot.get_user(payload.user_id)
                await user.send(f"Removed you from the event **{event.EventName}**")
            except discord.Forbidden:
                pass
    
    def sort_by_times(self, members: list, total: int, day: int):
        points = {m["id"]:0 for m in members}
        first_star = [m for m in members if "1" in m["completion_day_level"][f"{day}"]]
        second_star = [m for m in members if "2" in m["completion_day_level"][f"{day}"]]
        
        # sort by the person's submission time (earliest times at the end)
        sort_fn1 = lambda m: m["completion_day_level"][f"{day}"]["1"]["get_star_ts"]
        sort_fn2 = lambda m: m["completion_day_level"][f"{day}"]["2"]["get_star_ts"]
        first_star.sort(key=sort_fn1)
        second_star.sort(key=sort_fn2)
        
        for i, m in enumerate(first_star):
            points[m["id"]] = total - i
        for i, m in enumerate(second_star):
            points[m["id"]] += total - i
        
        final = sorted(points, key= lambda x: points[x], reverse=True)  # sorted by final points
        return final, points
        
    
    def create_pages(self, msg: str, CHAR_LIMIT: int) -> list[str]:
        pages = []
        while len(msg) > 0:
            # split quotes into multiple fields of max 1000 chars
            if len(msg) >= CHAR_LIMIT:
                rind2 = msg.rindex("\n", 0, CHAR_LIMIT)
                if rind2 == 0:
                    # one quote is more than 1000 chars
                    rind2 = msg.rindex(" ", 0, CHAR_LIMIT)
                    if rind2 == 0:
                        # the quote is longer than 1000 chars and has no spaces
                        rind2 = CHAR_LIMIT
            else:
                rind2 = len(msg)
            pages.append(msg[0:rind2])
            msg = msg[rind2:]
        return pages
    
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
        start = time.perf_counter()
        await ctx.trigger_typing()
        end = time.perf_counter()
        embed = discord.Embed(
            title=f"{title} 🏓",
            description=f"🌐 Ping: `{round((end - start) * 1000)}` ms\n"
                        f"❤ HEARTBEAT: `{round(self.bot.latency * 1000)}` ms",
            color=0xD7D7D7
            )
        await ctx.send(embed=embed)

    @commands.guild_only()
    @commands.group(aliases=["events"], usage="event [add/view/edit/delete/join/leave] [event name/event ID] [date] [time] [description]", invoke_without_command=True)
    async def event(self, ctx, command=None):
        """
        The event command is used to keep track of upcoming events. Each user can add a maximum of two events.

        Command specific help pages have been moved to their own help pages viewable with `{prefix}help event <subcommand>`.
        """
        if command is None:
            # list all upcoming events sorted by upcoming order
            event_results = SQLFunctions.get_events(self.conn, is_done=False, guild_id=ctx.message.guild.id, order=True, limit=10)
            embed = discord.Embed(title=f"Upcoming Events On {ctx.message.guild.name}", color=0xFCF4A3)
            embed.set_footer(text="$event view <ID> to get more details about an event")
            for event in event_results:
                form_time = starting_in(event.EventStartingAt)
                embed.add_field(name=f"**ID:** {event.EventID}"
                                     f"\n**Name:** {event.EventName}",
                                value=f"**At:** {event.EventStartingAt}\n**In:** {form_time}", inline=False)
            if len(event_results) == 0:
                embed.description = "-- There are no upcoming events --"
            await ctx.send(embed=embed)
        elif ctx.invoked_subcommand is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, the command you used is not recognized. Check `$help event` to get more "
                           f"info about the event command.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

    @commands.guild_only()
    @event.command(usage="add <event name> <date> <event time> [description]")
    async def add(self, ctx, event_name=None, date=None, event_time=None, *, event_description="[No Description]"):
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
        # check if the user already has created events
        events = SQLFunctions.get_events(self.conn, is_done=False, by_user_id=ctx.message.author.id, guild_id=ctx.message.guild.id)
        if len(events) < 3:
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
            member = SQLFunctions.get_or_create_discord_member(ctx.message.author, conn=self.conn)
            event = SQLFunctions.create_event(event_name, dt, event_description, member, self.conn)
            # Additionally joins the host as a joined user
            SQLFunctions.add_member_to_event(event, member, self.conn, host=True)

            # Creates and sends the embed message
            embed = discord.Embed(title="Added New Event", color=0xFCF4A3)
            embed.add_field(name="Event ID", value=event.EventID)
            embed.add_field(name="Event Name", value=event_name, inline=False)
            embed.add_field(name="Event Host", value=ctx.message.author.mention, inline=False)
            embed.add_field(name="Event Date", value=format_date_string(dt), inline=False)
            embed.add_field(name="Event Description", value=event.EventDescription, inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("ERROR! Each member can only add **three** events as of now.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

    @commands.guild_only()
    @event.command(usage="view <event name / ID>")
    async def view(self, ctx, event_name=None):
        """
        View existing events with more detail using this command.

        The event name parameter can either be a search term (meaning all fitting events will be displayed) or \
        a specific event ID to only show a single event. If multiple events are shown, they are ordered so that \
        events closest to starting are at the top.
        """

        if event_name is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you did not specify what event to view. Check `$help event` to get more "
                           f"info about the event command.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        else:
            events = SQLFunctions.get_events(self.conn, guild_id=ctx.message.guild.id, order=True)
            event_results = []
            for e in events:
                if e.EventName.lower() == event_name.lower() or str(e.EventID) == event_name:
                    event_results.append(e)
            if len(event_results) == 0:
                await ctx.send("ERROR! There is no event with a similar name. Simply type `$event` to get a list of upcoming events.",
                               delete_after=10)
                await ctx.message.delete(delay=10)
                raise discord.ext.commands.errors.BadArgument

            embed = discord.Embed(title="Indepth Event View", color=0xFCF4A3)
            embed.set_footer(text="Join an event with $event join <ID>")
            if len(event_results) > 2:
                embed.add_field(name="NOTICE",
                                value="*There are more than 2 matches with that event name. Only showing the two closest timewise.*",
                                inline=False)
                embed.add_field(name="\u200b", value="``` ```", inline=False)
            i = 1
            MAX_EVENTS = 2  # max amount of events to send per view command
            for e in event_results:
                # creates a list of all joined members
                joined_members = SQLFunctions.get_event_joined_users(e, self.conn)
                joined_users_msg = f"Total: {len(joined_members)}"
                counter = 1
                for member in joined_members:
                    joined_users_msg += f"\n> <@{member.DiscordUserID}>"
                    if counter >= 5:
                        joined_users_msg += "\n> . . ."
                        break
                    counter += 1

                # Adds the fields to an event
                add_event_fields(embed, e, joined_users_msg)

                # if not last field, add a spacer
                if i < MAX_EVENTS and i < len(event_results):
                    embed.add_field(name="\u200b", value="``` ```", inline=False)
                i += 1
                if i > MAX_EVENTS:
                    break
            await ctx.send(embed=embed)

    @commands.guild_only()
    @event.command(usage="delete <event ID>")
    async def delete(self, ctx, event_id=None):
        """
        Delete your own events using this command.

        Event ID has to be a valid ID of one of your own events. You cannot delete \
        other people's events.
        """
        if event_id is None:
            await ctx.send("ERROR! No Event ID given. Don't know what event I should delete <:NotLikeThis:821369098629808168>")
            raise discord.ext.commands.errors.BadArgument
        event_results = SQLFunctions.get_events(self.conn, guild_id=ctx.message.guild.id)
        for e in event_results:
            if str(e.EventID) == event_id:
                event: SQLFunctions.Event = e
                break
        else:
            await ctx.send(f"ERROR! No event found with the given ID `{event_id}`.")
            raise discord.ext.commands.errors.BadArgument
        if event.DiscordMember.DiscordUserID != ctx.message.author.id:
            await ctx.send(f"ERROR! You are not the host of the given event ID. You can't delete other people's events.")
            raise discord.ext.commands.errors.BadArgument
        SQLFunctions.delete_event(event, self.conn)
        embed = discord.Embed(title="Deleted Event",
                              description=f"**Name of deleted event:** {event.EventName}\n"
                                          f"**Event host:** {ctx.message.author.mention}",
                              color=0xFCF4A3)
        await ctx.send(embed=embed)

    @commands.guild_only()
    @event.command(usage="join <event name / ID>")
    async def join(self, ctx, event_id=None):
        """
        Joins an event using the event name or ID.
        When joining with the event name the first matching event is chosen. \
        To make sure you join the right event, use the ID.

        Examples:
        - `{prefix}event join 420BlazeIt`
        - `{prefix}event join 42`
        """
        await self.join_or_leave_message(ctx, event_id, "join")

    async def join_or_leave_message(self, ctx, event_id, command):
        if event_id is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you did not specify what event to {command}.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        if not event_id.isnumeric():
            await ctx.send(f"ERROR! {ctx.message.author.mention}, the given event ID is not an integer.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        event = SQLFunctions.get_event_by_id(int(event_id), self.conn)
        if event is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, could not find an event with that ID.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        success = await self.join_leave_event(ctx.message.author, ctx.message.guild.id, command, event_id=event.EventID)
        if success and command == "join":
            embed = discord.Embed(
                title="Joined Event",
                description=f"Added {ctx.message.author.mention} to event `{event.EventName}`."
                            f"You can leave the event with `$event leave {event.EventID}`",
                color=0xFCF4A3)
            await ctx.send(embed=embed)

            if event.SpecificChannelID is not None:
                try:
                    await self.set_event_channel_perms(ctx.message.author, event.SpecificChannelID, "join")
                except discord.Forbidden:
                    await ctx.send("Couldn't add you to the channel. Best to tag Mark.")
                except AttributeError:
                    await ctx.send("I can't see the event channel anymore. Can't add you :'(\nBest to tag Mark.")
        elif success and command == "leave":
            embed = discord.Embed(
                title="Left Event",
                description=f"Removed {ctx.message.author.mention} from the event `{event.EventName}`."
                            f"You can join the event again with `$event join {event.EventID}`",
                color=0xFCF4A3)
            await ctx.send(embed=embed)

            if event.SpecificChannelID is not None:
                try:
                    await self.set_event_channel_perms(ctx.message.author, event.SpecificChannelID, "leave")
                except discord.Forbidden:
                    await ctx.send("Couldn't remove you from the channel. Best to tag Mark.")
                except AttributeError:
                    await ctx.send("I can't see the event channel anymore, so I can't remove you from it :'(\nBest to tag Mark.")
        elif command == "join":
            await ctx.send("Whoops something went wrong. You probably already joined the event. Can't join twice.")
        elif command == "leave":
            await ctx.send("Whoops something went wrong. You can't leave an event you haven't even joined <:bruh_mike:937352413810151424>")
        else:
            await ctx.send("Whoops... if you see this message, don't even bother pinging Mark, cause this error shouldn't ever show up and"
                           "he doesn't have any logs to find the problem anyway.")

    @commands.guild_only()
    @event.command(usage="leave <event name / ID>")
    async def leave(self, ctx, event_id=None):
        """
        Leaves an event using the event name or ID.
        When leaving with the event name the first matching event is chosen. \
        To make sure you leave the right event, use the ID.

        Examples:
        - `{prefix}event leave 420BlazeIt`
        - `{prefix}event leave 42`
        """
        await self.join_or_leave_message(ctx, event_id, "leave")

    @commands.guild_only()
    @event.command(usage="update <event ID>")
    @has_permissions(kick_members=True)
    async def update(self, ctx, event_id=None):
        """
        Creates an updating event message, which constantly gets updated with \
        the joined members and the remaining time to start.

        There can only be a single updated message for each event. If the command \
        is called again, the older message will simply be deleted.

        Permissions: kick_members
        """
        if event_id is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you did not specify what event to create an updating message for.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        if not event_id.isnumeric():
            await ctx.send(f"ERROR! {ctx.message.author.mention}, the given event ID is not an integer.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        # Checks if the Event exists
        event = SQLFunctions.get_event_by_id(int(event_id), self.conn)
        if event is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, could not find an event with that ID.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        # Checks if there already exists an updating message, if there does, deletes old one
        if event.UpdatedChannelID is not None:
            try:
                channel = self.bot.get_channel(event.UpdatedChannelID)
                msg_to_delete = await channel.fetch_message(event.UpdatedMessageID)
                await msg_to_delete.delete()
            except (discord.NotFound, AttributeError):
                pass

        # Creates embed and sends the message
        joined_members = SQLFunctions.get_event_joined_users(event, self.conn)
        embed = create_event_embed(event, joined_members)
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(f"<a{self.emote}>")

        SQLFunctions.add_event_updated_message(msg.id, msg.channel.id, event.EventID, self.conn)
        await ctx.send("Successfully added updating event to DB.", delete_after=3)
        await ctx.message.delete()

    @commands.guild_only()
    @event.command(usage="channel <event ID> <channel ID>")
    @has_permissions(kick_members=True)
    async def channel(self, ctx, event_id=None, channel_id=None):
        """
        Link a channel to an event, so that when a user joins an event, they get access to the channel.
        Giving no channel ID as parameter clears the channel for that event. This should always be done \
        to avoid any unecessary errors when joining/leaving an event.

        Permissions: kick_members
        """
        # parsing user input
        if event_id is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you did not specify what event to create an updating message for.",
                           delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        # Checks if the Event exists
        if not event_id.isnumeric():
            await ctx.send(f"ERROR! {ctx.message.author.mention}, the given event ID is not an integer.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        event = SQLFunctions.get_event_by_id(int(event_id), self.conn)
        if event is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, could not find an event with that ID.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        # if no channel is given, clears the channel
        if channel_id is None:
            SQLFunctions.set_specific_event_channel(event.EventID, conn=self.conn)
            await ctx.send(f"Successfully cleared the linked channel for event {event_id}.")
            return

        if not channel_id.isnumeric():
            await ctx.send("ERROR! Channel ID is not a valid integer.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        # Gets the channel and makes sure the ID is valid
        channel_id = int(channel_id)
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, the channel ID you specified is invalid or I don't have access to the channel.",
                           delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        # Checks own permissions in that channel
        permissions = channel.permissions_for(ctx.message.guild.me)
        if not permissions.manage_channels:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, I don't have the permissions to change permissions on that channel.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        SQLFunctions.set_specific_event_channel(event.EventID, channel.id, self.conn)

        await ctx.send(f"Successfully linked channel with event {event_id}.")

        # goes through all users to add their correct perms to the channel
        join_members = SQLFunctions.get_event_joined_users(event, self.conn)

        for m in join_members:
            member = ctx.message.guild.get_member(m.DiscordUserID)
            if member is None:
                continue
            await self.set_event_channel_perms(member, channel_id, "join")

        await ctx.send(f"Successfully added the perms for all joined users for the event {event_id}.", delete_after=3)

    @commands.guild_only()
    @commands.cooldown(1, 120, BucketType.guild)
    @event.command(usage="ping <event ID>", name="ping")
    async def mention(self, ctx, event_id=None):
        """
        Ping all users that joined the event. This can only be called if the user themselves joined the event.
        """
        if event_id is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you did not specify what event to ping users on.",
                           delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        if not event_id.isnumeric():
            await ctx.send(f"ERROR! {ctx.message.author.mention}, the given event ID is not an integer.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        event = SQLFunctions.get_event_by_id(event_id, self.conn)
        if event is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, could not find an event with that ID.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        joined_members = SQLFunctions.get_event_joined_users(event, self.conn)
        if len(joined_members) == 0:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, could not find an event with that ID or the event has no joined users.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        ping_msg = ""
        event_name = event.EventName
        for member in joined_members:
            ping_msg += f"<@{member.DiscordUserID}> "

        if str(ctx.message.author.id) not in ping_msg:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you are not in the event. Can't ping it then.",
                           delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        await ctx.send(f"Mass event ping by {ctx.message.author.mention} for the event **{event_name}**\n||{ping_msg}||")

    @event.command(usage="list <event ID>")
    async def list(self, ctx, event_id=None):
        """
        Lists all joined people of an event.
        """
        if event_id is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, you did not specify what event to ping users on.",
                           delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument
        if not event_id.isnumeric():
            await ctx.send(f"ERROR! {ctx.message.author.mention}, the given event ID is not an integer.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        event = SQLFunctions.get_event_by_id(event_id, self.conn)
        if event is None:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, could not find an event with that ID.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        joined_members: list[SQLFunctions.DiscordMember] = SQLFunctions.get_event_joined_users(event, self.conn)
        if len(joined_members) == 0:
            await ctx.send(f"ERROR! {ctx.message.author.mention}, the event has no joined users.", delete_after=10)
            await ctx.message.delete(delay=10)
            raise discord.ext.commands.errors.BadArgument

        all_columns = []
        event_name = event.EventName
        COLUMNS = 2
        per_column = math.ceil(len(joined_members) / COLUMNS)
        single_column = []
        for member in joined_members:
            if len(single_column) == per_column:
                all_columns.append(single_column)
                single_column = []
            user = ctx.message.guild.get_member(member.DiscordUserID)
            if user is None:
                user = await ctx.message.guild.fetch_member(member.DiscordUserID)
            if user is None:
                username = member.User.DisplayName
            else:
                username = user.display_name
            single_column.append(f"* {username}".replace("`", "").replace("\\", ""))
        if len(single_column) > 0:
            all_columns.append(single_column)
        embed = discord.Embed(
            title=f"List of Members in Event {event_id}",
            description=f"All members in {event_name}:",
            color=0xFCF4A3
        )
        for field in all_columns:
            joined_msg = '\n'.join(field)
            embed.add_field(name="\u200B", value=f"```md\n{joined_msg}```")

        embed.set_footer(text=f"Event ID: {event_id}")

        await ctx.send(embed=embed)

    async def set_event_channel_perms(self, member, channel_id, command):
        """
        Adds users to a channel if they join an event or leave it.
        """
        if channel_id is None:
            return
        channel = self.bot.get_channel(int(channel_id))
        # add user to channel perms
        if command == "join":
            await channel.set_permissions(member, read_messages=True, reason="User joined event")
        elif command == "leave":
            await channel.set_permissions(member, overwrite=None, reason="User left event")


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
