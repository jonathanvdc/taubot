#!/usr/bin/env python3

import praw
import json
import time
from accounting import InMemoryServer
from commands import COMMANDS, list_commands_as_markdown

def read_config():
    """Reads the configuration file."""
    with open('bot-config.json') as f:
        return json.load(f)

def create_reddit(config):
    """Creates a Reddit handle."""
    return praw.Reddit(
        client_id=config['reddit_client_id'],
        client_secret=config['reddit_client_secret'],
        user_agent='PyEng Bot 0.1',
        username=config['reddit_username'],
        password=config['reddit_password'])

def reply(message, body):
    """Replies to a private message."""
    title = message.subject
    if not title.lower().startswith('re:'):
        title = 're: %s' % message.subject
    message.mark_read()
    return message.author.message(title, body)

def process_message(message, server):
    """Processes a message sent to the bot."""
    split_msg = message.body.split()
    if len(split_msg) == 0:
        reply(
            message,
            'Hi %s! You sent me an empty message. Here\'s a list of commands I do understand:\n\n%s' %
            (message.author.name, list_commands_as_markdown()))
    elif split_msg[0] in COMMANDS:
        reply(message, COMMANDS[split_msg[0]][2](message, server))
    else:
        reply(
            message,
            'Hi %s! I didn\'t quite understand command your command `%s`. Here\'s a list of commands I do understand:\n\n%s' %
            (message.author.name, split_msg[0], list_commands_as_markdown()))

def process_all_messages(reddit, server):
    """Processes all unread messages received by the bot."""
    for message in reddit.inbox.unread(limit=None):
        process_message(message, server)

if __name__ == '__main__':
    reddit = create_reddit(read_config())
    server = InMemoryServer()
    while True:
        # Process messages.
        process_all_messages(reddit, server)
        # Sleep for five seconds.
        time.sleep(5)
