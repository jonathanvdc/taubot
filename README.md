# taubot

This is a WIP Reddit economy bot implementation in Python.

## Dependencies

Taubot requires the `praw` and `pycryptodome` pip packages. Install with

```bash
pip3 install praw
pip3 install pycryptodome
```

## Usage

The bot will need credentials to log into Reddit. Summarize them in a JSON file named `bot-config.json` placed in the directory from which you run the bot. A `bot-config.json` looks like this:

```json
{
  "reddit_client_id": "CLIENT_ID",
  "reddit_client_secret": "CLIENT_SECRET",
  "reddit_username": "USERNAME",
  "reddit_password": "PASSWORD"
}
```

To make the bot respond to all unread messages, simply run `python3 src/bot.py`.
