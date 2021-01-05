# Taubot

This is a Reddit/Discord economy bot implementation in Python.

## Installation 

Taubot has a simple install script that will set up the database and install dependencies

```bash
./bin/install.sh
```

## Usage

The bot will need credentials to log into Reddit. Summarize them in a JSON file named `bot-config.json` placed in the directory from which you run the bot. A `bot-config.json` looks like this:

```json
{
  "reddit_client_id": "CLIENT_ID",
  "reddit_client_secret": "CLIENT_SECRET",
  "reddit_username": "USERNAME",
  "reddit_password": "PASSWORD",
  "discord_token": "BOT TOKEN",
  "server_key": "PEM PRIVATE RSA KEY",
  "prefix": ["Prefix 1", "Prefix 2", "etc"],
  "colour": "Hex code for embed colour",
  "server_configuration": {
    "url": "An optional SQL database url that will override the other parameters",
    "dialect": "the dialect to use defaults to postgresql",
    "uname": "the username to connect with",
    "psswd": "the password to connect with",
    "db": "the database to connect to",
  }
}
```
Please note that if any of the arguments are missing the bot will print a warning and gracefully degrade into not using the
associated feature

To make the bot respond to all unread messages, simply run `python3 src/bot.py`.
