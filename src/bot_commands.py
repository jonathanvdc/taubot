import commands
from Accounting import Server, AccountId
from Accounting import parse_account_id
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
        return (f"Usage: {self.name} {' '.join(self.args.keys())}",
                self.description,
                "Options: ",
                '\n'.join([f"    {arg} -- {meta[1]}"
                           for arg, meta in self.args.items()])
                )


# Command utilities
def _add_command(
        name: str,
        args: dict,
        func: Callable,
        description: str):
    """Adds a command to the global commands dict"""
    _commands.update({name: _Command(name, args, func, description)})


def _parse_command_args(cmd: _Command, message: str):
    """"Parse arguments from a command line"""
    split = message.split()
    if cmd.name != split[0]:
        raise ValueError("Command message does not match command")
    else:
        args = map(
            lambda arg, input: (arg[0], arg[1][0](input)),
            cmd.args,
            split[1:]
        )
        if len(args) < len(cmd.args):
            raise ValueError("Not enough arguments")
        rest = " ".join(split[:1+len(cmd.args)])
        return list(args), rest


def run_command(
        author: Union[AccountId, str],
        message: str, server: Server) -> str:
    """Method called by main bot script. Runs a command"""
    command = _commands[message.split()[0]]
    try:
        args, rest = _parse_command_args(command, message)
        return command.func(author, *args, rest)
    except ValueError as e:
        return f"Error: {e}"
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


# Commands
def _transfer(
        author: Union[AccountId, str],
        amount: Fraction, server: Server,
        destination: Union[AccountId, str]) -> str:
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
        server: Server) -> str:
    try:
        commands.open_account(author, author, server)
    except commands.AccountCommandException:
        return ("Looks like you already have an account."
                "No need to open another one")
    return "Account opened succesfully"


_add_command(
    'open',
    {},
    _open_account,
    "Opens a new account"
)
