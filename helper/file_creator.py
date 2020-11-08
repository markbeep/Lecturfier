import os
import json
from helper.log import log

def createFiles():
    """
    Creates the necessary files for the bot to work
    :return: None
    """
    keyword = "FILE"
    file_list = ["quotes", "reputation", "statistics", "ignored_users", "ignored_channels", "levels", "covid_guesses"]
    website_list = ["ad", "dm", "ep", "la"]
    stop = False

    settings_default = {
        "upload to git": False,
        "channel_to_post": "test",
        "test_livestream_message": True,
        "send_message_to_finn": False,
        "lecture": 111111111111111111111,
        "test": 111111111111111111111
    }

    schedule_default = {
        "eprog": {
            "Mon:04:20": "FILLER",
            "Tue:04:20": "FILLER",
            "url": "FILLER"
        },
        "diskmat": {
            "Wed:04:20": "FILLER",
            "Thu:04:20": "FILLER",
            "url": "FILLER"
        },
        "linalg": {
            "Fri:04:20": "FILLER",
            "Sat:04:20": "FILLER",
            "url": "FILLER"
        },
        "and": {
            "Sun:04:20": "FILLER",
            "url": "FILLER"
        },
        "test": {
            "test": "TEST MESSAGE",
            "url": "This is the url to the website"
        }
    }

    # This is the file that stores the token
    if not os.path.exists("../LECTURFIER.json"):
        log("Creating LECTURFIER.json", keyword)
        stop = True
        with open("../LECTURFIER.json", "w") as f:
            f.write('{"token":""}')

    if not os.path.exists("./data/settings.json"):
        log("Creating settings.json", keyword)
        stop = True
        with open("./data/settings.json", "w") as f:
            json.dump(settings_default, f, indent=2)

    for file in file_list:
        if not os.path.exists(f"./data/{file}.json"):
            log(f"Creating {file}.json", keyword)
            stop = True
            with open(f"./data/{file}.json", "w") as f:
                f.write("{}")

    if not os.path.exists("./data/schedule.json"):
        log("Creating schedule.json", keyword)
        stop = True
        with open("./data/schedule.json", "w") as f:
            json.dump(schedule_default, f, indent=2)

    for link in website_list:
        if not os.path.exists(f"./websites/{link}.html"):
            log(f"Creating {link}.html", keyword)
            stop = True
            with open(f"./websites/{link}.html", "w") as f:
                pass

    if stop:
        log("All files created. Restart the bot.", keyword)
        exit()