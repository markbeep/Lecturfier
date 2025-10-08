from dataclasses import dataclass
import datetime
import random
import time
import discord
from discord import app_commands
from discord.ext import commands
import helper.sql.SQLFunctions as sql
from helper.log import log


@dataclass
class SpamMessage:
    count: int
    first_message_at: float

    def resets_at(self) -> int:
        return int(self.first_message_at + 60)  # 1 minute later


class ModerateGroup(
    commands.GroupCog,
    group_name="limit",
    group_description="Message Limits",
):
    def __init__(self):
        super().__init__()
        self.channel_limits = sql.get_message_limit_channels()
        self.spam_messages: dict[int, SpamMessage] = {}

    def set_channel_limit(self, channel_id: int, limit: int):
        sql.reset_all_message_limits(channel_id)
        sql.insert_or_update_message_limit_channel(channel_id, limit)
        self.channel_limits = sql.get_message_limit_channels()

    def remove_channel_limit(self, channel_id: int):
        sql.reset_all_message_limits(channel_id)
        sql.delete_message_limit_channel(channel_id)
        self.channel_limits = sql.get_message_limit_channels()

    async def timeout_user(self, user: discord.Member, minutes: int, reason: str):
        try:
            await user.timeout(
                discord.utils.utcnow() + datetime.timedelta(minutes=minutes),
                reason=reason,
            )
        except discord.Forbidden:
            log("Lacking permissions to timeout user: " + str(user.id))

    def is_user_spamming(self, user_id: int, channel_id: int) -> bool:
        now = time.time()
        spam = self.spam_messages.get(user_id, SpamMessage(0, 0))
        spam.count += 1
        self.spam_messages[user_id] = spam

        if spam.resets_at() < now:
            # they're not spamming
            spam.first_message_at = now
            return False

        lower_bound = self.channel_limits.get(channel_id)
        if lower_bound is None:
            lower_bound = 5
        else:
            lower_bound = lower_bound.message_limit
        if spam.count > random.randint(lower_bound + 1, lower_bound + 10):
            # they sent more than 5-10 messages in the last moment
            return True

        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.channel or not message.guild:
            return

        if self.is_user_spamming(message.author.id, message.channel.id):
            member = message.guild.get_member(message.author.id)
            if member is None:
                return
            await self.timeout_user(
                member, 5, "Spamming messages while being channel limited"
            )
            return

        channel_limit = self.channel_limits.get(message.channel.id)
        if channel_limit is None:
            print("No limit for channel " + str(message.channel.id))
            return

        c = sql.get_message_limit(message.author.id, message.channel.id)

        # create initial user
        if not c:
            sql.increment_message_limit(message.author.id, message.channel.id)
            return

        # reset timer. allow user to send messages again
        if c.resets_at() < time.time():
            sql.reset_message_limit(
                message.author.id, message.channel.id, int(time.time()), 1
            )
            print("Reset message limit for user " + str(message.author.id), c)
            return

        if c.count >= channel_limit.message_limit:
            try:
                await message.delete()
            except discord.Forbidden:
                log("Lacking permissions to delete message")
                return
            try:
                await message.author.send(
                    f"You have reached the message limit for <#{message.channel.id}> of {channel_limit.message_limit} messages.\nPlease wait until your limit resets <t:{c.resets_at()}:R>."
                )
            except discord.Forbidden:
                log("Lacking permissions to DM user: " + str(message.author.id))
            return

        sql.increment_message_limit(message.author.id, message.channel.id)

    @app_commands.command(description="Check your current message limit status")
    async def check(self, inter: discord.Interaction):
        limits = sql.get_all_message_limits(inter.user.id)

        if len(limits) == 0:
            await inter.response.send_message(
                "You have no message limits.", ephemeral=True
            )
            return

        limit_msgs: list[str] = []
        for lim in limits:
            channel_limit = self.channel_limits.get(lim.channel_id)
            if channel_limit is None:
                continue

            remaining = channel_limit.message_limit - lim.count
            if lim.resets_at() < time.time():
                remaining = channel_limit
            limit_msgs.append(
                f"- <#{lim.channel_id}>: {remaining} messages remaining. Resets <t:{lim.resets_at()}:R>"
            )

        combined_limits = "\n".join(limit_msgs)
        await inter.response.send_message(
            f"## Time Limits\n{combined_limits}", ephemeral=True
        )

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="Set a message limit for a channel")
    @app_commands.describe(
        channel="The channel to set the limit for",
        limit="The number of messages allowed before muting",
    )
    async def set(
        self, inter: discord.Interaction, channel: discord.TextChannel, limit: int
    ):
        if limit < 1:
            await inter.response.send_message(
                "Limit must be at least 1", ephemeral=True
            )
            return
        self.set_channel_limit(channel.id, limit)
        await inter.response.send_message(
            f"Set message limit for <#{channel.id}> to {limit} messages.",
            ephemeral=True,
        )

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="Remove a message limit for a channel")
    @app_commands.describe(channel="The channel to remove the limit for")
    async def remove(self, inter: discord.Interaction, channel: discord.TextChannel):
        self.remove_channel_limit(channel.id)
        await inter.response.send_message(
            f"Removed message limit for <#{channel.id}>.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ModerateGroup())
