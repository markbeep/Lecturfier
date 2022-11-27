import sqlite3

conn = sqlite3.connect("./data/discord.db")

cols = [
"MessagesSent",
"MessagesDeleted",
"MessagesEdited",
"CharactersSent",
"WordsSent",
"SpoilersSent",
"EmojisSent",
"FilesSent",
"FileSizeSent",
"ImagesSent",
"ReactionsAdded",
"ReactionsRemoved",
"ReactionsReceived",
"ReactionsTakenAway",
"VoteCount"
]

exec_str = f"SELECT UniqueMemberID, {','.join([f'SUM({x})' for x in cols])} FROM UserStatistics GROUP BY UniqueMemberID;"
print(exec_str)
data = conn.execute(exec_str).fetchall()

# create new table
conn.execute("""CREATE TABLE IF NOT EXISTS "UserStatisticsTEMP" (
	"UniqueMemberID"	integer NOT NULL,
	"MessagesSent"	integer DEFAULT 0,
	"MessagesDeleted"	integer DEFAULT 0,
	"MessagesEdited"	integer DEFAULT 0,
	"CharactersSent"	integer DEFAULT 0,
	"WordsSent"	integer DEFAULT 0,
	"SpoilersSent"	integer DEFAULT 0,
	"EmojisSent"	integer DEFAULT 0,
	"FilesSent"	integer DEFAULT 0,
	"FileSizeSent"	integer DEFAULT 0,
	"ImagesSent"	integer DEFAULT 0,
	"ReactionsAdded"	integer DEFAULT 0,
	"ReactionsRemoved"	integer DEFAULT 0,
	"ReactionsReceived"	integer DEFAULT 0,
	"ReactionsTakenAway"	integer DEFAULT 0,
	"VoteCount"	integer DEFAULT 0,
	FOREIGN KEY("UniqueMemberID") REFERENCES "DiscordMembers",
	PRIMARY KEY("UniqueMemberID")
);""")

exec_str = f"INSERT INTO UserStatisticsTEMP(UniqueMemberID, {','.join(cols)}) VALUES(?,{','.join(['?' for _ in cols])});"
print(exec_str)
conn.executemany(
    exec_str,
    data
)

conn.execute("DROP TABLE UserStatistics;")
conn.execute("ALTER TABLE UserStatisticsTEMP RENAME TO UserStatistics;")



# subjects/courses
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
conn.execute(Courses)
conn.execute(Lectures)

data = conn.execute("SELECT SubjectID, SubjectName, SubjectAbbreviation, SubjectLink, SubjectSemester FROM Subjects").fetchall()
for l in data:
    if l[4] == 1:
        role_id = 773543051011555398
    elif l[4] == 3:
        role_id = 810241727800541194
    else:
        role_id = 810242456134221854
    channel_id = 756391202546384927
    guild_id = 747752542741725244
    conn.execute("INSERT INTO Courses(CourseId, Name, Abbreviation, Link, GuildId, DiscordRoleId, DiscordChannelId) VALUES(?,?,?,?,?,?,?)",
                 (l[0], l[1], l[2], l[3], guild_id, role_id, channel_id))

data = conn.execute("SELECT SubjectId, DayId, TimeFrom, StreamLink, OnSiteLocation FROM WeekDayTimes").fetchall()
for l in data:
    conn.execute("INSERT INTO Lectures(CourseId, DayId, HourFrom, MinuteFrom, StreamLink, OnSiteLocation) VALUES(?,?,?,?,?,?)",
                 (l[0], l[1], l[2], 0, l[3], l[4]))

conn.execute("DROP TABLE WeekDayTimes;")
conn.execute("DROP TABLE Subjects;")

conn.commit()
conn.close()
