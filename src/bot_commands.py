import commands
from accounting import Server, AccountId
from accounting import parse_account_id
from typing import Union, Callable
from fractions import Fraction

# Dictionary in which we store all commands
_commands = {}


# Command class, this thing stores metadata on commands to help with parsing
class _Command(object):
    """Data type representing a command"""

    def __init__(
            self,
            name: str, args: dict, func: Callable,
            description: str = ""):
        """Members:

        name -- string representint the command
        args -- a dictionary of arguments in the format of name:(type,desc)
        func -- the function the command object represents
        description -- an end-user readable description of the command
        (optional)
        """

        self.func = func
        self.args = args
        self.name = name
        self.description = description

    def usage(self):
        """Print usage for command"""
        return '\n'.join((f"Usage: {self.name} {' '.join(self.args.keys())}",
                          self.description+"",
                          "Options: ",
                          '\n'.join([f"    {arg} -- {meta[1]}"
                                     for arg, meta in self.args.items()])
                          ))

    def copy(self):
        return _Command(self.name, self.args, self.func, self.description)


# UI utilities
def _mixed(f: Fraction) -> str:
    if f.numerator % f.denominator == 0:
        return str(int(f.numerator/f.denominator))
    elif f.numerator / f.denominator <= 1:
        return str(f)
    else:
        return '%d %d/%d' % (
            int(f.numerator/f.denominator),
            f.numerator % f.denominator,
            f.denominator)


# Command utilities
def _add_command(
        name: str,
        args: dict,
        func: Callable,
        description: str):
    """Adds a command to the global commands dict"""
    _commands.update({name: _Command(name, args, func, description)})


def _alias(name: str, alias: str):
    """Alias a command"""
    cmd = _commands[name].copy()
    cmd.name = alias
    _commands.update(
        {alias: cmd}
    )


def _parse_command_args(cmd: _Command, message: str):
    """"Parse arguments from a command line"""
    split = message.split()
    if cmd.name != split[0]:
        raise ValueError("Command message does not match command")
    else:
        print(cmd.args.values())
        args = map(
            lambda arg, input: arg[0](input),
            cmd.args.values(),
            split[1:]
        )
        args = list(args)
        if len(args) < len(cmd.args):
            raise ValueError("Not enough arguments")
        rest = " ".join(split[:1+len(cmd.args)])
        return args, rest


def run_command(
        author: Union[AccountId, str],
        message: str, server: Server) -> str:
    """Method called by main bot script. Runs a command"""
    try:
        command = _commands[message.split()[0]]
        args, rest = _parse_command_args(command, message)
        return command.func(author, *args, rest, server)
    except ValueError as e:
        return '\n'.join((f"Error: {e}",
                          command.usage()))
    except commands.ValueCommandException as e:
        return (f"Invalid argument: {e}",
                "",
                command.usage())
    except commands.AccountCommandException as e:
        return f"Invalid account: {e}"
    except commands.UnauthorizedCommandException:
        return "Unauthorized command"
    except commands.ProcessCommandException:
        return "Something went wrong. Please try again later"
    except KeyError:
        return f'No such command: {message.split()[0]}'


# Commands
def _transfer(
        author: Union[AccountId, str],
        amount: Fraction,
        destination: Union[AccountId, str], rest: str,
        server: Server) -> str:
    commands.transfer(author, author, destination, amount, server)
    return "Transferred {amount}{server to {author}"


_add_command(
    'transfer',
    {
        'amount': (int, 'Amount to transfer'),
        'destination': (parse_account_id, 'Beneficiary to transfer to'),
    },
    _transfer,
    "Transfers an amount of money from your account to a beneficiary's")


def _open_account(
        author: Union[AccountId, str],
        rest: str,
        server: Server) -> str:
    try:
        commands.open_account(author, author, server)
    except commands.ValueCommandException:
        return ("Looks like you already have an account. "
                "No need to open another one")
    return "Account opened succesfully"


_add_command(
    'open',
    {},
    _open_account,
    "Opens a new account"
)


def _adm_open_account(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        rest: str,
        server: Server) -> str:
    try:
        commands.open_account(author, account, server)
    except commands.ValueCommandException:
        return ("Looks like they already have an account",
                "No need to open a new one")
    return "Account opened succefully"


_add_command(
    'admin-open',
    {
        'account': (parse_account_id, 'Account to open')
    },
    _adm_open_account,
    "Open a new account for someone else"
)


def _freeze_account(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        rest: str, server: Server) -> str:
    commands.freeze_account(author, account, server)
    return "Account frozen"


_add_command(
    'admin-freeze',
    {
        'account': (parse_account_id, 'Account to freeze')
    },
    _freeze_account,
    "Freeze an account"
)


def _unfreeze_account(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        rest: str, server: Server) -> str:
    commands.unfreeze_account(author, account, server)
    return "Account unfrozen"


_add_command(
    'admin-unfreeze',
    {
        'account': (parse_account_id, 'Account to unfreeze')
    },
    _unfreeze_account,
    "Unfreeze an account"
)


def _balance(
        author: Union[AccountId, str],
        rest: str, server: Server) -> str:
    bal = commands.balance(author, author, server)
    return f"Your balance is {_mixed(bal)}"


_add_command(
    'balance',
    {},
    _balance,
    "Print account balance"
)
_alias('balance', 'bal')


def _money_supply(
        author: Union[AccountId, str],
        rest: str, server: Server) -> str:
    bal = commands.get_money_supply(author, server)
    return f"The total money supply is {_mixed(bal)}"


_add_command(
    'money-supply',
    {},
    _money_supply,
    "Print the total money supply"
)


def _add_public_key(
        author: Union[AccountId, str], key: str,
        rest: str, server: Server) -> str:
    pem = '\n'.join(
        line for line in f"{key} {rest}".splitlines()
        if line and not line.isspace()
    )
    commands.add_public_key(author, author, pem, server)
    return 'Public key added successfully'


_add_command(
    'add-public-key',
    {
        'key': (lambda x: str(x), "Key to use")
    },
    _add_public_key,
    "Adds a public key to your account"
)


def _list_accounts(
        author: Union[AccountId, str],
        rest: str, server: Server) -> str:
    return '\n'.join(
        [''.join(((f" {':'.join(map(str,server.get_account_ids(acc))):<20}",
                   f" | {acc.get_authorization().name.lower():<9}",
                   f" | {acc.get_balance():<8}")))
         for acc in commands.list_accounts(author, server)])


_add_command(
    'list',
    {},
    _list_accounts,
    "List all accounts"
)
_alias('list', 'ls')


def _help(
        author: Union[AccountId, str],
        rest: str,
        server: Server) -> str:
    return '\n'.join(
        ("List of commands:",
         "\n".join(f"    {command.name} -- {command.description}"
                   for command in _commands.values())
         ))


_add_command(
    'help',
    {},
    _help,
    "List all commands"
)

_commands = {k: v for k, v in sorted(_commands.items(), key=lambda x: x[0])}
