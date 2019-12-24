#!/usr/bin/env python3

import praw
import json

def read_config():
    """Reads the configuration file."""
    with open('bot-config.txt') as f:
        return json.load(f)

def create_reddit(config):
    """Creates a Reddit handle."""
    return praw.Reddit(
        client_id='ppe35WDZIGxLDQ',
        client_secret='Rh5Ka0ZU119q3CdKDPz9r_YL1vU',
        user_agent='PyEng Bot 0.1',
        username=config['reddit_username'],
        password=config['reddit_password'])

def list_commands():
    """Creates a list of all commands accepted by this bot."""
    return ['help -- prints this help message.']

def list_commands_as_markdown():
    """Creates a list of all commands accepted by this bot and formats it as Markdown."""
    return '\n'.join('  * %s' % item for item in list_commands())

def get_help_message(username):
    """Gets the help message for the economy bot."""
    return '''
Hi %s! Here's a list of the commands I understand:

  %s''' % (username, list_commands_as_markdown())

def reply(message, body):
    """Replies to a private message."""
    title = message.subject
    if not title.lower().startswith('re:'):
        title = 're: %s' % message.subject
    message.mark_read()
    return message.author.message(title, body)

def process_message(message):
    """Processes a message sent to the bot."""
    if message.body == 'help':
        reply(message, get_help_message(message.author.name))
    else:
        reply(
            message,
            'Hi %s! I didn\'t quite understand that command (i.e., the first word in your message). Here\'s a list of the commands I do understand:\n\n%s' %
            (message.author.name, list_commands_as_markdown()))

def process_all_messages(reddit):
    """Processes all unread messages received by the bot."""
    for message in reddit.inbox.unread(limit=None):
        process_message(message)

if __name__ == '__main__':
    reddit = create_reddit(read_config())
    process_all_messages(reddit)
    print("Achieved inbox zero!")
