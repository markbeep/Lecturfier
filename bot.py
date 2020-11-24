import discord
from discord.ext import commands
import json
from helper import file_creator
from helper.log import log
import asyncio

with open("./data/settings.json", "r") as f:
    prefix = json.load(f)
bot = commands.Bot(command_prefix=prefix["prefix"], description='Lecture Notifier')

bot.remove_command("help")

file_creator.createFiles()

startup_extensions = ["player",
                      "statistics",
                      "minesweeper",
                      "hangman",
                      "quote",
                      "help",
                      "reputation",
                      "admin",
                      "owner",
                      "voice_xp",
                      "lecture_updates"]


@bot.command()
async def reload(ctx, cog=None):
    if await bot.is_owner(ctx.author):
        if cog is None:
            cog_list = '\n'.join(startup_extensions)
            await ctx.send(f"Following cogs exist:\n"
                           f"{cog_list}")
        elif cog in startup_extensions:
            if await stop_bg_task(cog):
                msg = "--Stopped background task--"
            else:
                msg = "--No background task to stop--"
            bot.reload_extension("cogs." + cog)
            await ctx.send(f"DONE - Reloaded `{cog}`\n{msg}")
        elif cog == "all":
            await ctx.send("Reloading all cogs")
            log("Reloading all cogs", "COGS")
            for cog in startup_extensions:
                if await stop_bg_task(cog):
                    msg = "--Stopped background task--"
                else:
                    msg = "--No background task to stop--"
                bot.reload_extension("cogs." + cog)
                await ctx.send(f"Reloaded `{cog}`\n{msg}")
            await ctx.send("DONE - Reloaded all cogs")
        else:
            await ctx.send(f"Cog does not exist.")
    else:
        raise discord.ext.commands.errors.NotOwner


async def stop_bg_task(task):
    task = task.lower()
    all_loops = {
        "lecture_updates": bot.get_cog("Updates").heartbeat(),
        "statistics": bot.get_cog("Statistics").heartbeat(),
        "voice_xp": bot.get_cog("Voice").heartbeat(),
        "player": bot.get_cog("Player").heartbeat()
    }
    if task in all_loops:
        return all_loops[task].cancel()
    return False


@bot.event
async def on_ready():
    log("Logged in as:", "LOGIN")
    log(f"Name: {bot.user.name}", "LOGIN")
    log(f"ID: {bot.user.id}", "LOGIN")
    log(f"Version: {discord.__version__}", "LOGIN")
    await bot.change_presence(activity=discord.Activity(name='closely...', type=discord.ActivityType.watching))
    print("-------------")


@bot.event
async def on_message(message):
    await bot.process_commands(message)

for extension in startup_extensions:
    try:
        loaded_cog = bot.load_extension("cogs." + extension)
        log("Loaded extension \"{}\".".format(extension), "EXTENSION")
    except Exception as e:
        log("Failed loading extension \"{}\"\n-{}: {}".format(extension, e, type(e)), "EXTENSION")
print("-------------------")

with open("../LECTURFIERBETA.json", "r") as f:
    settings = json.load(f)
if len(settings["token"]) == 0:
    log("NO TOKEN IN LECTURFIER.json! Stopping bot.", "TOKEN")
    exit()

bot.run(settings["token"])


