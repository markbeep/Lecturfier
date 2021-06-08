from peewee import *
import datetime

path = "./data/rewrite_discord.db"

sqlite_db = SqliteDatabase(path, pragmas={
    "journal_mode": "wal",
    "foreign_keys": 1,
    "ignore_check_constraints": 0
})


class BaseModel(Model):
    class Meta:
        database = sqlite_db


class Config(BaseModel):
    id = IntegerField(primary_key=True, unique=True)
    Key = TextField()
    Value = IntegerField()


class DiscordGuilds(BaseModel):
    DiscordGuildID = IntegerField(primary_key=True)
    DiscordGuildName = TextField()
    GuildRegion = TextField(null=True)
    GuildChannelCount = IntegerField(default=0)
    GuildMemberCount = IntegerField(default=0)
    GuildRoleCount = IntegerField(default=0)


class DiscordChannels(BaseModel):
    DiscordChannelID = IntegerField(primary_key=True)
    DiscordGuild = ForeignKeyField(DiscordGuilds, backref="channels")
    ChannelName = TextField()
    ChannelType = TextField()
    ChannelPosition = IntegerField()


class DiscordUsers(BaseModel):
    DiscordUserID = IntegerField(primary_key=True)
    DisplayName = TextField()
    Discriminator = IntegerField()
    IsBot = IntegerField()
    AvatarURL = TextField()
    CreatedAt = DateTimeField()


class DiscordMembers(BaseModel):
    DiscordMemberID = IntegerField(primary_key=True)
    DiscordUser = ForeignKeyField(DiscordUsers, backref="members")
    DiscordGuild = ForeignKeyField(DiscordGuilds, backref="members")
    JoinedAt = DateTimeField(null=True)
    Nickname = TextField(null=True)
    Semester = IntegerField(null=True)


class CovidGuessing(BaseModel):
    DiscordMember = ForeignKeyField(DiscordMembers, backref="covid_score")
    TotalPointsAmount = IntegerField()
    GuessCount = IntegerField()
    NextGuess = IntegerField(null=True)
    TempPoints = IntegerField(null=True)


class Events(BaseModel):
    id = IntegerField(primary_key=True)
    Name = TextField()
    CreatedAt = DateTimeField(default=datetime.datetime.now)
    StartingAt = DateTimeField()
    Description = TextField(default="[no description]")
    Host = ForeignKeyField(DiscordMembers, backref="events_hosting")
    IsDone = IntegerField(default=0)
    # These channels are not foreign fields, as this would result in errors
    # if the channel can't be seen by the bot
    UpdatedChannelID = IntegerField(null=True)
    UpdatedMessageID = IntegerField(null=True)
    SpecifiedChannelID = IntegerField(null=True)


class EventJoinedUsers(BaseModel):
    id = IntegerField(primary_key=True)
    Event = ForeignKeyField(Events, backref="joined_members", on_delete="CASCADE")
    DiscordMember = ForeignKeyField(DiscordMembers, backref="events_joined")
    JoinedAt = DateTimeField(default=datetime.datetime.now)
    IsHost = IntegerField(default=0)


class Quotes(BaseModel):
    id = IntegerField(primary_key=True)
    Quote = TextField()
    Name = TextField()
    DiscordMember = ForeignKeyField(DiscordMembers, backref="quotes", null=True)
    CreatedAt = DateTimeField()
    AddedBy = ForeignKeyField(DiscordMembers, backref="quotes_added", null=True)
    DiscordGuild = ForeignKeyField(DiscordGuilds, backref="quotes")


class QuoteAliases(BaseModel):
    id = IntegerField(primary_key=True)
    NameFrom = TextField()
    NameTo = TextField()


class QuotesToRemove(BaseModel):
    Quote = ForeignKeyField(Quotes, backref="to_remove", on_delete="CASCADE")
    Reporter = ForeignKeyField(DiscordMembers, backref="reported_quotes")


class Reputations(BaseModel):
    id = IntegerField(primary_key=True)
    DiscordMember = ForeignKeyField(DiscordMembers, backref="reputations")
    Message = TextField()
    CreatedAt = DateTimeField(default=datetime.datetime.now)
    AddedBy = ForeignKeyField(DiscordMembers, backref="reputations_added", null=True)
    IsPositive = IntegerField(default=1)


class Subjects(BaseModel):
    id = IntegerField(primary_key=True)
    Name = TextField()
    Abbreviation = TextField(default="n/a")
    Semester = TextField(default=0)
    Link = TextField(null=True)


class WeekDayTimes(BaseModel):
    id = IntegerField(primary_key=True)
    Subject = ForeignKeyField(Subjects, backref="times")
    DayID = IntegerField()
    TimeFrom = TimeField(formats=["%H:%M"])
    TimeTo = TimeField(formats=["%H:%M"])
    StreamLink = TextField(null=True)
    ZoomLink = TextField(null=True)
    OnSiteLocation = TextField(null=True)


class UserStatistics(BaseModel):
    id = AutoField(primary_key=True)
    Subject = ForeignKeyField(Subjects, backref="message_statistics")
    DiscordMember = ForeignKeyField(DiscordMembers, backref="message_statistics")
    MessagesSent = IntegerField(default=0)
    MessagesDeleted = IntegerField(default=0)
    MessagesEdited = IntegerField(default=0)
    CharactersSent = IntegerField(default=0)
    WordsSent = IntegerField(default=0)
    SpoilersSent = IntegerField(default=0)
    EmojisSent = IntegerField(default=0)
    FilesSent = IntegerField(default=0)
    FileSizeSent = IntegerField(default=0)
    ImagesSent = IntegerField(default=0)
    ReactionsAdded = IntegerField(default=0)
    ReactionsRemoved = IntegerField(default=0)
    ReactionsReceived = IntegerField(default=0)
    ReactionsTakenAway = IntegerField(default=0)


class VoiceLevels(BaseModel):
    DiscordMember = ForeignKeyField(DiscordMembers, backref="voice_xp")
    ExperienceAmount = IntegerField(default=0)


def create_tables():
    with sqlite_db:
        sqlite_db.create_tables([Config,
                                 DiscordGuilds,
                                 DiscordChannels,
                                 DiscordUsers,
                                 DiscordMembers,
                                 CovidGuessing,
                                 Events,
                                 EventJoinedUsers,
                                 Quotes,
                                 QuoteAliases,
                                 QuotesToRemove,
                                 Reputations,
                                 Subjects,
                                 WeekDayTimes,
                                 UserStatistics,
                                 VoiceLevels])

