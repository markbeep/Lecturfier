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
        self.requested_help = []  # list of DiscordUserIDs of who requested help
        self.requested_ta = []  # list of DiscordUserIDs which requested TA role to avoid spam

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # adds the user to the db
        try:
            SQLFunctions.get_or_create_discord_member(member, conn=self.conn)
        except Exception as e:
            print(e)

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

        # find out who deleted it
        await asyncio.sleep(3)  # small delay as audit log sometimes takes a bit
        audit: discord.AuditLogEntry = None
        async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=10):
            if entry.target.id == message.author.id and entry.created_at >= message.created_at:
                audit = entry
        if audit is None:
            embed.add_field(name="Deleted by", value="A bot or the user")
        else:
            embed.add_field(name="Deleted by", value=str(audit.user))
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

    @commands.is_owner()
    @commands.command()
    async def deleted_messages(self, ctx):
        async for entry in ctx.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=10):
            print('{0.user} did {0.action} to {0.target}'.format(entry))

    @commands.Cog.listener()
    async def on_button_click(self, res: discord_components.Interaction):
        if res.message is None:
            comp_id: str = res.component["custom_id"]
            results = comp_id.split(",")
            comp_id = results[0]
            if len(results) > 1:
                guild: discord.Guild = self.bot.get_guild(int(results[2]))
                member: discord.Member = guild.get_member(int(results[1]))
            else:
                member = None
                guild = None
        else:
            comp_id: str = res.component.id
            member = res.user
            guild = res.guild

        staff_channel = self.bot.get_channel(747768907992924192)
        admin_log_channel = self.bot.get_channel(774322031688679454)
        yes_emoji = self.bot.get_emoji(776717335242211329)
        no_emoji = self.bot.get_emoji(776717315139698720)

        # vvvvvvvvvvvvvvv  EXTERNAL ROLE FOR NEWCOMERS vvvvvvvvvvvvvvv
        if comp_id.startswith("first_external"):
            msg = "Are you sure you want to skip verifying? **You won't have access to a lot of study channels.**"
            buttons = [[
                Button(label="No, I'll verify", style=ButtonStyle.URL, url="https://dauth.spclr.ch/", emoji=yes_emoji),
                Button(label="Yes, skip verification", id=f"give_external,{res.user.id},{res.guild.id}", style=ButtonStyle.red, emoji=no_emoji)
            ]]
            await res.respond(ephemeral=True, content=msg, components=buttons)
        elif comp_id == "give_external":
            role = discord.Object(767315361443741717)
            await member.add_roles(role, reason="Not verified role")
            # for testing purposes
            embed = discord.Embed(description=f"Added **External** role to {member.mention}\n"
                                              f"ID: `{member.id}`", color=0xa52222)
            await admin_log_channel.send(embed=embed)
            await res.respond(type=InteractionType.DeferredUpdateMessage)
        # ^^^^^^^^^^^^^^^  EXTERNAL ROLE FOR NEWCOMERS ^^^^^^^^^^^^^^^

        # vvvvvvvvvvvvvvv  TA REQUEST FOR NEWCOMERS vvvvvvvvvvvvvvv
        elif comp_id == "ta_requested":
            if member.id in self.requested_ta:
                await res.respond(content="You already requested TA. Hold on")
            else:
                ta_embed = discord.Embed(
                    title=f"TA|{member.id}",
                    description=f"{member.mention} requests the TA role",
                    color=discord.Color.gold())
                role_ping = "<@&844572520497020988>"
                components = [[
                    Button(label="Accept", id=f"accept_ta_request", style=ButtonStyle.green, emoji=yes_emoji),
                    Button(label="Decline", id=f"decline_ta_request", style=ButtonStyle.red, emoji=no_emoji)
                ]]
                await staff_channel.send(role_ping, embed=ta_embed, components=components)
                embed = discord.Embed(
                    title="Successfully requested the TA role",
                    description="Expect a direct message from a staff member to verify your TA status.",
                    color=discord.Color.blue()
                )
                await res.respond(embed=embed)
                self.requested_ta.append(member.id)
        elif comp_id == "accept_ta_request":
            ta_user_id = int(res.message.embeds[0].title.split("|")[1])
            ta_user = res.message.guild.get_member(ta_user_id)
            if ta_user is None:
                await res.channel.send("lol, the user left before receiving the TA role")
                await res.respond(type=InteractionType.DeferredUpdateMessage)
            else:
                embed = discord.Embed(description=f"Added **TA** role to {ta_user.mention}\n"
                                                  f"Accepted by: {member.mention}", color=discord.Color.green())
                role = discord.Object(767084137361440819)
                await ta_user.add_roles(role, reason="Accepted TA role")
                await res.channel.send(embed=embed)
                embed = discord.Embed(title=f"TA|{ta_user.id}",
                                      description=f"{ta_user.mention} requested the TA role\n**ACCEPTED**",
                                      color=discord.Color.green())
                await res.respond(type=InteractionType.UpdateMessage, embed=embed, components=[])
        elif comp_id == "decline_ta_request":
            ta_user_id = int(res.message.embeds[0].title.split("|")[1])
            ta_user = res.message.guild.get_member(ta_user_id)
            if ta_user is None:
                await res.channel.send("lol, the user left anyway...")
                await res.respond(type=InteractionType.DeferredUpdateMessage)
            else:
                embed = discord.Embed(description=f"Did **not** add TA role to {ta_user.mention}\n"
                                                  f"Declined by: {member.mention}", color=discord.Color.red())
                await res.channel.send(embed=embed)
                embed = discord.Embed(title=f"TA|{ta_user.id}",
                                      description=f"{ta_user.mention} requested the TA role\n**DECLINED**",
                                      color=discord.Color.red())
                await res.respond(type=InteractionType.UpdateMessage, embed=embed, components=[])
        # ^^^^^^^^^^^^^^^  TA REQUEST FOR NEWCOMERS ^^^^^^^^^^^^^^^

        # vvvvvvvvvvvvvvv  HELP BUTTONS FOR NEWCOMERS vvvvvvvvvvvvvvv
        elif comp_id == "help":
            help_buttons = [[
                Button(label="Verifying my ETH account", id="help_verify"),
                Button(label="What is Discord?", style=ButtonStyle.URL, url="https://discord.com/safety/360044149331-What-is-Discord"),
                Button(label="Other", id=f"help_other,{member.id},{guild.id}")
            ]]
            embed = discord.Embed(title="Help Page", description="What do you need help with?", color=discord.Color.green())
            await res.respond(components=help_buttons, embed=embed)
        elif comp_id == "help_verify":
            content = """**How to verify that you're an ETH student:**
**1.** Click on the `Verify ETH Student` button underneath this message.
**2.** Login with your ETH credentials
**3.** If login was successfull, you are brought to a site with a token in the middle. Now you can do one of the following methods:
**-3a.** Click on the `CONFIRM ME PLS` button to login with Discord.
**-3b.** Send `\\confirm INSERT_TOKEN_HERE` in this channel.
**-3c.** Private message <@306523617188118528> and type `\\confirm INSERT_TOKEN_HERE`
**4.** If you sent the correct token, you should be verified now. The gif underneath shows how it should look."""
            embed = discord.Embed(title="Help with verifying", description=content, color=discord.Color.green())
            embed.set_image(url="https://cdn.discordapp.com/attachments/747768907992924192/856128802610741258/verify.gif")
            await res.respond(embed=embed,
                              components=[Button(label="Verify ETH Student", style=ButtonStyle.URL, url="https://dauth.spclr.ch/", emoji=yes_emoji)])
        elif comp_id == "help_other":
            channel: discord.TextChannel = self.bot.get_channel(747768907992924192)
            if channel is None:
                return
            if member.id in self.requested_help:
                await res.respond(content="You already requested help. Please wait.")
                return
            embed = discord.Embed(
                title="A newcomer needs help",
                description=f"{member.mention} ({str(member)}) requested help in <#815881148307210260>.",
                color=discord.Color.gold()
            )
            await channel.send(f"<@&844572520497020988>", embed=embed)
            await res.respond(content="The staff team was notified and will help you shortly.")
            self.requested_help.append(member.id)
        # ^^^^^^^^^^^^^^^  HELP BUTTONS FOR NEWCOMERS ^^^^^^^^^^^^^^^

    @commands.is_owner()
    @commands.command(usage="sendWelcome", aliases=["sendwelcome", "send_welcome"])
    async def sendWelcome(self, ctx):
        embed = discord.Embed(
            title="Welcome to the D-INFK ETH Server!",
            description=f"**To get the full experience of the server press one of the following buttons:**\n"
                        f"*(If you have any issues, private message one of the admins or moderators and they can help)*\n\n"
                        f"Click the corresponding button below to get access to the server.",
            color=0xadd8e6
        )
        embed.set_thumbnail(url=ctx.message.guild.icon_url)
        yes_emoji = self.bot.get_emoji(776717335242211329)
        no_emoji = self.bot.get_emoji(776717315139698720)
        components = [
            [
                Button(label="Verify ETH Student", style=ButtonStyle.URL, url="https://dauth.spclr.ch/", emoji=yes_emoji),
                Button(label="Don't Verify", style=ButtonStyle.red, id="first_external", emoji=no_emoji)
            ],
            [
                Button(label="I'm a teaching assistant", style=ButtonStyle.blue, id="ta_requested", emoji="🧑‍🏫"),
                Button(label="I need help", style=ButtonStyle.green, id="help", emoji="🙋‍♀️")
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
        await ctx.send(f"All messages will be deleted after {delete} seconds for the next `{seconds}` seconds.\n" + "<:that:758262252699779073>" * 10)
        await asyncio.sleep(seconds)
        if ctx.message.channel.id in self.secret_channels:
            self.secret_channels.pop(ctx.message.channel.id)
            await ctx.send("<:elthision:787256721508401152>\n" + "<:this:747783377662378004>" * 10 + "\nMessages are not Elthision anymore.")

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
