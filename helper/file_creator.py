import os
import json
from helper.log import log

def createFiles():
    keyword = "FILE"
    """
    Creates the necessary files for the bot to work
    :return: None
    """
    stop = False
    if not os.path.exists("./data/quotes.json"):
        log("Creating quotes.json", keyword)
        stop = True
        with open("./data/quotes.json", "w") as f:
            f.write("{}")

    if not os.path.exists("./data/reputation.json"):
        log("Creating reputation.json", keyword)
        stop = True
        with open("./data/reputation.json", "w") as f:
            f.write("{}")

    if not os.path.exists("./data/statistics.json"):
        log("Creating statistics.json", keyword)
        stop = True
        with open("./data/statistics.json", "w") as f:
            f.write("{}")
    
    if not os.path.exists("./data/ignored_users.json"):
        log("Creating ignored_users", keyword)
        stop = True
        with open("./data/ignored_users.json", "w") as f:
            f.write("[]")

    if not os.path.exists("./data/ignored_channels.json"):
        log("Creating ignored_channels.json", keyword)
        stop = True
        with open("./data/blocked_channels.json", "w") as f:
            f.write("[]")

    if not os.path.exists("./data/schedule.json"):
        log("Creating schedule.json", keyword)
        stop = True
        with open("./data/schedule_default.json", "r") as f:
            schedule = json.load(f)
        with open("./data/schedule.json", "w") as f:
            json.dump(schedule, f, indent=2)

    if not os.path.exists("./websites/ad.html"):
        log("Creating ad.html", keyword)
        stop = True
        with open("./websites/ad.html", "w"):
            pass

    if not os.path.exists("./websites/dm.html"):
        log("Creating dm.html", keyword)
        stop = True
        with open("./websites/dm.html", "w"):
            pass

    if not os.path.exists("./websites/ep.html"):
        log("Creating ep.html", keyword)
        stop = True
        with open("./websites/ep.html", "w"):
            pass

    if not os.path.exists("./websites/la.html"):
        log("Creating la.html", keyword)
        stop = True
        with open("./websites/la.html", "w"):
            pass

    if stop:
        log("All files created. Restart the bot.")
        exit()