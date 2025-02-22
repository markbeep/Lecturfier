import logging
import sqlite3
from datetime import datetime
import os
from typing import Tuple
import discord

logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.WARNING)


def connect(fp="./data/discord.db") -> sqlite3.Connection:
    if not os.path.exists("./data"):
        os.mkdir("data")
    conn = sqlite3.connect(fp)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    return conn


def get_datetime(dt: str) -> datetime:
    if dt is None:
        return datetime.now()
    if "." in dt:  # strips the microseconds away
        dt = dt.split(".")[0]
    return datetime.fromisoformat(dt)


class DiscordUser:
    def __init__(
        self, DiscordUserID, DisplayName, Discriminator, IsBot, AvatarURL, CreatedAt
    ):
        self.DiscordUserID = DiscordUserID
        self.DisplayName = DisplayName
        self.Discriminator = Discriminator
        self.IsBot = bool(IsBot)
        self.AvatarURL = AvatarURL
        self.CreatedAt = get_datetime(CreatedAt)


def get_or_create_discord_user(
    user: discord.User | discord.Member, conn=connect()
) -> DiscordUser:
    result = conn.execute(
        "SELECT * FROM DiscordUsers WHERE DiscordUserID = ?", (user.id,)
    ).fetchone()
    if result is None:
        # The user doesn't exist in the db
        try:
            conn.execute(
                """INSERT INTO DiscordUsers(DiscordUserID, DisplayName, Discriminator, IsBot, AvatarURL, CreatedAt)
                    VALUES (?,?,?,?,?,?)""",
                (
                    user.id,
                    user.display_name,
                    str(user.discriminator),
                    int(user.bot),
                    str(user.avatar.url if user.avatar else ""),
                    str(user.created_at),
                ),
            )
        finally:
            conn.commit()
        return get_or_create_discord_user(user, conn)
    return DiscordUser(
        DiscordUserID=result[0],
        DisplayName=result[1],
        Discriminator=result[2],
        IsBot=result[3],
        AvatarURL=result[4],
        CreatedAt=result[5],
    )


class DiscordGuild:
    def __init__(self, *args):
        self.DiscordGuildID = args[0]
        self.GuildName = args[1]
        self.GuildRegion = args[2]
        self.GuildChannelCount = args[3]
        self.GuildMemberCount = args[4]
        self.GuildRoleCount = args[5]


def get_or_create_discord_guild(guild: discord.Guild, conn=connect()) -> DiscordGuild:
    result = conn.execute(
        "SELECT * FROM DiscordGuilds WHERE DiscordGuildID = ?", (guild.id,)
    ).fetchone()
    if result is None:
        # The guild doesn't exist in the db
        try:
            conn.execute(
                """INSERT INTO DiscordGuilds(DiscordGuildID, GuildName, GuildRegion, GuildChannelCount, GuildMemberCount, GuildRoleCount) VALUES (?,?,?,?,?,?)""",
                (
                    guild.id,
                    guild.name,
                    "",
                    len(guild.channels),
                    guild.member_count,
                    len(guild.roles),
                ),
            )
        finally:
            conn.commit()
        return get_or_create_discord_guild(guild, conn)
    else:
        return DiscordGuild(*result)


class DiscordMember:
    def __init__(
        self,
        UniqueMemberID,
        DiscordUserID,
        DiscordGuildID,
        JoinedAt,
        Nickname,
        Semester,
        User: DiscordUser | None = None,
    ):
        self.UniqueMemberID = UniqueMemberID
        self.DiscordUserID = DiscordUserID
        self.DiscordGuildID = DiscordGuildID
        self.JoinedAt = get_datetime(JoinedAt)
        self.Nickname = Nickname
        self.Semester = Semester
        self.User = User


def get_or_create_discord_member(
    member: discord.Member, semester=0, conn=connect(), recursion_count=0
) -> DiscordMember:
    sql = """   SELECT  DM.UniqueMemberID, DM.DiscordUserID, DM.DiscordGuildID, DM.JoinedAt, DM.Nickname, DM.Semester,
                        DU.DiscordUserID, DU.DisplayName, DU.Discriminator, DU.IsBot, DU.AvatarURL, DU.CreatedAt
                FROM DiscordMembers DM
                INNER JOIN DiscordUsers DU on DU.DiscordUserID = DM.DiscordUserID
                WHERE DM.DiscordUserID = ? AND DM.DiscordGuildID = ?"""
    result = conn.execute(sql, (member.id, member.guild.id)).fetchone()
    if result is None:
        if recursion_count > 3:
            raise AttributeError
        try:
            try:
                conn.execute(
                    "INSERT INTO DiscordMembers(DiscordUserID, DiscordGuildID, Nickname, JoinedAt, Semester) VALUES (?,?,?,?,?)",
                    (
                        member.id,
                        member.guild.id,
                        member.nick,
                        str(member.joined_at),
                        semester,
                    ),
                )
            finally:
                conn.commit()
        except sqlite3.IntegrityError:
            get_or_create_discord_user(member, conn=conn)
            get_or_create_discord_guild(member.guild, conn=conn)
        return get_or_create_discord_member(member, semester, conn, recursion_count + 1)
    else:
        user = DiscordUser(*result[6:])
        return DiscordMember(*result[:6], User=user)


def get_or_create_user_statistics(member: discord.Member, conn=connect()):
    result = conn.execute(
        """SELECT * FROM UserStatistics US
                 INNER JOIN DiscordMembers DM on DM.UniqueMemberID = US.UniqueMemberID
                 WHERE DM.DiscordUserID = ? AND DM.DiscordGuildID = ?""",
        (member.id, member.guild.id),
    ).fetchone()
    if result is None:
        dm = get_or_create_discord_member(member, conn=conn)
        try:
            conn.execute(
                """INSERT INTO UserStatistics(UniqueMemberID) VALUES (?)""",
                (dm.UniqueMemberID,),
            )
        finally:
            conn.commit()


def update_statistics(
    member: discord.Member,
    conn=connect(),
    messages_sent=0,
    messages_deleted=0,
    messages_edited=0,
    characters_sent=0,
    words_sent=0,
    spoilers_sent=0,
    emojis_sent=0,
    files_sent=0,
    file_size_sent=0,
    images_sent=0,
    reactions_added=0,
    reactions_removed=0,
    reactions_received=0,
    reactions_taken_away=0,
    vote_count=0,
) -> bool:
    """
    Updates the statistics table
    :return: True if a new entry was created, False otherwise
    """
    dm = get_or_create_discord_member(member, conn=conn)
    sql = """   UPDATE OR IGNORE UserStatistics
                SET MessagesSent = MessagesSent + ?,
                    MessagesDeleted = MessagesDeleted + ?,
                    MessagesEdited = MessagesEdited + ?,
                    CharactersSent = CharactersSent + ?,
                    WordsSent = WordsSent + ?,
                    SpoilersSent = SpoilersSent + ?,
                    EmojisSent = EmojisSent + ?,
                    FilesSent = FilesSent + ?,
                    FileSizeSent = FileSizeSent + ?,
                    ImagesSent = ImagesSent + ?,
                    ReactionsAdded = ReactionsAdded + ?,
                    ReactionsRemoved = ReactionsRemoved + ?,
                    ReactionsReceived = ReactionsReceived + ?,
                    ReactionsTakenAway = ReactionsTakenAway + ?,
                    VoteCount = VoteCount + ?
                WHERE UniqueMemberID = ?"""
    value = False
    try:
        rows = conn.execute(
            sql,
            (
                messages_sent,
                messages_deleted,
                messages_edited,
                characters_sent,
                words_sent,
                spoilers_sent,
                emojis_sent,
                files_sent,
                file_size_sent,
                images_sent,
                reactions_added,
                reactions_removed,
                reactions_received,
                reactions_taken_away,
                vote_count,
                dm.UniqueMemberID,
            ),
        ).rowcount
        conn.commit()
        if rows == 0:
            get_or_create_user_statistics(member, conn)
            conn.execute(
                sql,
                (
                    messages_sent,
                    messages_deleted,
                    messages_edited,
                    characters_sent,
                    words_sent,
                    spoilers_sent,
                    emojis_sent,
                    files_sent,
                    file_size_sent,
                    images_sent,
                    reactions_added,
                    reactions_removed,
                    reactions_received,
                    reactions_taken_away,
                    vote_count,
                    dm.UniqueMemberID,
                ),
            )
            conn.commit()
            value = True
    finally:
        conn.commit()
    return value


def get_statistic_rows(column, limit, conn=connect()):
    sql = f"""  SELECT
                    ums.UniqueMemberID,
                    dm.DiscordUserID,
                    dm.DiscordGuildID,
                    dm.JoinedAt,
                    dm.Semester,
                    dm.Nickname,
                    SUM({column}) as sm,
                    RANK() OVER (order by {column} desc) rank
                FROM UserStatistics ums
                INNER JOIN DiscordMembers as dm on dm.UniqueMemberID=ums.UniqueMemberID
                INNER JOIN DiscordUsers DU on dm.DiscordUserID = DU.DiscordUserID
                WHERE DU.IsBot=0
                GROUP BY ums.UniqueMemberID
                ORDER BY sm DESC
                LIMIT ?"""
    result = conn.execute(sql, (limit,)).fetchall()
    stats = []
    for row in result:
        member = DiscordMember(
            UniqueMemberID=row[0],
            DiscordUserID=row[1],
            DiscordGuildID=row[2],
            JoinedAt=row[3],
            Semester=row[4],
            Nickname=row[5],
        )
        stats.append((member, row[6], row[7]))
    return stats


class UserStatistics:
    def __init__(
        self,
        MessagesSent,
        MessagesDeleted,
        MessagesEdited,
        CharactersSent,
        WordsSent,
        SpoilersSent,
        EmojisSent,
        FilesSent,
        FileSizeSent,
        ImagesSent,
        ReactionsAdded,
        ReactionsRemoved,
        ReactionsReceived,
        ReactionsTakenAway,
        VoteCount,
        MessagesSentRank,
        MessagesDeletedRank,
        MessagesEditedRank,
        CharactersSentRank,
        WordsSentRank,
        SpoilersSentRank,
        EmojisSentRank,
        FilesSentRank,
        FileSizeSentRank,
        ImagesSentRank,
        ReactionsAddedRank,
        ReactionsRemovedRank,
        ReactionsReceivedRank,
        ReactionsTakenAwayRank,
        VoteCountRank,
    ):
        self.MessagesSent = MessagesSent
        self.MessagesDeleted = MessagesDeleted
        self.MessagesEdited = MessagesEdited
        self.CharactersSent = CharactersSent
        self.WordsSent = WordsSent
        self.SpoilersSent = SpoilersSent
        self.EmojisSent = EmojisSent
        self.FilesSent = FilesSent
        self.FileSizeSent = FileSizeSent
        self.ImagesSent = ImagesSent
        self.ReactionsAdded = ReactionsAdded
        self.ReactionsRemoved = ReactionsRemoved
        self.ReactionsReceived = ReactionsReceived
        self.ReactionsTakenAway = ReactionsTakenAway
        self.VoteCount = VoteCount

        self.MessagesSentRank = MessagesSentRank
        self.MessagesDeletedRank = MessagesDeletedRank
        self.MessagesEditedRank = MessagesEditedRank
        self.CharactersSentRank = CharactersSentRank
        self.WordsSentRank = WordsSentRank
        self.SpoilersSentRank = SpoilersSentRank
        self.EmojisSentRank = EmojisSentRank
        self.FilesSentRank = FilesSentRank
        self.FileSizeSentRank = FileSizeSentRank
        self.ImagesSentRank = ImagesSentRank
        self.ReactionsAddedRank = ReactionsAddedRank
        self.ReactionsRemovedRank = ReactionsRemovedRank
        self.ReactionsReceivedRank = ReactionsReceivedRank
        self.ReactionsTakenAwayRank = ReactionsTakenAwayRank
        self.VoteCountRank = VoteCountRank


def get_statistics_per_user(
    member_id: discord.abc.Snowflake,
    guild_id: discord.abc.Snowflake,
    order_desc=True,
    conn=connect(),
) -> UserStatistics:
    desc = "desc" if order_desc else "asc"
    sql = f"""  SELECT
                    MessagesSent, rank.ms,
                    MessagesDeleted, rank.md,
                    MessagesEdited, rank.me,
                    CharactersSent, rank.cs,
                    WordsSent, rank.ws,
                    SpoilersSent, rank.ss,
                    EmojisSent, rank.es,
                    FilesSent, rank.fs,
                    FileSizeSent, rank.fss,
                    ImagesSent, rank.ims,
                    ReactionsAdded, rank.ra,
                    ReactionsRemoved, rank.rrm,
                    ReactionsReceived, rank.rrv,
                    ReactionsTakenAway, rank.rta,
                    VoteCount, rank.vc
                FROM UserStatistics ums
                INNER JOIN DiscordMembers as dm on dm.UniqueMemberID=ums.UniqueMemberID
                INNER JOIN
                    (SELECT
                        uniquememberid,
                        RANK() OVER (order by MessagesSent {desc}) ms,
                        RANK() OVER (order by MessagesDeleted {desc}) md,
                        RANK() OVER (order by MessagesEdited {desc}) me,
                        RANK() OVER (order by CharactersSent {desc}) cs,
                        RANK() OVER (order by WordsSent {desc}) ws,
                        RANK() OVER (order by SpoilersSent {desc}) ss,
                        RANK() OVER (order by EmojisSent {desc}) es,
                        RANK() OVER (order by FilesSent {desc}) fs,
                        RANK() OVER (order by FileSizeSent {desc}) fss,
                        RANK() OVER (order by ImagesSent {desc}) ims,
                        RANK() OVER (order by ReactionsAdded {desc}) ra,
                        RANK() OVER (order by ReactionsRemoved {desc}) rrm,
                        RANK() OVER (order by ReactionsReceived {desc}) rrv,
                        RANK() OVER (order by ReactionsTakenAway {desc}) rta,
                        RANK() OVER (order by VoteCount {desc}) vc
                    FROM UserStatistics
                    INNER JOIN DiscordMembers USING (UniqueMemberID)
                    INNER JOIN DiscordUsers USING (DiscordUserId)
                    WHERE DiscordGuildID=? AND IsBot=0
                    ) rank ON ums.UniqueMemberID=rank.UniqueMemberID
                WHERE dm.DiscordUserID=?"""
    result = conn.execute(sql, (guild_id, member_id)).fetchone()

    return UserStatistics(
        MessagesSent=result[0],
        MessagesDeleted=result[2],
        MessagesEdited=result[4],
        CharactersSent=result[6],
        WordsSent=result[8],
        SpoilersSent=result[10],
        EmojisSent=result[12],
        FilesSent=result[14],
        FileSizeSent=result[16],
        ImagesSent=result[18],
        ReactionsAdded=result[20],
        ReactionsRemoved=result[22],
        ReactionsReceived=result[24],
        ReactionsTakenAway=result[26],
        VoteCount=result[28],
        MessagesSentRank=result[1],
        MessagesDeletedRank=result[3],
        MessagesEditedRank=result[5],
        CharactersSentRank=result[7],
        WordsSentRank=result[9],
        SpoilersSentRank=result[11],
        EmojisSentRank=result[13],
        FilesSentRank=result[15],
        FileSizeSentRank=result[17],
        ImagesSentRank=result[19],
        ReactionsAddedRank=result[21],
        ReactionsRemovedRank=result[23],
        ReactionsReceivedRank=result[25],
        ReactionsTakenAwayRank=result[27],
        VoteCountRank=result[29],
    )


def get_total_statistics_score(
    guild_id: discord.abc.Snowflake, limit: int, include_bots=False, conn=connect()
):
    sql = f"""
        SELECT
            DiscordUserID,
            RANK() OVER (order by MessagesSent) +
            RANK() OVER (order by MessagesDeleted) +
            RANK() OVER (order by MessagesEdited) +
            RANK() OVER (order by CharactersSent) +
            RANK() OVER (order by WordsSent) +
            RANK() OVER (order by SpoilersSent) +
            RANK() OVER (order by EmojisSent) +
            RANK() OVER (order by FilesSent) +
            RANK() OVER (order by FileSizeSent) +
            RANK() OVER (order by ImagesSent) +
            RANK() OVER (order by ReactionsAdded) +
            RANK() OVER (order by ReactionsRemoved) +
            RANK() OVER (order by ReactionsReceived) +
            RANK() OVER (order by ReactionsTakenAway) +
            RANK() OVER (order by VoteCount) AS score
        FROM UserStatistics
        INNER JOIN DiscordMembers USING (UniqueMemberID)
        WHERE DiscordGuildID=? {"AND IsBot=0" if include_bots else ""}
        ORDER BY score DESC
        LIMIT ?
    """
    result = conn.execute(sql, (guild_id, limit)).fetchall()
    return result


def get_total_statistics_score_user(
    member_id: discord.abc.Snowflake,
    guild_id: discord.abc.Snowflake,
    include_bots=False,
    conn=connect(),
) -> Tuple[int, int]:
    sql = f"""
        SELECT
            score,
            rank
        FROM
            (SELECT
                DiscordUserID,
                score,
                RANK() OVER (order by score DESC) rank
            FROM
                (SELECT
                    UniqueMemberId,
                    DiscordUserID,
                    RANK() OVER (order by MessagesSent) +
                    RANK() OVER (order by MessagesDeleted) +
                    RANK() OVER (order by MessagesEdited) +
                    RANK() OVER (order by CharactersSent) +
                    RANK() OVER (order by WordsSent) +
                    RANK() OVER (order by SpoilersSent) +
                    RANK() OVER (order by EmojisSent) +
                    RANK() OVER (order by FilesSent) +
                    RANK() OVER (order by FileSizeSent) +
                    RANK() OVER (order by ImagesSent) +
                    RANK() OVER (order by ReactionsAdded) +
                    RANK() OVER (order by ReactionsRemoved) +
                    RANK() OVER (order by ReactionsReceived) +
                    RANK() OVER (order by ReactionsTakenAway) +
                    RANK() OVER (order by VoteCount) AS score
                FROM UserStatistics
                INNER JOIN DiscordMembers USING (UniqueMemberID)
                WHERE DiscordGuildID=? {"AND IsBot=0" if include_bots else ""}
                )
            )
        WHERE DiscordUserId=?
    """
    result = conn.execute(sql, (guild_id, member_id)).fetchone()
    return result


class Event:
    def __init__(
        self,
        event_id,
        event_name,
        event_created_at,
        event_starting_at,
        event_description,
        unique_member_id,
        updated_message_id,
        updated_channel_id,
        is_done,
        specific_channel_id,
        discord_member=None,
    ):
        self.EventID = event_id
        self.EventName = event_name
        self.EventCreatedAt = get_datetime(event_created_at)
        self.EventStartingAt = get_datetime(event_starting_at)
        self.EventDescription = event_description
        self.UniqueMemberID = unique_member_id
        self.DiscordMember: DiscordMember | None = discord_member
        self.UpdatedMessageID = updated_message_id
        self.UpdatedChannelID = updated_channel_id
        self.SpecificChannelID = specific_channel_id
        self.IsDone = bool(is_done)


def get_events(
    conn=connect(),
    is_done=None,
    limit=None,
    guild_id: int | None = None,
    order=False,
    by_user_id=None,
    row_id=None,
    event_id=None,
) -> list:
    """
    Returns a list of Event objects
    :param event_id:
    :param row_id:
    :param by_user_id:
    :param order:
    :param guild_id:
    :param guild:
    :param conn: SQLite connection
    :param is_done: If only finished or only unfinished or both events should be shown
    :param limit:
    :return:
    """
    sql = """   SELECT  E.EventID, E.EventName, E.EventCreatedAt, E.EventStartingAt, E.EventDescription, E.UniqueMemberID,
                        E.UpdatedChannelID, E.UpdatedMessageID, E.SpecificChannelID, E.IsDone, DM.UniqueMemberID,
                        DM.DiscordUserID, DM.DiscordGuildID, DM.JoinedAt, DM.Nickname, DM.Semester
                FROM Events as E
                INNER JOIN DiscordMembers DM on E.UniqueMemberID = DM.UniqueMemberID
                WHERE true"""
    values = []
    if is_done is not None:
        sql += " AND E.IsDone=?"
        values.append(int(is_done))
    if guild_id is not None:
        sql += " AND DM.DiscordGuildID=?"
        values.append(guild_id)
    if by_user_id is not None:
        sql += " AND DM.DiscordUserID=?"
        values.append(by_user_id)
    if row_id is not None:
        sql += " AND E.ROWID=?"
        values.append(row_id)
    if event_id is not None:
        sql += " AND E.EventID=?"
        values.append(event_id)
    if order:
        sql += " ORDER BY E.EventStartingAt"
    if limit is not None:
        sql += " LIMIT ?"
        values.append(limit)
    logger.debug(sql)
    result = conn.execute(sql, values).fetchall()
    events = []
    for row in result:
        member = DiscordMember(
            UniqueMemberID=row[10],
            DiscordUserID=row[11],
            DiscordGuildID=row[12],
            JoinedAt=row[13],
            Nickname=row[14],
            Semester=row[15],
        )
        event = Event(
            event_id=row[0],
            event_name=row[1],
            event_created_at=row[2],
            event_starting_at=row[3],
            event_description=row[4],
            unique_member_id=row[5],
            updated_channel_id=row[6],
            updated_message_id=row[7],
            specific_channel_id=row[8],
            is_done=row[9],
            discord_member=member,
        )
        events.append(event)
    return events


def get_event_by_id(event_id, conn=connect()) -> Event | None:
    event_results = get_events(conn, event_id=int(event_id))
    if len(event_results) == 0:
        return None
    return event_results[0]


def create_event(
    event_name,
    event_starting_at,
    event_description,
    member: DiscordMember,
    conn=connect(),
) -> Event:
    try:
        row_id = conn.execute(
            "INSERT INTO Events(EventName, EventStartingAt, EventDescription, UniqueMemberID) VALUES (?,?,?,?)",
            (
                event_name,
                str(event_starting_at),
                event_description,
                member.UniqueMemberID,
            ),
        ).lastrowid
    finally:
        conn.commit()
    events = get_events(conn, row_id=row_id)
    return events[0]


def delete_event(event: Event, conn=connect()):
    try:
        conn.execute("DELETE FROM Events WHERE EventID=?", (event.EventID,))
    finally:
        conn.commit()


def get_event_joined_users(event: Event, conn=connect()) -> list[DiscordMember]:
    if type(event) is int:
        event_id = int(event)
    else:
        event_id = event.EventID
    sql = """   SELECT DM.UniqueMemberID, DM.DiscordUserID, DM.DiscordGuildID, DM.JOinedAt, DM.Nickname, DM.Semester FROM EventJoinedUsers EJU
                INNER JOIN DiscordMembers DM on EJU.UniqueMemberID = DM.UniqueMemberID
                WHERE EventID=?"""
    result = conn.execute(sql, (event_id,)).fetchall()
    joined_members = []
    for row in result:
        joined_members.append(
            DiscordMember(
                UniqueMemberID=row[0],
                DiscordUserID=row[1],
                DiscordGuildID=row[2],
                JoinedAt=row[3],
                Nickname=row[4],
                Semester=row[5],
            )
        )
    return joined_members


def mark_events_done(current_time=datetime.now(), conn=connect()) -> int:
    try:
        events_changed = conn.execute(
            "Update Events SET IsDone=1 WHERE EventStartingAt < ?", (str(current_time),)
        ).rowcount
    finally:
        conn.commit()
    return events_changed


def add_member_to_event(
    event: Event, member_to_add: DiscordMember, conn=connect(), host=False
):
    logger.debug(f"Adding {member_to_add.DiscordUserID} to {event.EventID}")
    try:
        conn.execute(
            "INSERT INTO EventJoinedUsers(EventID, UniqueMemberID, IsHost) VALUES (?,?,?)",
            (event.EventID, member_to_add.UniqueMemberID, int(host)),
        )
    finally:
        conn.commit()


def remove_member_from_event(
    event: Event, member_to_remove: DiscordMember, conn=connect()
):
    logger.debug(f"Removing {member_to_remove.DiscordUserID} from {event.EventID}")
    try:
        conn.execute(
            "DELETE FROM EventJoinedUsers WHERE EventID=? AND UniqueMemberID=?",
            (event.EventID, member_to_remove.UniqueMemberID),
        )
    finally:
        conn.commit()


def add_event_updated_message(message_id, channel_id, event_id, conn=connect()):
    try:
        conn.execute(
            "UPDATE Events SET UpdatedMessageID=?, UpdatedChannelID=? WHERE EventID=?",
            (message_id, channel_id, event_id),
        )
    finally:
        conn.commit()


def set_specific_event_channel(event_id: int, specific_channel=None, conn=connect()):
    try:
        conn.execute(
            "UPDATE Events SET SpecificChannelID=? WHERE EventID=?",
            (specific_channel, event_id),
        )
    finally:
        conn.commit()


def get_config(key, conn=connect()) -> list:
    values = conn.execute(
        "SELECT ConfigValue FROM Config WHERE ConfigKey=?", (key,)
    ).fetchall()
    return [x[0] for x in values]


def delete_config(key, conn=connect()):
    try:
        conn.execute("DELETE FROM Config WHERE ConfigKey=?", (key,))
    finally:
        conn.commit()


def insert_or_update_config(key, value, conn=connect()):
    try:
        rows_changed = conn.execute(
            "UPDATE OR IGNORE Config SET ConfigValue=? WHERE ConfigKey=?", (value, key)
        ).rowcount
        if rows_changed == 0:
            conn.execute(
                "INSERT INTO Config(ConfigKey, ConfigValue) VALUES (?,?)", (key, value)
            )
    finally:
        conn.commit()


class CovidGuesser:
    def __init__(
        self,
        UniqueMemberID,
        TotalPointsAmount,
        GuessCount,
        NextGuess,
        TempPoints,
        member: DiscordMember,
    ):
        self.UniqueMemberID = UniqueMemberID
        self.TotalPointsAmount = TotalPointsAmount
        self.GuessCount = GuessCount
        self.NextGuess = NextGuess
        self.TempPoints = TempPoints
        self.member = member
        if (count := GuessCount) == 0:
            count = 1
        self.average = TotalPointsAmount / count


def get_covid_guessers(
    conn=connect(), guessed=False, discord_user_id=None, guild_id=None
) -> list[CovidGuesser]:
    sql = """   SELECT  CG.UniqueMemberID, CG.TotalPointsAmount, CG.GuessCount, CG.NextGuess, CG.TempPoints,
                        DM.DiscordUserID, DM.DiscordGuildID, DM.JoinedAt, DM.Nickname, DM.Semester
                FROM CovidGuessing CG
                INNER JOIN DiscordMembers DM on DM.UniqueMemberID = CG.UniqueMemberID
                WHERE true"""
    values = []
    if guessed is True:
        sql += " AND CG.NextGuess IS NOT NULL"
    if discord_user_id is not None:
        sql += " AND DM.DiscordUserID=?"
        values.append(discord_user_id)
    if guild_id is not None:
        sql += " AND DM.DiscordGuildID=?"
        values.append(guild_id)
    results = conn.execute(sql, values).fetchall()
    guessers = []
    for row in results:
        member = DiscordMember(
            UniqueMemberID=row[0],
            DiscordUserID=row[5],
            DiscordGuildID=row[6],
            JoinedAt=row[7],
            Nickname=row[8],
            Semester=row[9],
        )
        g = CovidGuesser(
            UniqueMemberID=row[0],
            TotalPointsAmount=row[1],
            GuessCount=row[2],
            NextGuess=row[3],
            TempPoints=row[4],
            member=member,
        )
        guessers.append(g)
    return guessers


def clear_covid_guesses(users: list[CovidGuesser], increment=True, conn=connect()):
    for guesser in users:
        points_gotten = guesser.TempPoints
        if points_gotten is None:
            points_gotten = 0
        sql = """   UPDATE CovidGuessing
                    SET
                        TotalPointsAmount=?,
                        GuessCount=GuessCount+?,
                        TempPoints=NULL,
                        NextGuess=NULL
                    WHERE
                        UniqueMemberID=?"""
        try:
            conn.execute(
                sql,
                (
                    guesser.TotalPointsAmount + points_gotten,
                    int(increment),
                    guesser.member.UniqueMemberID,
                ),
            )
        finally:
            conn.commit()


def insert_or_update_covid_guess(member: DiscordMember, guess: int, conn=connect()):
    try:
        rows_changed = conn.execute(
            "UPDATE OR IGNORE CovidGuessing SET NextGuess=? WHERE UniqueMemberID=?",
            (guess, member.UniqueMemberID),
        ).rowcount
        if rows_changed == 0:
            conn.execute(
                "INSERT INTO CovidGuessing(UniqueMemberID, NextGuess) VALUES(?,?)",
                (member.UniqueMemberID, guess),
            )
    finally:
        conn.commit()


class Quote:
    def __init__(
        self,
        QuoteID,
        QuoteText,
        Name,
        UniqueMemberID,
        CreatedAt,
        AddedByUniqueMemberID,
        DiscordGuildID,
        AmountBattled,
        AmountWon,
        Elo,
        Member: DiscordMember | None = None,
    ):
        self.QuoteID = QuoteID
        self.QuoteText = QuoteText
        self.Name = Name
        self.UniqueMemberID = UniqueMemberID
        self.Member = Member
        self.CreatedAt = get_datetime(CreatedAt)
        self.AddedByUniqueMemberID = AddedByUniqueMemberID
        self.DiscordGuildID = DiscordGuildID
        self.AmountBattled = AmountBattled
        self.AmountWon = AmountWon
        self.Elo = Elo

    def __repr__(self):
        return str(self.QuoteID)


def get_quote(
    quote_ID, guild_id, conn=connect(), row_id=None, random=False
) -> Quote | None:
    values = "QuoteID, Quote, Name, UniqueMemberID, CreatedAt, AddedByUniqueMemberID, DiscordGuildID, AmountBattled, AmountWon, Elo"
    if random:
        row = conn.execute(
            f"SELECT {values} FROM Quotes WHERE DiscordGuildID=? ORDER BY RANDOM() LIMIT 1",
            (guild_id,),
        ).fetchone()
    elif row_id is not None:
        row = conn.execute(
            f"SELECT {values} FROM Quotes WHERE ROWID=? AND DiscordGuildID=?",
            (row_id, guild_id),
        ).fetchone()
    else:
        row = conn.execute(
            f"SELECT {values} FROM Quotes WHERE QuoteID=? AND DiscordGuildID=?",
            (quote_ID, guild_id),
        ).fetchone()
    if row is None:
        return None
    return Quote(
        QuoteID=row[0],
        QuoteText=row[1],
        Name=row[2],
        UniqueMemberID=row[3],
        CreatedAt=row[4],
        AddedByUniqueMemberID=row[5],
        DiscordGuildID=row[6],
        AmountBattled=row[7],
        AmountWon=row[8],
        Elo=row[9],
    )


def get_quotes(
    discord_user_id=None,
    unique_member_id=None,
    name=None,
    quote=None,
    guild_id=None,
    conn: sqlite3.Connection | None = connect(),
    random=False,
    limit=None,
    rank_by_elo=False,
) -> list[Quote]:
    if not conn:
        conn = connect()
    sql = """   SELECT  Q.QuoteID, Q.Quote, Q.Name, Q.UniqueMemberID, Q.CreatedAt, Q.AddedByUniqueMemberID, Q.DiscordGuildID,
                        DM.UniqueMemberID, DM.DiscordUserID, DM.DiscordGuildID, DM.JoinedAt, DM.Nickname, DM.Semester,
                        Q.AmountBattled, Q.AmountWon, Q.Elo
                FROM Quotes Q
                LEFT JOIN DiscordMembers DM on Q.UniqueMemberID = DM.UniqueMemberID
                WHERE true"""
    values = []
    if discord_user_id is not None:
        sql += " AND DM.DiscordUserID=?"
        values.append(discord_user_id)
    if unique_member_id is not None:
        sql += " AND Q.UniqueMemberID=?"
        values.append(unique_member_id)
    if name is not None:
        sql += " AND Q.Name LIKE ?"
        values.append(name)
    if quote is not None:
        quote = "%" + quote + "%"
        sql += " AND Q.Quote LIKE ?"
        values.append(quote)
    if guild_id is not None:
        sql += " AND Q.DiscordGuildID=?"
        values.append(guild_id)
    if random:
        sql += " ORDER BY RANDOM()"
    if rank_by_elo:
        sql += " ORDER BY Q.Elo DESC"
    if limit is not None:
        sql += " LIMIT ?"
        values.append(limit)
    result = conn.execute(sql, values).fetchall()
    quotes = []
    for row in result:
        member = None
        if row[7] is not None:
            member = DiscordMember(
                UniqueMemberID=row[7],
                DiscordUserID=row[8],
                DiscordGuildID=row[9],
                JoinedAt=row[10],
                Nickname=row[11],
                Semester=row[12],
            )
        quote = Quote(
            QuoteID=row[0],
            QuoteText=str(row[1]),
            Name=row[2],
            UniqueMemberID=row[3],
            CreatedAt=row[4],
            AddedByUniqueMemberID=row[5],
            DiscordGuildID=row[6],
            Member=member,
            AmountBattled=row[13],
            AmountWon=row[14],
            Elo=row[15],
        )
        quotes.append(quote)
    return quotes


def get_members_by_name(
    name, guild_id, discord_user_id=None, conn=connect()
) -> list[DiscordMember]:
    values = [guild_id]
    if discord_user_id is not None:
        fill = "DM.DiscordUserID=?"
        values.append(discord_user_id)
    else:
        fill = "Q.Name LIKE ?"
        values.append(name)
    sql = f"""  SELECT  DM.UniqueMemberID, DM.DiscordUserID, DM.DiscordGuildID, DM.JoinedAt, DM.Nickname, DM.Semester,
                        DU.DiscordUserID, DU.DisplayName, DU.Discriminator, DU.IsBot, DU.AvatarURL, DU.CreatedAt
                FROM Quotes Q
                LEFT JOIN DiscordMembers DM on Q.UniqueMemberID = DM.UniqueMemberID
                LEFT JOIN DiscordUsers DU on DU.DiscordUserID = DM.DiscordUserID
                WHERE Q.DiscordGuildID=? AND {fill}
                GROUP BY DM.UniqueMemberID"""
    results = conn.execute(sql, values).fetchall()
    members = []
    for row in results:
        if row[0] is None:
            continue
        user = DiscordUser(*row[6:])
        members.append(DiscordMember(*row[:6], User=user))
    return members


def add_quote(
    quote,
    name,
    member: DiscordMember | None,
    added_by: DiscordMember,
    guild_id,
    conn=connect(),
) -> Quote | None:
    unique_member_id = None
    if member is not None:
        unique_member_id = member.UniqueMemberID
    values = [quote, name, unique_member_id, added_by.UniqueMemberID, guild_id]
    try:
        row_id = conn.execute(
            "INSERT INTO Quotes(Quote, Name, UniqueMemberID, AddedByUniqueMemberID, DiscordGuildID) VALUES (?,?,?,?,?)",
            values,
        ).lastrowid
    finally:
        conn.commit()
    return get_quote(-1, guild_id=guild_id, row_id=row_id, conn=conn)


def delete_quote(quote_id, conn=connect()):
    try:
        conn.execute("DELETE FROM Quotes WHERE QuoteID=?", (quote_id,))
    finally:
        conn.commit()


def delete_quote_to_remove(quote_id, conn=connect()):
    try:
        conn.execute("DELETE FROM main.QuotesToRemove WHERE QuoteID=?", (quote_id,))
    finally:
        conn.commit()


def get_quote_aliases(conn=connect()) -> dict[str, str]:
    result = conn.execute("SELECT NameFrom, NameTo FROM QuoteAliases").fetchall()
    aliases = {}
    for row in result:
        aliases[row[0]] = row[1]
    return aliases


def get_quote_stats(guild_id: int, conn=connect()) -> tuple[int, int, int]:
    """
    :return: (total_quotes, total_names)
    """
    total_quotes = conn.execute(
        "SELECT COUNT(*) FROM Quotes WHERE DiscordGuildID = ?", (guild_id,)
    ).fetchone()
    total_names = conn.execute(
        "SELECT COUNT(DISTINCT Name) FROM Quotes WHERE DiscordGuildID = ?", (guild_id,)
    ).fetchone()
    total_voted_on = conn.execute(
        "SELECT COUNT(*) FROM Quotes WHERE AmountBattled > 0 AND DiscordGuildID = ?",
        (guild_id,),
    ).fetchone()
    return total_quotes[0], total_names[0], total_voted_on[0]


def update_quote_battle(
    quote_id,
    battles_amount,
    battles_won,
    elo,
    conn: sqlite3.Connection | None = connect(),
):
    if not conn:
        conn = connect()
    sql = "UPDATE Quotes SET AmountBattled=?, AmountWon=?, Elo=? WHERE QuoteID=?"
    try:
        conn.execute(sql, (battles_amount, battles_won, elo, quote_id))
    finally:
        conn.commit()


def get_favorite_quotes_of_user(member: discord.Member, conn=connect()) -> list[Quote]:
    dm = get_or_create_discord_member(member, 0, conn)
    sql = """   SELECT Q.QuoteID, Q.Quote, Q.Name, Q.UniqueMemberID,
                       Q.CreatedAt, Q.AddedByUniqueMemberID, Q.DiscordGuildID,
                       Q.AmountBattled, Q.AmountWon, Q.Elo
                FROM FavoriteQuotes FQ
                INNER JOIN Quotes Q on FQ.QuoteID = Q.QuoteID
                WHERE FQ.UniqueMemberID = ?"""
    rows = conn.execute(sql, (dm.UniqueMemberID,))
    return [Quote(*q) for q in rows]


def add_favorite_quote(member: discord.Member, quote_id: int, conn=connect()):
    dm = get_or_create_discord_member(member, 0, conn)
    try:
        conn.execute(
            "INSERT INTO FavoriteQuotes(QuoteID, UniqueMemberID) VALUES (?,?)",
            (quote_id, dm.UniqueMemberID),
        )
    finally:
        conn.commit()


def remove_favorite_quote(member: discord.Member, quote_id: int, conn=connect()):
    dm = get_or_create_discord_member(member, 0, conn)
    try:
        conn.execute(
            "DELETE FROM FavoriteQuotes WHERE QuoteID=? AND UniqueMemberID=?",
            (quote_id, dm.UniqueMemberID),
        )
    finally:
        conn.commit()


class Name:
    def __init__(
        self, total_quotes: int, quote: Quote, member: DiscordMember | None = None
    ):
        self.total_quotes = total_quotes
        self.quote = quote
        self.member = member


def get_quoted_names(guild: discord.Guild, conn=connect()) -> list[Name]:
    sql = """   SELECT  COUNT(*), DM.UniqueMemberID, DM.DiscordUserID, DM.DiscordGuildID, DM.JoinedAt, DM.Nickname, DM.Semester,
                        Q.QuoteID, Q.Quote, Q.Name, Q.UniqueMemberID, Q.CreatedAt, Q.AddedByUniqueMemberID, Q.DiscordGuildID,
                        Q.AmountBattled, Q.AmountWon, Q.Elo
                FROM Quotes Q
                LEFT JOIN DiscordMembers DM on Q.UniqueMemberID = DM.UniqueMemberID
                WHERE DM.DiscordGuildID=?
                GROUP BY Q.Name
                ORDER BY COUNT(*) DESC"""
    results = conn.execute(sql, (guild.id,)).fetchall()
    all_names = []
    for row in results:
        member = None
        if row[1] is not None:
            member = DiscordMember(*row[1:7])
        quote = Quote(*row[7:], Member=member)
        all_names.append(Name(row[0], quote, member))
    return all_names


class QuoteToRemove:
    def __init__(self, quote: Quote, reason: str, member: DiscordMember):
        self.Quote = quote
        self.Reporter = member
        self.Reason = reason


def get_quotes_to_remove(guild_id, conn=connect()) -> list[QuoteToRemove]:
    sql = """   SELECT  DM.UniqueMemberID, DM.DiscordUserID, DM.DiscordGuildID, DM.JoinedAt, DM.Nickname, DM.Semester, --Quote Member
                        Q.QuoteID, Q.Quote, Q.Name, Q.UniqueMemberID, Q.CreatedAt, Q.AddedByUniqueMemberID, Q.DiscordGuildID, Q.AmountBattled,
                        Q.AmountWon, Q.Elo, -- Quote
                        REP.UniqueMemberID, REP.DiscordUserID, REP.DiscordGuildID, REP.JoinedAt, REP.Nickname, REP.Semester, -- Reporter
                        QTR.Reason
                FROM QuotesToRemove QTR
                INNER JOIN Quotes Q on QTR.QuoteID = Q.QuoteID
                INNER JOIN DiscordMembers DM on Q.UniqueMemberID = DM.UniqueMemberID
                INNER JOIN DiscordMembers REP on QTR.UniqueMemberiD = REP.UniqueMemberID
                WHERE Q.DiscordGuildID = ?"""
    result = conn.execute(sql, (guild_id,)).fetchall()
    quotes_to_remove = []
    for row in result:
        member = DiscordMember(*row[0:6])
        quote = Quote(*row[6:16], Member=member)
        reporter = DiscordMember(*row[16:22])
        quotes_to_remove.append(QuoteToRemove(quote, row[-1], reporter))
    return quotes_to_remove


def get_quotes_to_remove_name(guild_id, conn=connect()) -> list[QuoteToRemove]:
    sql = """   SELECT  Q.QuoteID, Q.Quote, Q.Name, Q.UniqueMemberID, Q.CreatedAt, Q.AddedByUniqueMemberID, Q.DiscordGuildID, Q.AmountBattled,
                        Q.AmountWon, Q.Elo, -- Quote
                        REP.UniqueMemberID, REP.DiscordUserID, REP.DiscordGuildID, REP.JoinedAt, REP.Nickname, REP.Semester, -- Reporter
                        QTR.Reason
                FROM QuotesToRemove QTR
                INNER JOIN Quotes Q on QTR.QuoteID = Q.QuoteID
                INNER JOIN DiscordMembers REP on QTR.UniqueMemberiD = REP.UniqueMemberID
                WHERE Q.UniqueMemberID is NULL AND Q.DiscordGuildID = ?"""
    result = conn.execute(sql, (guild_id,)).fetchall()
    quotes_to_remove = []
    for row in result:
        quote = Quote(*row[:10])
        reporter = DiscordMember(*row[10:-1])
        quotes_to_remove.append(QuoteToRemove(quote, row[-1], reporter))
    return quotes_to_remove


def insert_quote_to_remove(
    quote_id, reason: str, member: DiscordMember, conn=connect()
):
    try:
        # UniqueMemberID is the reporter's unique ID in this case
        conn.execute(
            "INSERT INTO QuotesToRemove(QuoteID, UniqueMemberID, Reason) VALUES(?,?,?)",
            (quote_id, member.UniqueMemberID, reason),
        )
    finally:
        conn.commit()


def get_reputations(member: discord.Member, conn=connect()) -> list[tuple[bool, str]]:
    sql = """   SELECT R.IsPositive, R.ReputationMessage
                FROM Reputations R
                INNER JOIN DiscordMembers DM on R.UniqueMemberID = DM.UniqueMemberID
                WHERE DM.DiscordUserID=? AND DM.DiscordGuildID=?"""
    reputations = conn.execute(sql, (member.id, member.guild.id)).fetchall()
    # makes the IsPositive into a boolean
    for i in range(len(reputations)):
        row = reputations[i]
        reputations[i] = [bool(row[0]), row[1]]
    return reputations


def get_most_recent_time(member: DiscordMember, conn=connect()):
    result = conn.execute(
        "SELECT CreatedAt from Reputations WHERE AddedByUniqueMemberID=? ORDER BY CreatedAt DESC",
        (member.UniqueMemberID,),
    ).fetchone()
    if result is None:
        return None
    # doesnt return the milliseconds of the datetime
    return result[0].split(".")[0]


def add_reputation(
    author: DiscordMember,
    receiver: DiscordMember,
    reputation_message: str,
    is_positive: bool,
    conn=connect(),
):
    sql = "INSERT INTO Reputations(UniqueMemberID, ReputationMessage, AddedByUniqueMemberID, IsPositive) VALUES (?,?,?,?)"
    try:
        conn.execute(
            sql,
            (
                receiver.UniqueMemberID,
                reputation_message,
                author.UniqueMemberID,
                int(is_positive),
            ),
        )
    finally:
        conn.commit()


class VoiceLevel:
    def __init__(self, member: DiscordMember, experience):
        self.member = member
        self.experience = experience


def get_voice_level(member: discord.Member, conn=connect()) -> VoiceLevel:
    sql = """   SELECT VL.ExperienceAmount, DM.UniqueMemberID, DM.DiscordUserID, DM.DiscordGuildID, DM.JoinedAt, DM.Nickname, DM.Semester
                FROM VoiceLevels VL
                INNER JOIN DiscordMembers DM on VL.UniqueMemberID = DM.UniqueMemberID
                WHERE DM.DiscordUserID=? AND DM.DiscordGuildID=?"""
    result = conn.execute(sql, (member.id, member.guild.id)).fetchone()
    if result is None:
        insert_or_update_voice_level(member, conn=connect())
        return get_voice_level(member, conn)
    ret_member = DiscordMember(*result[1:])
    return VoiceLevel(ret_member, result[0])


def insert_or_update_voice_level(
    member: discord.Member, experience_amount=0, conn=connect()
):
    discord_member = get_or_create_discord_member(member, conn=conn)
    sql = """   UPDATE OR IGNORE VoiceLevels
                SET ExperienceAmount = ExperienceAmount + ?
                WHERE UniqueMemberID = ?"""
    try:
        rows_changed = conn.execute(
            sql, (experience_amount, discord_member.UniqueMemberID)
        ).rowcount
    finally:
        conn.commit()
    if rows_changed == 0:
        try:
            conn.execute(
                "INSERT INTO VoiceLevels(UniqueMemberID, ExperienceAmount) VALUES (?,?)",
                (discord_member.UniqueMemberID, experience_amount),
            )
        finally:
            conn.commit()


def get_command_level(
    command_name: str,
    user_id: int,
    role_ids: list[int],
    channel_id: int,
    guild_id: int,
    conn=connect(),
) -> int:
    command_name = command_name.lower()
    role_or_msg = " OR ID = ?" * len(role_ids)
    result = conn.execute(
        f"SELECT PermissionLevel, Tag FROM CommandPermissions WHERE CommandName=? AND (ID = ? OR ID = ? OR ID = ? {role_or_msg})",
        (command_name, user_id, channel_id, guild_id, *role_ids),
    ).fetchall()
    user_level = 0
    role_level = 0
    channel_level = 0
    guild_level = 0
    for res in result:
        if res[1] == 0:
            continue
        if res[1] == "USER":
            user_level = res[0]
        if (
            res[1] == "ROLE"
        ):  # if there's a single role which allows it, allow the command
            if role_level == 1:
                continue
            role_level = res[0]
        elif res[1] == "CHANNEL":
            channel_level = res[0]
        elif res[1] == "GUILD":
            guild_level = res[0]
    if user_level != 0:
        return user_level
    if role_level != 0:
        return role_level
    if channel_level != 0:
        return channel_level
    return guild_level


class CommandLevel:
    def __init__(self, command_name, args):
        self.name = command_name
        self.guild_levels = {}
        self.channel_levels = {}
        self.role_levels = {}
        self.user_levels = {}
        for res in args:
            ID = res[0]
            perm_level = res[1]
            tag = res[2]
            if tag == "GUILD":
                self.guild_levels[ID] = perm_level
            elif tag == "CHANNEL":
                self.channel_levels[ID] = perm_level
            elif tag == "ROLE":
                self.role_levels[ID] = perm_level
            elif tag == "USER":
                self.user_levels[ID] = perm_level


def get_all_command_levels(command_name: str, conn=connect()) -> CommandLevel:
    command_name = command_name.lower()
    result = conn.execute(
        "SELECT ID, PermissionLevel, Tag FROM CommandPermissions WHERE CommandName=?",
        (command_name,),
    ).fetchall()
    return CommandLevel(command_name, result)


def insert_or_update_command_level(
    command_name: str,
    ID: int,
    permission_level: int,
    object_being_added: str,
    conn=connect(),
):
    command_name = command_name.lower()
    if permission_level == 0:
        # delete entry if perm level is 0
        try:
            conn.execute(
                "DELETE FROM CommandPermissions WHERE CommandName=? AND ID=?",
                (command_name, ID),
            )
        finally:
            conn.commit()
        return
    sql = """   UPDATE OR IGNORE CommandPermissions
                SET PermissionLevel = ?
                WHERE CommandName = ? AND ID = ?"""
    try:
        rows_changed = conn.execute(sql, (permission_level, command_name, ID)).rowcount
    finally:
        conn.commit()
    if rows_changed == 0:
        try:
            conn.execute(
                "INSERT INTO CommandPermissions(CommandName, ID, PermissionLevel, Tag) VALUES (?, ?, ?, ?)",
                (command_name, ID, permission_level, object_being_added),
            )
        finally:
            conn.commit()


##########################

# Lecture Updates

##########################


def add_course(
    abbreviation: str,
    name: str,
    guild_id: int,
    channel_id: int,
    role_id: int,
    link: str | None = None,
):
    conn = connect()
    sql = "INSERT INTO Courses(Abbreviation, Name, GuildId, DiscordChannelId, DiscordRoleId, Link) VALUES (?,?,?,?,?,?)"
    try:
        conn.execute(sql, (abbreviation, name, guild_id, channel_id, role_id, link))
    finally:
        conn.commit()


def update_course(
    course_id: int,
    abbreviation: str,
    name: str,
    channel_id: int,
    role_id: int,
    link: str | None = None,
):
    conn = connect()
    sql = "UPDATE Courses SET Name=?, Link=?, Abbreviation=?, channel_id=?, role_id=? WHERE CourseId=?"
    try:
        conn.execute(sql, (name, link, abbreviation, channel_id, role_id, course_id))
    finally:
        conn.commit()


def delete_course(course_id: int):
    conn = connect()
    sql = "DELETE FROM Courses WHERE CourseId=?"
    try:
        conn.execute(sql, (course_id,))
    finally:
        conn.commit()


def weekday_to_id(day: str):
    weekday = day.lower()
    return [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "none",
    ].index(weekday)


def add_lecture(
    abbreviation: str | None,
    guild_id: int,
    weekday: str,
    hour_from: int,
    minute_from: int,
    stream_link: str | None = None,
    secondary_link: str | None = None,
    on_site_location: str | None = None,
):
    conn = connect()
    sql = "SELECT CourseId FROM Courses WHERE GuildId = ? AND Abbreviation = ?"
    res = conn.execute(sql, (guild_id, abbreviation)).fetchone()
    if not res:
        print("There's no course for this abbreviation!")
        return False
    else:
        res = res[0]
    sql = "INSERT INTO Lectures (CourseId, DayId, HourFrom, MinuteFrom, StreamLink, SecondaryLink, OnSiteLocation) VALUES (?,?,?,?,?,?,?)"
    try:
        conn.execute(
            sql,
            (
                res,
                weekday_to_id(weekday),
                int(hour_from),
                int(minute_from),
                stream_link,
                secondary_link,
                on_site_location,
            ),
        )
    finally:
        conn.commit()
    return True


def update_lecture(
    abbreviation: str | None,
    guild_id: int,
    weekday: str,
    hour_from: int,
    minute_from: int,
    stream_link: str | None = None,
    secondary_link: str | None = None,
    on_site_location: str | None = None,
):
    conn = connect()
    sql = "SELECT CourseId FROM Courses WHERE GuildId = ? AND Abbreviation = ?"
    res = conn.execute(sql, (guild_id, abbreviation)).fetchone()
    if not res:
        print("There's no course for this abbreviation!")
        return False
    else:
        res = res[0]
    sql = f"UPDATE Lectures SET StreamLink=?, SecondaryLink=?, OnSiteLocation=? WHERE CourseId=? AND DayId=? AND HourFrom=? AND MinuteFrom=?"
    try:
        conn.execute(
            sql,
            [
                stream_link,
                secondary_link,
                on_site_location,
                res,
                weekday_to_id(weekday),
                hour_from,
                minute_from,
            ],
        )
    finally:
        conn.commit()


def get_abbreviations(guild_id: int, cur=""):
    conn = connect()
    sql = "SELECT Abbreviation FROM Courses WHERE GuildId = ? AND Abbreviation LIKE ?"
    res = conn.execute(sql, (guild_id, cur + "%")).fetchall()
    res = [x[0] for x in res]
    return res


def get_course_ids(guild_id: int, cur=""):
    conn = connect()
    sql = "SELECT CourseId, Abbreviation FROM Courses WHERE GuildId = ? AND CourseId+'' LIKE ?"
    res = conn.execute(sql, (guild_id, cur + "%")).fetchall()
    return res


def get_courses(guild_id: int):
    conn = connect()
    sql = "SELECT CourseId, Abbreviation, GuildId, Name, Link, DiscordChannelId, DiscordRoleId FROM Courses WHERE GuildId=?"
    res = conn.execute(sql, (guild_id,))
    return res.fetchall()


def get_single_course(course_id: int, guild_id=-1):
    conn = connect()
    sql = "SELECT CourseId, Abbreviation, GuildId, Name, Link FROM Courses WHERE CourseId=?"
    values = [course_id]
    if guild_id != -1:
        sql += " AND GuildId=?"
        values.append(guild_id)
    res = conn.execute(sql, values).fetchone()
    return res


def get_single_lecture(lecture_id: int, guild_id=-1):
    conn = connect()
    sql = """SELECT Abbreviation, DayId, HourFrom, MinuteFrom, StreamLink, SecondaryLink, OnSiteLocation
    FROM Lectures l
    INNER JOIN Courses c USING (CourseId)
    WHERE LectureId = ?"""
    values = [lecture_id]
    if guild_id != -1:
        sql += " AND GuildId=?"
        values.append(guild_id)
    return conn.execute(sql, values).fetchone()


def get_lectures(abbreviation: str, guild_id: int):
    conn = connect()
    sql = """SELECT LectureId, DayId, HourFrom, MinuteFrom, StreamLink, SecondaryLink, OnSiteLocation, Name
    FROM Lectures l
    INNER JOIN Courses c USING (CourseId)
    WHERE Abbreviation = ? AND GuildId = ?"""
    return conn.execute(sql, (abbreviation, guild_id)).fetchall()


def get_lecture_id(abbreviation: str, guild_id: int) -> int | None:
    conn = connect()
    sql = """SELECT LectureId
    FROM Lectures l
    INNER JOIN Courses c USING (CourseId)
    WHERE Abbreviation = ? AND GuildId = ?
    LIMIT 1"""
    return conn.execute(sql, (abbreviation, guild_id)).fetchone()


def delete_lecture(lecture_id: int):
    conn = connect()
    sql = "DELETE FROM Lectures WHERE LectureId=?"
    try:
        conn.execute(sql, (lecture_id,))
    finally:
        conn.commit()


def get_lecture_ids(guild_id: int, cur=""):
    conn = connect()
    sql = "SELECT LectureId, Abbreviation FROM Lectures INNER JOIN Courses USING (CourseId) WHERE GuildId = ? AND LectureId+'' LIKE ?"
    res = conn.execute(sql, (guild_id, cur + "%")).fetchall()
    return res


def get_lectures_by_time(day: str, hour: int, minute: int):
    conn = connect()
    sql = """SELECT c.Name, c.DiscordRoleId, c.DiscordChannelId, c.Link, l.StreamLink, l.SecondaryLink, l.OnSiteLocation, l.CourseId
        FROM Courses c
        INNER JOIN Lectures l USING (CourseId)
        WHERE l.HourFrom=? AND l.MinuteFrom=? AND l.DayId=?
        """
    users = conn.execute(sql, (hour, minute, weekday_to_id(day))).fetchall()
    return users


def get_steal_emote_servers(user_id: int, conn=connect()) -> list[int]:
    sql = """SELECT GuildID FROM StealEmote WHERE UserID = ?"""
    user_ids = conn.execute(sql, (user_id,)).fetchall()
    return [x[0] for x in user_ids]


def add_steal_emote_server(user_id: int, guild_id: int, conn=connect()):
    sql = """INSERT INTO StealEmote(UserID, GuildID) VALUES (?, ?)"""
    conn.execute(sql, (user_id, guild_id))
    conn.commit()
