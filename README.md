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
  "load_private_options_from_env": false,
  "reddit_client_id": "CLIENT_ID",
  "reddit_client_secret": "CLIENT_SECRET",
  "reddit_username": "USERNAME",
  "reddit_password": "PASSWORD",
  "discord_token": "BOT TOKEN",
  "server_key": "PEM PRIVATE RSA KEY",
  "prefix": ["Prefix 1", "Prefix 2", "etc"],
  "colour": "Hex code for embed colour",
  "ledger-path": "/path/to/ledger"
}
```
The password portions of the credentials can instead be set as environmental variables and loaded by setting `load_private_options_from_env` to be `true`.

Please note that if any of the arguments are missing the bot will print a warning and gracefully degrade into not using the
associated feature.

To make the bot respond to all unread messages, simply run `python3 src/bot.py`.
