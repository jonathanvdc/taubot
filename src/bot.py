#!/usr/bin/env python3

import praw
import discord
import json
import time
import asyncio
from accounting import LedgerServer, Authorization, RedditAccountId, DiscordAccountId, AccountId
from commands import COMMANDS, list_commands_as_markdown, CommandException, assert_authorized, process_command

# move this to config?
prefix = "e!"

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
    return message.author.message(title, '%s\n\n%s\n\n%s' % ('\n'.join('> %s' % line for line in message.body.split('\n')), body, 'Provided by r/SimDemocracy'))

def process_message(message, server):
    """Processes a message sent to the bot."""
    reply(message, process_command(RedditAccountId(message.author.name), message.body, server))

def process_all_messages(reddit, server):
    """Processes all unread messages received by the bot."""
    # Process private messages.
    for message in reddit.inbox.unread(limit=None):
        process_message(message, server)

def is_comment_replied_to(reddit, comment):
    comment.refresh()
    for reply in comment.replies:
        if reply.author == reddit.user.me():
            return True
    return False

def process_comment(comment, server):
    """Processes a comment with the proper prefix."""
    author = RedditAccountId(comment.author.name)
    comment.reply(process_command(author, comment.body[len(prefix):], server))

def process_recent_comments(reddit, server):
    """Processes the last 100 comments."""
    # TODO: have a list of subreddits and loop over it.
    for comment in reddit.subreddit('simeconomy').comments(limit=100):
        if not is_comment_replied_to(reddit, comment):
            if comment.body.startswith(prefix):
                process_comment(comment, server)

async def reddit_loop(reddit, server):
    """The bot's main Reddit loop."""
    # Let's make a tick twice every day.
    tick_duration = 12 * 60 * 60

    while True:
        # Process messages.
        process_all_messages(reddit, server)
        
        # Process comments.
        # TODO: re-enable this once we get around rate-limiting.
        # process_recent_comments(reddit, server)

        # Notify the server that one or more ticks have elapsed if necessary.
        time_diff = int(time.time() - server.last_tick_timestamp)
        if time_diff > tick_duration:
            for i in range(time_diff // tick_duration):
                server.notify_tick_elapsed()

        # Sleep for five seconds.
        await asyncio.sleep(5)

def split_into_chunks(message: bytes, max_length):
    """Splits a message into chunks. Prefers to split at newlines."""
    if len(message) < max_length:
        return [message]

    split_index = max_length
    newline_index = 0
    last_newline_index = -1
    while newline_index >= 0:
        last_newline_index = newline_index
        newline_index = message.find(b'\n', newline_index + 1, split_index)

    if last_newline_index > 0:
        split_index = last_newline_index

    return [message[:split_index], split_into_chunks(message[split_index:], max_length)]

if __name__ == '__main__':
    config = read_config()
    reddit = create_reddit(config)
    discord_client = discord.Client()

    # This is our main message callback.
    @discord_client.event
    async def on_message(message):
        if message.author == discord_client.user:
            return

        content = message.content.lstrip()
        prefixes = (
            '<@%s>' % discord_client.user.id,
            '<@!%s>' % discord_client.user.id)

        if content.startswith(prefixes):
            response = '<@%s> %s' % (
                message.author.id,
                process_command(
                    DiscordAccountId(str(message.author.id)),
                    content[content.index('>') + 1:].lstrip(),
                    server))

            chunks = split_into_chunks(response.encode('utf-8'), 2000)
            for chunk in chunks:
                await message.channel.send(chunk.decode('utf-8'))

    with LedgerServer('ledger.txt') as server:
        asyncio.get_event_loop().create_task(reddit_loop(reddit, server))
        discord_client.run(config['discord_token'])
