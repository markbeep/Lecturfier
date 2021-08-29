import discord
from discord.ext import commands


attributes = {
    "aliases": ["h", "halp", "hell", "hepl", "helps", "guide", "manual"],
    "usage": "help [command | group | cog]"
}


class Help(commands.HelpCommand):
    # help
    async def send_bot_help(self, mapping):
        embed = discord.Embed(color=0xcbd3d7)
        bot_prefix = self.clean_prefix
        # sorts by the amount of commands in the cog (after filtering)
        for cog, cmds in sorted(mapping.items(), key=lambda e: len(e[1]), reverse=True):
            if len(cmds) > 0:
                cog_name = getattr(cog, "qualified_name", "Other")
                msg = f"```md\n"
                for com in sorted(cmds, key=lambda e: e.name):
                    try:
                        run = await com.can_run(self.context)
                    except:
                        run = False
                    if run:
                        prefix = "*"
                    else:
                        prefix = ">"
                    msg += f"{prefix} {com}\n"
                msg += "```"
                embed.add_field(name=f"{cog_name}", value=msg)

        embed.set_footer(text=f"Use {bot_prefix}help <command / category> to get more information.")
        embed.set_author(name=self.context.message.author.name, icon_url=self.context.message.author.avatar_url)
        file = discord.File("./images/help_page.gif")
        channel = self.get_destination()
        await channel.send(embed=embed, file=file)

    # help <command>
    async def send_command_help(self, command):
        embed = self.create_command_help_embed(command)
        channel = self.get_destination()
        await channel.send(embed=embed)

    # help <group>
    async def send_group_help(self, group):
        embed = self.create_command_help_embed(group)
        sub_commands = [c.name for c in group.commands]
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Subcommands =\n{', '.join(sub_commands)}```")
        if len(command_chain := group.full_parent_name) > 0:
            command_chain = group.full_parent_name + " "
        embed.set_footer(text=f"This command has subcommands. Check their help page with {self.clean_prefix}help {command_chain}{group.name} <subcommand>")
        await self.context.send(embed=embed)

    # help <cog>
    async def send_cog_help(self, cog):
        cog_name = getattr(cog, "qualified_name", "Other")
        embed = discord.Embed(title=cog_name, color=0xcbd3d7)
        embed.description = cog.description
        if len(cog.description) == 0:
            embed.description = "*[no info]*"
        cmds = [c.name for c in cog.get_commands()]
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Commands =\n{', '.join(cmds)}```")
        channel = self.get_destination()
        await channel.send(embed=embed)

    def create_command_help_embed(self, command):
        command_name = command.name
        # command path
        if len(command.full_parent_name) > 0:
            command_name = command.full_parent_name.replace(" ", " > ") + " > " + command_name
        embed = discord.Embed(title=command_name, color=0xcbd3d7)

        help_msg = command.help
        if help_msg is None:
            help_msg = "No command information"

        # permissions
        if "Permissions" in help_msg:
            listified = help_msg.split("Permissions: ")
            help_msg = listified[0]
            permissions = listified[1]
        else:
            permissions = "@everyone"

        if command.aliases is None or len(command.aliases) == 0:
            aliases_msg = "[n/a]"
        else:
            aliases_msg = ", ".join(command.aliases)

        if command.usage is None:
            usage = "[n/a]"
        else:
            usage = command.usage
            if len(command.full_parent_name) > 0:
                usage = command.full_parent_name + " " + usage
            usage = self.clean_prefix + usage
        embed.add_field(name="Info", value=help_msg.replace("{prefix}", self.clean_prefix), inline=False)
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Aliases =\n{aliases_msg}```")
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Permissions =\n{permissions}```")
        """checks = [c.__name__ for c in command.checks]
        if len(checks) > 0:
            embed.add_field(name="\u200b", value=f"```asciidoc\n= Checks =\n{', '.join(checks)}```")"""
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Usage =\n{usage}```", inline=False)
        embed.set_author(name=self.context.message.author.name, icon_url=self.context.message.author.avatar_url)
        return embed


def setup(bot):
    bot.help_command = Help(command_attrs=attributes)
