import logging
import discord
import sqlite3
from datetime import datetime

logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect("./data/test.db")
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

