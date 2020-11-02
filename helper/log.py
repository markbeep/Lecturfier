import os
from datetime import datetime
from pytz import timezone


def log(text, keyword=None):
    """
    Logs a specific entry to a file.
    :param text: The text to log into a file
    :param keyword: An optional parameter which helps with sorting the log
    :return: None
    """
    if keyword is not None:
        text = f"{keyword} | {text}"
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
    print(f"Logged: {text}")
