import discord
import discord_components
from discord_components import DiscordComponents, Button, ButtonStyle, InteractionType
from discord.ext import commands
import asyncio
from helper.sql import SQLFunctions
from datetime import datetime
from pytz import timezone
import json
import time
from discord.ext.commands.cooldowns import BucketType


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.newcomers = {}
        self.ta_request = {}
        self.bot_prefix_path = "./data/bot_prefix.json"
        with open(self.bot_prefix_path, "r") as f:
            self.all_prefix = json.load(f)
        self.secret_channels = {}
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()
        self.welcome_message_id = SQLFunctions.get_config("WelcomeMessage", self.conn)
        self.yes = []
        self.no = []

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # adds the user to the db
        SQLFunctions.get_or_create_discord_member(member, self.conn)

        if member.bot:
            return
        # if the server is the main server
        if member.guild.id == 747752542741725244:
            channel = self.bot.get_channel(815936830779555841)
            await self.send_welcome_message(channel, member, member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot:
            return
        if member.guild.id == 747752542741725244:
            channel = self.bot.get_channel(815936830779555841)
            await self.send_leave_message(channel, member, member.guild)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id is None or payload.channel_id is None or payload.member is None:
            return
        channel = self.bot.get_channel(payload.channel_id)
        guild = self.bot.get_guild(payload.guild_id)
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            print("Did not find message to fetch")
            return
        admin_log_channel = self.bot.get_channel(774322847812157450)
        if admin_log_channel is None:
            return
        member = payload.member
        emoji = payload.emoji
        if member.bot:
            return
        if message.author.id in (755781649643470868, 776713845238136843) and len(message.embeds) > 0 and message.embeds[0].title is not discord.Embed.Empty:
            # Needs to be either Lecturfier or Lecturfier Beta
            try:
                if "Welcome" in message.embeds[0].title:
                    # If the reaction is on the welcome message

                    # EXTERNAL reaction
                    if str(emoji) == "<:bach:764174568000192552>":
                        role = discord.Object(767315361443741717)
                        await member.add_roles(role, reason="Reaction role")
                        embed = discord.Embed(description=f"Added **External** role to {member.mention}\n"
                                                          f"ID: `{member.id}`", color=0xa52222)
                        await admin_log_channel.send(embed=embed)

                    # STUDENT reaction (is given to students and TAs)
                    elif str(emoji) == "✏" or str(emoji) == "🧑‍🏫":
                        role = discord.Object(747786383317532823)
                        await member.add_roles(role, reason="Reaction role")
                        embed = discord.Embed(description=f"Added **Student** role to {member.mention}\n"
                                                          f"ID: `{member.id}`", color=0xff6c00)
                        await admin_log_channel.send(embed=embed)

                    # TA reaction
                    if str(emoji) == "🧑‍🏫":
                        staff_channel = self.bot.get_channel(747768907992924192)
                        ta_embed = discord.Embed(
                            title=f"TA|{member.id}",
                            description=f"{member.mention} requests to be a TA\n"
                                        f"<:checkmark:769279808244809798> to accept\n"
                                        f"<:xmark:769279807916998728> to decline",
                            color=discord.Color.gold())
                        role_ping = "<@&773908766973624340> <@&815932497920917514> <@&747753814723002500>"
                        ta_msg = await staff_channel.send(role_ping, embed=ta_embed)
                        await ta_msg.add_reaction("<:checkmark:769279808244809798>")
                        await ta_msg.add_reaction("<:xmark:769279807916998728>")
                        embed = discord.Embed(description=f"{str(member)} requested to be a TA\n"
                                                          f"ID: `{member.id}`", color=0x56aafd)
                        await admin_log_channel.send(embed=embed)

                elif "TA|" in message.embeds[0].title:
                    # CHECKMARK reaction
                    ta_id = int(message.embeds[0].title.split("|")[1])
                    ta_user = guild.get_member(ta_id)
                    if str(emoji) == "<:checkmark:769279808244809798>":
                        embed = discord.Embed(description=f"Added **TA** role to {ta_user.mention}\n"
                                                          f"Accepted by: {member.mention}", color=discord.Color.green())
                        role = discord.Object(767084137361440819)
                        await ta_user.add_roles(role, reason="Accepted TA role")
                    elif str(emoji) == "<:xmark:769279807916998728>":
                        embed = discord.Embed(description=f"Did **not** add TA role to {ta_user.mention}\n"
                                                          f"Declined by: {member.mention}", color=discord.Color.red())
                    else:
                        return

                    await admin_log_channel.send(embed=embed)
                    await channel.send(embed=embed)

                    # edits the previous sent message in the staff channel
                    role_ping = "<@&773908766973624340> <@&815932497920917514> <@&747753814723002500>"
                    await message.edit(content=role_ping, embed=embed)
                    await message.clear_reactions()
            except discord.NotFound:
                print("Did not find the role to give to the new member")
                return

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return

        # To send the deleted message
        channel_id = 774322847812157450
        channel = message.guild.get_channel(channel_id)
        attachments = len(message.attachments)
        embed = discord.Embed(
            description=f"**User ID:** {message.author.id}\n"
                        f"**Channel: <#{message.channel.id}>\n"
                        f"Attachments:** `{attachments}`\n"
                        f"----------MSG----------\n{message.content}",
            timestamp=datetime.now(timezone("Europe/Zurich")))

        attach_txt = ""
        for i in range(len(message.attachments)):
            attach_txt += f"File {i + 1}\n" \
                          f"Name: {message.attachments[i].filename}\n"
            if message.attachments[i].height is not None:
                # Then the file is an image
                embed.set_image(url=message.attachments[i].proxy_url)
        if len(message.attachments) > 0:
            embed.add_field(
                name="Attachments",
                value=attach_txt
            )

        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
        try:
            await channel.send(embed=embed)
        except AttributeError:
            print("Can't send deleted message")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == 755781649643470868 or message.author.id == 776713845238136843:
            return
        if message.channel.id in self.secret_channels:
            if time.time() < self.secret_channels[message.channel.id][0]:
                await asyncio.sleep(self.secret_channels[message.channel.id][1])
                await message.delete()
        if message.channel.id in [747776646551175217, 768600365602963496]:  # bot channels
            if message.content.lower().startswith("prefix") or message.content.lower().startswith("prefixes"):
                args = message.content.split(" ")
                desc = []
                command = None
                prefix = None
                if len(args) > 1:
                    command = args[1]
                if len(args) > 2:
                    prefix = args[2]
                if len(args) > 3:
                    # This means there is possibly a description at the end
                    desc = args[3:]
                await self.send_prefix(message, command, prefix, desc)

    @commands.Cog.listener()
    async def on_button_click(self, res: discord_components.Interaction):
        if res.message is None:
            return
        if res.component.id in ["yesUser", "noUser"]:
            if res.component.id == "yesUser":
                if res.user.id in self.yes:
                    self.yes.pop(self.yes.index(res.user.id))
                else:
                    self.yes.append(res.user.id)
            else:
                if res.user.id in self.no:
                    self.no.pop(self.no.index(res.user.id))
                else:
                    self.no.append(res.user.id)
            embed = res.message.embeds[0]
            description = embed.description
            results = description.split("\n")
            first_split = results[0].split(" ")
            second_split = results[1].split(" ")
            embed.description = f"{first_split[0]} {len(self.yes)}\n{second_split[0]} {len(self.no)}"
            await res.respond(type=InteractionType.UpdateMessage, embed=embed, ephemeral=True)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def poll(self, ctx):
        embed = discord.Embed(
            title="Welcome to the D-INFK ETH Server!",
            description=f"**To get the full experience of the server press one of the following reactions:**\n"
                        f"*(If you have any issues, private message one of the admins or moderators and they can help)*\n\n"
                        f"Click the corresponding button below to get access to the server."
        )
        yes_emoji = self.bot.get_emoji(776717335242211329)
        no_emoji = self.bot.get_emoji(776717315139698720)
        components = [
            [
                Button(label="Verify ETH Student", style=ButtonStyle.URL, url="https://dauth.spclr.ch/"),
                Button(label="Teaching Assistant", style=ButtonStyle.blue, id="taRequest", emoji="🧑‍🏫"),
                Button(label="Non-ETH Student", style=ButtonStyle.green, id="external", emoji=no_emoji)
            ]
        ]
        await ctx.send(embed=embed, components=components)

    async def send_prefix(self, message, command=None, prefix=None, args=[]):
        channel = message.channel
        author = message.author
        if command is None:
            msg = "**Already in use Bot Prefixes:**"
            for prefix in self.all_prefix.keys():
                msg += f"\n`{prefix}`: {self.all_prefix[prefix]}"
            await channel.send(msg)
        elif command.lower() == "add" and author.guild_permissions.kick_members:
            if prefix is None:
                await channel.send("Prefix and arguments missing.")
            else:
                self.all_prefix[prefix] = " ".join(args)
                with open(self.bot_prefix_path, "w") as f:
                    json.dump(self.all_prefix, f)
                await channel.send(f"Updated prefix table with prefix: `{prefix}`")
        elif command.lower() == "delete" or command.lower() == "del" and author.guild_permissions.kick_members:
            if prefix is None:
                await channel.send("Prefix to delete is missing.")
            else:
                try:
                    self.all_prefix.pop(prefix)
                    with open(self.bot_prefix_path, "w") as f:
                        json.dump(self.all_prefix, f)
                    await channel.send(f"Deleted prefix: {prefix}")
                except KeyError:
                    await channel.send("Invalid prefix")
        else:
            await channel.send("Unrecognized command.", delete_after=7)
            raise discord.ext.commands.errors.BadArgument

    @commands.cooldown(10, 10, BucketType.user)
    @commands.command(aliases=["prefixes"], usage="prefix [<add/delete> <prefix> <info>]")
    async def prefix(self, ctx, command=None, prefix=None, *args):
        """
        Is used to view all currently used prefixes for the bots on the server.
        The prefixes are saved in a dictionary, where the prefix itself is the key.
        Adding an already existing prefix changes the value instead of adding an additional entry.
        In <#747776646551175217> and <#768600365602963496> you can simply type `prefix` to get \
        a list of prefixes.
        """
        await self.send_prefix(ctx.message, command, prefix, args)

    @commands.cooldown(1, 5, BucketType.user)
    @commands.command(aliases=["secret"], usage="elthision [<time in seconds> [<delete after in seconds>]]")
    @commands.has_permissions(administrator=True)
    async def elthision(self, ctx, seconds=10, delete=2.0):
        """
        Deletes messages after the given seconds for the next given amount of seconds.
        Default is for 10 seconds and deletes messages after 2.0 seconds.

        `elthision 20 1.5` will delete all messages after 1.5 seconds for the next 20 seconds.
        Permissions: Administrator
        """
        self.secret_channels[ctx.message.channel.id] = [time.time() + seconds, delete]
        await ctx.send(f"All messages will be deleted after {delete} seconds for the next `{seconds}` seconds.\n"+"<:that:758262252699779073>"*10)
        await asyncio.sleep(seconds)
        if ctx.message.channel.id in self.secret_channels:
            self.secret_channels.pop(ctx.message.channel.id)
            await ctx.send("<:elthision:787256721508401152>\n"+"<:this:747783377662378004>"*10+"\nMessages are not Elthision anymore.")

    @commands.command(usage="sendWelcome")
    async def sendWelcome(self, ctx):
        """
        Sends the welcome message for the #newcomers channel
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            embed = discord.Embed(
                title="Welcome!",
                description=f"**To get the full experience of the server press one of the following reactions:**\n"
                            f"*(If you have any issues, private message one of the admins or the moderator and they can help)*\n\n"
                            f"🧑‍🏫   if you're a TA (press the TA reaction before the student)\n"
                            f"✏   if you're a **D-INFK** student.\n"
                            f"<:bach:764174568000192552>   if you're external.",
                color=0xadd8e6
            )
            message = await ctx.send(embed=embed)
            await message.add_reaction("🧑‍🏫")
            await message.add_reaction("✏")
            await message.add_reaction("<:bach:764174568000192552>")
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.command(usage="testWelcome")
    async def testWelcome(self, ctx):
        """
        Is used to test the welcome message when a new member joins or leaves the server.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            await self.send_welcome_message(ctx, ctx.author, ctx.message.guild)
            await self.send_leave_message(ctx, ctx.author, ctx.message.guild)
        else:
            raise discord.ext.commands.errors.NotOwner

    async def send_welcome_message(self, channel, user, guild):
        embed = discord.Embed(description=f"{user.mention} joined the server. **Welcome!**", color=0xadd8e6)
        memb_amt = len(guild.members)
        embed.set_footer(text=f"There are now {memb_amt} members")
        embed.set_author(name=str(user), icon_url=user.avatar_url)
        message = await channel.send(embed=embed)
        await message.edit(content=user.mention, embed=embed)
        await message.add_reaction("<a:blobjoin:821030765143785572>")

    async def send_leave_message(self, channel, user, guild):
        embed = discord.Embed(description=f"{user.mention} left the server.", color=0x84001B)
        memb_amt = len(guild.members)
        embed.set_footer(text=f"There are now {memb_amt} members")
        embed.set_author(name=str(user), icon_url=user.avatar_url)
        message = await channel.send(embed=embed)
        await message.add_reaction("<a:blobleave:821030764812304445>")

    @commands.cooldown(1, 5, BucketType.user)
    @commands.command(usage="ban <user>")
    @commands.has_permissions(administrator=True)
    async def ban(self, ctx, person):
        """
        Plays a little joke and "bans" the given user
        Permissions: Administrator
        """
        await ctx.send(f"Banning {person}...")
        await asyncio.sleep(10)
        await ctx.send("Was justa prank brudi")


def setup(bot):
    bot.add_cog(Admin(bot))
