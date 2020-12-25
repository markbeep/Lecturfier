import discord
from discord.ext import commands
import asyncio
from helper.log import log
from datetime import datetime
from pytz import timezone
import json
import time


# TODO Add a wrapper around commands to easily enable/disable commands per server
# labels: ADMIN
# TODO Select what roles (maybe even user sepecific) should be able to use what command on a per server basis
# labels: ADMIN
# TODO Edit command to check what an edited message was changed from and to
# labels: ADMIN
# TODO Past nicknames command
# labels: ADMIN
class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.newcomers = {}
        self.ta_request = {}
        self.bot_prefix_path = "./data/bot_prefix.json"
        with open(self.bot_prefix_path, "r") as f:
            self.all_prefix = json.load(f)
        self.secret_channels = {}

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        if member.guild.id == 747752542741725244:  # if the server is the main server
            channel = self.bot.get_channel(747794480517873685)
            await self.send_welcome_message(channel, member, member.guild)

    # TODO make on_reaction_add raw to improve reliability
    # labels: ADMIN
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return
        # If the reaction giver is one of the newcomers
        if user.id in self.newcomers:
            if reaction.message.id == self.newcomers[user.id]:
                # EXTERNAL reaction
                if str(reaction) == "<:bach:764174568000192552>":
                    role = discord.Object(767315361443741717)
                    await user.add_roles(role, reason="Reaction role")
                    log(f"Added External role to {str(user)}.", "ROLE")
                    embed = discord.Embed(title="External role added",
                                          description=f"Added **External** role to {str(user)}", color=0xa52222)

                # STUDENT reaction
                elif str(reaction) == "✏":
                    role = discord.Object(747786383317532823)
                    await user.add_roles(role, reason="Reaction role")
                    log(f"Added Student role to {str(user)}.", "ROLE")
                    embed = discord.Embed(title="Student role added",
                                          description=f"Added **Student** role to {str(user)}", color=0xff6c00)

                # TA reaction
                elif str(reaction) == "🧑‍🏫":
                    await reaction.clear()
                    channel = self.bot.get_channel(747768907992924192)
                    ta_embed = discord.Embed(
                        title="TA REQUEST",
                        description=f"{str(user)} requests to be a TA\n"
                                    f"<:checkmark:769279808244809798> to accept\n"
                                    f"<:xmark:769279807916998728> to decline",
                        color=discord.Color.gold())
                    ta_msg = await channel.send(embed=ta_embed)
                    await ta_msg.add_reaction("<:checkmark:769279808244809798>")
                    await ta_msg.add_reaction("<:xmark:769279807916998728>")
                    self.ta_request[ta_msg.id] = user.id
                    log(f"Member {str(user)} requested the TA role.", "ROLE")

                    embed = discord.Embed(
                        title="TA role requested",
                        description=f"{str(user)}'s request to be a **TA** has been forwarded to the admins. "
                                    f"You can select the **Student** role as well or wait till you get the TA role.",
                        color=0x56aafd)
                    await reaction.message.channel.send(embed=embed)
                    return
                else:
                    return

                self.newcomers.pop(user.id, None)
                await reaction.message.channel.send(embed=embed)
                await reaction.message.delete()

        # CHECKMARK reaction
        if reaction.message.id in self.ta_request:
            ta_user = reaction.message.guild.get_member(self.ta_request[reaction.message.id])
            if str(reaction) == "<:checkmark:769279808244809798>":
                embed = discord.Embed(title="Accepted TA Role", description=f"Added **TA** role to {str(ta_user)}",
                                      color=discord.Color.green())
                role = discord.Object(767084137361440819)
                await ta_user.add_roles(role, reason="Accepted TA role")
                log(f"Added TA role to {str(user)}.", "ROLE")
            elif str(reaction) == "<:xmark:769279807916998728>":
                embed = discord.Embed(title="Rejected TA Role",
                                      description=f"Did **not** add TA role to {str(ta_user)}",
                                      color=discord.Color.red())
                log(f"Did NOT add TA role to {str(user)}.", "ROLE")
            else:
                return

            await reaction.message.channel.send(embed=embed)
            await reaction.message.delete()
            self.ta_request.pop(reaction.message.id, None)

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
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == 755781649643470868 or message.author.id == 776713845238136843:
            return
        if message.channel.id in self.secret_channels:
            if time.time() < self.secret_channels[message.channel.id][0]:
                await asyncio.sleep(self.secret_channels[message.channel.id][1])
                await message.delete()

    @commands.command(aliases=["prefixes"], usage="prefix <add/delete> <prefix> <info>")
    async def prefix(self, ctx, command=None, prefix=None, *args):
        """
        Is used to view all currently used prefixes for the bots on the server.
        The prefixes are saved in a dictionary, where the prefix itself is the key.
        Adding an already existing prefix changes the value instead of adding an additional entry.
        """
        if command is None:
            msg = "**Already in use Bot Prefixes:**"
            for prefix in self.all_prefix.keys():
                msg += f"\n`{prefix}`: {self.all_prefix[prefix]}"
            await ctx.send(msg)
        elif command.lower() == "add" and ctx.author.guild_permissions.kick_members:
            if prefix is None:
                await ctx.send("Prefix and arguments missing.")
            else:
                self.all_prefix[prefix] = " ".join(args)
                with open(self.bot_prefix_path, "w") as f:
                    json.dump(self.all_prefix, f)
                await ctx.send(f"Updated prefix table with prefix: {prefix}")
        elif command.lower() == "delete" or command.lower() == "del" and ctx.author.guild_permissions.kick_members:
            if prefix is None:
                await ctx.send("Prefix to delete is missing.")
            else:
                try:
                    self.all_prefix.pop(prefix)
                    with open(self.bot_prefix_path, "w") as f:
                        json.dump(self.all_prefix, f)
                    await ctx.send(f"Deleted prefix: {prefix}")
                except KeyError:
                    await ctx.send("Invalid prefix")
        else:
            await ctx.send("Unrecognized command.", delete_after=7)
            raise discord.ext.commands.errors.BadArgument

    @commands.command(aliases=["secret"])
    @commands.has_permissions(administrator=True)
    async def elthision(self, ctx, seconds=10, delete=2.0):
        self.secret_channels[ctx.message.channel.id] = [time.time() + seconds, delete]
        await ctx.send(f"All messages will be deleted after {delete} seconds for the next `{seconds}` seconds.\n"+"<:that:758262252699779073>"*10)
        await asyncio.sleep(seconds)
        if ctx.message.channel.id in self.secret_channels:
            self.secret_channels.pop(ctx.message.channel.id)
            await ctx.send("<:elthision:787256721508401152>\n"+"<:this:747783377662378004>"*10+"\nMessages are not Elthision anymore.")

    @commands.command(usage="testWelcome")
    @commands.has_permissions(administrator=True)
    async def testWelcome(self, ctx):
        """
        Is used to test the welcome message when a new member joins the server.
        Permissions: Administrator
        """
        await self.send_welcome_message(ctx, ctx.author, ctx.message.guild)

    async def send_welcome_message(self, channel, user, guild):
        msg = f"Welcome {user.mention}! Head to <#769261792491995176> to read " \
              f"through the few rules we have on this server. " \
              f"Then press one of the following reactions.\n\n" \
              f"🧑‍🏫   if you're a TA (press the TA reaction before the student)\n" \
              f"✏   if you're a **D-INFK** student.\n" \
              f"<:bach:764174568000192552>   if you're external.\n\n" \
              f"**YOUR EMAIL ADDRESS FOR DISCORD NEEDS TO BE VERIFIED FOR YOU TO BE ABLE TO CHAT AND PARTICIPATE ON THIS SERVER**"
        embed = discord.Embed(title=f"**WELCOME!**", description=msg, color=0xadd8e6)
        embed.set_thumbnail(url=user.avatar_url)
        embed.set_footer(text=f"You are the {len(guild.members)}. member")
        message = await channel.send(user.mention, embed=embed)
        self.newcomers[user.id] = message.id
        await message.add_reaction("🧑‍🏫")
        await message.add_reaction("✏")
        await message.add_reaction("<:bach:764174568000192552>")

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
