# This module defines logic for processing bot commands.
import base64
from typing import Union
from accounting import Authorization, Account, AccountId, Server, parse_account_id, RedditAccountId, DiscordAccountId
from Crypto.PublicKey import ECC
from Crypto.Signature import DSS
from Crypto.Hash import SHA3_512
from random import choice, randint

class CommandException(Exception):
    """The type of exception that is thrown when a command fails."""
    pass

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

def process_transfer(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a transfer command."""
    parse_result = parse_transfer_command(message)

    if parse_result is None:
        return 'Transfer formatted incorrectly. Expected `transfer AMOUNT BENEFICIARY`, ' \
            'where AMOUNT is a positive integer and BENEFICIARY is a username.'

    amount, destination_name = parse_result

    return perform_transfer(author, author, destination_name, amount, server)

def parse_admin_transfer_command(message):
    """Parses a transfer command message."""
    body = message.split()
    if len(body) != 4:
        return None

    _, amount_text, sender, destination = body
    try:
        amount = int(amount_text)
    except ValueError:
        return None

    return (sender, amount, destination)

def process_admin_transfer(author: AccountId, message: str, server: Server, **kwargs):
    """Processes an admin transfer command."""
    assert_authorized(author, server, Authorization.ADMIN)
    parse_result = parse_admin_transfer_command(message)

    if parse_result is None:
        return 'Admin transfer formatted incorrectly. Expected `admin-transfer AMOUNT SENDER BENEFICIARY`, ' \
            'where AMOUNT is a positive integer and SENDER, BENEFICIARY are account holders.'

    sender_name, amount, destination_name = parse_result

    return perform_transfer(author, sender_name, destination_name, amount, server)

def perform_transfer(author_name, sender_name, destination_name, amount, server):
    """Helper function that performs a transfer."""
    author = assert_is_account(author_name, server)
    sender = assert_is_account(sender_name, server)
    dest = assert_is_account(destination_name, server)

    # TODO: check for common reasons for why a transfer might not be able to go through (e.g., insufficient
    # balance) and provide a helpful error message for each of those cases.

    if not server.can_transfer(sender, dest, amount):
        return 'Sorry, but I can\'t perform that transfer.'

    proof = server.transfer(author, sender, dest, amount)
    proof_string = ' Proof: %s.' % proof if proof is not None else ''
    return 'Transfer performed successfully.%s' % proof_string

def process_open_account(author: AccountId, message: str, server: Server, prefix='', platform_name='Reddit', **kwargs):
    """Processes a message that tries to open a new account."""
    if server.has_account(author):
        return 'Hi there %s. Looks like you already have an account. No need to open another one.' % author.readable()

    server.open_account(author)
    return 'Hi there %s. Your account has been opened successfully. Thank you for your business. %s' % (author.readable(), get_generic_help_message(author, prefix, platform_name))

def parse_account_name_command(message: str) -> str:
    """Parses a command that has a single parameter: an account name."""
    body = message.split()
    if len(body) != 2:
        raise CommandException(
            'Incorrectly formatted command; expected `%s ACCOUNT_NAME`.' % body[0])
    return body[1]

def process_admin_open_account(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a message that tries to open a new account."""
    assert_authorized(author, server, Authorization.ADMIN)
    account_name = parse_account_name_command(message)
    if server.has_account(account_name):
        raise CommandException('Account `%s` already exists.' % account_name)

    server.open_account(account_name)
    return 'Account `%s` has been opened successfully.' % account_name

def process_admin_freeze(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a message that freezes an account."""
    author_account = assert_authorized(author, server, Authorization.ADMIN)
    account_name = parse_account_name_command(message)
    account = assert_is_account(account_name, server)

    server.set_frozen(author_account, account, True)
    return 'Account %s was frozen successfully.' % account_name

def process_admin_unfreeze(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a message that unfreezes an account."""
    author_account = assert_authorized(author, server, Authorization.ADMIN)
    account_name = parse_account_name_command(message)
    account = assert_is_account(account_name, server)

    server.set_frozen(author_account, account, False)
    return 'Account %s was unfrozen successfully.' % account_name

def process_balance(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a message requesting the balance on an account."""
    if not server.has_account(author):
        return 'Hi there %s. I can\'t tell you what the balance on your account is because you don\'t have an account yet. ' \
            'You can open one with the `open` command.' % author.readable()

    account = server.get_account(author)
    main_response = 'The balance on your account is %s.' % account.get_balance()
    return 'Hi there %s %s. %s Have a great day.' % (account.get_authorization().name.lower(), author.readable(), main_response)

def process_add_public_key(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a message that requests for a public key to be associated with an account."""
    account = assert_is_account(author, server)
    pem = '\n'.join(line for line in message.split('\n')[1:] if line != '' and not line.isspace())
    try:
        key = ECC.import_key(pem)
    except Exception as e:
        raise CommandException("Incorrectly formatted key. Inner error message: %s." % str(e))

    server.add_public_key(account, key)
    return 'Public key added successfully.'

def assert_is_account(account_name: Union[str, AccountId], server: Server) -> Account:
    """Asserts that a particular account exists. Returns the account."""
    if isinstance(account_name, str):
        account_name = parse_account_id(account_name)

    if not server.has_account(account_name):
        raise CommandException(
            ('Sorry, I can\'t process your request because %s does not have an account yet. '
             'Accounts can be opened using the `open` command.') % account_name.readable())

    return server.get_account(account_name)

def assert_authorized(account_name: Union[str, AccountId], server: Server, auth_level: Authorization) -> Account:
    """Asserts that a particular account exists and has an authorization level that is at least `auth_level`.
       Returns the account."""
    if isinstance(account_name, str):
        account_name = parse_account_id(account_name)

    account = assert_is_account(account_name, server)

    if account.get_authorization().value < auth_level.value:
        raise CommandException('Sorry, I can\'t process your request because %s does not have the required authorization.' % account_name.readable())

    return account

def parse_authorization(message):
    """Parses an authorization message."""
    body = message.split()
    if len(body) != 3:
        return None

    _, beneficiary, auth_level = body
    auth_level = auth_level.upper()
    try:
        return (beneficiary, Authorization[auth_level])
    except KeyError:
        return None

def process_authorization(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a message requesting an authorization change."""
    author_account = assert_authorized(author, server, Authorization.ADMIN)
    parsed = parse_authorization(message)
    if parsed is None:
        raise CommandException('Authorization formatted incorrectly. The right format is `authorize BENEFICIARY citizen|admin|developer`.')

    beneficiary, auth_level = parsed
    beneficiary_account = assert_is_account(beneficiary, server)
    server.authorize(author_account, beneficiary_account, auth_level)
    return '%s now has authorization level %s.' % (beneficiary, auth_level.name)

def process_list_accounts(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a message requesting a list of all accounts."""
    return '\n'.join(['| Account | Balance |', '| --- | --- |'] + [
        '| %s | %s |' % (' aka '.join(str(x) for x in server.get_account_ids(account)), account.get_balance())
        for account in server.list_accounts()
    ])

def parse_print_money(message):
    """Parses a money printing request."""
    body = message.split()
    if len(body) != 3:
        return None

    _, amount_text, beneficiary = body
    try:
        amount = int(amount_text)
    except ValueError:
        return None

    return (amount, parse_account_id(beneficiary))

def process_print_money(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a request to print a batch of money and deposit it in an account."""
    author_account = assert_authorized(author, server, Authorization.ADMIN)
    parsed = parse_print_money(message)
    if parsed is None:
        raise CommandException('Command formatted incorrectly. Expected format `print-money AMOUNT BENEFICIARY`.')

    amount, beneficiary = parsed
    beneficiary_account = assert_is_account(beneficiary, server)
    server.print_money(author_account, beneficiary_account, amount)
    return 'Money printed successfully.'

def parse_admin_create_recurring_transfer(message):
    """Parses an admin-create-recurring-transfer message."""
    body = message.split()
    if len(body) != 5:
        return None

    _, amount_text, sender, destination, tick_count_text = body
    try:
        amount = int(amount_text)
        tick_count = int(tick_count_text)
    except ValueError:
        return None

    return (amount, parse_account_id(sender), parse_account_id(destination), tick_count)

def process_admin_create_recurring_transfer(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a request to set up an arbitrary recurring transfer."""
    assert_authorized(author, server, Authorization.ADMIN)
    parse_result = parse_admin_create_recurring_transfer(message)

    if parse_result is None:
        return 'Request formatted incorrectly. Expected `admin-create-recurring-transfer AMOUNT_PER_TICK SENDER BENEFICIARY TICK_COUNT`.'

    amount, sender_name, destination_name, tick_count = parse_result

    author_account = assert_is_account(author, server)
    sender_account = assert_is_account(sender_name, server)
    dest_account = assert_is_account(destination_name, server)

    transfer = server.create_recurring_transfer(
        author_account,
        sender_account,
        dest_account,
        amount * tick_count,
        tick_count)
    return 'Recurring transfer set up with ID `%s`.' % transfer.get_id()

def parse_create_recurring_transfer(message):
    """Parses a create-recurring-transfer message."""
    body = message.split()
    if len(body) != 4:
        return None

    _, amount_text, destination, tick_count_text = body
    try:
        amount = int(amount_text)
        tick_count = int(tick_count_text)
    except ValueError:
        return None

    return (amount, parse_account_id(destination), tick_count)

def process_create_recurring_transfer(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a request to set up a recurring transfer."""
    parse_result = parse_create_recurring_transfer(message)

    if parse_result is None:
        return 'Request formatted incorrectly. Expected `create-recurring-transfer AMOUNT_PER_TICK BENEFICIARY TICK_COUNT`.'

    amount, destination_name, tick_count = parse_result

    author_account = assert_is_account(author, server)
    dest_account = assert_is_account(destination_name, server)

    transfer = server.create_recurring_transfer(
        author_account,
        author_account,
        dest_account,
        amount * tick_count,
        tick_count)
    return 'Recurring transfer set up with ID `%s`.' % transfer.get_id()

def parse_proxy_command(message):
    """Parses a proxy command into its components."""
    def parse_impl():
        split_message = message.split('\n', 1)
        if len(split_message) != 2:
            return None

        proxy_line, command = split_message
        command = command.strip('\n\r')

        proxy_elems = proxy_line.split()
        if len(proxy_elems) != 4:
            return None

        _, protocol, account_name, enc_signature = proxy_elems
        if protocol != 'dsa':
            return None

        return (parse_account_id(account_name), enc_signature, command)

    result = parse_impl()
    if result == None:
        raise CommandException('Invalid formatting; expected `proxy dsa PROXIED_ACCOUNT SIGNATURE` followed by another command on the next line.')
    else:
        return result

def sign_message(message: str, key) -> str:
    """Signs a message's SHA3-512 digest using the DSA algorithm."""
    message = message.strip()
    message_hash = SHA3_512.new(message.encode('utf-8'))
    signer = DSS.new(key, 'fips-186-3')
    return base64.b64encode(signer.sign(message_hash)).decode('utf-8')

def compose_proxy_command(proxied_account_name, key, command):
    """Composes a proxy command."""
    command = command.strip()
    return 'proxy dsa %s %s\n%s' % (proxied_account_name, sign_message(command, key), command)

def is_signed_by(account: Account, message: str, base64_signature: str) -> bool:
    """Checks if `message` with signature `base64_signature` was signed by `account`."""
    try:
        signature = base64.b64decode(base64_signature)
    except Exception as e:
        raise CommandException('Invalid signature. %s' % str(e))

    message_hash = SHA3_512.new(message.strip().encode('utf-8'))
    any_verified = False
    for key in account.list_public_keys():
        verifier = DSS.new(key, 'fips-186-3')
        try:
            verifier.verify(message_hash, signature)
            any_verified = True
        except ValueError:
            pass

        if any_verified:
            break

    return any_verified

def process_proxy_command(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a command by proxy."""
    account_name, signature, command = parse_proxy_command(message)
    account = assert_is_account(account_name, server)

    if is_signed_by(account, command, signature):
        return process_command(parse_account_id(account_name), command, server)
    else:
        raise CommandException('Cannot execute command by proxy because the signature is invalid.')

def process_name(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a request for an account name."""
    return 'Hello there %s. Your local account ID is `%s`.' % (author.readable(), str(author))

def process_request_alias(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a request for an alias code."""
    account = assert_is_account(author, server)

    split_msg = message.split()
    if len(split_msg) != 2:
        raise CommandException('Incorrect formatting. Expected `request-alias ALIAS_ACCOUNT_NAME`.')

    _, alias_name = split_msg
    alias_id = parse_account_id(alias_name)
    if server.has_account(alias_id):
        raise CommandException(
            'An account has already been associated with %s, so it cannot be an alias for this account.' %
            alias_id.readable())

    # To generate an alias code, we generate an ECC public/private key pair, use the
    # private key to generate a signed version of the aliased account name and associate
    # the public key with the account.
    key = ECC.generate(curve='P-256')
    signature = sign_message(str(alias_id), key)
    server.add_public_key(account, key.public_key())

    # At this point we will allow the private key to be forgotten.

    # Compose a helpful message for as to how the bot can be contacted to link accounts.
    if isinstance(alias_id, RedditAccountId):
        contact_message = 'Send me that exact command as a Reddit Private Message (not a direct chat) from %s.' % alias_id.readable()
    elif isinstance(alias_id, DiscordAccountId):
        contact_message = 'Send me that exact command prefixed with a mention of my name via Discord from account %s.' % alias_id
    else:
        contact_message = ''

    return ('I created an alias request code for you. '
        'Make {0} an alias for this account ({2}) by sending me the following message from {3}.\n\n```\nadd-alias {4} {1}\n```\n\n{5}').format(
            str(alias_id), signature, author.readable(), alias_id.readable(), str(author), contact_message)

def process_add_alias(author: AccountId, message: str, server: Server, **kwargs):
    """Processes a request to add `author` as an alias to an account."""
    if server.has_account(author):
        raise CommandException(
            'An account has already been associated with %s, so it cannot be an alias for another account.' % author.readable())

    split_msg = message.split()
    if len(split_msg) != 3:
        raise CommandException('Incorrect formatting. Expected `add-alias ALIASED_ACCOUNT ALIAS_REQUEST_CODE`.')

    _, aliased_account_name, signature = split_msg
    aliased_account = assert_is_account(aliased_account_name, server)

    if is_signed_by(aliased_account, str(author), signature):
        server.add_account_alias(aliased_account, author)
        return 'Alias set up successfully. %s and %s now refer to the same account.' % (
            aliased_account_name, author.readable())
    else:
        raise CommandException('Cannot set up alias because the signature is invalid.')

def process_command(author: AccountId, message: str, server: Server, prefix=''):
    """Processes an arbitrary command."""
    split_msg = message.split()
    if len(split_msg) == 0:
        return 'Hi %s! You sent me an empty message. Here\'s a list of commands I do understand:\n\n%s' % (
            author.readable(), list_commands_as_markdown(author, server))
    elif split_msg[0] in COMMANDS:
        try:
            cmd = COMMANDS[split_msg[0]]
            if len(cmd) >= 4 and cmd[3].value > Authorization.CITIZEN.value:
                assert_authorized(author, server, cmd[3])

            platform_name = 'Discord' if isinstance(author, DiscordAccountId) else 'Reddit'
            return cmd[2](author, message, server, prefix=prefix, platform_name=platform_name)
        except CommandException as e:
            return str(e)
    else:
        return 'Hi %s! I didn\'t quite understand command your command `%s`. Here\'s a list of commands I do understand:\n\n%s' % (
            author.readable(), split_msg[0], list_commands_as_markdown(author, server)) # Sends the help message.

def list_commands(author: AccountId, server: Server):
    """Creates a list of all commands accepted by this bot."""
    return [
        '`%s` – %s' % (COMMANDS[key][0], COMMANDS[key][1])
        for key in sorted(COMMANDS)
        if len(COMMANDS[key]) < 4 or get_authorization_or_citizen(author, server).value >= COMMANDS[key][3].value
    ]

def get_authorization_or_citizen(author: AccountId, server: Server):
    """Gets an account's authorization if it exists and the default citizen authorization otherwise."""
    return server.get_account(author).get_authorization() \
        if server.has_account(author) \
        else Authorization.CITIZEN

def list_commands_as_markdown(author: AccountId, server: Server):
    """Creates a list of all commands accepted by this bot and formats it as Markdown."""
    return '\n'.join('  * %s' % item for item in list_commands(author, server))

PLATFORMS = {
    'Discord': {
        'reach_how': 'by pinging me at the start of a message'
    },
    'Reddit': {
        'reach_how': 'by sending me a private message (I ignore the subject, only the body matters); only PMs work, chat does not',
        'example_username': 'jedi-turncoat'
    }
}

def get_how_to_reach_message(platform_name):
    """Gets a message that tells the user how to reach the bot."""
    how_to_reach_msg = 'Here on %s you can reach me %s.' % (platform_name, PLATFORMS[platform_name]['reach_how'])
    for key, props in PLATFORMS.items():
        if key != platform_name:
            how_to_reach_msg += ' On %s you can reach me %s.' % (key, props['reach_how'])
    return how_to_reach_msg

def get_generic_help_message(author: AccountId, prefix, platform_name):
    """Gets the generic help message for account holders."""
    interpersonal_relation = choice(['friend', 'BFF', 'homie', 'buddy', 'mortal enemy', 'frenemy', 'next door neighbor'])
    suggested_amount = randint(1, 100)
    suggested_name = PLATFORMS[platform_name]['example_username'] if 'example_username' in PLATFORMS[platform_name] else prefix
    return '''How can I help you today?

If you want to check your balance, send me this:

> {0}balance

To transfer, say, {1} tau to your {3} {2} just run the following command:

> {0}transfer {1} {2}

For a complete list of commands, run

> {0}reference

If you need help from an actual person, get in touch with the Department of Integration and they'll help you out.'''.format(
    prefix, suggested_amount, suggested_name, interpersonal_relation)

def process_help(author: AccountId, message: str, server: Server, prefix='', platform_name='Reddit', **kwargs):
    """Gets the help message for the economy bot."""
    if server.has_account(author):
        return '''Howdy partner! It's always a pleasure to meet an account holder. %s %s''' % (get_how_to_reach_message(platform_name), get_generic_help_message(author, prefix, platform_name))
    else:
        return '''Hi! You look new. {1} If you don't have an account with me yet, you can open one using this command:

> {0}open

Alternatively, if you already have an account then please don't create a new one here.
Instead, link your existing account to {2} by running the following command from a username that's already associated with the account.

> request-alias {3}

(If you're sending me that over Discord you'll also have to ping me at the start of that command.)'''.format(
    prefix, get_how_to_reach_message(platform_name), author.readable(), str(author))

def process_reference(author: AccountId, message: str, server: Server, **kwargs):
    """Gets the command reference message for the economy bot."""
    return '''
Hi %s! Here's a list of the commands I understand:

%s''' % (author.readable(), list_commands_as_markdown(author, server))

# A list of the commands accepted by the bot. Every command
# is essentially a function that maps a message to a reply.
# For convenience, every command is associated with a help
# string here. It's formatted as such:
# 'commandName': ('commandFormat', 'helpDescription', 'command')
COMMANDS = {
    'reference': ('reference', 'prints a command reference message.', process_reference),
    'help': ('help', 'prints a help message.', process_help),
    'transfer': ('transfer AMOUNT BENEFICIARY', 'transfers `AMOUNT` to user `BENEFICIARY`\'s account.', process_transfer),
    'open': ('open', 'opens a new account.', process_open_account),
    'balance': ('balance', 'prints the balance on your account.', process_balance),
    'bal': ('bal', 'prints the balance on your account.', process_balance),
    'add-public-key': (
        'add-public-key',
        'associates an ECC public key with your account. '
        'The public key should be encoded as the contents of a PEM file that is placed on a line after the command itself.',
        process_add_public_key),
    'proxy': (
        'proxy dsa PROXIED_ACCOUNT SIGNATURE',
        'makes `PROXIED_ACCOUNT` perform the action described in the remainder of the message (starting on the next line). '
        '`SIGNATURE` must be an ECDSA-signed SHA3-512 hash of the remainder of the message, where the key that signs the '
        'message must have its public key associated with the proxied account. This command allows a user or application to '
        'safely perform actions on an account holder\'s behalf.',
        process_proxy_command),
    'request-alias': (
        'request-alias ALIAS_ACCOUNT_NAME',
        'generates a code that will allow you to securely associate an alias `ALIAS_ACCOUNT_NAME` with this account. '
        'Concretely, an alias is an additional Reddit or Discord user that you can use to directly '
        'manage this account. If you don\'t know what to put in `ALIAS_ACCOUNT_NAME`, use the name produced by the `name` command.',
        process_request_alias),
    'add-alias': (
        'add-alias ALIASED_ACCOUNT ALIAS_REQUEST_CODE',
        'registers this account as an alias for `ALIASED_ACCOUNT`. `ALIAS_REQUEST_CODE` must be a code '
        'generated by `ALIASED_ACCOUNT` using the `request-alias` command. **NOTE:** for this to work, '
        'the Reddit/Discord account that sends this message **must not** be associated with an existing '
        'account yet.',
        process_add_alias),
    'name': (
        'name',
        'responds with your account name, even if you don\'t have an account yet.',
        process_name),
    'authorize': (
        'authorize ACCOUNT citizen|admin|developer',
        'sets an account\'s authorization.',
        process_authorization,
        Authorization.ADMIN),
    'admin-transfer': (
        'admin-transfer AMOUNT SENDER BENEFICIARY',
        'transfers `AMOUNT` from `SENDER` to `BENEFICIARY`.',
        process_admin_transfer,
        Authorization.ADMIN),
    'list': (
        'list',
        'lists all accounts and the balance on the accounts.',
        process_list_accounts,
        Authorization.ADMIN),
    'print-money': (
        'print-money AMOUNT BENEFICIARY',
        'generates `AMOUNT` money and deposits it in `BENEFICIARY`\'s account.',
        process_print_money,
        Authorization.ADMIN),
    'create-recurring-transfer': (
        'create-recurring-transfer AMOUNT_PER_TICK BENEFICIARY TICK_COUNT',
        'creates a transfer that will transfer `AMOUNT_PER_TICK` from your account to `BENEFICIARY` every tick, for `TICK_COUNT` ticks.',
        process_create_recurring_transfer,
        Authorization.CITIZEN),
    'admin-create-recurring-transfer': (
        'admin-create-recurring-transfer AMOUNT_PER_TICK SENDER BENEFICIARY TICK_COUNT',
        'creates a transfer that will transfer `AMOUNT_PER_TICK` from `SENDER` to `BENEFICIARY` every tick, for `TICK_COUNT` ticks.',
        process_admin_create_recurring_transfer,
        Authorization.ADMIN),
    'admin-open': (
        'admin-open ACCOUNT_NAME',
        'opens a new account with name `ACCOUNT_NAME`. '
            'If an existing user has `ACCOUNT_NAME`, then the newly created account will become that user\'s account.',
        process_admin_open_account,
        Authorization.ADMIN),
    'admin-freeze': (
        'admin-freeze ACCOUNT_NAME',
        'freezes the account with name `ACCOUNT_NAME`.',
        process_admin_freeze,
        Authorization.ADMIN),
    'admin-unfreeze': (
        'admin-unfreeze ACCOUNT_NAME',
        'unfreezes the account with name `ACCOUNT_NAME`.',
        process_admin_unfreeze,
        Authorization.ADMIN)
}
