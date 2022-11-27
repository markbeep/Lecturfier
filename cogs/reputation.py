import datetime
import json
import time

import discord
from discord.ext import commands

from helper.sql import SQLFunctions


def get_valid_guild_id(message):
    # To avoid errors when commands are used in DMs
    try:
        guild_id = message.guild.id
    except AttributeError:
        guild_id = 0
    return guild_id


async def valid_chars_checker(message_content):
    valid_chars = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', "ä", "ü", "ö", "Ä", "Ü", "Ö", '!', '"', '#', '$', '%', '&', "'", '(', ')', '*', '+', ',', '-', '.', '/', ':', ';', '<', '=', '>', '?', '@', '[', ']', '^', '_', '{', '|', '}', '~', ' ', '\t', '\n', '\r', '\x0b', '\x0c']
    for letter in message_content:
        if letter not in valid_chars:
            return False
    return True


class Reputation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open("./data/ignored_users.json") as f:
            self.ignored_users = json.load(f)
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()
        self.time_to_wait = 20 * 3600  # Wait 20 hours before repping again

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

    @commands.guild_only()
    @commands.command(aliases=["reputation", "commend", "praise"], usage="rep [<user> [<rep message>]]")
    async def rep(self, ctx, user_mention=None, *, rep=None):
        """
        Can be used to commend another user for doing something you found nice.
        Can also be used to give negative reps if the rep message starts with a \
        minus sign: `{prefix}rep <user> -doesn't like chocolate`
        `{prefix}rep <user>` lists the reputation messages of a user.
        """
        if ctx.message.author.id in self.ignored_users:
            await ctx.send(f"{ctx.message.author.mention} this discord account is blocked from using +rep.")

        if user_mention is None:  # If there's only the command:
            await self.send_reputations(ctx.message, ctx.message.author)
            return

        if rep is None:  # If there's only the command a mention
            u_id = user_mention.replace("<@", "").replace(">", "").replace("!", "")
            member = ctx.message.guild.get_member(int(u_id))
            await self.send_reputations(ctx.message, member)
            return

        # If the message is long enough, add it as a reputation
        # check if it is a mention
        u_id = user_mention.replace("<@", "").replace(">", "").replace("!", "")
        member = ctx.message.guild.get_member(int(u_id))

        if member.id == ctx.message.author.id:
            embed = discord.Embed(title="Error",
                                  description="You can't rep yourself.",
                                  color=discord.Color.red())
            await ctx.send(embed=embed, delete_after=10)
            raise commands.errors.BadArgument()

        # checks if the message chars are valid
        if not await valid_chars_checker(ctx.message.content):
            embed = discord.Embed(title="Error",
                                  description="You can only use printable ascii characters in reputation messages.",
                                  color=discord.Color.red())
            await ctx.send(embed=embed, delete_after=10)
            raise commands.errors.BadArgument()

        # Add reputation to user
        time_valid = await self.add_rep(ctx.message, member, ctx.message.author)

        # Send return message
        if time_valid:
            display_name = member.display_name.replace("*", "").replace("_", "").replace("~", "").replace("\\", "").replace("`", "").replace("||", "").replace("@", "")
            embed = discord.Embed(
                title="Added rep",
                description=f"Added rep to {display_name}",
                color=discord.Color.green())
            embed.add_field(name="Comment:", value=f"```{rep}```")
            embed.set_author(name=str(ctx.message.author))
            await ctx.send(embed=embed)

        else:
            discord_member = SQLFunctions.get_or_create_discord_member(ctx.message.author, conn=self.conn)
            last_sent_time = SQLFunctions.get_most_recent_time(discord_member, self.conn)
            if last_sent_time is not None:
                seconds = datetime.datetime.fromisoformat(last_sent_time).timestamp() + self.time_to_wait
                next_time = datetime.datetime.fromtimestamp(seconds).strftime("%A at %H:%M")
                embed = discord.Embed(
                    title="Error",
                    description=f"You've repped too recently. You can rep again on {next_time}.",
                    color=discord.Color.red())
                await ctx.send(embed=embed, delete_after=10)
            else:
                embed = discord.Embed(title="Error",
                                      description="Had problems parsing something. Tbh this error shouldn't show up...",
                                      color=discord.Color.red())
                await ctx.send(embed=embed, delete_after=10)

    async def send_reputations(self, message: discord.Message, member: discord.Member):
        reputation_msg = ""
        rows = SQLFunctions.get_reputations(member, self.conn)

        # Create reputation message
        if len(rows) == 0:
            reputation_msg = "--- it's pretty empty here, go help some people out"
        else:
            for r in rows:
                if r[0]:  # If message is positive
                    reputation_msg += "+ "
                else:
                    reputation_msg += "- "
                reputation_msg += f"{r[1]}\n"

        display_name = member.display_name.replace("*", "").replace("_", "").replace("~", "").replace("\\", "").replace("`", "").replace("||", "").replace("@", "")
        msg = f"```diff\nReputations: {display_name}\n__________________________\n{reputation_msg}```"
        embed = discord.Embed(description=msg)
        embed.set_footer(icon_url=member.avatar_url, text=str(member))
        await message.channel.send(embed=embed)

    def check_valid_time(self, member: SQLFunctions.DiscordMember):
        result = SQLFunctions.get_most_recent_time(member, self.conn)
        if result is None:
            return True
        time_sent = datetime.datetime.fromisoformat(result)
        if time.time() - time_sent.timestamp() > self.time_to_wait:
            return True
        return False

    async def add_rep(self, message, member, author):
        """
        Adds the reputation to the file
        """
        # Can the user rep yet?
        author_member = SQLFunctions.get_or_create_discord_member(author, conn=self.conn)
        if not self.check_valid_time(author_member):
            return False

        receiver_member = SQLFunctions.get_or_create_discord_member(member, conn=self.conn)

        # Format the reputation message
        msg_list = message.content.split(" ")
        if len(msg_list) > 2:
            msg = " ".join(msg_list[2:])
        else:
            return False

        # Check if the rep is positive
        if msg.startswith("-"):
            isPositive = False
            msg = msg[1:].strip()
        else:
            isPositive = True

        # Add to DB
        SQLFunctions.add_reputation(author_member, receiver_member, msg, isPositive, self.conn)
        return True


async def setup(bot):
    await bot.add_cog(Reputation(bot))
