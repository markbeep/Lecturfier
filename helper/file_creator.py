import json
import os

from helper.log import log
from helper.sql.SQLTables import *


def createFiles():
    """
    Creates the necessary files for the bot to work
    :return: None
    """
    keyword = "FILE"
    file_list = ["ignored_users", "bot_prefix", "versions"]
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
        print("Making sure all DB tables exist")
        create_tables()
        check_columns()
        print("----- DB Check Complete -----")

    if not os.path.exists("./config/settings.json"):
        log("Creating settings.json", keyword)
        stop = True
        with open("./config/settings.json", "w") as f:
            json.dump(settings_default, f, indent=2)

    for file in file_list:
        if not os.path.exists(f"./data/{file}.json"):
            log(f"Creating {file}.json", keyword)
            stop = True
            with open(f"./data/{file}.json", "w") as f:
                f.write("{}")

    if stop:
        log("All files created. Restart the bot.", keyword)
        exit()
