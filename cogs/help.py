import discord
from discord.ext import commands
import datetime
from pytz import timezone
from helper import git_tools
import json
import os


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_message_ids = {}
        with open("./data/versions.json", "r") as f:
            self.versions = json.load(f)
        with open("./data/settings.json", "r") as f:
            self.prefix = json.load(f)["prefix"]

    @commands.Cog.listener()
    async def on_ready(self):
        await self.update_versions()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.content.startswith("man "):
            args = message.content.split(" ")
            args.pop(0)
            modifiers = []
            for a in args:
                if a.startswith("-"):
                    modifiers.append(a)
            modifiers = ", ".join(modifiers)
            specific_command, sorted_commands = await self.get_specific_com(args[0])
            bots_with_command = []
            if specific_command != "":
                print(specific_command)
                bots_with_command.append("Lecturfier")

            if len(bots_with_command) == 0:
                bots_with_command.append("None")
            bots_with_command = ", ".join(bots_with_command)
            await message.channel.send(f"Command: {args[0]}\n"
                                       f"Bots with that command: {bots_with_command}\n"
                                       f"Modifiers: {modifiers}\n"
                                       f"**Note:** This hasn't been implemented yet.")

    async def update_versions(self):
        """
        Goes through all file versions and updates them accordingly, adding them to the versions.json file
        """
        print("### Running version updater ###")
        updated_versions = await git_tools.get_versions(os.getcwd())
        for v in updated_versions.keys():
            if updated_versions[v]["status"]:
                if v not in self.versions:
                    print(f"--- {v} is a newly committed file ---")
                elif updated_versions[v]["version"] != self.versions[v]:
                    print(f"--- {v} version was updated ---")
                self.versions[v] = updated_versions[v]["version"]
        with open("./data/versions.json", "w") as f:
            json.dump(self.versions, f, indent=2)
        print("### Version updater done ###")

    @commands.command(aliases=["halp", "h"], usage="help <command>")
    async def help(self, ctx, specific_command=None):
        """
        You madlad just called help on the help command.
        You can get more detailed information about a command by using $help <command> on any command.
        """

        specific_command, sorted_commands = await self.get_specific_com(specific_command)

        if specific_command is None:
            # file = discord.File("./readme_images/help_page.png")
            embed = discord.Embed(description="""██╗░░██╗███████╗██╗░░░░░██████╗░
██║░░██║██╔════╝██║░░░░░██╔══██╗
███████║█████╗░░██║░░░░░██████╔╝
██╔══██║██╔══╝░░██║░░░░░██╔═══╝░
██║░░██║███████╗███████╗██║░░░░░
╚═╝░░╚═╝╚══════╝╚══════╝╚═╝░░░░░""", color=0x245C84)

            sorted_commands = self.sort_by_dict_size(sorted_commands)
            for key in sorted_commands.keys():
                sorted_commands[key] = self.sort_by_com_name(sorted_commands[key])
                version = "v00.0.0.0"
                version_key = str(key).lower() + ".py"
                if version_key in self.versions:
                    version = self.versions[version_key]
                msg = ""
                msg += f"```asciidoc\n= {key} =\n{version}\n=======\n"
                for com in sorted_commands[key]:
                    if com.help is None:
                        prefix = "-"
                    else:
                        prefix = "*"
                    msg += f"{prefix} {com}\n"
                msg += "```"
                embed.add_field(name="\u200b", value=msg)
                embed.set_footer(text="Commands with a star (*) have extra info when viewed with $help <command>")
            await ctx.send(embed=embed)
        else:
            embed = await self.command_help(specific_command)
            if embed == "":
                await ctx.send(f"The command `{specific_command}` has no help page.")
                return
            await ctx.send(embed=embed)

    async def get_specific_com(self, specific_command):
        sorted_commands = {}
        for cog in self.bot.cogs:
            sorted_commands[cog] = []
            all_commands = self.bot.get_cog(cog).get_commands()
            for com in all_commands:
                if specific_command == com.name:
                    specific_command = com
                sorted_commands[cog].append(com)
            if len(sorted_commands[cog]) == 0:
                sorted_commands.pop(cog)
        return [specific_command, sorted_commands]

    async def command_help(self, specific_command):
        print(type(specific_command) == str)
        if type(specific_command) == str or specific_command.help is None:
            return ""
        help_msg = specific_command.help
        aliases = specific_command.aliases
        usage = specific_command.usage
        if "Permissions" in help_msg:
            listified = help_msg.split("Permissions: ")
            help_msg = listified[0]
            permissions = listified[1]
        else:
            permissions = "@everyone"

        nl = "\n"
        aliases_msg = f"- {f'{nl}- '.join(aliases)}"
        if aliases_msg == "- ":
            aliases_msg = "none"
        embed = discord.Embed(title=specific_command.name, color=0x245C84)
        embed.add_field(name="Info", value=help_msg.replace("Permissions:", "\n**Permissions:**"), inline=False)
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Aliases =\n{aliases_msg}```")
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Permissions =\n{permissions}```")
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Usage =\n{self.prefix}{usage}```", inline=False)
        embed.set_thumbnail(url=self.bot.user.avatar_url)
        return embed

    def sort_by_com_name(self, inp):
        with_keys = {}
        for command in inp:
            with_keys[command.name] = command
        sorted_keys = sorted(list(with_keys.keys()))
        com_sorted = []
        for key in sorted_keys:
            com_sorted.append(with_keys[key])
        return com_sorted

    def sort_by_dict_size(self, inp):
        d = {}
        for key in inp:
            d[key] = len(inp[key])
        d = {k: d[k] for k in sorted(d, key=d.get, reverse=True)}
        sort = {}
        for key in d:
            sort[key] = inp[key]
        return sort


def setup(bot):
    bot.add_cog(Help(bot))
