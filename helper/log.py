import os
from datetime import datetime
from pytz import timezone

# TODO replace the log system with a proper logging library
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
        try:
            with open(f"logs/{date}.log", "r") as f:
                existing_log = f.read()
            with open(f"logs/{date}.log", "w") as f:
                f.write(f"{existing_log}\n[{time}] -- {text}")
        except UnicodeEncodeError:
            with open(f"logs/{date}.log", "w") as f:
                text = text.encode('UTF-8')
                print("!!!-----UnicodeEncodeError while logging-----!!!")
                f.write(f"{existing_log}\n\n#############UnicodeEncodeError#############\n\n[{time}] -- {text}")
    print(f"Logged: {text}")
