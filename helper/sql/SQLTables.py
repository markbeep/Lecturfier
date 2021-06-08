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
DiscordChannels = """ CREATE TABLE IF NOT EXISTS DiscordChannels (
                        DiscordChannelID integer NOT NULL PRIMARY KEY,
                        DiscordGuildID integer NOT NULL,
                        ChannelName text NOT NULL,
                        ChannelType text NOT NULL,
                        ChannelPosition integer NOT NULL,
                        FOREIGN KEY (DiscordGuildID) REFERENCES DiscordGuilds(DiscordGuildID)
                        );"""
DiscordMembers = """ CREATE TABLE IF NOT EXISTS DiscordMembers (
                        UniqueMemberID integer PRIMARY KEY,
                        DiscordUserID integer NOT NULL,
                        DiscordGuildID integer NOT NULL,
                        JoinedAt text NOT NULL,
                        Nickname text,
                        Semester integer default 0,
                        FOREIGN KEY (DiscordUserID) REFERENCES DiscordUsers(DiscordUserID),
                        FOREIGN KEY (DiscordGuildID) REFERENCES DiscordGuilds(DiscordGuildID)
                        );"""
Subjects = """ CREATE TABLE IF NOT EXISTS Subjects (
                        SubjectID integer NOT NULL PRIMARY KEY,
                        SubjectName text NOT NULL,
                        SubjectAbbreviation text,
                        SubjectSemester integer default 0,
                        SubjectLink text
                        );"""
WeekDayTimes = """ CREATE TABLE IF NOT EXISTS WeekDayTimes (
                        UniqueDayTimesID integer PRIMARY KEY,
                        SubjectID integer NOT NULL,
                        DayID integer NOT NULL,
                        TimeFrom text NOT NULL,
                        TimeTo text NOT NULL,
                        StreamLink text,
                        ZoomLink text,
                        OnSiteLocation text,
                        FOREIGN KEY (SubjectID) REFERENCES Subject(SubjectID)
                        );"""
UserStatistics = """ CREATE TABLE IF NOT EXISTS UserStatistics (
                        UserStatisticID integer PRIMARY KEY,
                        UniqueMemberID integer NOT NULL,
                        -- stats for each subject, where subjectID 0 is no current subject
                        SubjectID integer NOT NULL,
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
                        FOREIGN KEY (UniqueMemberID) REFERENCES DiscordMembers(UniqueMemberID),
                        FOREIGN KEY (SubjectID) REFERENCES Subject(SubjectID)
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
                                    IsDone integer,
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
                                    FOREIGN KEY("UniqueMemberID") REFERENCES "DiscordMembers"("UniqueMemberID"),
                                    FOREIGN KEY("DiscordGuildID") REFERENCES "DiscordGuilds"("DiscordGuildID")
                                    );"""
QuoteAliases = """  CREATE TABLE IF NOT EXISTS "QuoteAliases" (
                                    "AliasID" INTEGER PRIMARY KEY,
                                    "NameFrom" TEXT NOT NULL,
                                    "NameTo" TEXT NOT NULL
                                    );"""
Config = """   CREATE TABLE IF NOT EXISTS "Config" (
                                    "ConfigID" INTEGER PRIMARY KEY,
                                    "ConfigKey" TEXT NOT NULL,
                                    "ConfigValue" INTEGER NOT NULL
                                    );"""
QuotesToRemove = """   CREATE TABLE IF NOT EXISTS "QuotesToRemove" (
                                    "QuoteID" INTEGER PRIMARY KEY,
                                    "UniqueMemberID" INTEGER,
                                    FOREIGN KEY("UniqueMemberID") REFERENCES "DiscordMembers"("UniqueMemberID"),
                                    FOREIGN KEY("QuoteID") REFERENCES "DiscordMembers"("QuoteID")
                                    );"""

all_tables = [DiscordUsers, DiscordGuilds, DiscordChannels, DiscordMembers, Subjects, WeekDayTimes,
              UserStatistics, VoiceLevels, CovidGuessing, Reputations, Events, EventJoinedUsers,
              Quotes, QuoteAliases, QuotesToRemove, Config]


def create_tables():
    conn = connect()
    try:
        for table in all_tables:
            print(table)
            conn.execute(table)
    except Exception as e:
        print(e)
    finally:
        conn.commit()
