import asyncio

import discord
from discord.ext import commands
import re
from helper import handySQL
import string
from discord.ext.commands.cooldowns import BucketType
import threading
import time
import concurrent.futures


def joinTuple(string_tuples) -> str:
    return " ".join(string_tuples)


class Hangman(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sending = False
        self.db_path = "./data/discord.db"
        self.conn = handySQL.create_connection(self.db_path)

    def dict_query(self, not_like_msg, language, inputted_word):
        conn = handySQL.create_connection(self.db_path)
        c = conn.cursor()
        c.execute(f"SELECT Word FROM Dictionary WHERE WordLanguage=? AND Word LIKE ? {not_like_msg} GROUP BY Word COLLATE NOCASE",
                  (language, inputted_word))
        # As results is a list of tuples, join them
        return list(map(joinTuple, c.fetchall()))

    def get_connection(self):
        """
        Retreives the current database connection
        :return: Database Connection
        """
        if self.conn is None:
            self.conn = handySQL.create_connection(self.db_path)
        return self.conn

    def open_file(self, file_name):
        with open(file_name, "r") as f:
            word_file = f.read()
            word_file = re.sub(r'\([^)]*\)', '', word_file)
            word_file = re.findall(r"[\w']+", word_file)
        return word_file

    def clean_string(self, inp):
        inp = inp.lower()
        valid = string.ascii_lowercase + "_äöüàéè"
        corrected = ""
        for s in inp:
            if s in valid:
                corrected += s
        return corrected

    async def word_guesser(self, inputted_word, unused_letters="", language="english"):
        # Ununused letters
        not_like_msg = ""
        for l in unused_letters:
            not_like_msg += f' AND NOT Word LIKE "%{l}%"'

        # sql query takes up the most time, so its performed in a separate thread to prevent the whole bot from blocking
        event_loop = asyncio.get_event_loop()
        blocking_task = [event_loop.run_in_executor(concurrent.futures.ThreadPoolExecutor(max_workers=1), self.dict_query, not_like_msg, language, inputted_word)]
        completed, pending = await asyncio.wait(blocking_task)

        fitting_words = []
        for t in completed:
            fitting_words.extend(t.result())

        alphabet = {'a': 0, 'b': 0, 'c': 0, 'd': 0, 'e': 0, 'f': 0, 'g': 0, 'h': 0, 'i': 0, 'j': 0, 'k': 0, 'l': 0,
                    'm': 0, 'n': 0, 'o': 0, 'p': 0, 'q': 0, 'r': 0, 's': 0, 't': 0, 'u': 0, 'v': 0, 'w': 0, 'x': 0,
                    'y': 0, 'z': 0, 'ä': 0, 'ö': 0, 'ü': 0, }
        total = 0

        if len(fitting_words) == 0:
            return {'fitting_words': [], 'alphabet': alphabet, 'total': total}
        else:
            count_words = []

            # Removes all duplicate characters from every word and puts the words in a list to count
            for i, word in enumerate(fitting_words):
                count_words.append(str(set(word)))

            # Puts all strings into one long string to count it easier.
            all_string = ''.join(count_words)

            # Counts all the letters in the words (but only letters that haven't been mentioned yet)
            for key in alphabet.keys():
                if key in inputted_word:
                    continue
                else:
                    count = all_string.count(key)
                    if count > 0:
                        total += count
                        alphabet[key] = count
            return {'fitting_words': fitting_words, 'alphabet': alphabet, 'total': total}

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
                things = await self.word_guesser(inputted_word, unused_letters, language)
                alphabet = things['alphabet']
                fitting_words = things['fitting_words']
                total = things['total']

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
            msg = await ctx.send("❗❗ Already working on a hangman. Hold on ❗❗", delete_after=7)
            raise discord.ext.commands.errors.BadArgument
        else:
            await ctx.send("No input given. Check `$help hangman` to see how this command is used.")
            raise discord.ext.commands.errors.BadArgument

def setup(bot):
    bot.add_cog(Hangman(bot))