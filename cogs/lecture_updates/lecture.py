from sqlite3 import IntegrityError
import traceback
import discord
import helper.sql.SQLFunctions as sql
import string

VALID_ABB_CHARS = string.ascii_lowercase + string.digits + "_"

class CourseModal(discord.ui.Modal, title="Course"):
    def __init__(self, user, channel, role):
        super().__init__()
        self.user = user
        self.channel = channel
        self.role = role
    
    course = discord.ui.TextInput(
        label="Course Name",
        placeholder="Analysis II",
        max_length=70
    )
    abbreviation = discord.ui.TextInput(
        label=f"Unique Course Abbreviation",
        placeholder="ana2 (no spaces, only letters and digits)",
        min_length=1,
        max_length=10
    )
    course_link = discord.ui.TextInput(
        label="Course Website Link",
        placeholder="https://departement.ethz.ch",
        required=False
    )

    async def on_submit(self, inter: discord.Interaction):
        if inter.user.id != self.user.id:
            await inter.response.send_message(f"You can't use this menu.", ephemeral=True)
            return
        assert inter.guild_id
        
        for c in self.abbreviation.value:
            if c not in VALID_ABB_CHARS:
                await inter.response.send_message(
                    f"Invalid abbreviation given. You can only use the following characters: `{VALID_ABB_CHARS}`",
                    ephemeral=True)
                return
        
        sql.add_course(self.abbreviation.value, self.course.value, inter.guild_id, self.channel.id, self.role.id, self.course_link.value)
        embed = discord.Embed(
            title="Added Course",
            description=f"**Course:** `{self.course.value}`\n"
            f"**Abbreviation:** `{self.abbreviation.value}`\n"
            f"**Course Link:** {self.course_link}\n"
            f"**Channel:** <#{self.channel.id}>\n"
            f"**Role:** <@&{self.role.id}>",
            color=discord.colour.Color.light_gray()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

    async def on_error(self, inter: discord.Interaction, error: Exception) -> None:
        if isinstance(error, IntegrityError):
            await inter.response.send_message(f"This abbreviation is already in use!", ephemeral=True)
            return
        
        await inter.response.send_message(f"Something went wrong!", ephemeral=True)
        traceback.print_exception(error)


class UpdateCourseModal(discord.ui.Modal, title="Course"):
    def __init__(self, user, abbreviation, course_id, channel, role):
        super().__init__()
        self.user = user
        self.data = sql.get_single_course(course_id)
        self.course_id = course_id
        self.abbreviation.default = abbreviation
        self.course.default = self.data[3]
        if self.data[4]:
            self.course_link.default = self.data[4]
        self.channel = channel
        self.role = role
    
    course = discord.ui.TextInput(
        label="Course Name",
        placeholder="Analysis II",
        max_length=70
    )
    
    abbreviation = discord.ui.TextInput(
        label=f"Unique Course Abbreviation",
        placeholder="ana2 (no spaces, only letters and digits)",
        min_length=1,
        max_length=10
    )
    
    course_link = discord.ui.TextInput(
        label="Course Website Link",
        placeholder="https://departement.ethz.ch",
        required=False
    )

    async def on_submit(self, inter: discord.Interaction):
        if inter.user.id != self.user.id:
            await inter.response.send_message(f"You can't use this menu.", ephemeral=True)
            return
        course_link = None
        if len(self.course_link.value) > 0:
            course_link = self.course_link.value
        sql.update_course(self.course_id, self.abbreviation.value, self.course.value, self.channel.id, self.role.id, course_link)
        embed = discord.Embed(
            title="Updated Course",
            description=f"**Course:** `{self.course.value}`\n"
            f"**Abbreviation:** `{self.abbreviation.value}`\n"
            f"**Course Link:** {self.course_link}\n"
            f"**Channel:** <#{self.channel.id}>\n"
            f"**Role:** <@&{self.role.id}>",
            color=discord.colour.Color.light_gray()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

    async def on_error(self, inter: discord.Interaction, error: Exception) -> None:
        await inter.response.send_message(f"Something went wrong!", ephemeral=True)
        traceback.print_exception(error)
        

class LectureData:
    weekday: str | None = None
    hour_from: int = -1
    minute_from: int = -1
    stream_link: str | None = None
    secondary_link: str | None = None
    on_site_location: str | None = None
    title: str | None = None
    abbreviation: str | None = None
    def __init__(self, lecture_id: int) -> None:
        res = sql.get_single_lecture(lecture_id)
        if res:
            weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "None"]
            self.abbreviation = res[0]
            self.weekday = weekdays[res[1]]
            self.hour_from = res[2]
            self.minute_from = res[3]
            self.stream_link = res[4]
            self.secondary_link = res[5]
            self.on_site_location = res[6]


def create_lecture_embed(data: LectureData):
    hour_from = "XX"
    if data.hour_from > 0:
        hour_from = "%02d" % data.hour_from
    minute_from = "XX"
    if data.minute_from >= 0:
        minute_from = "%02d" % data.minute_from
    embed = discord.Embed(
        description=f"Abbreviation: `{data.abbreviation}`\n"
        f"**Weekday:** `{data.weekday}`\n"
        f"**Start Time:** `{hour_from}:{minute_from}`\n"
        f"\n__Text Input Fields__\n**On Site Location:** `{data.on_site_location}`\n"
        f"**Stream Link:** {data.stream_link}\n"
        f"**Secondary Link:** {data.secondary_link}\n",
        color=discord.colour.Color.light_gray()
    )
    if data.title:
        embed.title = data.title
    return embed


class LectureModal(discord.ui.Modal, title="Lecture Reminder"):
    def __init__(self, data: LectureData, user: discord.User | discord.Member, message: discord.Message):
        super().__init__()
        self.user = user
        self.data = data
        self.message = message
    
    location = discord.ui.TextInput(
        label="On-Site Location (with spaces)",
        placeholder="HG E 5",
        required=False
    )

    stream_link = discord.ui.TextInput(
        label="Stream Link",
        placeholder="https://video.ethz.ch/live/lectures/zentrum/eta/eta-f-5.html",
        required=False
    )

    secondary_link = discord.ui.TextInput(
        label="Secondary Stream Link (if there is one)",
        placeholder="https://ethz.zoom.us/j/123...",
        required=False
    )

    async def on_submit(self, inter: discord.Interaction):
        if inter.user.id != self.user.id:
            await inter.response.send_message(f"You can't use this menu.", ephemeral=True)
            return
        self.data.on_site_location = self.location.value
        if len(self.data.on_site_location) == 0:
            self.data.on_site_location = None
        self.data.stream_link = self.stream_link.value
        if len(self.data.stream_link) == 0:
            self.data.stream_link = None
        self.data.secondary_link = self.secondary_link.value
        if len(self.data.secondary_link) == 0:
            self.data.secondary_link = None
        
        await inter.response.edit_message(embed=create_lecture_embed(self.data))

    async def on_error(self, inter: discord.Interaction, error: Exception) -> None:
        if isinstance(error, IntegrityError):
            await inter.response.send_message(f"There already exists a lecture for that course on this day, hour and minute!", ephemeral=True)
            return
        print(type(error), type(IntegrityError))
            
        await inter.response.send_message(f"Something went wrong!", ephemeral=True)
        traceback.print_exception(error)


class HourDropdown(discord.ui.Select):
    def __init__(self, data: LectureData, user: discord.User | discord.Member) -> None:
        self.user = user
        self.data = data
        options = [
            discord.SelectOption(label="%02d" % i, description="Hour %02d:XX}" % i) for i in range(24)
        ]
        super().__init__(placeholder="Select the hour when the lecture starts.", options=options)
        if self.data.hour_from != -1:
            self.placeholder = "%02d" % self.data.hour_from

    async def callback(self, inter: discord.Interaction):
        if inter.user.id != self.user.id:
            await inter.response.send_message(f"You can't use this menu.", ephemeral=True)
            return
        self.data.hour_from = int(self.values[0])
        self.placeholder = self.values[0]
        await inter.response.edit_message(embed=create_lecture_embed(self.data), view=self.view)


class MinuteDropdown(discord.ui.Select):
    def __init__(self, data: LectureData, user: discord.User | discord.Member) -> None:
        self.user = user
        self.data = data
        options = [
            discord.SelectOption(label="%02d" % i, description="Hour XX:%02d}" % i) for i in range(0, 56, 5)
        ]
        super().__init__(placeholder="Select the minute when the lecture starts.", options=options)
        if self.data.minute_from != -1:
            self.placeholder = "%02d" % self.data.minute_from

    async def callback(self, inter: discord.Interaction):
        if inter.user.id != self.user.id:
            await inter.response.send_message(f"You can't use this menu.", ephemeral=True)
            return
        self.data.minute_from = int(self.values[0])
        self.placeholder = self.values[0]
        await inter.response.edit_message(embed=create_lecture_embed(self.data), view=self.view)


class DayDropdown(discord.ui.Select):
    def __init__(self, data: LectureData, user: discord.User | discord.Member) -> None:
        self.user = user
        self.data = data
        options = [
            discord.SelectOption(label="Monday"),
            discord.SelectOption(label="Tuesday"),
            discord.SelectOption(label="Wednesday"),
            discord.SelectOption(label="Thursday"),
            discord.SelectOption(label="Friday"),
            discord.SelectOption(label="Saturday"),
            discord.SelectOption(label="Sunday"),
            discord.SelectOption(label="None (prevents pings)", value="None"),
        ]
        super().__init__(placeholder="Select the day the lecture takes place.", options=options)
        if self.data.weekday is not None:
            self.placeholder = self.data.weekday

    async def callback(self, inter: discord.Interaction):
        if inter.user.id != self.user.id:
            await inter.response.send_message(f"You can't use this menu.", ephemeral=True)
            return
        self.data.weekday = self.values[0]
        self.placeholder = self.values[0]
        await inter.response.edit_message(embed=create_lecture_embed(self.data), view=self.view)


class AddLectureView(discord.ui.View):
    def __init__(self, abbreviation: str, user: discord.User | discord.Member, lecture_id=-1):
        """
        Args:
            abbreviation (str): Where to add the lecture to.
            user (discord.User): User that is adding the message.
            lecture_id (int, optional): If this updating a specific lecture.
        """
        super().__init__()
        self.data = LectureData(lecture_id)
        self.add = True
        self.data.title = "Adding Lecture"
        if lecture_id != -1:
            self.add = False
            self.data.title = "Updating Lecture"
        else:
            self.data.abbreviation = abbreviation
        self.user = user
        self.add_item(HourDropdown(self.data, user))
        self.add_item(MinuteDropdown(self.data, user))
        self.add_item(DayDropdown(self.data, user))
    
    @discord.ui.button(label="Text Input", style=discord.ButtonStyle.primary, row=4)
    async def text_input(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user.id != self.user.id:
            await inter.response.send_message(f"You can't use this menu.", ephemeral=True)
            return
        assert inter.message
        await inter.response.send_modal(LectureModal(self.data, inter.user, inter.message))
    
    @discord.ui.button(label="Save", style=discord.ButtonStyle.success, row=4)
    async def save(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user.id != self.user.id:
            await inter.response.send_message(f"You can't use this menu.", ephemeral=True)
            return
        assert inter.guild_id
        
        if self.add:
            if self.data.hour_from == -1:
                await inter.response.send_message(f"The starting hour is missing!", ephemeral=True)
                return
            if self.data.minute_from == -1:
                await inter.response.send_message(f"The starting minute is missing!", ephemeral=True)
                return
            if self.data.weekday is None:
                await inter.response.send_message(f"The weekday is missing!", ephemeral=True)
                return
            
            sql.add_lecture(
                self.data.abbreviation,
                inter.guild_id,
                self.data.weekday,
                self.data.hour_from,
                self.data.minute_from,
                self.data.stream_link,
                self.data.secondary_link,
                self.data.on_site_location
            )
        else:
            if self.data.weekday is None:
                await inter.response.send_message(f"There was an error. The weekday is missing!", ephemeral=True)
                return
            sql.update_lecture(
                self.data.abbreviation,
                inter.guild_id,
                self.data.weekday,
                self.data.hour_from,
                self.data.minute_from,
                self.data.stream_link,
                self.data.secondary_link,
                self.data.on_site_location
            )
    
        await inter.response.edit_message(content=f"Successfully saved", embed=create_lecture_embed(self.data), view=None)
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=4)
    async def cancel(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user.id != self.user.id:
            await inter.response.send_message(f"You can't use this menu.", ephemeral=True)
            return
    
        await inter.response.edit_message(content=f"Cancelled lecture adding", embed=create_lecture_embed(self.data), view=None)
        self.stop()
    
    @discord.ui.button(label="Create Link", style=discord.ButtonStyle.secondary, row=4)
    async def link(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user.id != self.user.id:
            await inter.response.send_message(f"You can't use this menu.", ephemeral=True)
            return
        if not self.data.on_site_location:
            await inter.response.send_message(
                f"This button turns the On-Site Location into the default video portal link for lectures in **Zentrum**. "
                "There's currently no on-site location given though.", ephemeral=True)
            return
        splitted = self.data.on_site_location.lower().split(" ")
        modified_loc = "-".join(splitted)
        url = f"https://video.ethz.ch/live/lectures/zentrum/{splitted[0]}/{modified_loc}.html"
        self.data.stream_link = url
        await inter.response.edit_message(embed=create_lecture_embed(self.data))
