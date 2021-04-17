import discord
from discord.ext import commands
from helper import hangman
import string
from discord.ext.commands.cooldowns import BucketType


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

    @commands.cooldown(1, 5, BucketType.user)
    @commands.command(aliases=["hm"], usage="hangman <word up till now> <wrong letters or 0> <language>")
    async def hangman(self, ctx, inputted_word=None, unused_letters="", language="e"):
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
                        text += f'{key} : {round(alphabet[key]/total * 100, 2)}% | '

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
