import os
import json
from helper.log import log
from helper import handySQL
from helper.sql.SQLTables import *


def createFiles():
    """
    Creates the necessary files for the bot to work
    :return: None
    """
    keyword = "FILE"
    file_list = ["ignored_users", "ignored_channels", "bot_prefix", "versions"]
    website_list = ["ad", "dm", "ep", "la"]
    stop = False

    settings_default = {
        "upload to git": False,
        "channel_to_post": "test",
        "test_livestream_message": True,
        "send_message_to_finn": False,
        "lecture": 111111111111111111111,
        "test": 111111111111111111111,
        "prefix": "$"
    }

    # This is the file that stores the token
    if not os.path.exists("../LECTURFIER.json"):
        log("Creating LECTURFIER.json", keyword)
        stop = True
        with open("../LECTURFIER.json", "w") as f:
            f.write('{"token":""}')

    if os.path.exists("./data/discord.db"):
        print("Creating DB tables")
        handySQL.create_all_tables("./data/discord.db")
        print("Created DB tables successfully")

    if not os.path.exists("./data/test.db"):
        print("Creating rewrite DB table")
        create_tables()
        print("Created rewrite DB tables successfully")

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

    for link in website_list:
        if not os.path.exists(f"./websites/{link}.html"):
            log(f"Creating {link}.html", keyword)
            stop = True
            with open(f"./websites/{link}.html", "w") as f:
                pass

    if not os.path.exists(f"./data/covid19.txt"):
        log(f"Creating covid19.txt", keyword)
        stop = True
        with open(f"./data/covid19.txt", "w") as f:
            f.write("0")

    if stop:
        log("All files created. Restart the bot.", keyword)
        exit()
