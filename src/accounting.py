import uuid
import time
import os.path


class Server(object):
    """A server manages a number of accounts that all have the same currency."""

    def open_account(self, id, account_uuid=None):
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        raise NotImplementedError()

    def get_account(self, id):
        """Gets the account that matches an ID. Raises an exception if there is no such account."""
        raise NotImplementedError()

    def has_account(self, id):
        """Tests if an account with a particular ID exists on this server."""
        raise NotImplementedError()

    def transfer(self, source, destination, amount):
        """Transfers a particular amount of money from one account on this server to another.
           `destination` and `amount` are both `Account` objects. This action must not complete
           successfully if the transfer cannot be performed."""
        raise NotImplementedError()

    def can_transfer(self, source, destination, amount):
        """Tells if a particular amount of money can be transferred from one account on this
           server to another. `destination` and `amount` are both `Account` objects."""
        return amount > 0 and \
            source.get_balance() - amount >= 0 and \
            not source.is_frozen() and \
            not destination.is_frozen()


class Account(object):
    """An account. Every account has globally unique ID. Additionally, servers have one server-local ID
       per account on the server."""

    def get_uuid(self):
        """Gets this account's unique identifier."""
        raise NotImplementedError()

    def get_balance(self):
        """Gets the balance on this account."""
        raise NotImplementedError()

    def is_frozen(self):
        """Tells if this account is frozen."""
        raise NotImplementedError()


class InMemoryServer(Server):
    """A server that maintains accounts in memory. Nothing is persistent.
       This server implementation can be used to implement more sophisticated
       (persistent) servers."""

    def __init__(self):
        self.accounts = {}
        self.inv_accounts = {}

    def open_account(self, id, account_uuid=None):
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        if self.has_account(id):
            raise Exception("Account already exists.")

        account = InMemoryAccount(account_uuid)
        self.accounts[id] = account
        self.inv_accounts[account] = id
        return account

    def get_account(self, id):
        """Gets the account that matches an ID. Raises an exception if there is no such account."""
        return self.accounts[id]

    def get_account_id(self, account):
        """Gets an account's local ID. Raises an exception if the account is not registered here."""
        return self.inv_accounts[account]

    def has_account(self, id):
        """Tests if an account with a particular ID exists on this server."""
        return id in self.accounts

    def transfer(self, source, destination, amount):
        """Transfers a particular amount of money from one account on this server to another.
           `destination` and `amount` are both `Account` objects. This action must not complete
           successfully if the transfer cannot be performed."""
        if not self.can_transfer(source, destination, amount):
            raise Exception("Cannot perform transfer.")

        source.balance -= amount
        destination.balance += amount


class InMemoryAccount(Account):
    """An in-memory account data structure."""

    def __init__(self, account_uuid=None):
        """Initializes an in-memory account."""
        self.uuid = account_uuid if account_uuid is not None else str(
            uuid.uuid4())
        self.balance = 0
        self.frozen = False

    def get_uuid(self):
        """Gets this account's unique identifier."""
        return self.uuid

    def get_balance(self):
        """Gets the balance on this account."""
        return self.balance

    def is_frozen(self):
        """Tells if this account is frozen."""
        return self.frozen


class LedgerServer(InMemoryServer):
    """A server implementation that logs every action in a ledger.
       The ledger can be read to reconstruct the state of the server."""

    def __init__(self, ledger_path):
        """Initializes a ledger-based server."""
        super().__init__()
        if os.path.isfile(ledger_path):
            self._read_ledger(ledger_path)
        self.ledger_file = open(ledger_path, 'a')

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.ledger_file.close()

    def _read_ledger(self, ledger_path):
        """Reads a ledger at a particular path."""
        with open(ledger_path, 'r') as f:
            lines = f.readlines()

        for line in lines:
            elems = line.split()[1:]
            cmd = elems[0]
            if cmd == 'open':
                super().open_account(elems[1], elems[2])
            elif cmd == 'transfer':
                super().transfer(
                    self.get_account(elems[1]),
                    self.get_account(elems[2]),
                    int(elems[3]))
            else:
                raise Exception("Unknown ledger command '%s'." % cmd)

    def _ledger_write(self, *args):
        self.ledger_file.writelines(' '.join([str(time.time())] + list(map(str, args))))

    def open_account(self, id, account_uuid=None):
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        account = super().open_account(id, account_uuid)
        self._ledger_write('open', id, account.get_uuid())
        return account

    def transfer(self, source, destination, amount):
        """Transfers a particular amount of money from one account on this server to another.
           `destination` and `amount` are both `Account` objects. This action must not complete
           successfully if the transfer cannot be performed."""
        account = super().transfer(source, destination, amount)
        self._ledger_write(
            'transfer',
            self.get_account_id(source),
            destination,
            self.get_account_id(amount))
        return account
