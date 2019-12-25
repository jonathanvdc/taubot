# taubot

This is a WIP Reddit economy bot implementation in Python.

## Usage

The bot will need credentials to log into Reddit. Summarize them in a JSON file named `bot-config.json` placed in the directory from which you run the bot. A `bot-config.json` looks like this:

```json
{
  "reddit_username": "USERNAME",
  "reddit_password": "PASSWORD"
}
```

To make the bot respond to all unread messages, simply run `python3 src/bot.py`.
