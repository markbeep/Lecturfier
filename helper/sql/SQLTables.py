import sqlite3

from helper.sql.SQLFunctions import connect

DiscordUsers = """  CREATE TABLE IF NOT EXISTS DiscordUsers (
                        DiscordUserID integer NOT NULL PRIMARY KEY,
                        DisplayName text NOT NULL,
                        Discriminator integer NOT NULL,
                        IsBot integer NOT NULL,
                        AvatarURL text NOT NULL,
                        CreatedAt text NOT NULL
                    );"""
DiscordGuilds = """ CREATE TABLE IF NOT EXISTS DiscordGuilds (
                        DiscordGuildID integer NOT NULL PRIMARY KEY,
                        GuildName text NOT NULL,
                        GuildRegion text,
                        GuildChannelCount integer default 0,
                        GuildMemberCount integer default 1,
                        GuildRoleCount integer default 0
                        );"""
DiscordChannels = """CREATE TABLE IF NOT EXISTS DiscordChannels (
                        DiscordChannelID integer NOT NULL PRIMARY KEY,
                        DiscordGuildID integer NOT NULL,
                        ChannelName text NOT NULL,
                        ChannelType text NOT NULL,
                        ChannelPosition integer NOT NULL,
                        FOREIGN KEY (DiscordGuildID) REFERENCES DiscordGuilds(DiscordGuildID)
                        );"""
DiscordMembers = """CREATE TABLE IF NOT EXISTS DiscordMembers (
                        UniqueMemberID integer PRIMARY KEY,
                        DiscordUserID integer NOT NULL,
                        DiscordGuildID integer NOT NULL,
                        JoinedAt text NOT NULL,
                        Nickname text,
                        Semester integer default 0,
                        FOREIGN KEY (DiscordUserID) REFERENCES DiscordUsers(DiscordUserID),
                        FOREIGN KEY (DiscordGuildID) REFERENCES DiscordGuilds(DiscordGuildID)
                        );"""
Courses = """        CREATE TABLE IF NOT EXISTS Courses (
                        CourseId INTEGER PRIMARY KEY AUTOINCREMENT,
                        Abbreviation TEXT NOT NULL,
                        GuildId INTEGER NOT NULL,
                        Name TEXT NOT NULL,
                        DiscordRoleId INTEGER NOT NULL,
                        DiscordChannelId INTEGER NOT NULL,
                        Link TEXT,
                        UNIQUE (Abbreviation, GuildId)
                        );"""

Lectures = """       CREATE TABLE IF NOT EXISTS Lectures (
                        LectureId INTEGER PRIMARY KEY AUTOINCREMENT,
                        CourseId INTEGER NOT NULL,
                        DayId INTEGER NOT NULL,
                        HourFrom INTEGER NOT NULL,
                        MinuteFrom INTEGER NOT NULL,
                        StreamLink TEXT,
                        SecondaryLink TEXT,
                        OnSiteLocation TEXT,
                        FOREIGN KEY (CourseId) REFERENCES Courses(CourseId)
                        ON DELETE CASCADE ON UPDATE CASCADE,
                        UNIQUE (CourseId, DayId, HourFrom, MinuteFrom)
                        );"""
UserStatistics = """CREATE TABLE IF NOT EXISTS UserStatistics (
                        UniqueMemberID integer NOT NULL,
                        MessagesSent integer DEFAULT 0,
                        MessagesDeleted integer DEFAULT 0,
                        MessagesEdited integer DEFAULT 0,
                        CharactersSent integer DEFAULT 0,
                        WordsSent integer DEFAULT 0,
                        SpoilersSent integer DEFAULT 0,
                        EmojisSent integer DEFAULT 0,
                        FilesSent integer DEFAULT 0,
                        FileSizeSent integer DEFAULT 0,
                        ImagesSent integer DEFAULT 0,
                        ReactionsAdded integer DEFAULT 0,
                        ReactionsRemoved integer DEFAULT 0,
                        ReactionsReceived integer DEFAULT 0,
                        ReactionsTakenAway integer DEFAULT 0,
                        VoteCount integer DEFAULT 0,
                        FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID)
                        );"""
VoiceLevels = """ CREATE TABLE IF NOT EXISTS VoiceLevels (
                    UniqueMemberID integer NOT NULL PRIMARY KEY,
                    ExperienceAmount integer DEFAULT 0,
                    FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID)
                            );"""
CovidGuessing = """  CREATE TABLE IF NOT EXISTS CovidGuessing (
                        UniqueMemberID integer NOT NULL PRIMARY KEY,
                        TotalPointsAmount integer DEFAULT 0,
                        GuessCount integer DEFAULT 0,
                        NextGuess integer,
                        TempPoints integer,
                        FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID)
                        );"""
Reputations = """    CREATE TABLE IF NOT EXISTS Reputations (
                                ReputationID integer PRIMARY KEY,
                                UniqueMemberID integer NOT NULL,
                                ReputationMessage text NOT NULL,
                                CreatedAt text DEFAULT CURRENT_TIMESTAMP,
                                AddedByUniqueMemberID integer,
                                IsPositive integer DEFAULT 1,
                                FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID),
                                FOREIGN KEY (AddedByUniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID)
                                );"""
Events = """     CREATE TABLE IF NOT EXISTS Events (
                                    EventID integer PRIMARY KEY,
                                    EventName text NOT NULL,
                                    EventCreatedAt text DEFAULT CURRENT_TIMESTAMP,
                                    EventStartingAt text NOT NULL,
                                    EventDescription text default '[No Description]',
                                    UniqueMemberID integer NOT NULL,
                                    UpdatedMessageID integer,
                                    UpdatedChannelID integer,
                                    SpecificChannelID integer,
                                    IsDone integer DEFAULT 0,
                                    FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID)
                                    );"""

EventJoinedUsers = """   CREATE TABLE IF NOT EXISTS "EventJoinedUsers" (
                                    "EventJoinedID"	INTEGER,
                                    "EventID"	INTEGER,
                                    "UniqueMemberID"	INTEGER,
                                    "JoinedAt"	TEXT DEFAULT CURRENT_TIMESTAMP,
                                    "IsHost"	INTEGER DEFAULT 0,
                                    FOREIGN KEY("UniqueMemberID") REFERENCES "DiscordMembers"("UniqueMemberID"),
                                    PRIMARY KEY("EventJoinedID"),
                                    FOREIGN KEY("EventID") REFERENCES "Events"("EventID") ON DELETE CASCADE
                                    );"""
Quotes = """   CREATE TABLE IF NOT EXISTS "Quotes" (
                                    "QuoteID" INTEGER PRIMARY KEY,
                                    "Quote" INTEGER NOT NULL,
                                    "Name" TEXT NOT NULL, -- name of who the quote is from
                                    "UniqueMemberID" INTEGER, -- uniqueID if it exists
                                    "CreatedAt"	TEXT DEFAULT CURRENT_TIMESTAMP,
                                    "AddedByUniqueMemberID" INTEGER,
                                    "DiscordGuildID" INTEGER NOT NULL,
                                    "AmountBattled" INTEGER DEFAULT 0,
                                    "AmountWon" INTEGER DEFAULT 0,
                                    "Elo" INTEGER DEFAULT 1000,
                                    FOREIGN KEY("UniqueMemberID") REFERENCES "DiscordMembers"("UniqueMemberID"),
                                    FOREIGN KEY("DiscordGuildID") REFERENCES "DiscordGuilds"("DiscordGuildID")
                                    );"""
QuoteAliases = """  CREATE TABLE IF NOT EXISTS "QuoteAliases" (
                                    "AliasID" INTEGER PRIMARY KEY,
                                    "NameFrom" TEXT NOT NULL,
                                    "NameTo" TEXT NOT NULL
                                    );"""
QuotesToRemove = """   CREATE TABLE IF NOT EXISTS "QuotesToRemove" (
                                    "QuoteID" INTEGER PRIMARY KEY,
                                    "UniqueMemberID" INTEGER,
                                    "Reason" TEXT,
                                    FOREIGN KEY("UniqueMemberID") REFERENCES "DiscordMembers"("UniqueMemberID") ON DELETE CASCADE,
                                    FOREIGN KEY("QuoteID") REFERENCES "Quotes"("QuoteID") ON DELETE CASCADE
                                    );"""
Config = """   CREATE TABLE IF NOT EXISTS "Config" (
                                    "ConfigID" INTEGER PRIMARY KEY,
                                    "ConfigKey" TEXT NOT NULL,
                                    "ConfigValue" INTEGER NOT NULL
                                    );"""
CommandPermissions = """    CREATE TABLE IF NOT EXISTS "CommandPermissions" (
                                "PermissionID" INTEGER PRIMARY KEY,
                                "CommandName" TEXT,
                                "ID" INTEGER NOT NULL,
                                "PermissionLevel" INTEGER DEFAULT 0,
                                "Tag" TEXT -- tag is for finding out what object ID was added
                                );"""
CovidCases = """   CREATE TABLE IF NOT EXISTS "CovidCases" (
                        "CovidCaseID" INTEGER PRIMARY KEY,
                        "Cases" INTEGER NOT NULL,
                        "Date" TEXT NOT NULL,
                        "Weekday" INTEGER NOT NULL
                    );"""
FavoriteQuotes = """   CREATE TABLE IF NOT EXISTS "FavoriteQuotes" (
                            "FavoriteID" INTEGER PRIMARY KEY,
                            "QuoteID" INTEGER NOT NULL,
                            "UniqueMemberID" INTEGER NOT NULL,
                            FOREIGN KEY("UniqueMemberID") REFERENCES "DiscordMembers"("UniqueMemberID") ON DELETE CASCADE 
                        );"""
StealEmote = """   CREATE TABLE IF NOT EXISTS "StealEmote" (
                            "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                            "UserID" INTEGER NOT NULL,
                            "GuildID" INTEGER NOT NULL
                        );"""
MessageLimits = """   CREATE TABLE IF NOT EXISTS "LimitMessages" (
                            "UserID" INTEGER NOT NULL,
                            "ChannelID" INTEGER NOT NULL,
                            "MessageCount" INTEGER DEFAULT 0,
                            "FirstMessageAt" INTEGER,
                            PRIMARY KEY ("UserID", "ChannelID")
                        );"""
MessageLimitChannels = """   CREATE TABLE IF NOT EXISTS "MessageLimitChannels" (
                            "ChannelID" INTEGER PRIMARY KEY,
                            "MessageLimit" INTEGER DEFAULT 0
                        );"""

all_tables = [
    DiscordUsers,
    DiscordGuilds,
    DiscordChannels,
    DiscordMembers,
    Courses,
    Lectures,
    UserStatistics,
    VoiceLevels,
    CovidGuessing,
    Reputations,
    Events,
    EventJoinedUsers,
    Quotes,
    QuoteAliases,
    QuotesToRemove,
    Config,
    CommandPermissions,
    CovidCases,
    FavoriteQuotes,
    StealEmote,
    MessageLimits,
    MessageLimitChannels,
]


def create_tables(conn=connect()):
    try:
        for table in all_tables:
            conn.execute(table)
    except Exception as e:
        print(e)
    finally:
        conn.commit()
        conn.close()


def get_table_name(table: str) -> str:
    spl = table.replace('"', "").split(" ")
    return spl[spl.index("(\n") - 1]  # gets the word right before the opening bracket


def compare_headers(table: str, header: list[str]):
    name = get_table_name(table)
    spl = table.replace('"', "").replace("\t", " ").split("\n")
    ex_headers = []
    for line in spl[1:-1]:
        tmp = line.split(" ")
        tmp = [x for x in tmp if x != ""]  # takes out all the whitespace elements
        if (
            tmp[0].startswith("FOREIGN")
            or tmp[0].startswith("PRIMARY")
            or tmp[0].startswith("--")
        ):
            continue
        ex_headers.append(tmp[0])
    for col in header:  # check if headers are the same both way
        if col not in ex_headers:
            print(
                f"WARNING! {name}: {col} exists in table, but is not defined in SQLTables.py!"
            )
    for col in ex_headers:  # check if headers are the same both way
        if "UNIQUE" in col or "ON" in col:
            continue
        if col not in header:
            print(
                f"WARNING! {name}: {col} is defined in SQLTables.py, but is not in the actual DB! (This can cause problems!)"
            )


def check_columns(conn=connect()):
    for table in all_tables:
        name = get_table_name(table)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"PRAGMA table_info({name});").fetchall()
        header = [x[1] for x in rows]
        compare_headers(table, header)
    conn.close()


if __name__ == "__main__":
    check_columns(connect())
