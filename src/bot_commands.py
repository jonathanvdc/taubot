import commands
from accounting import Server, AccountId, Authorization
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
        args = map(
            lambda arg, input: arg[0](input),
            cmd.args.values(),
            split[1:]
        )
        args = list(args)
        if len(args) < len(cmd.args):
            raise ValueError("Not enough arguments")
        rest = " ".join(split[1+len(cmd.args):])
        return args, rest


def run_command(
        author: Union[AccountId, str],
        message: str, server: Server) -> str:
    """Method called by main bot script. Runs a command"""
    try:
        command = _commands[message.split()[0]]
        args, rest = _parse_command_args(command, message)
        # print(args, rest)
        return command.func(author, *args, rest, server)
    except ValueError as e:
        return '\n'.join((f"Error: {e}",
                          command.usage()))
    except commands.ValueCommandException as e:
        return '\n'.join((f"Invalid argument: {e}",
                          "",
                          command.usage()))
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
    return f"Transferred {amount} to {destination}"


_add_command(
    'transfer',
    {
        'amount': (Fraction, 'Amount to transfer'),
        'destination': (parse_account_id, 'Beneficiary to transfer to'),
    },
    _transfer,
    "Transfers an amount of money from your account to a beneficiary's")


def _adm_transfer(
        author: Union[AccountId, str],
        amount: Fraction,
        source: Union[AccountId, str],
        destination: Union[AccountId, str], rest: str,
        server: Server) -> str:
    commands.transfer(author, source, destination, amount, server)
    return f"Transferred {amount} from {source} to {destination}"


_add_command(
    'admin-transfer',
    {
        'amount': (Fraction, 'Amount to transfer'),
        'source': (parse_account_id, 'Account from which the amount is sent'),
        'destination': (parse_account_id, 'Beneficiary to transfer to'),
    },
    _adm_transfer,
    "Transfers an amount of money from a source account to a beneficiary's")


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
        [''.join(((f" {':'.join(map(str,server.get_account_ids(acc))):<28}",
                   f" | {acc.get_authorization().name.lower():<9}",
                   f" | {_mixed(acc.get_balance()):>8}")))
         for acc in commands.list_accounts(author, server)])


_add_command(
    'list',
    {},
    _list_accounts,
    "List all accounts"
)
_alias('list', 'ls')


def _print_money(
        author: Union[AccountId, str],
        amount: int, account: Union[AccountId, str],
        rest: str, server: Server) -> str:
    try:
        commands.print_money(author, account, amount, server)
    except commands.ValueCommandException:
        return "Invalid arguement: Cannot print negative amounts"
    return f"Printed {_mixed(amount)} to {account}"


def _remove_funds(
        author: Union[AccountId, str],
        amount: int, account: Union[AccountId, str],
        rest: str, server: Server) -> str:
    try:
        commands.remove_funds(author, account, amount, server)
    except commands.ValueCommandException:
        return "Invalid arguement: Cannot remove negative amounts"
    return f"Deleted {_mixed(amount)} from {account}"


_add_command(
    'print-money',
    {
        'amount': (Fraction, "Amount to print"),
        'account': (parse_account_id, "Account to print to")
    },
    _print_money,
    "Print amount of money to account"
)
_add_command(
    'remove-funds',
    {
        'amount': (Fraction, "Amount to delete"),
        'account': (parse_account_id, "Account to print to")
    },
    _remove_funds,
    "Deletes fund from an account"
)


def _create_recurring_transfer(
        author: Union[AccountId, str],
        amount: Fraction,
        destination: Union[AccountId, str],
        tick_count: int, rest: str, server: Server) -> str:
    transfer_id = commands.create_recurring_transfer(
        author, author,
        destination, amount,
        tick_count, server).get_id()
    return ''.join((
        f"Set up recurring transfer of {_mixed(amount)}",
        f" to {destination.readable()} every {tick_count} ticks",
        f" (Transfer {transfer_id})."))


def _admin_create_recurring_transfer(
        author: Union[AccountId, str],
        amount: Fraction,
        source: Union[AccountId, str],
        destination: Union[AccountId, str],
        tick_count: int, rest: str, server: Server) -> str:
    transfer_id = commands.create_recurring_transfer(
        author, source,
        destination, amount,
        tick_count, server).get_id()
    return ''.join((
        f"Set up recurring transfer of {_mixed(amount)}",
        f" from {source.readable()}"
        f" to {destination.readable()} every {tick_count} ticks",
        f" (Transfer {transfer_id})."))


_add_command(
    'create-recurring-transfer',
    {
        'amount': (Fraction, "Amount to transfer"),
        'destination': (parse_account_id, 'Beneficiary to transfer to'),
        'tick_count': (int, "Interval to transfer by, in ticks")
    },
    _create_recurring_transfer,
    "Create a transfer which reccurs according to an interval"
)
_add_command(
    'admin-create-recurring-transfer',
    {
        'amount': (Fraction, "Amount to transfer"),
        'source': (Fraction, "Source to transfer from"),
        'destination': (parse_account_id, 'Beneficiary to transfer to'),
        'tick_count': (int, "Interval to transfer by, in ticks")
    },
    _create_recurring_transfer,
    "Create a transfer from someon else which reccurs according to an interval"
)


def _proxy(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        command: str, rest: str, server: Server) -> str:
    if commands.verify_proxy(author, account, None, command+' '+rest, server):
        return run_command(account, command+' '+rest, server)
    return "Unauthorized proxy"


def _proxy_dsa(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        signature: str, command: str,
        rest: str, server: Server) -> str:
    if commands.verify_proxy(author, account, signature,
                             command+' '+rest, server):
        return run_command(account, command+' '+rest, server)
    return "Unauthorized proxy"


_add_command(
    'proxy',
    {
        'account': (parse_account_id, "Account to proxy"),
        'command': (str, "Command to run")
    },
    _proxy,
    "Proxy another account"
)
_add_command(
    'proxy-dsa',
    {
        'account': (parse_account_id, "Account to proxy"),
        'signature': (str, "ECDSA signature of command to run"),
        'command': (str, "Command to run")
    },
    _proxy_dsa,
    "Proxy another account using ECDSA verification"
)


def _request_alias(
        author: Union[AccountId, str],
        alias: Union[AccountId, str],
        rest: str, server: Server) -> str:
    alias_code = commands.request_alias(author, alias, server)
    return f"Alias request code: `{alias_code}`"


def _add_alias(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        request_code: str, rest: str, server: Server) -> str:
    commands.add_alias(author, account, request_code, server)
    return ''.join((f"{author.readable()} and {account.readable()}",
                    "now refer to the same account"))


_add_command(
    'request-alias',
    {
        'account': (parse_account_id, "Account to alias")
    },
    _request_alias,
    "Request an alias code"
)
_add_command(
    'add-alias',
    {
        'account': (parse_account_id, "Account to alias"),
        'request_code': (str, "Code generated on the other account")
    },
    _add_alias,
    "Add another account as an alias"
)


def _admin_add_proxy(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        proxy: Union[AccountId, str],
        rest: str, server: Server) -> str:
    commands.add_proxy(author, account, proxy, server)
    return "Account proxied"


def _admin_remove_proxy(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        proxy: Union[AccountId, str],
        rest: str, server: Server) -> str:
    commands.remove_proxy(author, account, proxy, server)
    return "Account unproxied"


_add_command(
    'admin-add-proxy',
    {
        'account': (parse_account_id, 'Account to let proxy'),
        'proxy': (parse_account_id, 'Account to proxy')
    },
    _admin_add_proxy,
    "Let an account proxy another account"
)
_add_command(
    'admin-remove-proxy',
    {
        'account': (parse_account_id, 'Account to not let proxy'),
        'proxy': (parse_account_id, 'Account being proxied')
    },
    _admin_remove_proxy,
    "Unlet an account proxy another account"
)


def _delete_account(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        rest: str, server: Server) -> str:
    commands.delete_account(author, account, server)
    return "Account deleted."


_add_command(
    'admin-delete-account',
    {
        'account': (parse_account_id, "Account to delete")
    },
    _delete_account,
    "Delete an account"
)


def _add_tax_bracket(
        author: Union[AccountId, str],
        start: Fraction, rate: Fraction, end: Fraction,
        name: str, rest: str, server: Server) -> str:
    end = end if end >= 0 else None
    commands.add_tax_bracket(
        author, start, end, rate, name, server)
    return f"Tax bracket {name}: [{start}–{end}] {rate} added"


def _remove_tax_bracket(
        author: Union[AccountId, str],
        name: str, rest: str, server: Server) -> str:
    commands.remove_tax_bracket(author, name, server)
    return "Removed tax bracket"


_add_command(
    'add-tax-bracket',
    {
        'start': (Fraction, "Lower bound of the tax bracket"),
        'end': (Fraction, "Upper bound of the tax bracker (-1 for infinity)"),
        'rate': (Fraction, "Tax rate"),
        'name': (Fraction, "Name of the tax bracket")
    },
    _add_tax_bracket,
    "Add a tax bracket"
)
_add_command(
    'remove-tax-bracket',
    {
        'name': (Fraction, "Name of the bracket to delete")
    },
    _remove_tax_bracket,
    "Removes a tax bracker"
)


def _force_tax(
        author: Union[AccountId, str],
        rest: str, server: Server) -> str:
    commands.force_tax(author, server)
    return "Applied tax"


_add_command(
    'force-tax',
    {},
    _force_tax,
    "Manually apply tax brakcets"
)


def _toggle_auto_tax(
        author: Union[AccountId, str],
        rest: str, server: Server) -> str:
    ans = commands.auto_tax(author, server)
    return f"Automatic taxation { 'on' if ans else 'off'}"


_add_command(
    'auto-tax',
    {},
    _toggle_auto_tax,
    "Toggle automatic taxation"
)


def _force_ticks(
        author: Union[AccountId, str],
        ticks: int,
        rest: str, server: Server) -> str:
    commands.force_ticks(author, ticks, server)
    return f"Forced {ticks} ticks"


_add_command(
    'force-ticks',
    {
        'ticks': (int, "Amount of ticks to force")
    },
    _force_ticks,
    "Forcibly run ticks"
)


def _authorize(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        level: Authorization,
        rest: str, server: Server) -> str:
    commands.authorize(author, account, level, server)
    return "Authorized"


_add_command(
    'authorize',
    {
        'account': (parse_account_id, "Account to authorize"),
        'level': (
            lambda s: {a.name.lower(): a for a in Authorization}[s.lower()],
            "Authorization level"
        )
    },
    _authorize,
    "Authorize a command"
)
_alias('authorize', 'authorise')


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
