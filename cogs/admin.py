import asyncio
import json
import re
from datetime import datetime

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from pytz import timezone

from helper.sql import SQLFunctions

YES_EMOJI_ID = "776717335242211329"
NO_EMOJI_ID = "776717315139698720"

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.newcomers = {}
        self.ta_request = {}
        self.bot_prefix_path = "./data/bot_prefix.json"
        with open(self.bot_prefix_path, "r", encoding="utf8") as f:
            self.all_prefix = json.load(f)
        self.db_path = "./data/discord.db"
        self.conn = SQLFunctions.connect()
        self.welcome_message_id = SQLFunctions.get_config("WelcomeMessage", self.conn)
        self.requested_help = []  # list of DiscordUserIDs of who requested help
        self.requested_ta = []  # list of DiscordUserIDs which requested TA role to avoid spam
        self.bot.add_view(WelcomeViewPersistent())

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

        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url if message.author.avatar else None)

        # find out who deleted it
        await asyncio.sleep(3)  # small delay as audit log sometimes takes a bit
        audit: discord.AuditLogEntry | None = None
        try:
            async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=10):
                if entry.target.id == message.author.id and entry.created_at >= message.created_at:
                    audit = entry
        except discord.errors.Forbidden:
            pass
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
        if message.channel.id in [747776646551175217, 768600365602963496, 948506487716737034]:  # bot channels
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
    @commands.command(usage="sendWelcome", aliases=["sendwelcome", "send_welcome"])
    async def sendWelcome(self, ctx):
        """
        Sends the welcome message for the D-INFK ETH server with the required buttons
        to get set up.
        """
        embed = discord.Embed(
            title="Welcome to the D-INFK ETH Server!",
            description=f"**To get the full experience of the server press one of the following buttons:**\n"
                        f"*(If you have any issues, private message one of the admins or moderators and they can help)*\n\n"
                        f"Click the corresponding button below to get access to the server.",
            color=0xadd8e6
        )
        if ctx.message.guild.icon:
            embed.set_thumbnail(url=ctx.message.guild.icon.url)
        await ctx.send(embed=embed, view=WelcomeViewPersistent())

    async def send_prefix(self, message, command=None, prefix=None, args=[]):
        channel = message.channel
        author = message.author
        guild = message.guild
        if command is None:
            # first creates a list of all bot prefixes and checks if they're online or offline
            online = []
            offline = []
            for prefix in self.all_prefix.keys():
                prefix_line = self.all_prefix[prefix]
                r = re.compile(r"<@!?(\d+)>")
                res = r.findall(prefix_line)
                # checks if the bot is online
                if len(res) > 0 and res[0].isnumeric():
                    user = guild.get_member(int(res[0]))
                    if not user:  # ignore bots not on the server
                        continue
                    if user.status != discord.Status.offline:
                        online.append(f"<:online:1015269202338263140> `{prefix}`: {prefix_line}")
                    else:
                        offline.append(f"<:offline:1015269203684638720> `{prefix}`: {prefix_line}")        
                else:
                    offline.append(f"<:offline:1015269203684638720> `{prefix}`: {prefix_line}")
            embed = discord.Embed(title="Bot Prefixes", color=0xcbd3d7)
            combined = online + offline
            n = len(combined)
            if n > 10: # make two fields next to each other
                partition_size = (n+1)//4
                embed.add_field(name="\u200b", value="\n".join(combined[:partition_size]), inline=False)
                embed.add_field(name="\u200b", value="\n".join(combined[partition_size:2*partition_size]), inline=False)
                embed.add_field(name="\u200b", value="\n".join(combined[2*partition_size:3*partition_size]), inline=False)
                embed.add_field(name="\u200b", value="\n".join(combined[3*partition_size:]), inline=False)
            else:
                embed.add_field(name="\u200b", value="\n".join(combined))
            await channel.send(embed=embed)
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
            raise commands.errors.BadArgument()

    @commands.cooldown(10, 10, BucketType.user)
    @commands.guild_only()
    @commands.command(aliases=["prefixes"], usage="prefix [<add/delete> <prefix> <info>]")
    async def prefix(self, ctx, command=None, prefix=None, *args):
        """
        Is used to view all currently used prefixes for the bots on the server.
        The prefixes are saved in a dictionary, where the prefix itself is the key.
        Adding an already existing prefix changes the value instead of adding an additional entry.
        In <#747776646551175217> and <#768600365602963496> you can simply type `prefix` to get \
        a list of prefixes.
        """
        if ctx.message.guild.id != 747752542741725244:
            await ctx.reply("This command is not supported on this server.")
            return
        await self.send_prefix(ctx.message, command, prefix, args)

    @commands.command(usage="testWelcome")
    @commands.is_owner()
    async def testWelcome(self, ctx):
        """
        Is used to test the welcome message when a new member joins or leaves the server.
        Permissions: Owner
        """
        await self.send_welcome_message(ctx, ctx.author, ctx.message.guild)
        await self.send_leave_message(ctx, ctx.author, ctx.message.guild)

    async def send_welcome_message(self, channel, user, guild):
        embed = discord.Embed(description=f"{user.mention} joined the server. **Welcome!**", color=0xadd8e6)
        memb_amt = len(guild.members)
        embed.set_footer(text=f"There are now {memb_amt} members")
        embed.set_author(name=str(user), icon_url=user.avatar.url if user.avatar else None)
        message = await channel.send(embed=embed)
        await message.edit(content=user.mention, embed=embed)
        await message.add_reaction("<a:blobjoin:944973432007839765>")

    async def send_leave_message(self, channel, user, guild):
        embed = discord.Embed(description=f"{user.mention} left the server.", color=0x84001B)
        memb_amt = len(guild.members)
        embed.set_footer(text=f"There are now {memb_amt} members")
        embed.set_author(name=str(user), icon_url=user.avatar.url if user.avatar else None)
        message = await channel.send(embed=embed)
        await message.add_reaction("<a:blobleave:944973431307399199>")

    @commands.cooldown(1, 5, BucketType.user)
    @commands.command(usage="ban <user>")
    async def ban(self, ctx, person, *, reason=None):
        """
        Plays a little joke and "bans" the given user
        """
        embed = discord.Embed(
            title="Banning...",
            description=f"`Who:` {person}\n`Executed by:` {ctx.message.author.mention}\n`Reason:` {str(reason)}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url="https://c.tenor.com/n9bi4Y3smL0AAAAC/ban-hammer.gif")
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(10)
        embed = discord.Embed(
            description=f"Was just a prank brudi {person}",
            color=discord.Color.green()
        )
        await msg.reply(embed=embed)


class WelcomeViewPersistent(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.requested_ta = []
        self.add_item(discord.ui.Button(label="Verify ETH Student", style=discord.ButtonStyle.url, emoji=YES_EMOJI_ID, url="https://dauth.spclr.ch/"))

    @discord.ui.button(label="Don't verify", custom_id="welcome_view_persistent:dont_verify", style=discord.ButtonStyle.red, emoji=NO_EMOJI_ID)
    async def dont_verify(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_message(view=WelcomeViewDecline(), ephemeral=True)
        
    @discord.ui.button(label="I'm a teaching assistant", custom_id="welcome_view_persistent:teaching_assistant", style=discord.ButtonStyle.blurple, emoji="🧑‍🏫")
    async def teaching_assistant(self, interaction: discord.Interaction, _: discord.ui.Button):
        member = interaction.user
        if member.id in self.requested_ta:
            await interaction.response.send_message("You already requested TA. Hold on", ephemeral=True)
            return
        if not interaction.guild or not isinstance(member, discord.Member):
            raise ValueError("Not in a guild.")
        staff_channel = interaction.guild.get_channel(747768907992924192)
        if staff_channel is None:
            print("TA role was accepted. Don't have access to staff channels.")
            staff_channel = interaction.guild.get_channel(237673537429700609)
        if not isinstance(staff_channel, discord.abc.Messageable):
            raise ValueError("Staff channel isn't a text channel")
        ta_embed = discord.Embed(
            title=f"TA|{member.id}",
            description=f"{member.mention} requests the TA role",
            color=discord.Color.gold())
        role_ping = f"||<@&844572520497020988>|| {member.mention}"
        await staff_channel.send(role_ping, embed=ta_embed, view=WelcomeViewTA())
        embed = discord.Embed(
            title="Successfully requested the TA role",
            description="Expect a direct message from a staff member to verify your TA status.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.requested_ta.append(member.id)
            
    
    @discord.ui.button(label="I need help", custom_id="welcome_view_persistent:help", style=discord.ButtonStyle.green, emoji="🙋‍♀️")
    async def need_help(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_message(view=WelcomeViewHelp(), ephemeral=True)

        
class WelcomeViewDecline(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="No, I'll verify", style=discord.ButtonStyle.url, emoji=YES_EMOJI_ID, url="https://dauth.spclr.ch/"))
        
    @discord.ui.button(label="Yes, skip verification", custom_id="give_external", style=discord.ButtonStyle.red, emoji=NO_EMOJI_ID)
    async def verify_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        role = discord.Object(767315361443741717)
        member = interaction.user
        if not interaction.guild or not isinstance(interaction.guild, discord.abc.Messageable) or not isinstance(member, discord.Member):
            raise ValueError("Not a member")
        await member.add_roles(role, reason="Not verified role")
        # for testing purposes
        embed = discord.Embed(description=f"Added **External** role to {member.mention}\n"
                                            f"ID: `{member.id}`", color=0xa52222)
        embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else None)
        log_channel = interaction.guild.get_channel(774322031688679454)
        if not log_channel or not isinstance(log_channel, discord.abc.Messageable):
            raise ValueError("Did not find log channel")
        await log_channel.send(embed=embed)
        await interaction.response.defer()
        

class WelcomeViewTA(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="I need help", custom_id="welcome_view_ta_admin_persistent:decline", style=discord.ButtonStyle.green, emoji=YES_EMOJI_ID)
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.guild is None:
            raise ValueError("Interaction not in a guild")
        if not interaction.message or not type(interaction.message.embeds) == list or len(interaction.message.embeds) == 0 or not interaction.message.embeds[0].title:
            raise ValueError("Invalid message object")
        ta_user_id = int(interaction.message.embeds[0].title.split("|")[1])
        ta_user = interaction.guild.get_member(ta_user_id)
        if ta_user is None:
            await interaction.response.send_message("lol, the user left before receiving the TA role")
            embed = discord.Embed(description="User left before receiving TA role", color=discord.Color.red())
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = discord.Embed(description=f"Added **TA** role to {ta_user.mention}\n"
                                                f"Accepted by: {interaction.user}", color=discord.Color.green())
            role = discord.Object(767084137361440819)
            await ta_user.add_roles(role, reason="Accepted TA role")
            await interaction.response.send_message(embed=embed)
            embed = discord.Embed(title=f"TA|{ta_user.id}",
                                    description=f"{ta_user.mention} requested the TA role\n**ACCEPTED**",
                                    color=discord.Color.green())
            await interaction.response.edit_message(embed=embed, view=None)
            
    @discord.ui.button(label="I need help", custom_id="welcome_view_ta_admin_persistent:decline", style=discord.ButtonStyle.red, emoji=NO_EMOJI_ID)
    async def decline(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.guild is None:
            raise ValueError("Interaction not in a guild")
        if not interaction.message or not type(interaction.message.embeds) == list or len(interaction.message.embeds) == 0 or not interaction.message.embeds[0].title:
            raise ValueError("Invalid message object")
        ta_user_id = int(interaction.message.embeds[0].title.split("|")[1])
        ta_user = interaction.guild.get_member(ta_user_id)
        if interaction.channel is None or not isinstance(interaction.channel, discord.abc.Messageable):
            raise ValueError("Channel is not a text channel")
        if ta_user is None:
            await interaction.channel.send("lol, the user left anyway...")
            embed = discord.Embed(description="User left already and didn't get TA role anyway", color=discord.Color.red())
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = discord.Embed(description=f"Did **not** add TA role to {ta_user.mention}\n"
                                                f"Declined by: {interaction.user}", color=discord.Color.red())
            await interaction.channel.send(embed=embed)
            embed = discord.Embed(
                title=f"TA|{ta_user.id}",
                description=f"{ta_user.mention} requested the TA role\n**DECLINED**",
                color=discord.Color.red())
            await interaction.response.edit_message(embed=embed, view=None)


class WelcomeViewHelp(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.requested_help = []
        self.add_item(discord.ui.Button(label="What is Discord?", style=discord.ButtonStyle.url, url="https://discord.com/safety/360044149331-What-is-Discord"))

    @discord.ui.button(label="Verifying my ETH account", custom_id="welcome_view_help:verify", style=discord.ButtonStyle.grey, emoji=YES_EMOJI_ID)
    async def verify(self, interaction: discord.Interaction, _: discord.ui.Button):
        content = """**How to verify that you're an ETH student:**
**1.** Click on the `Verify ETH Student` button above.
**2.** Login with your ETH credentials.
**3.** Click on the `CONFIRM ME PLS` button to login with Discord. This will verify your Discord account.
**4.** You should now have access to tons of channels."""
        embed = discord.Embed(title="Help with verifying", description=content, color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="I need help", custom_id="welcome_view_help:other", style=discord.ButtonStyle.grey, emoji=YES_EMOJI_ID)
    async def other(self, interaction: discord.Interaction, _: discord.ui.Button):
        member = interaction.user
        if interaction.guild is None or not isinstance(member, discord.Member):
            raise ValueError("Interaction not in a guild")
        staff_channel = interaction.guild.get_channel(747768907992924192)
        if staff_channel is None:
            print("Help was requested. Don't have access to staff channels.")
            staff_channel = interaction.guild.get_channel(237673537429700609)
            if staff_channel is None:
                raise ValueError("No staff channel found")
        if not isinstance(staff_channel, discord.abc.Messageable):
           raise ValueError("Staff channel isn't a text channel")
        if member.id in self.requested_help:
            await interaction.response.send_message("You already requested help. Please wait.", ephemeral=True)
            return
        embed = discord.Embed(
            title="A newcomer needs help",
            description=f"{member.mention} ({str(member)}) requested help in <#881611441105416263>.",
            color=discord.Color.gold()
        )
        await staff_channel.send(f"||<@&844572520497020988>|| {member.mention}", embed=embed)
        await interaction.response.send_message("The staff team was notified and will help you shortly. \
            You additionally should now have access to the <#881611441105416263> channel.", ephemeral=True)
        self.requested_help.append(member.id)
        # gives the user permissions to see the support channel
        support_channel = interaction.guild.get_channel(881611441105416263)
        if support_channel is None:
            support_channel = interaction.guild.get_channel(402551175272202252)
        if not isinstance(support_channel, discord.abc.Messageable):
           raise ValueError("Support channel isn't a text channel")
        await support_channel.set_permissions(member, read_messages=True, reason="User requested help")
        await support_channel.send(f"{member.mention}, what do you need help with?")

async def setup(bot):
    await bot.add_cog(Admin(bot))
