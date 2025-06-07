import asyncio
from dataclasses import dataclass
import io
import re
from typing import Iterable, NewType, Optional

import aiohttp
import discord
from discord.ext import commands
from PIL import Image
from apng import APNG

from helper.sql import SQLFunctions


@dataclass
class LocalEmote:
    name: str
    id: int


@dataclass
class LocalImage:
    url: str
    name: str


@dataclass
class LocalSticker:
    name: str
    sticker: discord.StickerItem


@dataclass
class BytesEmote:
    name: str
    image: bytes


ErrorStr = NewType("ErrorStr", str)


@dataclass
class EmoteState:
    emote: BytesEmote
    emoji: discord.Emoji | ErrorStr
    guild: discord.Guild

    @property
    def success(self) -> bool:
        return isinstance(self.emoji, discord.Emoji)


class StealException(Exception):
    pass


class BotMissingPermissions(StealException):
    pass


class UserMissingPermissions(StealException):
    pass


class UserNotInGuild(StealException):
    pass


class BotNotInGuild(StealException):
    pass


class InvalidInput(StealException):
    pass


@dataclass
class GuildState:
    guild: discord.Guild | int
    error: StealException | None = None


def _get_emotes_from_content(content: str) -> list[LocalEmote]:
    emote_name_ids: list[tuple[str, str]] = re.findall(r"<a?:(\w+):(\d+)>", content)
    return [
        LocalEmote(name, int(emote_id))
        for name, emote_id in emote_name_ids
        if emote_id.isnumeric()
    ]


def _get_emotes_from_embeds(
    embeds: list[discord.Embed],
) -> tuple[list[LocalEmote], list[LocalImage]]:
    images: list[LocalImage] = []
    content: list[str] = []
    for embed in embeds:
        content.append(embed.description or "")
        content.append(embed.title or "")
        content.append(embed.footer.text or "")
        content.append(embed.author.name or "")
        content.extend([f.value for f in embed.fields if f.value])

        if embed.image and embed.image.url:
            images.append(LocalImage(embed.image.url, "embed_image"))
        if embed.thumbnail and embed.thumbnail.url:
            images.append(LocalImage(embed.thumbnail.url, "embed_thumbnail"))

    return _get_emotes_from_content("\n".join(content)), images


def _get_emotes_from_message(
    message: discord.Message,
) -> tuple[list[LocalEmote], list[LocalImage], list[LocalSticker]]:
    content = message.content
    reactions = message.reactions
    images = message.attachments
    stickers = [LocalSticker(sticker.name, sticker) for sticker in message.stickers]

    # if message forwards another message, copy over the content (and hence emote ids) from the forwarded message
    if (
        message.reference
        and message.reference.type == discord.MessageReferenceType.forward
    ):
        for snapshot in message.message_snapshots:
            content += f"\n{snapshot.content}"
            images += snapshot.attachments
            stickers += [
                LocalSticker(sticker.name, sticker) for sticker in snapshot.stickers
            ]

    emotes = _get_emotes_from_content(content)
    for reaction in reactions:
        if (
            isinstance(reaction.emoji, discord.PartialEmoji)
            or isinstance(reaction.emoji, discord.Emoji)
        ) and reaction.emoji.id:
            emotes.append(LocalEmote(reaction.emoji.name, reaction.emoji.id))

    local_images = [LocalImage(img.url, img.filename) for img in images]
    embed_emotes, embed_images = _get_emotes_from_embeds(message.embeds)

    return emotes + embed_emotes, local_images + embed_images, stickers


def _filter_emotes(
    emotes: list[LocalEmote],
    images: list[LocalImage],
    stickers: list[LocalSticker],
    name_ids: Iterable[int | str],
) -> tuple[list[LocalEmote], list[LocalImage], list[LocalSticker]]:
    lower_name_ids = [str(x).lower() for x in name_ids]
    valid_emotes: list[LocalEmote] = []
    valid_images: list[LocalImage] = []
    valid_stickers: list[LocalSticker] = []
    for emote in emotes:
        if str(emote.id) in lower_name_ids or emote.name.lower() in lower_name_ids:
            valid_emotes.append(emote)
    for image in images:
        if str(image.name).lower() in lower_name_ids:
            valid_images.append(image)
    for sticker in stickers:
        if str(sticker.name).lower() in lower_name_ids:
            valid_stickers.append(sticker)
    return valid_emotes, valid_images, valid_stickers


def _convert_apng_to_gif(orig: bytes) -> bytes:
    frames = []
    durations = []
    with io.BytesIO(orig) as file:
        apng = APNG.open(file)
        for frame, control in apng.frames:
            with io.BytesIO() as buffer:
                frame.save(buffer)
                img = Image.open(buffer).convert("RGBA")
                frames.append(img)
                durations.append(control.delay * 10)

    with io.BytesIO() as output:
        frames[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
        )
        return output.getvalue()


async def _download_emotes(
    emotes: list[LocalEmote],
    images: list[LocalImage],
    stickers: list[LocalSticker],
) -> list[BytesEmote]:
    async def fetch_emote(
        emote: LocalEmote, session: aiohttp.ClientSession
    ) -> Optional[BytesEmote]:
        async with session.get(
            f"https://cdn.discordapp.com/emojis/{emote.id}"
        ) as response:
            if response.status != 200:
                return None
            return BytesEmote(emote.name, await response.read())

    async def fetch_image(
        image: LocalImage, session: aiohttp.ClientSession
    ) -> Optional[BytesEmote]:
        async with session.get(image.url) as response:
            if response.status != 200:
                return None
            return BytesEmote(image.name, await response.read())

    async def fetch_sticker(sticker: discord.StickerItem) -> Optional[BytesEmote]:
        if sticker.format == discord.StickerFormatType.lottie:
            # the discord inbuilt ones can't be downloaded
            return None
        sticker_file = await sticker.read()
        if sticker.format == discord.StickerFormatType.apng:
            sticker_file = _convert_apng_to_gif(sticker_file)
        return BytesEmote(
            sticker.name,
            sticker_file,
        )

    async with aiohttp.ClientSession() as session:
        emote_tasks = [fetch_emote(emote, session) for emote in emotes]
        image_tasks = [fetch_image(image, session) for image in images]
        sticker_tasks = [fetch_sticker(sticker.sticker) for sticker in stickers]
        results = await asyncio.gather(*(emote_tasks + image_tasks + sticker_tasks))
        return [result for result in results if result is not None]


async def _assert_guild_permissions(
    bot: discord.Client, guild: discord.Guild | int, user: discord.User | discord.Member
) -> GuildState:
    if isinstance(guild, int):
        try:
            guild = await bot.fetch_guild(guild)
        except discord.NotFound:
            return GuildState(guild, InvalidInput(f"Invalid guild {guild}"))
        except discord.Forbidden:
            return GuildState(guild, BotNotInGuild(f"Bot not in guild {guild}"))

    try:
        member = await guild.fetch_member(user.id)
    except discord.NotFound:
        return GuildState(guild, UserNotInGuild(f"User not in guild {guild.id}"))
    except discord.Forbidden:
        return GuildState(guild, UserNotInGuild(f"User not in guild {guild.id}"))
    except discord.HTTPException:
        return GuildState(guild, BotNotInGuild(f"Bot not in guild {guild.id}"))

    if (
        not member.guild_permissions.create_expressions
        or not member.guild_permissions.manage_emojis
    ):
        return GuildState(
            guild,
            UserMissingPermissions(f"User missing permissions in guild {guild.id}"),
        )

    assert bot.user
    me = await guild.fetch_member(bot.user.id)
    if (
        not me.guild_permissions.create_expressions
        or not me.guild_permissions.manage_emojis
    ):
        return GuildState(
            guild, BotMissingPermissions(f"Bot missing permissions in guild {guild.id}")
        )

    return GuildState(guild)


async def _upload_emotes(
    guilds: list[discord.Guild],
    emotes: list[BytesEmote],
) -> list[EmoteState]:
    async def upload_emote(guild: discord.Guild, emote: BytesEmote) -> EmoteState:
        try:
            corrected_name = "".join([c for c in emote.name if c.isalnum() or c == "_"])
            if not (2 <= len(corrected_name) < 32):
                corrected_name = "placeholder"
            emoji = await guild.create_custom_emoji(
                name=corrected_name,
                image=emote.image,
            )
            return EmoteState(emote, emoji, guild)
        except discord.Forbidden:
            return EmoteState(emote, ErrorStr("Forbidden"), guild)
        except discord.HTTPException as e:
            return EmoteState(emote, ErrorStr(f"Failed to add emote: {e.text}"), guild)

    done: set[bytes] = set()
    success: list[EmoteState] = []
    failed: list[EmoteState] = []
    # try to upload emotes to each server if there are failures
    for guild in guilds:
        succ = await asyncio.gather(
            *[upload_emote(guild, emote) for emote in emotes if emote.image not in done]
        )
        for emote in succ:
            if emote.success:
                done.add(emote.emote.image)
                success.append(emote)
            else:
                failed.append(emote)

        if len(success) == len(emotes):
            break

    return success + failed


class StealEmote(commands.Cog):
    """Commands to steal emotes from messages and reactions and add them to your own server."""

    def __init__(self, bot):
        self.bot = bot
        self.conn = SQLFunctions.connect()

    @commands.command(
        usage="stealemote {emote_ids | emote_names}",
        aliases=["stealemote", "se"],
    )
    async def steal_emote(self, ctx: commands.Context, *name_ids: int | str):
        """
        Steal emotes of another message by replying to it. Optional IDs or names of emotes can be passed in to specify which emote to steal.
        Without any options, all emotes will be stolen. If names are passed in and there are multiple with the same name, all of them will be stolen.

        What will be stolen and turned into emotes: emotes (in normal and embed messages), reactions, images, embed thumbnails, embed images, and stickers (animated ones are buggy).
        """
        if not ctx.message.reference or not ctx.message.reference.message_id:
            await ctx.reply("Reply to a message to steal emotes from.")
            raise commands.errors.BadArgument()
        async with ctx.typing():
            guilds = SQLFunctions.get_steal_emote_servers(ctx.author.id, self.conn)
            if len(guilds) == 0:
                await ctx.reply(
                    "You have no servers to steal emotes to. Use `$set_server <server_id>` to set a server."
                )
                raise commands.errors.BadArgument()

            guild_coros = [
                _assert_guild_permissions(self.bot, guild_id, ctx.author)
                for guild_id in guilds
            ]
            guilds = await asyncio.gather(*guild_coros)
            allowed_guilds = [
                g.guild
                for g in guilds
                if isinstance(g.guild, discord.Guild) and not g.error
            ]
            invalid_guilds = [g for g in guilds if g.error]

            message = await ctx.fetch_message(ctx.message.reference.message_id)

            emotes, images, stickers = _get_emotes_from_message(message)
            if len(name_ids) > 0:
                emotes, images, stickers = _filter_emotes(
                    emotes, images, stickers, name_ids
                )
            bytes_emotes = await _download_emotes(emotes, images, stickers)
            if len(bytes_emotes) == 0:
                await ctx.reply("No *valid* emotes/images found in the message.")
                raise commands.errors.BadArgument()

            emote_states = await _upload_emotes(allowed_guilds, bytes_emotes)
            success = [x for x in emote_states if x.success]
            errors = [x for x in emote_states if not x.success]

            invalid_msg = ""
            success_msg = ""
            errors_msg = ""
            if len(invalid_guilds) > 0:
                invalid_msg = "\n**Invalid Servers:**\n" + "\n".join(
                    [f"- `{x.guild}`: {x.error}" for x in invalid_guilds]
                )
            if len(success) > 0:
                success_msg = "**Success:**\n" + "\n".join(
                    [f"- `{x.guild.id}`: {x.emoji}" for x in success]
                )
            if len(errors) > 0:
                errors_msg = "**Errors:**\n" + "\n".join(
                    [f"- `{x.guild.id}`: ({x.emote.name}) {x.emoji}" for x in errors]
                )

            description = "\n\n".join(
                x for x in [invalid_msg, success_msg, errors_msg] if len(x) > 0
            )
            if len(description) > 2000:
                description = description[:2000] + "..."

            embed = discord.Embed(description=description)
            await ctx.reply(embed=embed)

    @commands.command(usage="set_server <server_id>", aliases=["setserver"])
    async def set_server(self, ctx: commands.Context, id: int):
        """
        Set the server that $stealemote steals emotes to. You can add multiple servers which will each be tried
        incase there's an error with any.
        """
        guild_state = await _assert_guild_permissions(self.bot, id, ctx.author)
        if not guild_state.error and isinstance(guild_state.guild, discord.Guild):
            guilds = SQLFunctions.get_steal_emote_servers(ctx.author.id, self.conn)
            if guild_state.guild.id in guilds:
                await ctx.reply(
                    "You already have that server set. Use `$remove_server <server_id>` to remove it."
                )
                raise commands.errors.BadArgument()
            SQLFunctions.add_steal_emote_server(ctx.author.id, id, self.conn)
            await ctx.reply("Successfully set server for stealing emotes.")
            return

        if isinstance(guild_state.error, BotNotInGuild):
            await ctx.reply(
                "Blud, I can't see that server. Invite me to your server first."
            )
            raise commands.errors.BadArgument()
        if isinstance(guild_state.error, UserNotInGuild):
            await ctx.reply("Ayoo, you're not even on that server.")
            raise commands.errors.BadArgument()
        if isinstance(guild_state.error, UserMissingPermissions):
            await ctx.reply(
                "You don't have the permissions to create/manage emojis on that server."
            )
            raise commands.errors.BadArgument()
        if isinstance(guild_state.error, BotMissingPermissions):
            await ctx.reply(
                "I don't have the permissions to create/manage emojis on that server."
            )
            raise commands.errors.BadArgument()
        if isinstance(guild_state.error, InvalidInput):
            await ctx.reply("Invalid server ID")
            raise commands.errors.BadArgument()

        await ctx.reply("Undefined bevaviour. Whoops. Setting the server failed.")
        raise commands.errors.BadArgument()

    @commands.command(
        usage="get_servers",
        aliases=["getservers", "listservers", "list_servers"],
    )
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
