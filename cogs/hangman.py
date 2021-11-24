import asyncio
import random
import string
import time

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from discord_components import *

from helper import hangman


def joinTuple(string_tuples) -> str:
    return " ".join(string_tuples)


class Hangman(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sending = False

    def clean_string(self, inp):
        inp = inp.lower()
        valid = string.ascii_lowercase + "_äöüàéè"
        corrected = ""
        for s in inp:
            if s in valid:
                corrected += s
        return corrected

    @commands.cooldown(1, 5, BucketType.channel)
    @commands.group(aliases=["hm"], invoke_without_command=True, usage="hm")
    async def hangman(self, ctx):
        """
        Using this command as a standalone initializes a hangman guessing game. \
        You can guess letters by using the dropdown menu.
        The game ends after **100** seconds.
        """
        if ctx.invoked_subcommand is None:
            start = time.time()
            word_length = random.randint(4, 15)
            previous = []
            ignored = []
            current_word = ["_"] * word_length
            guesses = 0

            def generate_select() -> list[Select]:
                emoji_letters = ["🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭", "🇮", "🇯", "🇰", "🇱", "🇲", "🇳", "🇴", "🇵", "🇶", "🇷", "🇸",
                                 "🇹", "🇺", "🇻", "🇼", "🇽", "🇾", "🇿"]
                select_options = []
                count = 0
                for letter in string.ascii_lowercase:
                    if letter in ignored or letter in current_word:
                        continue
                    if count == 25:  # we only put the first 25 letters into the dropdown
                        break
                    if 0 <= ord(letter)-97 < len(emoji_letters):
                        select_options.append(SelectOption(label=letter, value=letter, emoji=emoji_letters[ord(letter)-97]))
                    else:
                        select_options.append(SelectOption(label=letter, value=letter))
                    count += 1
                return [Select(options=select_options, placeholder="Guess a letter...")]

            msg = await ctx.reply(content="Make an initial guess for a letter", components=generate_select())

            while True:
                try:
                    res: Interaction = await self.bot.wait_for("select_option", timeout=60)
                except asyncio.TimeoutError:
                    break
                if res.user.id != ctx.message.author.id:
                    await res.respond(type=InteractionType.ChannelMessageWithSource, content="This isn't your hangman game.")
                    continue
                if res is None or res.component is None:
                    continue
                guess = res.component[0].label
                await res.respond(type=InteractionType.ChannelMessageWithSource, content=f"You guessed {guess}.")
                ignored.append(guess)
                guesses += 1

                letter_count, fitting = hangman.solve("".join(current_word), ignore=ignored)

                if len(fitting) == 0:  # no fitting letters
                    if len(previous) == 0:  # this is called in the first iteration if previous hasn't been filled in yet
                        word_length -= 1
                        if word_length < 0:
                            break
                        else:
                            current_word = ["_"] * word_length  # we create a new underscore word
                    else:  # we found no fitting words, so pick one of the previous words randomly
                        rand_word = random.choice(previous)  # pick a random word of the previous list
                        if guess in rand_word:  # if the guess is in the word, we have to change all _ to the guess
                            for i in range(len(rand_word)):
                                if rand_word[i] == guess:
                                    current_word[i] = guess
                            ignored.pop(ignored.index(guess))  # additionally remove the letter from the ignored chars
                        else:  # we keep the guess as a wrong guess
                            pass
                else:
                    previous = fitting.copy()
                    
                if current_word.count("_") == 0:
                    await ctx.send(f"{ctx.message.author.mention}! You guessed the word!\n`{''.join(current_word)}`")
                    break

                embed = discord.Embed(
                    title="Hangman Game",
                    description=f"Current Word: `{''.join(current_word)}`\n"
                                f"Wrong Letters: {', '.join(ignored)}\n"
                                f"Amount of guesses: {guesses}\n"
                                f"**Guess a letter:**"
                )
                if msg is not None:
                    await msg.delete()
                embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
                msg = await ctx.send(embed=embed, components=generate_select())

            # if no initial character was given
            if len(previous) == 0:
                await msg.delete()
                return

            if "_" in current_word:
                final_word = random.choice(previous)
            else:
                final_word = "".join(current_word)
            embed = discord.Embed(
                title="Hangman Game",
                description=f"Correct Word: `{final_word}`\n"
                            f"Wrong Letters: {', '.join(ignored)}\n"
                            f"Amount of guesses: {guesses}"
            )
            embed.set_author(name=str(ctx.message.author), icon_url=ctx.message.author.avatar_url)
            if msg is not None:
                await msg.delete()
            await ctx.send(embed=embed, components=[])

    @commands.cooldown(1, 5, BucketType.user)
    @hangman.command(name="solve", usage="solve <word up till now> <wrong letters or 0> <language>")
    async def solve_hangman(self, ctx, inputted_word=None, unused_letters="", language="e"):
        """
        This is used to solve hangman the best way possible. It is not optimized, so take it easy with the usage.
        To use this command properly, you want to insert an underscore (\\_) for every unknown character and the known letters \
        for any letters you know of already. The word "apple" would be `_____` for example.

        Wrong letters is any guessed letter that was wrong. If there are none, enter 0.

        As for the language, this command works for both English and German words. If no language is specified, English is used by default. \
        It has some problems with long German words that are just stringed together, because those words are usually not \
        in the dictionary.
        """
        if inputted_word is not None and unused_letters is not None and not self.sending:
            async with ctx.typing():
                self.sending = True
                inputted_word = inputted_word.lower()
                if language.startswith('g'):
                    language = "german"
                else:
                    language = "english"

                unused_letters = self.clean_string(unused_letters)
                inputted_word = self.clean_string(inputted_word)
                if len(inputted_word) == 0:
                    self.sending = False
                    await ctx.send("Invalid input word")
                    return

                # Sets up the variables
                result = hangman.solve(inputted_word, list(unused_letters), language)
                alphabet = result[0]
                fitting_words = result[1]
                total = sum(alphabet.values())

                text = ''
                # Creates the word list with
                for key in sorted(alphabet, key=alphabet.get, reverse=True):
                    if alphabet[key] == 0:
                        continue
                    else:
                        text += f'{key} : {round(alphabet[key] / total * 100, 2)}% | '

                # Only print all the words if there're less than 20 words
                message = ""
                if len(fitting_words) == 0:
                    message += 'No matching words.\n'
                elif len(fitting_words) <= 20:
                    message += f"\nWords:\n{' | '.join(fitting_words)}\n"
                message += f'--- {len(fitting_words)} words ---\n\n'
                message += text
                self.sending = False
            await ctx.send(message)
        elif self.sending:
            await ctx.send("❗❗ Already working on a hangman. Hold on ❗❗", delete_after=7)
            raise discord.ext.commands.errors.BadArgument
        else:
            await ctx.send("No input given. Check `$help hangman` to see how this command is used.")
            raise discord.ext.commands.errors.BadArgument


def setup(bot):
    bot.add_cog(Hangman(bot))
