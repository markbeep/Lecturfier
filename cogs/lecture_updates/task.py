from discord.ext import tasks, commands
import discord
from discord import app_commands
import datetime
from helper.log import log
import helper.sql.SQLFunctions as sql
from pytz import timezone
import re

# list of all times during the day in 5 minute intervals so that tasks
# always start at the beginning of a minute
times_to_check = [datetime.time(h, m) for h in range(24) for m in range(0, 60, 5)]
weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "None"]

def create_lecture_embed(course_name, course_link, stream_link, secondary_link, on_site_location, course_id):
    embed = discord.Embed(
        title=f"Lecture Starting: {course_name} [{course_id}]",
        color=discord.colour.Color.light_gray(),
        timestamp=datetime.datetime.now(timezone("Europe/Zurich"))
    )
    if stream_link is not None:
        stream_link = f"[Click Here]({stream_link})"
    if course_link is not None:
        course_link = f"[Click Here]({course_link})"
    if secondary_link is not None:
        secondary_link = f"[Click Here]({secondary_link})"

    embed.description = f"**Course Website URL:** {course_link}\n" \
                        f"**Room:** {on_site_location}\n" \
                        f"**Stream URL:** {stream_link}\n" \
                        f"**Secondary URL:** {secondary_link}"
    return embed

class Task(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.latest_minute = 0
        self.check_lectures.start()  # pylint: disable=no-member
        self.bot = bot
    
    def heartbeat(self):
        return self.check_lectures.is_running()  # pylint: disable=no-member
    
    def cog_unload(self):
        self.check_lectures.cancel()  # pylint: disable=no-member
        
    @tasks.loop(time=times_to_check)
    async def check_lectures(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.now(timezone("Europe/Zurich"))
        result = sql.get_lectures_by_time(weekdays[now.weekday()], now.hour, now.minute)
        for name, role_id, channel_id, link, stream_link, secondary_link, location, course_id in result:
            embed = create_lecture_embed(name, link, stream_link, secondary_link, location, course_id)
            channel = self.bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.abc.Messageable):
                await channel.send(f"<@{role_id}>", embed=embed)
            else:
                log(f"Didn't find channel {channel_id} to send lecture updates to.", True, True)
    
    @check_lectures.before_loop
    async def before_check_lectures(self):
        await self.bot.wait_until_ready()
    
    @app_commands.command()
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(hour="Hour to test for")
    @app_commands.describe(minute="Minute to test for")
    @app_commands.choices(hour=[app_commands.Choice(name=str(x), value=x) for x in range(24)])
    @app_commands.choices(minute=[app_commands.Choice(name=str(x), value=x) for x in range(0, 60, 5)])
    @app_commands.choices(day=[app_commands.Choice(name=x, value=x) for x in weekdays])
    async def test(self, inter: discord.Interaction, day: str, hour: int, minute: int):
        result = sql.get_lectures_by_time(day, hour, minute)
        count = 0
        failed = 0  # to keep track if and how many updates failed
        for name, role_id, channel_id, link, stream_link, secondary_link, location, course_id in result:
            embed = create_lecture_embed(name, link, stream_link, secondary_link, location, course_id)
            channel = self.bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.abc.Messageable):
                await channel.send(f"`<@{role_id}>`", embed=embed)
            else:
                failed += 1
                log(f"TEST: Didn't find channel {channel_id} to send lecture updates to.", True, True)
        if count == 0:
            await inter.response.send_message(f"No lectures at this time. Failed: {failed}", ephemeral=True)
        else:
            await inter.response.send_message(f"Sent updates in the corresponding channels. Failed: {failed}", ephemeral=True)


def get_course_id_from_embed(message):
    r = re.compile(r".*(\[\d+\])")
    return int(r.findall(message.embeds[0].title)[0])

async def setup(bot):
    await bot.add_cog(Task(bot))
