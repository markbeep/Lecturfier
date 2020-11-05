import discord
from discord.ext import commands
import asyncio
from helper.log import log


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.newcomers = {}
        self.ta_request = {}

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        channel = self.bot.get_channel(747794480517873685)
        await self.send_welcome_message(channel, member)

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

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx):
        await self.send_welcome_message(ctx, ctx.author)

    async def send_welcome_message(self, channel, user):
        msg = f"Welcome {user.mention}! Head to <#769261792491995176> to read " \
              f"through the few rules we have on this server. " \
              f"Then press one of the following reactions.\n\n" \
              f"🧑‍🏫   if you're a TA (press the TA reaction before the student)\n" \
              f"✏   if you're a **D-INFK** student.\n" \
              f"<:bach:764174568000192552>   if you're external.\n\n" \
              f"**YOUR EMAIL ADDRESS FOR DISCORD NEEDS TO BE VERIFIED FOR YOU TO BE ABLE TO CHAT AND PARTICIPATE ON THIS SERVER**"
        embed = discord.Embed(title="**WELCOME!**", description=msg, color=0xadd8e6)
        embed.set_thumbnail(url=user.avatar_url)
        message = await channel.send(user.mention, embed=embed)
        self.newcomers[user.id] = message.id
        await message.add_reaction("🧑‍🏫")
        await message.add_reaction("✏")
        await message.add_reaction("<:bach:764174568000192552>")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ban(self, ctx, person):
        await ctx.send(f"Banning {person}...")
        await asyncio.sleep(10)
        await ctx.send("Was justa prank brudi")


def setup(bot):
    bot.add_cog(Admin(bot))
