import discord
from discord import app_commands
from discord.ext import commands
from .lecture import CourseModal, AddLectureView, UpdateCourseModal, create_lecture_embed, LectureData
import helper.sql.SQLFunctions as sql

async def abbreviation_autocomplete(inter: discord.Interaction, cur: str
    ) -> list[app_commands.Choice[str]]:
    assert inter.guild_id
    res = sql.get_abbreviations(inter.guild_id, cur)
    return [
        app_commands.Choice(name=x, value=x)
        for x in res
    ]

async def lecture_id_autocomplete(inter: discord.Interaction, cur: str
    ) -> list[app_commands.Choice[str]]:
    assert inter.guild_id
    if len(cur) > 0:
        cur = cur.split(" ")[0]
    res = sql.get_lecture_ids(inter.guild_id, cur)
    return [
        app_commands.Choice(name=f"{x[0]} ({x[1]})", value=str(x[0]))
        for x in res
    ]

async def course_id_autocomplete(inter: discord.Interaction, cur: str
    ) -> list[app_commands.Choice[str]]:
    assert inter.guild_id
    if len(cur) > 0:
        cur = cur.split(" ")[0]
    res = sql.get_course_ids(inter.guild_id, cur)
    return [
        app_commands.Choice(name=f"{x[0]} ({x[1]})", value=str(x[0]))
        for x in res
    ]


@app_commands.guild_only()
class CourseGroup(commands.GroupCog, group_name="course", group_description="Course commands"):    
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="Add a course")
    @app_commands.describe(role="Role to ping")
    @app_commands.describe(channel="Channel to send pings to")
    async def add(self, inter: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
        await inter.response.send_modal(CourseModal(inter.user, channel, role))

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="Update a course")
    @app_commands.describe(course_id="Course ID to update")
    @app_commands.autocomplete(course_id=course_id_autocomplete)
    @app_commands.describe(role="Role to ping")
    @app_commands.describe(channel="Channel to send pings to")
    async def update(self, inter: discord.Interaction, course_id: str, channel: discord.TextChannel, role: discord.Role):
        # to make sure we only have actual valid ids
        assert inter.guild_id
        res = sql.get_course_ids(inter.guild_id, course_id)
        ids = [str(x[0]) for x in res]
        if course_id not in ids:
            await inter.response.send_message(
                f"{course_id} is an invalid course ID!",
                ephemeral=True
            )
            return
        abbreviation = res[0][1]
        
        await inter.response.send_modal(UpdateCourseModal(inter.user, abbreviation, course_id, channel, role))

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="Deletes a course (deletes all lectures of this course)")
    @app_commands.describe(course_id="Course ID to delete")
    @app_commands.autocomplete(course_id=course_id_autocomplete)
    async def delete(self, inter: discord.Interaction, course_id: str):
        assert inter.guild_id
        c = sql.get_single_course(int(course_id), inter.guild_id)
        if c is None:
            await inter.response.send_message("That course doesn't exist.", ephemeral=True)
        else:
            sql.delete_course(int(course_id))
            await inter.response.send_message(f"Deleted the course with ID `{course_id}` ({c[1]})", ephemeral=True)
        

    def create_list_embed(self, result):
        embed = discord.Embed(title="Course list", color=discord.colour.Color.light_gray())
        fields = []
        size = 0
        for i, r in enumerate(result):
            if (i == 24):
                embed.add_field(
                    name="WARNING",
                    value="There are currently too many courses to show them all. Delete some courses.",
                    inline=False
                )
                break
            link = "*No Course Link*"
            if r[4]:
                link = f"{r[4]}"
            line = f"**ID:** `{r[0]}`, **Name:** `{r[3]}`, **Abbrev.:** `{r[1]}`, **Channel:** <#{r[5]}>, **Role:** <@&{r[6]}>, **Link:** {link}"
            if len(line) + size  > 1000:
                embed.add_field(name="\u200b", value="\n".join(fields), inline=False)
                fields = []
                size = 0
            fields.append(line)
            size += len(line) + 1
        if len(fields) > 0:
            embed.add_field(name="\u200b", value="\n".join(fields), inline=False)
        if len(embed.fields) == 0:
            embed.add_field(name="\u200b", value="*No courses yet*")
        return embed

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="lists all courses on this server")
    async def list(self, inter: discord.Interaction):
        assert inter.guild_id
        result = sql.get_courses(inter.guild_id)
        await inter.response.send_message(embed=self.create_list_embed(result), ephemeral=True)

@app_commands.guild_only()
class LectureGroup(commands.GroupCog, group_name="lecture", group_description="Lecture reminder commands"):
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="Add a lecture reminder")
    @app_commands.describe(abbreviation="Abbreviation to add a lecture for")
    @app_commands.autocomplete(abbreviation=abbreviation_autocomplete)
    async def add(self, inter: discord.Interaction, abbreviation: str):
        # to make sure we only have actual valid ids
        assert inter.guild_id
        res = sql.get_abbreviations(inter.guild_id, abbreviation)
        # res of type [LectureId, DayId, HourFrom, MinuteFrom, StreamLink, SecondaryLink, OnSiteLocation, Name]
        if abbreviation not in res:
            await inter.response.send_message(
                f"{abbreviation} is an invalid abbreviation! (Does not exist)",
                ephemeral=True
            )
            return
        
        lecture_id = sql.get_lecture_id(abbreviation, inter.guild_id)
        assert lecture_id
        await inter.response.send_message(
            embed=create_lecture_embed(LectureData(lecture_id)),
            view=AddLectureView(abbreviation, inter.user),
            ephemeral=True
        )

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="Add a lecture reminder")
    @app_commands.describe(lecture_id="Lecture ID to update")
    @app_commands.autocomplete(lecture_id=lecture_id_autocomplete)
    async def update(self, inter: discord.Interaction, lecture_id: str):
        # to make sure we only have actual valid ids
        assert inter.guild_id
        res = sql.get_lecture_ids(inter.guild_id, lecture_id)
        res = [str(x[0]) for x in res]
        if lecture_id not in res:
            await inter.response.send_message(
                f"{lecture_id} is an invalid lecture ID!",
                ephemeral=True
            )
            return
        
        await inter.response.send_message(
            embed=create_lecture_embed(LectureData(int(lecture_id))),
            view=AddLectureView(lecture_id, inter.user, int(lecture_id)),
            ephemeral=True
        )

    def create_list_embed(self, result, abbreviation):
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "None"]
        embed = discord.Embed(title=f"Lecture Reminder list ({abbreviation})", color=discord.colour.Color.light_gray())
        if len(result) > 0:
            embed.description = f"**Course:** {result[0][7]}"
        for i, r in enumerate(result):
            if (i == 24):
                embed.add_field(name="WARNING", value="More than 25 Lectures added. Can't show them all. Delete some lectures.")
                break
            time_format = "%02d:%02d" % (r[2], r[3])
            stream_link = "*No Stream Link*"
            if r[4]:
                stream_link = f"{r[4]}"
            secondary_link = "*No Secondary Link*"
            if r[5]:
                secondary_link = f"{r[5]}"
            embed.add_field(
                name=f"ID {r[0]}",
                value=
                    f"**Day:** `{time_format}` on `{weekdays[r[1]]}`\n"
                    f"**Stream Link:** {stream_link}\n**Secondary Link:** {secondary_link}\n**Location:** `{r[6]}`"
            )
        if len(embed.fields) == 0:
            embed.add_field(name="\u200b", value="*No lectures for this abbreviation yet*")
        return embed

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="list all added lecture reminders")
    @app_commands.describe(abbreviation="Abbreviation to list all lectures for")
    @app_commands.autocomplete(abbreviation=abbreviation_autocomplete)
    async def list(self, inter: discord.Interaction, abbreviation: str):
        # to make sure we only have actual valid ids
        assert inter.guild_id
        res = sql.get_abbreviations(inter.guild_id, abbreviation)
        if abbreviation not in res:
            await inter.response.send_message(
                f"{abbreviation} is an invalid abbreviation! (Does not exist)",
                ephemeral=True
            )
            return
        
        result = sql.get_lectures(abbreviation, inter.guild_id)
        await inter.response.send_message(embed=self.create_list_embed(result, abbreviation), ephemeral=True)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(description="Deletes a lecture")
    @app_commands.describe(lecture_id="Lecture ID to delete")
    @app_commands.autocomplete(lecture_id=lecture_id_autocomplete)
    async def delete(self, inter: discord.Interaction, lecture_id: str):
        assert inter.guild_id
        c = sql.get_single_lecture(int(lecture_id), inter.guild_id)
        if c is None:
            await inter.response.send_message("That lecture doesn't exist.", ephemeral=True)
        else:
            sql.delete_lecture(int(lecture_id))
            await inter.response.send_message(f"Deleted the lecture with ID `{lecture_id}` ({c[0]})", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CourseGroup())
    await bot.add_cog(LectureGroup())

