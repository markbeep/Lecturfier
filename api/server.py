from flask import Flask, jsonify
import sqlite3


app = Flask(__name__)

conn = sqlite3.connect("./data/discord.db")

@app.route("/api/random-quote")
def random_quote():
    res = conn.execute("SELECT QuoteID, Quote, Name, CreatedAt, Elo FROM Quotes WHERE DiscordGuildID=747752542741725244 ORDER BY RANDOM() LIMIT 1").fetchone()
    return jsonify({
        "id": res[0],
        "quote": res[1],
        "name": res[2],
        "createdAt": res[3],
        "elo": res[4],
    })
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
