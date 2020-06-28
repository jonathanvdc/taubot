from Accounting import Server, Account, AccountId, Authorization
from Accounting import parse_account_id
from fractions import Fraction
from typing import Union, Optional


# EXCEPTIONS
class CommandException(Exception):
    """Commands module superexception, for catching others"""
    pass


class UnauthorizedCommandException(Exception):
    """Thrown on unauthorized command.
    Expect message to be relevant account ids
    """
    pass


class AccountCommandException(Exception):
    """Thrown on problem with account, such as nonexistence.
    Message should be the account id
    """
    pass


class ValueCommandException(Exception):
    """Thrown when a value (such as a transfer amount) is invalid
    in some way, such as account balance being too low. Equivalent to
    4XX errors in HTTP.
    """
    pass


class ProcessCommandException(Exception):
    """Thrown on failure during the process of a executing a command.
    Generic 'process error', equivalent to 5XX errors in HTTP
    """
    pass


# UTILITY FUNCTIONS (mostly module privates)
def _check_authorization(
        subject: Account, object: Account,
        admin_level: Authorization = Authorization.ADMIN) -> bool:
    """Check whether subject is authorized to perform operations to object

       Keyword arguments:
       admin_level -- Authorization level to consider "administrative"
       (default Authorization.ADMIN)
       """
    # Admin-authorization
    if subject.get_authorization().value < admin_level.value:
        return True

    # Self-authorization
    elif subject.get_uuid() == object.get_uuid():
        return True

    # Proxying?


def _assert_authorized(
        subject: Account, object: Optional[Account],
        admin_level: Authorization = Authorization.ADMIN):
    """Raise exception unless subject is authorized to perform
       operations to object

       Keyword arguments:
       admin_level -- Authorization level to consider "administrative"
       (default Authorization.ADMIN)
       """
    if not _check_authorization(subject, object, admin_level):
        raise UnauthorizedCommandException(subject, object)


def _get_account(account_id: Union[AccountId, str], server: Server) -> Account:
    """Get account from server, unless it doesn't exist, in which case raise"""
    account_id = parse_account_id(account_id)
    if not server.has_account(account_id):
        raise AccountCommandException(account_id)

    return server.get_account(account_id)


# COMMANDS
def transfer(
        author: Union[AccountId, str],  source: Union[AccountId, str],
        destination: Union[AccountId, str],
        amount: Fraction, server: Server):
    """Transfer amount ¤ from source to destination with authorization
       from author on server"""
    author = _get_account(author, server)
    source = _get_account(source, server)
    destination = _get_account(destination, server)
    _assert_authorized(author, source)

    if not server.can_transfer(source, destination, amount):
        raise ValueCommandException(amount)

    proof = server.transfer(source, destination, amount)
    return proof


def open_account(
        author: Union[AccountId, str],
        account: Union[AccountId, str], server: Server):
    """Open account through authorization of author on server.
    Author can be the same account as account"""
    if server.has_account(account):
        raise ValueCommandException(account)
    if server.has_account(author):
        _assert_authorized(author)
    server.open_account(account)


