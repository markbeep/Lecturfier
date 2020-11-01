import discord
from discord.ext import commands
import random
import time
import re

class Hangman(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def open_file(self, file_name):
        with open(file_name, "r") as f:
            word_file = f.read()
            word_file = re.sub(r'\([^)]*\)', '', word_file)
            word_file = re.findall(r"[\w']+", word_file)
        return word_file

    async def word_guesser(self, word_file, inputted_word, unused_letters=[]):
        possible_words = []

        word_length = len(inputted_word)

        # Puts all words with the certain length in a list
        for word in word_file:
            if len(word) == word_length:
                possible_words.append(word)

        letters = list(inputted_word)

        fitting_words = []

        # For every word, if one of the not-allowed letters is in the word, go to the next word
        for word_index, word in enumerate(possible_words):
            word = word.lower()
            check_letters = True
            for letter in unused_letters:
                if letter in word:
                    check_letters = False
                    continue

            # All the possible words, check if each letter lines up. If the last letter is reached and it fits, append
            if check_letters:
                for index, i in enumerate(letters):
                    if i == '_':
                        if index == len(letters) - 1:
                            fitting_words.append(word)
                        else:
                            continue
                    elif i == word[index]:
                        if index == len(letters) - 1:
                            fitting_words.append(word)
                        else:
                            continue
                    else:
                        break

        alphabet = {'a': 0, 'b': 0, 'c': 0, 'd': 0, 'e': 0, 'f': 0, 'g': 0, 'h': 0, 'i': 0, 'j': 0, 'k': 0, 'l': 0,
                    'm': 0, 'n': 0, 'o': 0, 'p': 0, 'q': 0, 'r': 0, 's': 0, 't': 0, 'u': 0, 'v': 0, 'w': 0, 'x': 0,
                    'y': 0, 'z': 0, 'ä': 0, 'ö': 0, 'ü': 0, }
        total = 0
        fitting_words = list(set(fitting_words))

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

    @commands.command(aliases=["hm"])
    async def hangman(self, ctx, inputted_word=None, unused_letters=None, language="e"):
        if inputted_word is not None and unused_letters is not None:
            if language.startswith('g'):
                file_name = 'data/german.txt'
                print('Selected German.')
            else:
                file_name = 'data/english.txt'
                print('Selected English.')

            if unused_letters == 0:
                unused_letters = ""

            word_file = await self.open_file(file_name)

            # Sets up the variables
            things = await self.word_guesser(word_file, inputted_word, unused_letters)
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
                await ctx.send('No matching words.')
            elif len(fitting_words) <= 20:
                message += f"\nWords:\n{'|'.join(fitting_words)}\n"
            message += f'--- {len(fitting_words)} words ---\n\n'
            message += text
            await ctx.send(message)

def setup(bot):
    bot.add_cog(Hangman(bot))