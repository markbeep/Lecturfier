import os
from datetime import datetime
from pytz import timezone


def log(text, keyword=None):
    """
    Logs a specific entry to a file.
    :param text: The text to log into a file
    :param keyword: An optional parameter which will get displayed in the console
    :return: None
    """
    date = datetime.now(timezone("Europe/Zurich")).strftime("%Y-%m-%d")
    time = datetime.now(timezone("Europe/Zurich")).strftime("%H:%M:%S")
    if not os.path.exists(f"logs/{date}.log"):
        print(f"logs/{date}.log")
        with open(f"logs/{date}.log", "w") as f:
            f.write(f"[{time}] -- {text}")
    else:
        with open(f"logs/{date}.log", "r") as f:
            existing_log = f.read()
        with open(f"logs/{date}.log", "w") as f:
            f.write(f"{existing_log}\n[{time}] -- {text}")
    if keyword is not None:
        print(f"Logged ({keyword})")