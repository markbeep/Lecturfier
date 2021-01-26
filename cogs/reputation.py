import discord
from discord.ext import commands
import datetime
import time
import asyncio
import json
import traceback
from helper.log import log


class Reputation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.TIME_TO_WAIT = 20 * 3600  # hours to wait between reps
        with open("./data/ignored_users.json") as f:
            self.ignored_users = json.load(f)
        self.reputation_filepath = "./data/reputation.json"

        with open(self.reputation_filepath, "r") as f:
            self.reputation = json.load(f)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        # Reps a user
        if message.content.startswith("+rep"):
            await self.rep(message)

    async def rep(self, message):
        """
        Used to add positive reputation to a user
        :param message: The message content including the +rep
        :return: None
        """
        if message.author.id in self.ignored_users:
            await message.channel.send(f"{message.author.mention} this discord account is blocked from using +rep.")

        args = message.content.split(" ")
        try:
            if len(args) == 1:  # If there's only the command:
                await self.send_reputations(message, message.author)

            elif len(args) == 2:  # If there's only the command a mention
                u_id = args[1].replace("<@", "").replace(">", "").replace("!", "")
                member = message.guild.get_member(int(u_id))
                await self.send_reputations(message, member)

            else:  # If the message is long enough, add it as a reputation
                # check if it is a mention
                u_id = args[1].replace("<@", "").replace(">", "").replace("!", "")
                member = message.guild.get_member(int(u_id))

                if member.id == message.author.id:
                    raise ValueError

                # checks if the message chars are valid
                if not await self.valid_chars_checker(message.content):
                    raise ValueError

                # check if the user exists
                await self.rep_checkup(message.guild.id, member.id)
                await self.rep_checkup(message.guild.id, message.author.id)

                # Add reputation to user
                time_valid = await self.add_rep(message, member, message.author)
                if time_valid:
                    display_name = member.display_name.replace("*", "").replace("_", "").replace("~", "").replace("\\", "").replace("`", "").replace("||", "").replace("@", "")
                    embed = discord.Embed(
                        title="Added +rep",
                        description=f"Added +rep to {display_name}",
                        color=discord.Color.green())
                    if len(args) > 2:
                        embed.add_field(name="Comment:", value=f"```{' '.join(args[2:])}```")
                    embed.set_author(name=str(message.author))
                    await message.channel.send(embed=embed)
                    await message.delete()

                else:
                    send_time = self.reputation[str(message.guild.id)]['last_rep_time'][str(message.author.id)] + self.TIME_TO_WAIT
                    send_time = datetime.datetime.fromtimestamp(send_time).strftime("%A at %H:%M")
                    embed = discord.Embed(
                        title="Error",
                        description=f"You've repped too recently. You can rep again on {send_time}.",
                        color=discord.Color.red())
                    msg = await message.channel.send(embed=embed, delete_after=10)

        except ValueError:
            embed = discord.Embed(title="Error", description="Only mention one user, don't mention yourself, only use printable ascii characters, and keep it under 40 characters.", color=discord.Color.red())
            embed.add_field(name="Example", value="+rep <@755781649643470868> helped with Eprog")
            msg = await message.channel.send(embed=embed, delete_after=10)

    async def valid_chars_checker(self, message_content):
        valid_chars = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', "ä", "ü", "ö", "Ä", "Ü", "Ö", '!', '"', '#', '$', '%', '&', "'", '(', ')', '*', '+', ',', '-', '.', '/', ':', ';', '<', '=', '>', '?', '@', '[', ']', '^', '_', '{', '|', '}', '~', ' ', '\t', '\n', '\r', '\x0b', '\x0c']
        for letter in message_content:
            if letter not in valid_chars:
                return False
        return True

    async def send_reputations(self, message, member):
        await self.rep_checkup(message.guild.id, member.id)
        reputation_msg = ""
        for rep in self.reputation[str(message.guild.id)]["rep"][str(member.id)]:
            reputation_msg += f"+ {rep}\n"
        if len(reputation_msg) == 0:
            reputation_msg = "--- it's pretty empty here, go help some people out"
        display_name = member.display_name.replace("*", "").replace("_", "").replace("~", "").replace("\\", "").replace("`", "").replace("||", "").replace("@", "")
        msg = f"```diff\nReputations: {display_name}\n__________________________\n{reputation_msg}```"
        await message.channel.send(msg)

    async def add_rep(self, message, member, author):
        """
        Adds the reputation to the file
        """
        if self.reputation[str(message.guild.id)]["last_rep_time"][str(author.id)] + self.TIME_TO_WAIT > time.time():
            return False

        self.reputation[str(message.guild.id)]["last_rep_time"][str(author.id)] = time.time()
        msg = message.content.split(" ")
        if len(msg) > 2:
            self.reputation[str(message.guild.id)]["rep"][str(member.id)].append(" ".join(msg[2:]))

        # SAVE FILE
        try:
            with open(self.reputation_filepath, "w") as f:
                json.dump(self.reputation, f, indent=2)
            log("SAVED REPUTATION", "REPUTATION")
        except Exception:
            log(f"Saving REPUTATION file failed:\n{traceback.format_exc()}", "REPUTATION")
            user = self.bot.get_user(self.bot.owner_id)
            await user.send(f"Saving REPUTATION file failed:\n{traceback.format_exc()}")
        return True

    async def rep_checkup(self, guild_id, name):
        # If the guild doesn't exist in reputation yet
        if str(guild_id) not in self.reputation:
            self.reputation[str(guild_id)] = {}

        # If the categories don't exist in reputation yet
        if "rep" not in self.reputation[str(guild_id)]:
            self.reputation[str(guild_id)]["rep"] = {}
            self.reputation[str(guild_id)]["last_rep_time"] = {}

        # If the user doesn't exist in reputation yet
        if str(name) not in self.reputation[str(guild_id)]["rep"]:
            self.reputation[str(guild_id)]["rep"][str(name)] = []
            self.reputation[str(guild_id)]["last_rep_time"][str(name)] = 0


def setup(bot):
    bot.add_cog(Reputation(bot))
