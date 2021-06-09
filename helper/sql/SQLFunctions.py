import logging
import discord
import sqlite3
from datetime import datetime

logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect("./data/discord.db")
    conn.execute("PRAGMA journal_mode=WAL")
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
    def __init__(self, DiscordUserID, DisplayName, Discriminator, IsBot, AvatarURL, CreatedAt):
        self.DiscordUserID = DiscordUserID
        self.DisplayName = DisplayName
        self.Discriminator = Discriminator
        self.IsBot = bool(IsBot)
        self.AvatarURL = AvatarURL
        self.CreatedAt = get_datetime(CreatedAt)


def get_or_create_discord_user(user: discord.User, conn=connect()) -> DiscordUser:
    result = conn.execute("SELECT * FROM DiscordUsers WHERE DiscordUserID = ?", (user.id,)).fetchone()
    if result is None:
        # The user doesn't exist in the db
        conn.execute(
            """INSERT INTO DiscordUsers(DiscordUserID, DisplayName, Discriminator, IsBot, AvatarURL, CreatedAt)
                VALUES (?,?,?,?,?,?)""",
            (user.id, user.display_name, user.discriminator, int(user.bot), user.avatar_url, user.created_at)
        )
        conn.commit()
        return get_or_create_discord_user(user, conn)
    return DiscordUser(
        DiscordUserID=result[0],
        DisplayName=result[1],
        Discriminator=result[2],
        IsBot=result[3],
        AvatarURL=result[4],
        CreatedAt=result[5]
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
    result = conn.execute("SELECT * FROM DiscordGuilds WHERE DiscordGuildID = ?", (guild.id,)).fetchone()
    if result is None:
        # The guild doesn't exist in the db
        conn.execute(
            """INSERT INTO DiscordGuilds(DiscordGuildID, GuildName, GuildRegion, GuildChannelCount, GuildMemberCount, GuildRoleCount) VALUES (?,?,?,?,?,?)""",
            (guild.id, guild.name, str(guild.region), len(guild.channels), guild.member_count, len(guild.roles))
        )
        conn.commit()
        return get_or_create_discord_guild(guild, conn)
    return DiscordGuild(result)


class DiscordMember:
    def __init__(self, UniqueMemberID, DiscordUserID, DiscordGuildID, JoinedAt, Nickname, Semester):
        self.UniqueMemberID = UniqueMemberID
        self.DiscordUserID = DiscordUserID
        self.DiscordGuildID = DiscordGuildID
        self.JoinedAt = get_datetime(JoinedAt)
        self.Nickname = Nickname
        self.Semester = Semester


def get_or_create_discord_member(member: discord.Member, semester=0, conn=connect()) -> DiscordMember:
    result = conn.execute("SELECT * FROM DiscordMembers WHERE DiscordUserID = ? AND DiscordGuildID = ?", (member.id, member.guild.id)).fetchone()
    if result is None:
        try:
            conn.execute(
                "INSERT INTO DiscordMembers(DiscordUserID, DiscordGuildID, Nickname, JoinedAt, Semester) VALUES (?,?,?,?,?)",
                (member.id, member.guild.id, member.nick, str(member.joined_at), semester)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            get_or_create_discord_user(member, conn=conn)
            get_or_create_discord_guild(member.guild, conn=conn)
            return get_or_create_discord_member(member, semester, conn)
    return DiscordMember(
        UniqueMemberID=result[0],
        DiscordUserID=result[1],
        DiscordGuildID=result[2],
        JoinedAt=result[3],
        Nickname=result[4],
        Semester=result[5]
    )


class UserStatistics:
    def __init__(self, *args):
        self.UserStatisticsID = args[0]
        self.UniqueMemberID = args[1]
        self.SubjectID = args[2]
        self.MessagesSent = args[3]
        self.MessageDeleted = args[4]
        self.MessageEdited = args[5]
        self.CharactersSent = args[6]
        self.WordsSent = args[7]
        self.SpoilersSent = args[8]
        self.EmojisSent = args[9]
        self.FilesSent = args[10]
        self.FileSizeSent = args[11]
        self.ImagesSent = args[12]
        self.ReactionsAdded = args[13]
        self.ReactionsRemoved = args[14]
        self.ReactionsReceived = args[15]
        self.ReactionTakenAway = args[16]


def get_or_create_user_statistics(member: discord.Member, subject_id, conn=connect()) -> UserStatistics:
    result = conn.execute("""SELECT * FROM UserStatistics US
                 INNER JOIN DiscordMembers DM on DM.UniqueMemberID = US.UniqueMemberID
                 WHERE DM.DiscordUserID = ? AND DM.DiscordGuildID = ?""", (member.id, member.guild.id)).fetchone()
    if result is None:
        dm = get_or_create_discord_member(member, conn=conn)
        conn.execute("""INSERT INTO UserStatistics(UniqueMemberID, SubjectID) VALUES (?,?)""", (dm.UniqueMemberID, subject_id))
        return get_or_create_user_statistics(member, subject_id, conn)
    return UserStatistics(result)


def update_statistics(member: discord.Member, subject_id: int, conn=connect(), messages_sent=0, messages_deleted=0, messages_edited=0,
                      characters_sent=0,
                      words_sent=0, spoilers_sent=0, emojis_sent=0, files_sent=0, file_size_sent=0, images_sent=0, reactions_added=0,
                      reactions_removed=0, reactions_received=0, reactions_taken_away=0) -> bool:
    """
    Updates the statistics table
    :return: True if a new entry was created, False otherwise
    """
    dm = get_or_create_discord_member(member, conn=conn)
    sql = """   UPDATE UserStatistics
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
                    ReactionsTakenAway = ReactionsTakenAway + ?
                WHERE UniqueMemberID = ? AND SubjectID = ?"""
    try:
        conn.execute(sql, (messages_sent, messages_deleted, messages_edited, characters_sent, words_sent, spoilers_sent, emojis_sent, files_sent,
                           file_size_sent, images_sent, reactions_added, reactions_removed, reactions_received, reactions_taken_away,
                           dm.UniqueMemberID, subject_id))
        conn.commit()
        return False
    except sqlite3.IntegrityError:
        # The user doesn't have a statistics entry yet
        get_or_create_user_statistics(member, subject_id, conn)
        conn.execute(sql, (messages_sent, messages_deleted, messages_edited, characters_sent, words_sent, spoilers_sent, emojis_sent, files_sent,
                           file_size_sent, images_sent, reactions_added, reactions_removed, reactions_received, reactions_taken_away,
                           dm.UniqueMemberID, subject_id))
        conn.commit()
        return True


def get_current_subject_id(semester: int, conn=connect()) -> int:
    logger.debug(msg="Getting current subject ID")
    dt = datetime.now()
    hour = dt.hour
    minute = dt.minute
    formatted_time = f"{hour}:{minute}:00"
    sql = """   SELECT W.SubjectID FROM WeekDayTimes W
                INNER JOIN Subjects S on W.SubjectID = S.SubjectID
                WHERE W.TimeFrom <= ? AND ? < W.TimeTo AND S.SubjectSemester = ?"""
    subject = conn.execute(sql, (formatted_time, formatted_time, semester)).fetchone()
    if subject is None:
        return 0
    return subject[0]


def get_statistic_rows(column, limit, conn=connect()):
    sql = f"""  SELECT ums.UniqueMemberID, dm.DiscordUserID, dm.DiscordGuildID, dm.JoinedAt, dm.Semester, dm.Nickname, SUM({column}) as sm
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
            Nickname=row[5]
        )
        stats.append((member, row[6]))
    return stats


class Event:
    def __init__(self, event_id, event_name, event_created_at, event_starting_at, event_description, unique_member_id, updated_message_id,
                 updated_channel_id, is_done, specific_channel_id, discord_member=None):
        self.EventID = event_id
        self.EventName = event_name
        self.EventCreatedAt = get_datetime(event_created_at)
        self.EventStartingAt = get_datetime(event_starting_at)
        self.EventDescription = event_description
        self.UniqueMemberID = unique_member_id
        self.DiscordMember: DiscordMember = discord_member
        self.UpdatedMessageID = updated_message_id
        self.UpdatedChannelID = updated_channel_id
        self.SpecificChannelID = specific_channel_id
        self.IsDone = bool(is_done)


def get_events(conn=connect(), is_done=None, limit=None, guild_id: int = None, order=False, by_user_id=None, row_id=None, event_id=None) -> list:
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
            Semester=row[15]
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
            discord_member=member
        )
        events.append(event)
    return events


def get_event_by_id(event_id, conn=connect()) -> Event:
    event_results = get_events(conn, event_id=int(event_id))
    if len(event_results) == 0:
        return None
    return event_results[0]

def create_event(event_name, event_starting_at, event_description, member: DiscordMember, conn=connect()) -> Event:
    row_id = conn.execute("INSERT INTO Events(EventName, EventStartingAt, EventDescription, UniqueMemberID) VALUES (?,?,?,?)",
                          (event_name, str(event_starting_at), event_description, member.UniqueMemberID)).lastrowid
    conn.commit()
    events = get_events(conn, row_id=row_id)
    return events[0]


def delete_event(event: Event, conn=connect()):
    conn.execute("DELETE FROM Events WHERE EventID=?", (event.EventID,))
    conn.commit()


def get_event_joined_users(event: Event, conn=connect()) -> list:
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
                Semester=row[5]
            )
        )
    return joined_members


def mark_events_done(current_time=datetime.now(), conn=connect()) -> int:
    events_changed = conn.execute("Update Events SET IsDone=1 WHERE EventStartingAt < ?", (str(current_time),)).rowcount
    conn.commit()
    return events_changed


def add_member_to_event(event: Event, member_to_add: DiscordMember, conn=connect(), host=False):
    logger.debug(f"Adding {member_to_add.DiscordUserID} to {event.EventID}")
    conn.execute("INSERT INTO EventJoinedUsers(EventID, UniqueMemberID, IsHost) VALUES (?,?,?)", (event.EventID, member_to_add.UniqueMemberID, int(host)))
    conn.commit()


def remove_member_from_event(event: Event, member_to_remove: DiscordMember, conn=connect()):
    logger.debug(f"Removing {member_to_remove.DiscordUserID} from {event.EventID}")
    conn.execute("DELETE FROM EventJoinedUsers WHERE EventID=? AND UniqueMemberID=?", (event.EventID, member_to_remove.UniqueMemberID))
    conn.commit()


def add_event_updated_message(message_id, channel_id, event_id, conn=connect()):
    conn.execute("UPDATE Events SET UpdatedMessageID=?, UpdatedChannelID=? WHERE EventID=?", (message_id, channel_id, event_id))
    conn.commit()

def set_specific_event_channel(event_id: int, specific_channel=None, conn=connect()):
    conn.execute("UPDATE Events SET SpecificChannelID=? WHERE EventID=?", (event_id, specific_channel))
    conn.commit()


def get_config(key, conn=connect()) -> int:
    value = conn.execute("SELECT ConfigValue FROM Config WHERE ConfigKey=?", (key,)).fetchone()
    if value is None:
        return None
    return value[0]


def delete_config(key, conn=connect()):
    conn.execute("DELETE FROM Config WHERE ConfigKey=?", (key,))
    conn.commit()


def insert_or_update_config(key, value, conn=connect()):
    try:
        rows_changed = conn.execute("UPDATE OR IGNORE Config SET ConfigValue=? WHERE ConfigKey=?", (value, key)).rowcount
        if rows_changed == 0:
            conn.execute("INSERT INTO Config(ConfigKey, ConfigValue) VALUES (?,?)", (key, value))
    finally:
        conn.commit()


class CovidGuesser:
    def __init__(self, UniqueMemberID, TotalPointsAmount, GuessCount, NextGuess, TempPoints, member: DiscordMember):
        self.UniqueMemberID = UniqueMemberID
        self.TotalPointsAmount = TotalPointsAmount
        self.GuessCount = GuessCount
        self.NextGuess = NextGuess
        self.TempPoints = TempPoints
        self.member = member
        if count := GuessCount == 0:
            count = 1
        self.average = TotalPointsAmount / count


def get_covid_guessers(conn=connect(), guessed=False):
    sql = """   SELECT  CG.UniqueMemberID, CG.TotalPointsAmount, CG.GuessCount, CG.NextGuess, CG.TempPoints,
                        DM.DiscordUserID, DM.DiscordGuildID, DM.JoinedAt, DM.Nickname, DM.Semester
                FROM CovidGuessing CG
                INNER JOIN DiscordMembers DM on DM.UniqueMemberID = CG.UniqueMemberID"""
    if guessed is True:
        sql += " WHERE CG.NextGuess IS NOT NULL"
    results = conn.execute(sql).fetchall()
    guessers = []
    for row in results:
        member = DiscordMember(
            UniqueMemberID=row[0],
            DiscordUserID=row[5],
            DiscordGuildID=row[6],
            JoinedAt=row[7],
            Nickname=row[8],
            Semester=row[9]
        )
        g = CovidGuesser(
            UniqueMemberID=row[0],
            TotalPointsAmount=row[1],
            GuessCount=row[2],
            NextGuess=row[3],
            TempPoints=row[4],
            member=member
        )
        guessers.append(g)
    return guessers


def clear_covid_guesses(increment=True, conn=connect()):
    sql = """   UPDATE CovidGuessing
                SET
                    TotalPointsAmount=TotalPointsAmount+TempPoints,
                    GuessCount=GuessCount+?,
                    TempPoints=NULL,
                    NextGuess=NULL
                WHERE
                    TempPoints IS NOT NULL"""
    conn.execute(sql, (int(increment),))
    conn.commit()
