import random
import string

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

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
    async def hangman(self, ctx: commands.Context):
        """
        Using this command as a standalone initializes a hangman guessing game. \
        You can guess letters by using the dropdown menu.
        The game ends after **100** seconds.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(view=HangmanGuesserView(ctx.author, ctx.message))

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
                # Creates most frequent character list
                for key in sorted(alphabet.keys(), key=lambda x: alphabet[x], reverse=True):
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
            raise commands.errors.BadArgument()
        else:
            await ctx.send("No input given. Check `$help hangman` to see how this command is used.")
            raise commands.errors.BadArgument()

class LetterSelect(discord.ui.Select):
    def __init__(self, ignored: list[str], current_word: list[str], edit_callback):
        # defines the options
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
                select_options.append(
                    discord.SelectOption(
                        label=letter, 
                        description=f"Guesses the letter {letter}", 
                        value=letter, 
                        emoji=emoji_letters[ord(letter)-97]
                    )
                )
            else:
                select_options.append(
                    discord.SelectOption(
                        label=letter, 
                        description=f"Guesses the letter {letter}", 
                        value=letter, 
                    )
                )
            count += 1
            
        super().__init__(placeholder="Make an initial guess for a letter", min_values=1, max_values=1, options=select_options)
        self.edit_callback = edit_callback

    async def callback(self, interaction: discord.Interaction):
        await self.edit_callback(interaction, self.values[0])

# TODO finish implementing hangman down here
class HangmanGuesserView(discord.ui.View):
    def __init__(self, user: discord.Member | discord.User, message: discord.Message):
        super().__init__()
        self.word_length = random.randint(5, 15)
        self.previous = []
        self.ignored = []
        self.current_word = ["_"] * self.word_length
        self.guesses = 0
        self.user = user
        self.message = message
        self.sent_message: discord.Message | None = None
        
        self.add_item(LetterSelect(self.ignored, self.current_word, self.callback))
    
    async def callback(self, interaction: discord.Interaction, guess: str):
        """
        Updates the message view upon receiving an input
        """
        self.sent_message = interaction.message
        
        if self.user != interaction.user:
            await interaction.response.send_message("You are not the initiater of this game.", ephemeral=True)
            return

        self.ignored.append(guess)
        letter_count, fitting = hangman.solve("".join(self.current_word), ignore=self.ignored)
        
        # now we try to figure out if the new guess resulted in 0 matches
        if len(fitting) == 0: # no words with these ignored letters
            if self.guesses == 0: # first guess. No words of this length with this letter
                self.word_length -= 1
                if self.word_length <= 0:
                    await interaction.response.send_message("Can't find any words right now. Quitting.", ephemeral=True)
                    self.stop()
                    return
                self.current_word = ["_"] * self.word_length # regenerate empty word
            
            else: # randomly pick one of the previous words and fill in the letters there
                assert len(self.previous) > 0
                random_word = random.choice(self.previous)
                if guess in random_word:
                    # update current_word to include the new guess at the correct spots
                    for i, c in enumerate(random_word):
                        if guess == c:
                            self.current_word[i] = guess
                    # remove the guessed letter from the ignored list again
                    self.ignored.pop(self.ignored.index(guess))
        else:
            self.previous = fitting.copy()
        self.guesses += 1
        self.clear_items()
        
        # check if game is over
        if self.current_word.count("_") == 0:
            await self.message.channel.send(f"{self.user.mention}! You guessed the word!\n`{''.join(self.current_word)}`")
            embed = discord.Embed(
                title="Hangman Game",
                description=f"Correct Word: `{''.join(self.current_word)}`\n"
                            f"Wrong Letters: {', '.join(self.ignored)}\n"
                            f"Amount of guesses: {self.guesses}"
            )
            embed.set_author(name=str(self.user), icon_url=self.user.avatar.url if self.user.avatar else None)
            await interaction.response.edit_message(embed=embed, view=None)
            
        else: # add select options back
            self.add_item(LetterSelect(self.ignored, self.current_word, self.callback))
            embed = discord.Embed(
                title="Hangman Game",
                description=f"Current Word: `{''.join(self.current_word)}`\n"
                            f"Wrong Letters: {', '.join(self.ignored)}\n"
                            f"Amount of guesses: {self.guesses}\n"
                            f"**Guess a letter:**"
            )
            embed.set_author(name=str(self.user), icon_url=self.user.avatar.url if self.user.avatar else None)
            await interaction.response.edit_message(embed=embed, view=self)
        
        
    async def on_timeout(self):
        if self.guesses == 0 or not self.sent_message: # we won't have any fitting words
            return
        
        random_word = random.choice(self.previous)
        await self.message.channel.send(f"{self.user.mention}! You guessed the word!\n`{random_word}`")
        embed = discord.Embed(
            title="Hangman Game",
            description=f"Correct Word: `{random_word}`\n"
                        f"Wrong Letters: {', '.join(self.ignored)}\n"
                        f"Amount of guesses: {self.guesses}"
        )
        embed.set_author(name=str(self.user), icon_url=self.user.avatar.url if self.user.avatar else None)
        await self.sent_message.edit(embed=embed, view=None)

async def setup(bot):
    await bot.add_cog(Hangman(bot))
