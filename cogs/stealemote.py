import asyncio
import re
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from helper.sql import SQLFunctions


class StealEmote(commands.Cog):
    """Commands to steal emotes from messages and reactions and add them to your own server."""

    def __init__(self, bot):
        self.bot = bot
        self.conn = SQLFunctions.connect()

    @commands.command(
        usage="stealemote [emote_id | emote_name]",
        aliases=["stealemote", "se"],
    )
    async def steal_emote(self, ctx: commands.Context, id: Optional[int | str] = None):
        """
        Steal emotes of another message by replying to it. An optional ID or name of the emote can be passed in to specify which emote to steal.
        Without any options, all emotes will be stolen. If a name is passed in and there are multiple with the same name, all of them will be stolen.
        """
        if not ctx.message.reference:
            await ctx.reply("Reply to a message to steal emotes from.")
            raise commands.errors.BadArgument()
        async with ctx.typing():
            guilds = SQLFunctions.get_steal_emote_servers(ctx.author.id, self.conn)
            if len(guilds) == 0:
                await ctx.reply(
                    "You have no servers to steal emotes to. Use `$set_server <server_id>` to set a server."
                )
                raise commands.errors.BadArgument()
            message = await ctx.fetch_message(ctx.message.reference.message_id)

            # get all emotes from message
            emote_name_ids: list[tuple[str, str]] = re.findall(
                r"<a?:(\w+):(\d+)>", message.content
            )

            # get all emotes in reactions
            for reaction in message.reactions:
                if isinstance(reaction.emoji, discord.PartialEmoji) or isinstance(
                    reaction.emoji, discord.Emoji
                ):
                    emote_name_ids.append((reaction.emoji.name, str(reaction.emoji.id)))

            if len(emote_name_ids) == 0:
                await ctx.reply("No emotes found in the message.")
                raise commands.errors.BadArgument()
            emote_ids: list[str] = []
            emote_names: dict[str, str] = {}
            for name, emote_id in emote_name_ids:
                if not emote_id.isnumeric():
                    continue
                if id is None:  # add all emotes
                    emote_ids.append(emote_id)
                    emote_names[emote_id] = name
                elif (
                    str(id) == name or str(id) == emote_id
                ):  # add only emotes that match id or name
                    emote_ids.append(emote_id)
                    emote_names[emote_id] = name

            async def fetch(emote_id: str):
                base_url = "https://cdn.discordapp.com/emojis/"
                async with aiohttp.ClientSession() as session:
                    async with session.get(base_url + emote_id) as response:
                        if response.status != 200:
                            return None
                        return await response.read()

            results: list[bytes | None] = await asyncio.gather(
                *[fetch(emote) for emote in emote_ids]
            )
            results: list[bytes] = [result for result in results if result]
            if len(results) == 0:
                await ctx.reply("No *valid* emotes found in the message.")
                raise commands.errors.BadArgument()

            success: list[str] = []
            errors: list[str] = []
            added = []
            for guild_id in guilds:
                try:
                    guild = await self.bot.fetch_guild(guild_id, with_counts=False)
                except Exception:
                    errors.append(f"{guild_id}: Unable to fetch")
                    continue

                for result in results:
                    if result in added:
                        continue
                    try:
                        emoji = await guild.create_custom_emoji(
                            name=emote_names[emote_id], image=result
                        )
                        success.append(f"{guild_id}: Success: {str(emoji)}")
                        added.append(result)
                    except discord.Forbidden:
                        errors.append(
                            f"{guild_id}: Missing permissions (`{emote_names[emote_id]}`)"
                        )
                        continue
                    except discord.HTTPException:
                        errors.append(
                            f"{guild_id}: Failed to add emote (`{emote_names[emote_id]}`)"
                        )
                        continue

            if len(success) > 0:
                success = "**Success:**\n" + "\n".join([f"- {x}" for x in success])
            else:
                success = ""
            if len(errors) > 0:
                errors = "**Errors:**\n" + "\n".join([f"- {x}" for x in errors])
            else:
                errors = ""
            description = "\n\n".join(x for x in [success, errors] if len(x) > 0)
            embed = discord.Embed(description=description)
            await ctx.reply(embed=embed)

    @commands.command(usage="set_server <server_id>", aliases=["setserver"])
    async def set_server(self, ctx: commands.Context, id: int):
        """
        Set the server that $stealemote steals emotes to. You can add multiple servers which will each be tried
        incase there's an error with any.
        """
        try:
            guild = await self.bot.fetch_guild(id)
        except discord.Forbidden:
            await ctx.reply(
                "Blud, I can't see that server. Invite me to your server first."
            )
            raise commands.errors.BadArgument()
        except discord.HTTPException:
            await ctx.reply(
                "Blud, I can't work with that server. Invite me to your server first."
            )
            raise commands.errors.BadArgument()

        try:
            user = await guild.fetch_member(ctx.author.id)
        except discord.Forbidden:
            await ctx.reply(
                "Blud, I can't see that server. Invite me to your server first."
            )
            raise commands.errors.BadArgument()
        except discord.NotFound:
            await ctx.reply("Ayoo, you're not even on that server.")
            raise commands.errors.BadArgument()
        except discord.HTTPException:
            await ctx.reply("Invalid server ID")
            raise commands.errors.BadArgument()

        if not user.guild_permissions.create_expressions:
            await ctx.reply(
                "You don't have the permissions to manage emojis on that server."
            )
            raise commands.errors.BadArgument()

        myself = await guild.fetch_member(self.bot.user.id)
        if not myself.guild_permissions.create_expressions:
            await ctx.reply(
                "I don't have the permissions to create emojis on that server."
            )
            raise commands.errors.BadArgument()

        SQLFunctions.add_steal_emote_server(ctx.author.id, id, self.conn)
        await ctx.reply("Successfully set server for stealing emotes.")

    @commands.command(usage="get_servers", aliases=["getservers"])
    async def get_servers(self, ctx: commands.Context):
        """
        Retrieve all servers that you have configured to steal emotes to.
        """
        servers = SQLFunctions.get_steal_emote_servers(ctx.author.id, self.conn)
        if len(servers) == 0:
            await ctx.reply("You have no servers to steal emotes to.")
            raise commands.errors.BadArgument()
        servers = [str(guild_id) for guild_id in servers]
        await ctx.reply(f"Your servers: {', '.join(f'`{x}`' for x in servers)}")

    @commands.command(usage="remove_server <server_id>", aliases=["removeserver"])
    async def remove_server(self, ctx: commands.Context, id: int):
        """
        Remove a server from the list of servers to steal emotes to.
        """
        SQLFunctions.remove_steal_emote_server(ctx.author.id, id, self.conn)
        await ctx.reply("Successfully removed server from stealing emotes.")


async def setup(bot):
    await bot.add_cog(StealEmote(bot))
