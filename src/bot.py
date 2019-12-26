#!/usr/bin/env python3

import praw
import json
import time
from accounting import LedgerServer, Authorization
from commands import COMMANDS, list_commands_as_markdown, CommandException, assert_authorized

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
    split_msg = message.body.split()
    author = message.author.name
    if len(split_msg) == 0:
        reply(
            message,
            'Hi %s! You sent me an empty message. Here\'s a list of commands I do understand:\n\n%s' %
            (author, list_commands_as_markdown(author, server)))
    elif split_msg[0] in COMMANDS:
        try:
            cmd = COMMANDS[split_msg[0]]
            if len(cmd) >= 4 and cmd[3].value > Authorization.CITIZEN.value:
                assert_authorized(author, server, cmd[3])

            reply(message, cmd[2](author, message.body, server))
        except CommandException as e:
            reply(message, str(e))
    else:
        reply(
            message,
            'Hi %s! I didn\'t quite understand command your command `%s`. Here\'s a list of commands I do understand:\n\n%s' %
            (author, split_msg[0], list_commands_as_markdown(author, server)))

def process_all_messages(reddit, server):
    """Processes all unread messages received by the bot."""
    # Process private messages.
    for message in reddit.inbox.unread(limit=None):
        process_message(message, server)

    # TODO: process comments where the bot is mentioned.

if __name__ == '__main__':
    reddit = create_reddit(read_config())
    # Let's make a tick five seconds for now (should be way longer later).
    tick_duration = 5
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
