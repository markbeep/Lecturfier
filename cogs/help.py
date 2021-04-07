import discord
from discord.ext import commands
from helper import handySQL
from helper import git_tools
import json
import os
from discord.ext.commands.cooldowns import BucketType


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_message_ids = {}
        with open("./data/settings.json", "r") as f:
            self.prefix = json.load(f)["prefix"]
        self.db_path = "./data/discord.db"


    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

    @commands.command(usage="doTheThing")
    async def doTheThing(self, ctx):
        """
        Used to transfer all current commands to the slash command-manual \
        we have set up on the server.
        Permissions: Owner
        """
        if await self.bot.is_owner(ctx.author):
            for cog in self.bot.cogs:
                all_commands = self.bot.get_cog(cog).get_commands()
                for com in all_commands:
                    await ctx.send(f"\\botman {com} {com.help}")
            await ctx.send("Done")
        else:
            raise discord.ext.commands.errors.NotOwner

    @commands.cooldown(4, 10, BucketType.user)
    @commands.command(aliases=["halp", "h"], usage="help <command>")
    async def help(self, ctx, given_command=None, *args):
        """
        You madlad just called help on the help command.
        You can get more detailed information about a command by using $help <command> on any command.
        """

        specific_command, sorted_commands, sub_commands = await self.get_specific_com(given_command)
        if specific_command is None:
            file = discord.File("./images/help_page.gif")
            embed = discord.Embed(color=0xcbd3d7)

            sorted_commands = self.sort_by_dict_size(sorted_commands)

            updated_versions = git_tools.get_versions(os.getcwd())
            for key in sorted_commands.keys():
                sorted_commands[key] = self.sort_by_com_name(sorted_commands[key])
                version = "v00.0.0.0"
                version_key = str(key).lower() + ".py"
                if version_key in updated_versions:
                    version = updated_versions[version_key]["version"]
                msg = f"```asciidoc\n"
                for com in sorted_commands[key]:
                    if com.help is None:
                        prefix = "-"
                    else:
                        prefix = "*"
                    msg += f"{prefix} {com}\n"
                msg += "```"
                embed.add_field(name=f"{key} | *{version}*", value=msg)
                embed.set_footer(text="Commands with a star (*) have extra info when viewed with $help <command>")
            await ctx.send(file=file, embed=embed)
        else:
            # if a subcommand is called, we have the command object, but it could be wrong if there
            # are multiple subcommands with the same name. So we don't show it.
            if specific_command.name != given_command:
                await ctx.send(f"The command `{given_command}` only exists as a subcommand.")
                return

            specific_command, command_chain = await self.get_recursive_command(specific_command, args)
            if type(specific_command) == str:
                if specific_command == "":
                    await ctx.send(f"The command `{given_command}` does not exist.")
                    return
                elif specific_command == "n/a":
                    await ctx.send(f"The command `{given_command}` has no help page.")
                    return
                elif specific_command == "no sub":
                    await ctx.send(f"The command chain `{given_command} {' '.join(args)}` does not exist.")
                    return
            embed = await self.command_help(specific_command, command_chain)
            await ctx.send(embed=embed)

    async def get_specific_com(self, specific_command):
        sorted_commands = {}
        sub_commands = {}
        for cog in self.bot.cogs:
            sorted_commands[cog] = []
            all_commands = self.bot.get_cog(cog).get_commands()
            for com in all_commands:
                # adds all subcommands to another list
                try:
                    sub_commands[com.name] = []
                    for sub_com in com.commands:
                        sub_commands[com.name].append(sub_com)
                        if specific_command == sub_com.name:
                            # makes the specific command be the group command
                            specific_command = com
                except AttributeError:
                    pass
                if specific_command == com.name:
                    specific_command = com
                sorted_commands[cog].append(com)
            if len(sorted_commands[cog]) == 0:
                sorted_commands.pop(cog)
        return [specific_command, sorted_commands, sub_commands]

    async def get_recursive_command(self, specific_command, args, command_chain=""):
        """
        Goes down a command to see if any of its subcommands was called for
        """
        if type(specific_command) == str:
            return "", command_chain  # if the command doesn't even exist
        if specific_command.help is None:
            return "n/a", command_chain  # if there's no help page, but the command exists
        coms = list(args)
        if len(coms) > 0:
            try:
                for com in specific_command.commands:
                    if com.name == coms[0].lower():
                        # command_chain is used to display the command chain in the help page
                        specific_command, command_chain = await self.get_recursive_command(com, coms[1:], f"{command_chain}{specific_command.name} ")
            except AttributeError:
                if specific_command.name == args[0]:
                    return specific_command, command_chain
                return "no sub", command_chain  # if the command doesnt have a subcommand with that name
        return specific_command, command_chain

    async def command_help(self, specific_command, command_chain):
        help_msg = specific_command.help
        aliases = specific_command.aliases
        usage = specific_command.usage

        # if the command has subcommands
        sub_commands = []
        try:
            for com in specific_command.commands:
                sub_commands.append(com.name)
        except AttributeError:
            pass

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
        command_name = f"{command_chain}{specific_command.name}".replace(" ", " > ")
        embed = discord.Embed(title=command_name, color=0xcbd3d7)
        embed.add_field(name="Info", value=help_msg.replace("Permissions:", "\n**Permissions:**").replace("{prefix}", self.prefix), inline=False)
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Aliases =\n{aliases_msg}```")
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Permissions =\n{permissions}```")
        embed.add_field(name="\u200b", value=f"```asciidoc\n= Usage =\n{self.prefix}{usage}```", inline=False)

        # only adds sub_commands field if there exist any
        if len(sub_commands) > 0:
            embed.add_field(name="\u200b", value=f"```asciidoc\n= Subcommands =\n{', '.join(sub_commands)}```")
            embed.set_footer(text=f"This command has subcommands. Check their help page with {self.prefix}help {command_chain} {specific_command.name} <subcommand>")
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
