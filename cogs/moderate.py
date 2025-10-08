from collections import defaultdict
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
    """Used to determine if a user is spamming messages after reaching the message limit"""

    count: int = 0
    first_message_at: float = 0.0

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
        self.spam_messages: dict[tuple[int, int], SpamMessage] = defaultdict(
            SpamMessage
        )
        config = sql.get_config("ignore_admins_channel_limit")
        self.ignore_admins = len(config) == 1 and config[0] == 1

    def set_channel_limit(self, channel_id: int, limit: int):
        sql.delete_message_limits(channel_id)
        sql.insert_or_update_message_limit_channel(channel_id, limit)
        self.channel_limits = sql.get_message_limit_channels()

    def remove_channel_limit(self, channel_id: int):
        sql.delete_message_limits(channel_id)
        sql.delete_message_channel_limit(channel_id)
        self.channel_limits = sql.get_message_limit_channels()

    async def timeout_user(self, user: discord.Member, minutes: int, reason: str):
        try:
            log(f"Timeout user {user.id} for {minutes} minutes: {reason}")
            await user.timeout(
                discord.utils.utcnow() + datetime.timedelta(minutes=minutes),
                reason=reason,
            )
        except discord.Forbidden:
            log("Lacking permissions to timeout user: " + str(user.id))

    def is_user_spamming(self, user_id: int, channel_id: int) -> bool:
        now = time.time()
        spam = self.spam_messages[(user_id, channel_id)]
        spam.count += 1

        if spam.resets_at() < now:
            # they're not spamming
            spam.first_message_at = now
            return False

        if spam.count > random.randint(4, 8):
            # they sent more than 4-8 messages in the last minute
            return True

        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.author.bot
            or not message.channel
            or not isinstance(message.author, discord.Member)
            or not message.guild
            or message.guild.id not in (747752542741725244, 944968090490380318)
        ):
            return

        if self.ignore_admins and message.author.guild_permissions.moderate_members:
            log(
                f"'{message.author.id}' has moderate_members permission, skipping message limit check"
            )
            return

        channel_limit = self.channel_limits.get(message.channel.id)
        if channel_limit is None:
            return

        user_count = sql.get_message_limit(message.author.id, message.channel.id)

        # create initial user limit tracking
        if not user_count:
            log(
                f"Creating initial message limit tracking for user {message.author.id} in channel {message.channel.id}"
            )
            sql.increment_message_limit(message.author.id, message.channel.id)
            return

        # reset timer. allow user to send messages again
        if user_count.resets_at() < time.time():
            sql.reset_message_limit(
                message.author.id, message.channel.id, int(time.time()), 1
            )
            log("Reset message limit for user " + str(message.author.id))
            return

        if user_count.count >= channel_limit.message_limit:
            if self.is_user_spamming(message.author.id, message.channel.id):
                await self.timeout_user(
                    message.author, 5, "Spamming messages while being channel limited"
                )

            try:
                log(
                    f"Deleting message from {message.author.id} in {message.channel.id} due to message limit"
                )
                await message.delete()
            except discord.Forbidden:
                log("Lacking permissions to delete message")
                return
            try:
                await message.author.send(
                    f"You have reached the message limit for <#{message.channel.id}> of {channel_limit.message_limit} messages.\nPlease wait until your limit resets <t:{user_count.resets_at()}:R>."
                )
            except discord.Forbidden:
                log("Lacking permissions to DM user: " + str(message.author.id))
            return

        sql.increment_message_limit(message.author.id, message.channel.id)

    @app_commands.command(description="Check your current message limit status")
    async def check(self, inter: discord.Interaction):
        if len(self.channel_limits) == 0:
            await inter.response.send_message(
                "No message limits are currently set.", ephemeral=True
            )
            return

        user_counts = sql.get_all_message_limits(inter.user.id)

        now = time.time()
        user_counts = {
            lim.channel_id: lim for lim in user_counts if lim.resets_at() > now
        }
        limit_msgs: list[str] = []
        for lim in self.channel_limits.values():
            remaining = lim.message_limit
            resets_at = None
            if lim.channel_id in user_counts:
                remaining = lim.message_limit - user_counts[lim.channel_id].count
                resets_at = user_counts[lim.channel_id].resets_at()

            msg = f"- <#{lim.channel_id}>: {remaining} messages remaining."
            if resets_at:
                msg += f" Resets <t:{resets_at}:R>."
            else:
                msg += " No timer started yet."
            limit_msgs.append(msg)

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
        self,
        inter: discord.Interaction,
        channel: discord.TextChannel | discord.Thread,
        limit: int,
        ephemeral: bool = True,
    ):
        if not inter.guild or inter.guild.id not in (
            747752542741725244,
            944968090490380318,
        ):
            await inter.response.send_message("Invalid guild", ephemeral=ephemeral)
            return

        if limit < 1:
            await inter.response.send_message(
                "Limit must be at least 1", ephemeral=ephemeral
            )
            return
        self.set_channel_limit(channel.id, limit)
        await inter.response.send_message(
            f"Set message limit for <#{channel.id}> to {limit} messages.",
            ephemeral=ephemeral,
        )

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="Remove a message limit for a channel")
    @app_commands.describe(channel="The channel to remove the limit for")
    async def remove(
        self,
        inter: discord.Interaction,
        channel: discord.TextChannel | discord.Thread,
        ephemeral: bool = True,
    ):
        if not inter.guild or inter.guild.id not in (
            747752542741725244,
            944968090490380318,
        ):
            await inter.response.send_message("Invalid guild", ephemeral=ephemeral)
            return

        self.remove_channel_limit(channel.id)
        await inter.response.send_message(
            f"Removed message limit for <#{channel.id}>.", ephemeral=ephemeral
        )

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="List all current message limits")
    async def list(self, inter: discord.Interaction, ephemeral: bool = True):
        if not inter.guild or inter.guild.id not in (
            747752542741725244,
            944968090490380318,
        ):
            await inter.response.send_message("Invalid guild", ephemeral=ephemeral)
            return

        if len(self.channel_limits) == 0:
            await inter.response.send_message(
                "No message limits are currently set.", ephemeral=ephemeral
            )
            return

        limit_msgs: list[str] = []
        for lim in self.channel_limits.values():
            msg = f"- <#{lim.channel_id}>: {lim.message_limit} messages."
            limit_msgs.append(msg)

        combined_limits = "\n".join(limit_msgs)
        await inter.response.send_message(
            f"## Message Limits\n{combined_limits}", ephemeral=ephemeral
        )

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="If admins should be exempt from channel limits")
    async def ignore(
        self,
        inter: discord.Interaction,
        ignore: bool,
        ephemeral: bool = True,
    ):
        if not inter.guild or inter.guild.id not in (
            747752542741725244,
            944968090490380318,
        ):
            await inter.response.send_message("Invalid guild", ephemeral=ephemeral)
            return

        sql.insert_or_update_config("ignore_admins_channel_limit", 1 if ignore else 0)
        self.ignore_admins = ignore
        await inter.response.send_message(
            f"Set ignore admins from channel limits to {ignore}.", ephemeral=ephemeral
        )


async def setup(bot):
    await bot.add_cog(ModerateGroup())
