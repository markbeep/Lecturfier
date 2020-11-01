import os
import json

def createFiles():
    """
    Creates the necessary files for the bot to work
    :return: None
    """
    stop = False
    if not os.path.exists("Data/quotes.json"):
        print("Creating quotes.json")
        stop = True
        with open("Data/quotes.json", "w") as f:
            f.write("{}")

    if not os.path.exists("Data/reputation.json"):
        print("Creating reputation.json")
        stop = True
        with open("Data/reputation.json", "w") as f:
            f.write("{}")

    if not os.path.exists("Data/statistics.json"):
        print("Creating statistics.json")
        stop = True
        with open("Data/statistics.json", "w") as f:
            f.write("{}")

    if not os.path.exists("Data/schedule.json"):
        print("Creating schedule.json")
        stop = True
        with open("Data/schedule_default.json", "r") as f:
            schedule = json.load(f)
        with open("Data/schedule.json", "w") as f:
            json.dump(schedule, f, indent=2)

    if stop:
        print("All files created. Restart the bot.")
        exit()