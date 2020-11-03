import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from pytz import timezone
import time
from helper.lecture_scraper.scrape import scraper
import json
import traceback
from helper import file_creator
from helper.log import log

bot = commands.Bot(command_prefix="$", description='Lecture Notifier')

bot.remove_command("help")

file_creator.createFiles()

with open("./data/schedule.json", "r") as f:
    schedule = json.load(f)

channel_list = {"lecture": 756391202546384927, "test": 402563165247766528}

####################################################
# GLOBAL VARIABLES


                                                                                    # DEFAULT:
channel_to_post = channel_list["test"]  # "lecture" or "test"                    # "lecture"
test_livestream_message = False  # set True to send test time                       # False
send_message_to_finn = False  # set True to send messages to Finn                    # True
lecture_updater_version = "v2.1"  # The version of the lecture updates sender       # v0.5


####################################################

async def background_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            channel = bot.get_channel(channel_to_post)
            cur_time = datetime.now(timezone("Europe/Zurich")).strftime("%a:%H:%M")
            if test_livestream_message:
                cur_time = "test"
            if int(datetime.now(timezone("Europe/Zurich")).strftime("%M")) % 10 == 0:  # Only check updates every 10 minutes
                await check_updates(channel, cur_time, lecture_updater_version)
            if cur_time in all_times(schedule):
                await send_livestream(cur_time, channel, lecture_updater_version)
            await asyncio.sleep(40)
            await bot.change_presence(activity=discord.Activity(name=datetime.now(timezone("Europe/Zurich")).strftime("time: %H:%M"), type=discord.ActivityType.watching))
        except Exception:
            user = bot.get_user(205704051856244736)
            await user.send(f"Error in background loop: {traceback.format_exc()}")
            log(f"Error in background loop bot.py: {traceback.format_exc()}", "BACKGROUND")
            await asyncio.sleep(10)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def edit(ctx, id: int = None, link = None):
    try:
        await ctx.message.delete()
        if id is None or link is None:
            msg = await ctx.send("No link sent")
            await asyncio.sleep(7)
            await msg.delete()
            return
        room = get_room(link)
        message = await ctx.channel.fetch_message(id)
        title = message.embeds[0].title
        embed = discord.Embed(title=f"{title} is starting soon!",
                              description=f"**Lecture is in {room}**\n[**>> Click here to view the livestream <<**]({link})\n---------------------\n",
                              timestamp=datetime.fromtimestamp(time.time()), color=discord.Color.light_grey())
        embed.set_footer(text="(Edited)")
        await message.edit(embed=embed)
    except Exception:
        user = bot.get_user(205704051856244736)
        await user.send(f"No lesson error: {traceback.format_exc()}")

async def check_updates(channel, cur_time, version):
    start = time.time()
    scraped_info = scraper()
    changes = scraped_info[0]
    lecture_urls = scraped_info[1]
    send_ping = False
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
                        user = bot.get_user(205704051856244736)
                        await user.send(f"Lesson: {lesson}\nError: KeyError\nChanges: `{changes}`")
                    if correct_changes["event"] == "other":
                        embed = discord.Embed(title=f"{lesson} has been changed!", description=f"[Click here to get to {lesson}'s website]({lecture_urls[lesson]}).", timestamp=datetime.utcfromtimestamp(time.time()), color=color)
                        if send_message_to_finn:
                            users = [205704051856244736, 304014259975880704]  # 304014259975880704
                        else:
                            users = [205704051856244736]
                        for u_id in users:
                            user = bot.get_user(u_id)
                            await user.send(embed=embed)

                    elif correct_changes["event"] == "edit":
                        log(f"{lesson} was changed", "LESSON")
                        title = f"There has been an edit on __{lesson}__"
                        description = f"""**OLD**:
    {format_exercise(correct_changes["content"]["old"])}
    
    **NEW**:
    {format_exercise((correct_changes["content"]["new"]), correct_changes["content"]["keys"])}"""
                        embed = discord.Embed(title=title, description=description, timestamp=datetime.utcfromtimestamp(time.time()), color=color)
                        embed.set_footer(text=f"{version} | This message took {round(time.time()-start, 2)} seconds to send")
                        await channel.send(embed=embed)
                        send_ping = True

                    elif correct_changes["event"] == "new":
                        log(f"{lesson} got an new update", "LESSON")
                        title = f"Something new was added on __{lesson}__"
                        description = f"""**NEW**:\n{format_exercise(correct_changes["content"])}"""
                        embed = discord.Embed(title=title, description=description, timestamp=datetime.utcfromtimestamp(time.time()), color=color)
                        embed.set_footer(text=f"{version} | This message took {round(time.time()-start, 2)} seconds to send")
                        await channel.send(embed=embed)
                        send_ping = True

        except Exception:
            user = bot.get_user(205704051856244736)
            await user.send(f"Lesson{lesson}\nError: {traceback.format_exc()}")
    if send_ping:
        await channel.send("<@&759615935496847412>")

def format_exercise(version, edited_keys=None):
    topics = {"name": "Name", "date": "Date", "abgabe_date": "Submission Date", "links": "Link"}
    formatted_text = ""
    for key in version:
        if edited_keys is not None and key in edited_keys:
            formatted_text += f"__{topics[key]}: {check_link(key, version[key])}__\n"
        else:
            formatted_text += f"{topics[key]}: {check_link(key, version[key])}\n"
    return formatted_text

def check_link(key, data):
    if key == "links":
        text = ""
        for diff_url in range(len(data)):
            text += f"[Click Here for {data[diff_url]['text']}]({data[diff_url]['url'].replace(' ', '%20')})\n"
        return text
    else:
        return data



async def send_livestream(cur_time: str, channel, version):
    color = discord.Color.lighter_grey()
    log("Sending Embed Message for livestream.", "LIVESTREAM")
    link = ""
    name = ""
    website_url = ""
    if cur_time in schedule['eprog']:  # Eprog
        link = schedule['eprog'][cur_time]
        website_url = schedule['eprog']['url']
        name = "Introduction to Programming"
        color = discord.Color.blue()
    elif cur_time in schedule['diskmat']:  # diskmat
        link = schedule['diskmat'][cur_time]
        website_url = schedule['diskmat']['url']
        name = "Discrete Mathematics"
        color = discord.Color.purple()
    elif cur_time in schedule['linalg']:  # linalg
        link = schedule['linalg'][cur_time]
        website_url = schedule['linalg']['url']
        name = "Linear Algebra"
        color = discord.Color.gold()
    elif cur_time in schedule['and']:  # AnD
        link = schedule['and'][cur_time]
        website_url = schedule['and']['url']
        name = "Algorithms and Data Structures"
        color = discord.Color.magenta()
    elif cur_time in schedule['test']:  # TEST
        link = schedule['test'][cur_time]
        website_url = schedule['test']['url']
        name = "< Test Message >"

    room = get_room(link)
    embed = discord.Embed(title=f"{name} is starting soon!", description=f"**Lecture is in {room}**\n[**>> Click here to view the lecture <<**]({link})\n---------------------\n[*Link to Website*]({website_url})", timestamp=datetime.utcfromtimestamp(time.time()), color=color)
    embed.set_footer(text=f"{version}")
    await channel.send("<@&759615935496847412>", embed=embed)

    await asyncio.sleep(40)  # So it doesnt send the stream twice in a minute

def all_times(schedule):
    times = []
    for subject in schedule:
        for time_text in schedule[subject]:
            times.append(time_text)
    return times

def get_room(link):
    if "zoom" in link:
        room = "Zoomland"
    elif "ethz" in link:
        link = link[46:-5]
        room = link[link.index("/") + 1:].replace("-", " ").upper()
    else:
        room = "(N/A)"

    return room


@bot.event
async def on_ready():
    log("Logged in as:", "LOGIN")
    log(f"Name: {bot.user.name}", "LOGIN")
    log(f"ID: {bot.user.id}", "LOGIN")
    log(f"Version: {discord.__version__}", "LOGIN")
    await bot.change_presence(activity=discord.Activity(name='lectures!', type=discord.ActivityType.watching))
    print("-------------")


@bot.event
async def on_message(message):
    await bot.process_commands(message)

startup_extensions = ["player", "statistics", "minesweeper", "hangman", "quote", "help", "reputation", "admin", "owner"]

for extension in startup_extensions:
    try:
        loaded_cog = bot.load_extension("cogs." + extension)
        log("Loaded extension \"{}\".".format(extension), "EXTENSION")
    except Exception as e:
        log("Failed loading extension \"{}\"\n-{}: {}".format(extension, e, type(e)), "EXTENSION")
print("-------------------")

with open("../LECTURFIER.json", "r") as f:
    settings = json.load(f)
if len(settings["token"]) == 0:
    log("NO TOKEN IN LECTURFIER.json! Stopping bot.", "TOKEN")
    exit()
bot.loop.create_task(background_loop())
bot.run(settings["token"])


