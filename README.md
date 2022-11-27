**Note:** The Lecturfier bot has been fitted for a specific Discord server, so a lot of things might not work when run on your system.

# Lecturfier

Lecturfier is a Discord Bot that helps out in tons of ways for the ETH D-INFK 2020 Discord Server.

- Pings users on website updates/ lecture starts
- Tracks stats
- Stores quotes
- Manages user events
- and much much more

## Progress View

[Click Here](https://github.com/markbeep/Lecturfier/projects/1)

## List of noteworthy functions (not up to date)

- Quote (Quote users and get their quotes anytime you want)
- Event (Plan and organize events)
- Help (Fully fleshed out help page with a lot of information on how to use commands)
- Voice XP (Get xp points for being active in voice channels and for chatting)
- Lecture starts (Get pings when lectures start)
- Statistics (Get all kinds of Discord statistics)
- Minesweeper (Play minesweeper, just like the original one)
- Hangman solver (Finds the best fitting letter for hangman)

##

<img src="https://i.imgur.com/RiUvcML.jpg" width="460"/>

## Running Lecturfier

Lecturfier is setup to run using Docker so it can easily be deployed on a Kubernetes cluster. Because of that the latest Docker image is always available at https://hub.docker.com/repository/docker/markbeep/lecturfier and can be pulled via `docker pull markbeep/lecturfier:latest` or `docker pull markbeep/lecturfier:staging`.

To run it simply run `docker compose up --build`

---

## Rework

- [x] admin.py
- [x] draw.py
- [x] hangman.py
- [x] help.py
- [x] information.py
- [x] aoc.py
- [x] mainbot.py
- [x] minesweeper.py
- [x] owner.py
- [x] quote.py
- [x] reputation.py
- [x] statistics.py
- [x] updates.py
- [x] voice.py

## Tested

- [ ] admin.py
- [ ] draw.py
- [x] hangman.py
- [x] help.py
- [ ] aoc.py
- [ ] information.py
- [ ] mainbot.py
- [ ] minesweeper.py
- [ ] owner.py
- [ ] quote.py
- [ ] reputation.py
- [ ] statistics.py
- [ ] updates.py
- [ ] voice.py
