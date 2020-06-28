from Accounting import Server, Account, AccountId, Authorization
from Accounting import parse_account_id
from fractions import Fraction
from typing import Union, Optional
from Crypto.PublicKey import ECC
from Crypto.Signature import DSS
from Crypto.Hash import SHA3_512
import base64


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
        admin_level: Authorization = Authorization.ADMIN,
        min_level: Authorization = Authorization.CITIZEN) -> bool:
    """Check whether subject is authorized to perform operations to object

       Keyword arguments:
       admin_level -- Authorization level to consider "administrative"
       (default Authorization.ADMIN)
       min_level -- Minimum authorization level required (default
       Authorization.ADMIN)
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
        admin_level: Authorization = Authorization.ADMIN,
        min_level: Authorization = Authorization.CITIZEN):
    """Raise exception unless subject is authorized to perform
       operations to object

       Keyword arguments:
       admin_level -- Authorization level to consider "administrative"
       (default Authorization.ADMIN)
       min_level -- Minimum authorization level required (default
       Authorization.ADMIN)
       """
    if not _check_authorization(subject, object, admin_level, min_level):
        raise UnauthorizedCommandException(subject, object)


def _get_account(account_id: Union[AccountId, str], server: Server) -> Account:
    """Get account from server, unless it doesn't exist, in which case raise"""
    account_id = parse_account_id(account_id)
    if not server.has_account(account_id):
        raise AccountCommandException(account_id)

    return server.get_account(account_id)


def _is_signed_by(
        account: Union[AccountId, str],
        message: str, signature: str) -> bool:
    """Check whether account has signed message with signature"""
    try:
        signature = base64.b64decode(signature)
    except Exception:
        raise ValueCommandException(signature)

    msg_hash = SHA3_512.new(message.strip().encode('utf-8'))

    for key in account.list_public_keys():
        verifier = DSS.new(key, 'fips-186-3')
        try:
            verifier.verify(msg_hash, signature)
            return True
        except ValueError:
            pass
    return False


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


def freeze_account(
        author: Union[AccountId, str],
        account: Union[AccountId, str], server: Server):
    """Freeze account with authorization from author"""
    author = _get_account(author, server)
    account = _get_account(account, server)
    _assert_authorized(author, account, min_level=Authorization.ADMIN)

    server.set_frozen(author, account, True)


def unfreeze_account(
        author: Union[AccountId, str],
        account: Union[AccountId, str], server: Server):
    """Unfreeze account with authorization from author"""
    author = _get_account(author, server)
    account = _get_account(account, server)
    _assert_authorized(author, account, min_level=Authorization.ADMIN)

    server.set_frozen(author, account, False)


def balance(
        author: Union[AccountId, str],
        account: Union[AccountId, str], server: Server) -> Fraction:
    """Get the balance of account with authorization from author"""
    author = _get_account(author, server)
    account = _get_account(account, server)
    _assert_authorized(author, account)

    return account.get_balance()


def get_money_supply(
        author: Union[AccountId, str],
        server: Server) -> Fraction:
    """Return sum of all account balances"""
    return sum(map(lambda acc: acc.get_balance(),
                   server.get_accounts()))


def add_public_key(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        key: Union[str, ECC.EccKey], server: Server):
    """Add public key to account, with authorization from author"""
    author = _get_account(author, server)
    account = _get_account(account, server)
    _assert_authorized(author, account)
    if not isinstance(key, ECC.EccKey):
        key = ECC.import_key(key)
    server.add_public_key(account, key)


def list_accounts(author: Union[AccountId, str], server: Server):
    """List all accounts"""
    author = _get_account(author)
    _assert_authorized(author)
    return server.list_accounts()


def print_money(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        amount: Fraction, server: Server):
    """Print an amount of money into an account,
       with the authorization of author, on server
       """
    if amount <= 0:
        raise ValueCommandException(amount)

    author = _get_account(author, server)
    account = _get_account(account, server)

    server.print_money(author, account, amount)


def remove_funds(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        amount: Fraction, server: Server):
    """Remove funds from an account. Rules applying to
       print_money apply.
       """
    if amount <= 0:
        raise ValueCommandException(amount)

    author = _get_account(author, server)
    account = _get_account(account, server)

    server.remove_funds(author, account, amount)


def create_recurring_transfer(
        author: Union[AccountId, str],
        sender: Union[AccountId, str],
        destinarion: Union[AccountId, str],
        amount: Fraction, tick_count: int, server: Server):
    """Create a recurring transfer."""
    author = _get_account(author, server)
    sender = _get_account(sender, server)
    destination = _get_account(destinarion, server)
    _assert_authorized(author, sender)

    transfer = server.create_recurring_transfer(
            author,
            sender,
            destination,
            amount*tick_count,
            tick_count)

    return transfer


def verify_proxy(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        signature: str,
        command: str,
        server: Server) -> bool:
    """Verifies a proxy signature of a message."""
    author = _get_account(author, server)
    account = _get_account(account, server)

    if not signature:
        return author in account.get_proxies()
    else:
        return _is_signed_by(account, command, signature)


def request_alias(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        server: Server) -> str:
    """Generates an alias code for linking accounts together"""
    if server.has_account(account):
        raise AccountCommandException(account)
    author = _get_account(author, server)

    key = ECC.generate(curve='P-256')
    signer = DSS.new(key, 'fips-186-3')
    signature = base64.b64encode(signer.sign(
        SHA3_512.new(str(account).encode('utf-8')).decode('utf-8')))
    server.add_public_key(author, key.public_key())

    return signature


def add_alias(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        signature: str, server: Server):
    """Alias author to account using an alias code (signature)"""
    if server.has_account(author):
        raise AccountCommandException(account)

    account = _get_account(account, server)

    if _is_signed_by(account, str(author), signature):
        server.add_account_alias(account, author)
    else:
        raise ValueCommandException(signature)


def add_proxy(
        author: Union[AccountId, str],
        account: Union[AccountId, str],
        proxy: Union[AccountId, str],
        server: Server):
    """Add proxy to account with authorization from author on server"""
    author = _get_account(author, server)
    account = _get_account(account, server)
    proxy = _get_account(proxy, server)
    _assert_authorized(author)

    server.add_proxy(author, proxy, account)


def remove_proxy(
        author: Union[AccountId, str],
        account: Union[AccountId. str],
        proxy: Union[AccountId, str],
        server: Server):
    """Remove proxy 'proxy' from account with authorization from author."""
    author = _get_account(author, server)
    account = _get_account(account, server)
    proxy = _get_account(proxy, server)
    _assert_authorized(author)

   server.remove_proxy(author, proxy, account)


def delete_account(
        author: Union[AccountId, str],
        account: Union[AccountId, str], server: Server):
    """Delete account with authorization from account on server."""
    author = _get_account(author)
    _assert_authorized(author)

    if not server.delete_account(author, account):
        raise ProcessCommandException()


def add_tax_bracket(
        author: Union[AccountId, str],
        start: Fraction, end: Fraction,
        rate: Fraction, name: str, server: Server):
    """Add a tax bracket to a server with authorization from author"""
    author = _get_account(author, server)
    _assert_authorized(author)
    server.add_tax_bracket(author, start, end, rate, name)


def remove_tax_bracket(
        author: Union[AccountId, str],
        name: str, server: Server):
    """Remove tax bracket by name with authorization from author"""
    author = _get_account(author, server)
    _assert_authorized(author)
    server.remove_tax_bracket(author, name)


def force_tax(author: Union[AccountId, str], server: Server):
    """Manually trigger taxation"""
    author = _get_account(author, server)
    _assert_authorized(author)
    server.force_tax(author)


def auto_tax(author: Union[AccountId, str], server: Server) -> bool:
    """Toggle automatic taxation"""
    author = _get_account(author, server)
    _assert_authorized(author)
    return server.toggle_auto_tax(author)


def force_ticks(
        author: Union[AccountId, str],
        amount: int, sever: Server):
    """Forcibly run multiple ticks"""
    author = _get_account(author, server)
    _assert_authorized(account)
    for i in range(amount):
        server.notify_tick_elapsed(time.time())
