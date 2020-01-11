# taubot

This is a Reddit/Discord economy bot implementation in Python.

## Dependencies

Taubot's dependencies are defined in the `requirements.txt` file. Install them with

```bash
pip3 install -r requirements.txt
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
