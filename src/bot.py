#!/usr/bin/env python3

import praw
import json
import time
from accounting import LedgerServer, Authorization
from commands import COMMANDS, list_commands_as_markdown, CommandException, assert_authorized, process_command

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
    return message.author.message(title, '%s\n\n%s' % ('\n'.join('> %s' % line for line in message.body.split('\n')), body))

def process_message(message, server):
    """Processes a message sent to the bot."""
    reply(message, process_command(message.author.name, message.body, server))

def process_all_messages(reddit, server):
    """Processes all unread messages received by the bot."""
    # Process private messages.
    for message in reddit.inbox.unread(limit=None):
        process_message(message, server)

    # TODO: process comments where the bot is mentioned.

if __name__ == '__main__':
    reddit = create_reddit(read_config())
    # Let's make a tick five minutes for now (should be way longer later).
    tick_duration = 5 * 60
    with LedgerServer('ledger.txt') as server:
        while True:
            # Process messages.
            process_all_messages(reddit, server)

            # Notify the server that one or more ticks have elapsed if necessary.
            time_diff = int(time.time() - server.last_tick_timestamp)
            if time_diff > tick_duration:
                for i in range(time_diff // tick_duration):
                    server.notify_tick_elapsed()

            # Sleep for five seconds.
            time.sleep(5)
