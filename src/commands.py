# This module defines logic for processing bot commands.

def parse_transfer_command(message):
    """Parses a transfer command message."""
    body = message.split()
    if len(body) != 3:
        return None

    _, amount_text, destination = body
    try:
        amount = int(amount_text)
    except ValueError:
        return None

    return (amount, destination)

def process_transfer(author, message, server):
    """Processes a transfer command."""
    parse_result = parse_transfer_command(message)

    if parse_result is None:
        return 'Transfer formatted incorrectly. Expected `transfer AMOUNT BENEFICIARY`, ' \
            'where AMOUNT is a positive integer and BENEFICIARY is a username.'

    amount, destination_name = parse_result

    if not server.has_account(author):
        return 'Sorry, but I can\'t perform that transfer: you do not have an account yet. ' \
            'You can open one with the `open` command.'

    sender = server.get_account(author)

    if not server.has_account(destination_name):
        return 'Sorry, but I can\'t perform that transfer: your beneficiary %s does not have an account yet.' % destination_name

    dest = server.get_account(destination_name)

    # TODO: check for common reasons for why a transfer might not be able to go through (e.g., insufficient
    # balance) and provide a helpful error message for each of those cases.

    if not server.can_transfer(sender, dest, amount):
        return 'Sorry, but I can\'t perform that transfer.'

    proof = server.transfer(sender, dest, amount)
    proof_string = ' Proof: %s.' % proof if proof is not None else ''
    return 'Transfer performed successfully.%s' % proof_string

def process_open_account(author, message, server):
    """Processes a message that tries to open a new account."""
    if server.has_account(author):
        return 'Hi there %s. Looks like you already have an account. No need to open another one.' % author

    server.open_account(author)
    return 'Hi there %s. Your account has been opened successfully. Thank you for your business.' % author

def list_commands():
    """Creates a list of all commands accepted by this bot."""
    return ['`%s` &ndash; %s' % (COMMANDS[cmd][0], COMMANDS[cmd][1]) for cmd in sorted(COMMANDS)]

def list_commands_as_markdown():
    """Creates a list of all commands accepted by this bot and formats it as Markdown."""
    return '\n'.join('  * %s' % item for item in list_commands())

def get_help_message(username):
    """Gets the help message for the economy bot."""
    return '''
Hi %s! Here's a list of the commands I understand:

%s''' % (username, list_commands_as_markdown())

# A list of the commands accepted by the bot. Every command
# is essentially a function that maps a message to a reply.
# For convenience, every command is associated with a help
# string here.
COMMANDS = {
    'help': ('help', 'prints a help message.', lambda author, msg, server: get_help_message(msg.author.name)),
    'transfer': ('transfer AMOUNT BENEFICIARY', 'transfers AMOUNT to user BENEFICIARY\'s account', process_transfer),
    'open': ('open', 'opens a new account.', process_open_account)
}
