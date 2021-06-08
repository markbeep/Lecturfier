from helper.sql.SQLTables import *
import logging
import discord

logger = logging.getLogger("peewee")
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


def get_or_create_discord_user(user: discord.User) -> Model:
    isbot = 0
    if user.bot:
        isbot = 1
    new_user, created = DiscordUsers.get_or_create(
        DiscordUserID=user.id,
        defaults={
            "DisplayName": user.display_name,
            "Discriminator": user.discriminator,
            "IsBot": isbot,
            "AvatarURL": user.avatar_url,
            "CreatedAt": user.created_at
        }
    )
    return new_user


def get_or_create_discord_guild(guild: discord.Guild) -> Model:
    new_guild, created = DiscordUsers.get_or_create(
        DiscordGuildID=guild.id,
        defaults={
            "DiscordGuildName": guild.name,
            "DiscordGuildRegion": str(guild.region),
            "GuildChannelCount": len(guild.channels),
            "GuildMemberCount": guild.member_count,
            "GuildRoleCount": len(guild.roles)
        }

    )
    return new_guild


def get_or_create_discord_member(member: discord.Member, semester=0) -> Model:
    try:
        new_member, created = DiscordMembers.get_or_create(
            DiscordUser=member.id,
            DiscordGuild=member.guild.id,
            defaults={
                "JoinedAt": member.joined_at,
                "Nickname": member.nick,
                "Semester": semester}
        )
    except IntegrityError:
        # Missing discord user or discord guild entry
        get_or_create_discord_user(member)
        get_or_create_discord_guild(member.guild)
        new_member = get_or_create_discord_member(member, semester)

    return new_member


def get_or_create_user_statistics(member: discord.Member, subject_id, messages_sent=0, messages_deleted=0, messages_edited=0, characters_sent=0,
                                  words_sent=0, spoilers_sent=0, emojis_sent=0, files_sent=0, file_size_sent=0, images_sent=0, reactions_added=0,
                                  reactions_removed=0, reactions_received=0, reactions_taken_away=0) -> Model:
    model_member = get_or_create_discord_member(member)
    new_statistics, created = UserStatistics.get_or_create(
        Subject=subject_id,
        DiscordMember=model_member,
        defaults={
            "MessagesSent": messages_sent,
            "MessagesDeleted": messages_deleted,
            "MessagesEdited": messages_edited,
            "CharactersSent": characters_sent,
            "WordsSent": words_sent,
            "SpoilersSent": spoilers_sent,
            "EmojisSent": emojis_sent,
            "FilesSent": files_sent,
            "FileSizeSent": file_size_sent,
            "ImagesSent": images_sent,
            "ReactionsAdded": reactions_added,
            "ReactionsRemoved": reactions_removed,
            "ReactionsReceived": reactions_received,
            "ReactionsTakenAway": reactions_taken_away,
        }
    )
    return new_statistics


def update_statistics(member: discord.Member, subject_id: int, messages_sent=0, messages_deleted=0, messages_edited=0, characters_sent=0,
                      words_sent=0, spoilers_sent=0, emojis_sent=0, files_sent=0, file_size_sent=0, images_sent=0, reactions_added=0,
                      reactions_removed=0, reactions_received=0, reactions_taken_away=0) -> None:
    model = get_or_create_user_statistics(member, subject_id)
    logger.debug(msg=f"Adding values to the user with ID {model}")
    model.MessagesSent += messages_sent
    model.MessagesDeleted += messages_deleted
    model.MessagesEdited += messages_edited
    model.CharactersSent += characters_sent
    model.WordsSent += words_sent
    model.SpoilersSent += spoilers_sent
    model.EmojisSent += emojis_sent
    model.FilesSent += files_sent
    model.FileSizeSent += file_size_sent
    model.ImagesSent += images_sent
    model.ReactionsAdded += reactions_added
    model.ReactionsRemoved += reactions_removed
    model.ReactionsReceived += reactions_received
    model.ReactionsTakenAway += reactions_taken_away
    model.save()


def get_current_subject_id(semester: int) -> int:
    logger.debug(msg="Getting current subject ID")
    dt = datetime.datetime.now()
    hour = dt.hour
    minute = dt.minute
    try:
        weekdaytime = WeekDayTimes.select().join(Subjects).where(
            (WeekDayTimes.DayID == dt.weekday())
            & (
                    (hour > WeekDayTimes.TimeFrom.hour)
                    | ((WeekDayTimes.TimeFrom.hour == hour) & (minute >= WeekDayTimes.TimeFrom.minute))
            )
            & (
                    (hour < WeekDayTimes.TimeTo.hour)
                    | ((hour == WeekDayTimes.TimeTo.hour) & (minute < WeekDayTimes.TimeTo.minute))
            )
            & (Subjects.Semester == semester)
        ).get()
        return weekdaytime.Subject
    except DoesNotExist:
        return 0


def get_statistic_rows():
    query = (UserStatistics
             .select(fn.SUM(UserStatistics.MessagesSent).alias("sm"))
             .join(DiscordMembers)
             .join(DiscordUsers)
             .where(DiscordUsers.IsBot == 0)
             .group_by(DiscordUsers.DiscordUserID)
             .order_by(SQL("sm").desc())
             .limit(10)
             )
    for row in query:
        print(row["sm"])