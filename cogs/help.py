import discord
from discord.ext import commands
import datetime
from pytz import timezone


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_message_ids = {}

    @commands.command(aliases=["halp", "h"], usage="help <command>")
    async def help(self, ctx, specific_command=None):
        """
        You madlad just called help on the help command.
        You can get more detailed information about a command by using $help <command> on any command.
        """
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
                msg = ""
                msg += f"```asciidoc\n= {key} =\n"
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
            help_msg = str(specific_command.help)
            if help_msg == "None":
                await ctx.send(f"**{specific_command.name}** has no help page yet.")
                return
            aliases = specific_command.aliases
            usage = specific_command.usage
            if "Permissions" in help_msg:
                listified = help_msg.split("Permissions: ")
                help_msg = listified[0]
                permissions = listified[1]
            else:
                permissions = "`everyone`"

            nl = "\n"
            aliases_msg = f"- {f'{nl}- '.join(aliases)}"
            if aliases_msg == "- ":
                aliases_msg = "= None ="
            embed = discord.Embed(title=specific_command.name)
            embed.add_field(name="Info", value=help_msg.replace("Permissions:", "\n**Permissions:**"), inline=False)
            embed.add_field(name="Aliases", value=f"```asciidoc\n{aliases_msg}```")
            embed.add_field(name="Usage", value=f"`{usage}`")
            embed.add_field(name="Permissions", value=f"`{permissions}`")
            embed.set_thumbnail(url=self.bot.user.avatar_url)
            await ctx.send(embed=embed)

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
