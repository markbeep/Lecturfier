import discord
from discord.ext import commands
import datetime
import time
import json
import traceback
from helper.log import log
from helper import handySQL


def get_most_recent_time(conn, uniqueMemberID):
    c = conn.cursor()
    c.execute("SELECT CreatedAt from Reputations WHERE AddedByUniqueMemberID=? ORDER BY CreatedAt DESC", (uniqueMemberID,))
    result = c.fetchone()
    if result is None:
        return None
    return result[0]


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
        self.conn = handySQL.create_connection(self.db_path)
        self.time_to_wait = 20 * 3600  # Wait 20 hours before repping again

    def get_connection(self):
        """
        Retreives the current database connection
        :return: Database Connection
        """
        if self.conn is None:
            self.conn = handySQL.create_connection(self.db_path)
        return self.conn

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
                if not await valid_chars_checker(message.content):
                    raise ValueError

                # Add reputation to user
                time_valid = await self.add_rep(message, member, message.author)

                # Send return message
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
                    conn = self.get_connection()
                    guild_id = get_valid_guild_id(message)
                    uniqueID = handySQL.get_uniqueMemberID(conn, message.author.id, guild_id)
                    last_sent_time = get_most_recent_time(conn, uniqueID)
                    if last_sent_time is not None:
                        seconds = datetime.datetime.strptime(last_sent_time, '%Y-%m-%d %H:%M:%S.%f').timestamp() + self.time_to_wait
                        next_time = datetime.datetime.fromtimestamp(seconds).strftime("%A at %H:%M")
                        embed = discord.Embed(
                            title="Error",
                            description=f"You've repped too recently. You can rep again on {next_time}.",
                            color=discord.Color.red())
                        await message.channel.send(embed=embed, delete_after=10)
                    else:
                        embed = discord.Embed(title="Error",
                                              description="Had problems parsing something. Tbh this error shouldn't show up...",
                                              color=discord.Color.red())
                        await message.channel.send(embed=embed, delete_after=10)

        except ValueError:
            embed = discord.Embed(title="Error", description="Only mention one user, don't mention yourself, only use printable ascii characters, and keep it under 40 characters.", color=discord.Color.red())
            embed.add_field(name="Example", value="+rep <@755781649643470868> helped with Eprog")
            await message.channel.send(embed=embed, delete_after=10)

    async def send_reputations(self, message, member):
        reputation_msg = ""
        conn = self.get_connection()
        c = conn.cursor()
        guild_id = get_valid_guild_id(message)
        sql = """   SELECT R.IsPositive, R.ReputationMessage
                    FROM Reputations R
                    INNER JOIN DiscordMembers DM on R.UniqueMemberID = DM.UniqueMemberID
                    WHERE DM.DiscordUserID=? AND DM.DiscordGuildID=?"""
        c.execute(sql, (member.id, guild_id))
        rows = c.fetchall()

        # Create reputation message
        if len(rows) == 0:
            reputation_msg = "--- it's pretty empty here, go help some people out"
        else:
            for r in rows:
                if r[0] == 1:  # If message is positive
                    reputation_msg += "+ "
                else:
                    reputation_msg += "- "
                reputation_msg += f"{r[1]}\n"

        display_name = member.display_name.replace("*", "").replace("_", "").replace("~", "").replace("\\", "").replace("`", "").replace("||", "").replace("@", "")
        msg = f"```diff\nReputations: {display_name}\n__________________________\n{reputation_msg}```"
        await message.channel.send(msg)

    def check_valid_time(self, conn, uniqueMemberID):
        result = get_most_recent_time(conn, uniqueMemberID)
        if result is None:
            return True
        time_sent = datetime.datetime.strptime(result, '%Y-%m-%d %H:%M:%S.%f')
        if time.time() - time_sent.timestamp() > self.time_to_wait:
            return True
        return False

    async def add_rep(self, message, member, author):
        """
        Adds the reputation to the file
        """
        conn = self.get_connection()

        # To avoid errors when commands are used in DMs
        try:
            guild_id = message.guild.id
        except AttributeError:
            guild_id = 0
        uniqueID = handySQL.get_uniqueMemberID(conn, member.id, guild_id)

        # Can the user rep yet?
        authorUniqueID = handySQL.get_uniqueMemberID(conn, author.id, guild_id)
        if not self.check_valid_time(conn, authorUniqueID):
            return False

        # Format the reputation message
        msg_list = message.content.split(" ")
        if len(msg_list) > 2:
            msg = " ".join(msg_list[2:])
        else:
            return False

        # Check if the rep is positive
        if msg.startswith("-"):
            isPositive = 0
            msg = msg[1:].strip()
        else:
            isPositive = 1

        # Add to DB
        c = conn.cursor()
        sql = """   INSERT INTO Reputations(
                        UniqueMemberID,
                        ReputationMessage,
                        CreatedAt,
                        AddedByUniqueMemberID,
                        IsPositive
                    )
                    VALUES (?,?,?,?,?)"""
        c.execute(sql, (uniqueID, msg, datetime.datetime.now(), authorUniqueID, isPositive))
        conn.commit()
        return True


def setup(bot):
    bot.add_cog(Reputation(bot))
