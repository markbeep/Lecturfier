import os
import json

def createFiles():
    """
    Creates the necessary files for the bot to work
    :return: None
    """
    stop = False
    if not os.path.exists("data/quotes.json"):
        print("Creating quotes.json")
        stop = True
        with open("data/quotes.json", "w") as f:
            f.write("{}")

    if not os.path.exists("data/reputation.json"):
        print("Creating reputation.json")
        stop = True
        with open("data/reputation.json", "w") as f:
            f.write("{}")

    if not os.path.exists("data/statistics.json"):
        print("Creating statistics.json")
        stop = True
        with open("data/statistics.json", "w") as f:
            f.write("{}")

    if not os.path.exists("data/schedule.json"):
        print("Creating schedule.json")
        stop = True
        with open("data/schedule_default.json", "r") as f:
            schedule = json.load(f)
        with open("data/schedule.json", "w") as f:
            json.dump(schedule, f, indent=2)

    if not os.path.exists("websites/ad.html"):
        print("Creating ad.html")
        stop = True
        with open("websites/ad.html", "w"):
            pass

    if not os.path.exists("websites/dm.html"):
        print("Creating dm.html")
        stop = True
        with open("websites/dm.html", "w"):
            pass

    if not os.path.exists("websites/ep.html"):
        print("Creating ep.html")
        stop = True
        with open("websites/ep.html", "w"):
            pass

    if not os.path.exists("websites/la.html"):
        print("Creating la.html")
        stop = True
        with open("websites/la.html", "w"):
            pass

    if stop:
        print("All files created. Restart the bot.")
        exit()