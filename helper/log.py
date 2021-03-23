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

    # In rare cases some characters can cause an UnicodeEncodeError
    try:
        with open(f"logs/{date}.log", "a") as f:
            f.write(f"[{time}] -- {text}\n")
    except UnicodeEncodeError:
        with open(f"logs/{date}.log", "a") as f:
            text = text.encode('UTF-8')
            print("!!!-----UnicodeEncodeError while logging-----!!!")
            f.write(f"\n\n#############UnicodeEncodeError#############\n\n[{time}] -- {text}\n")
    print(f"Logged: {text}")
