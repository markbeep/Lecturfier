from flask import Flask, jsonify
import sqlite3
import re

app = Flask(__name__)


def remove_emote_ids(phrase: str) -> str:
    """Removes emote ids from quotes.
    <:pog:753549087172853764> is turned into :pog: for example
    """
    r = re.compile(r"<:(\d|\w+):\d+>")
    while match := r.search(phrase):
        emote_name = r.findall(phrase)[0]
        phrase = phrase[:match.start()] + f":{emote_name}:" + phrase[match.end():]
    return phrase


@app.route("/api/random-quote")
def random_quote():
    conn = sqlite3.connect("./data/discord.db")
    res = conn.execute("SELECT QuoteID, Quote, Name, CreatedAt, Elo FROM Quotes WHERE DiscordGuildID=747752542741725244 ORDER BY RANDOM() LIMIT 1").fetchone()
    return jsonify({
        "id": res[0],
        "quote": remove_emote_ids(res[1]),
        "name": res[2],
        "createdAt": res[3],
        "elo": res[4],
    })
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
