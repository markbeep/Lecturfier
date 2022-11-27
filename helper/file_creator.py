import os
from sqlite3 import connect
from helper.log import log
from helper.sql.SQLTables import create_tables, check_columns

def createFiles():
    """
    Creates the necessary files for the bot to work
    :return: None
    """
    file_list = ["ignored_users", "bot_prefix", "versions"]
    stop = False
            
    print("Making sure all DB tables exist")
    create_tables()
    check_columns()
    print("----- DB Check Complete -----")

    for file in file_list:
        if not os.path.exists(f"./data/{file}.json"):
            log(f"Creating {file}.json", True)
            stop = True
            with open(f"./data/{file}.json", "w") as f:
                f.write("{}")

    if stop:
        log("All files created.", True)
