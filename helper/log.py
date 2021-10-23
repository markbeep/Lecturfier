import logging

logger = logging.getLogger("discord")
logger.setLevel(logging.WARNING)
handler = logging.FileHandler(filename="./logs/discord.log", encoding="utf-8", mode="w")
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)


def log(text, print_it=True, warning=False) -> None:
    """
    Logs a specific entry to a file.
    :param warning:
    :param text: The text to log into a file
    :param print_it: An optional parameter which helps with sorting the log
    :return: None
    """
    if print_it:
        print(text)
    level = logging.INFO
    if warning:
        level = logging.WARNING
    logger.log(msg=text, level=level)
