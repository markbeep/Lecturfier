"""
Hangman Solver

v.1.0:  The basic and naive approach at finding matching words in the list of words.
        Average time per searched word:
            English: 0.0805s
            German: 0.4664s
        Word list sizes (words):
            English: 370'102
            German: 1908815

v.1.1:  Tried to clean up the words to remove any duplicates, words with punctuations and
        words that contain letters I don't account for. There were barely any words
        to remove though.
        Word list sizes (words):
            English: 370'000
            German: 1'908'814

v.2.0:  Splitting the word list into files depending on the length of the word.
        This way we reduce the file sizes by immense amounts.
        Average time per searched word:
            English: 0.0301s
            German: 0.2128s
        Max word list sizes (words):
            English: 53'403 (length 9 words)
            German: 190'217 (length 13 words)

v.3.0:  Hoping to make the word search faster by splitting the word list into multiple chunks.
        Python Multithreading: (Multiprocessing was a lot slower, because of the giant overhead)
        Average time per searched word:
            English: 0.0309s (with 16 threads)
            German: 0.1564s (with 8 threads)

v.3.1:  Tried the search using the Python multiprocessing library. The overhead
        turned out to be a too big of a problem, which is why multiprocessing won't
        be the way to go. For each separate process it took about an extra 0.1s.

v.3.2:  Cleaned up code and removed multithreading/multiprocessing completely, as it only
        made code slower.


v.4.0:  Numba implementation. Because it keeps having to compile, it made the code a
        lot slower.

v.5.0:  Turns out doing it sequential and without libraries turned out the best. So back to the original!
        Cleaned up the code and made some changes to make it faster.
        Average time per searched word:
            English: 0.0306s
            German: 0.14996s

German word list: https://gist.github.com/MarvinJWendt/2f4f4154b8ae218600eb091a5706b5f4
English word list: https://github.com/dwyl/english-words

"""

import os


def solve(wtg: str, ignore=None, language="english"):
    """Returns a type dict with all letters and the amount of words
    that contain that letter and a type list with the list of fitting
    words.

    Args:
        wtg (str): Word to guess
        ignore (list, optional): Letters to ignore. Defaults to [].
        language (str, optional): The language to find matches in. Defaults to "english".

    Returns:
        tuple: (letter_count:dict, fitting:list)
    """

    if ignore is None:
        ignore = []
    word_list_path = get_filename(wtg, language)

    if word_list_path is None:
        return {}, []

    # get the word list
    with open(word_list_path, "r", encoding='utf-8') as f:
        cont = f.read()
    words = cont.split("\n")

    letter_count = {'a': 0, 'b': 0, 'c': 0, 'd': 0, 'e': 0, 'f': 0, 'g': 0, 'h': 0, 'i': 0, 'j': 0, 'k': 0, 'l': 0,
                    'm': 0, 'n': 0, 'o': 0, 'p': 0, 'q': 0, 'r': 0, 's': 0, 't': 0, 'u': 0, 'v': 0, 'w': 0, 'x': 0,
                    'y': 0, 'z': 0, 'ä': 0, 'ö': 0, 'ü': 0}
    fitting = []

    get_fitting(words, wtg, fitting, ignore)
    count_chars(fitting, wtg, letter_count, ignore)

    return letter_count, fitting


def count_chars(words, wtg, letter_count, ignore):
    """
    Count the amount of words each letter is in.
    
    Note: we don't want to count all letters in each word,
          only the amount of words a letter is in.
    """

    for w in words:
        if len(w) == len(wtg):  # only consider words of the same length
            for c in w:
                c = c.lower()
                if c not in ignore and c not in wtg:
                    try:
                        letter_count[c] += 1
                    except KeyError:
                        pass


def get_fitting(words, wtg, fitting_words, ignore):
    for w in words:
        if len(w) == len(wtg):  # only consider words of the same length
            for i, c in enumerate(w):
                if (wtg[i] != "_" and c != wtg[i]) or c in ignore:
                    break
            else:
                fitting_words.append(w)


def get_filename(wtg: str, language: str):
    """We use this to easily return the name of the
    word list file. This can then easily be changed
    later on.

    Args:
        wtg (str): The word we're looking for
        language (str): The language we're looking for

    Returns:
        str: The filename of the word list
    """
    if language == "english":
        fp = f"./data/english/{len(wtg)}.txt"
        if os.path.isfile(fp):
            return f"./data/english/{len(wtg)}.txt"
    if language == "german":
        fp = f"./data/german/{len(wtg)}.txt"
        if os.path.isfile(fp):
            return f"./data/german/{len(wtg)}.txt"
    return None


def max_length(language: str):
    """Returns the maximum length word

    Args:
        language (str): [description]

    Returns:
        int: [description]
    """
    mx = 0
    for f in os.listdir(language):
        mx = max(mx, int(f.replace(".txt", "")))
    return mx


def main():
    wtg = "______"  # word to guess
    ignore = []  # unused letters
    result = solve(wtg, ignore, "english")
    print(result[0])


if __name__ == "__main__":
    main()
