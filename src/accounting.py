import uuid
import time
import os.path
from enum import Enum


class Server(object):
    """A server manages a number of accounts that all have the same currency."""

    def open_account(self, id, account_uuid=None):
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        raise NotImplementedError()

    def get_account(self, id):
        """Gets the account that matches an ID. Raises an exception if there is no such account."""
        raise NotImplementedError()

    def get_account_id(self, account):
        """Gets an account's local ID. Raises an exception if the account is not registered here."""
        raise NotImplementedError()

    def has_account(self, id):
        """Tests if an account with a particular ID exists on this server."""
        raise NotImplementedError()

    def get_government_account(self):
        """Gets the main government account for this server."""
        raise NotImplementedError()

    def list_accounts(self):
        """Lists all accounts on this server."""
        raise NotImplementedError()

    def authorize(self, author, account, auth_level):
        """Makes `author` set `account`'s authorization level to `auth_level`."""
        raise NotImplementedError()

    def get_recurring_transfer(self, id):
        """Gets a recurring transfer based on its ID."""
        raise NotImplementedError()

    def list_recurring_transfers(self):
        """Produces a list of all recurring transfers."""
        raise NotImplementedError()

    def create_recurring_transfer(self, author, source, destination, total_amount, tick_count):
        """Creates and registers a new recurring transfer, i.e., a transfer that is spread out over
           many ticks. The transfer is authorized by `author` and consists of `total_amount` being
           transferred from `source` to `destination` over the course of `tick_count` ticks. A tick
           is a server-defined timespan."""
        raise NotImplementedError()

    def notify_tick_elapsed(self):
        """Notifies the server that a tick has elapsed."""
        raise NotImplementedError()

    def transfer(self, author, source, destination, amount):
        """Transfers a particular amount of money from one account on this server to another on
           the authority of `author`. `author`, `destination` and `amount` are `Account` objects.
           This action must not complete successfully if the transfer cannot be performed."""
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

    def get_authorization(self):
        """Gets this account's level of authorization."""
        raise NotImplementedError()


class RecurringTransfer(object):
    """A recurring transfer."""

    def get_id(self):
        """Gets the ID for the transfer."""
        raise NotImplementedError()

    def get_author(self):
        """Gets the account that authorized the transfer."""
        raise NotImplementedError()

    def get_source(self):
        """Gets the account from which the money originates."""
        raise NotImplementedError()

    def get_destination(self):
        """Gets the account to which the money must go."""
        raise NotImplementedError()

    def get_tick_count(self):
        """Gets the number of ticks over the course of which the transfer must complete."""
        raise NotImplementedError()

    def get_total_amount(self):
        """Gets the total amount to transfer."""
        raise NotImplementedError()

    def get_remaining_amount(self):
        """Gets the remaining amount to transfer."""
        raise NotImplementedError()

    def get_transferred_amount(self):
        """Gets the amount of money that has already been transferred."""
        return self.get_total_amount() - self.get_remaining_amount()


class Authorization(Enum):
    """Defines various levels of authorization for account."""
    CITIZEN = 0
    ADMIN = 1
    DEVELOPER = 2


class InMemoryServer(Server):
    """A server that maintains accounts in memory. Nothing is persistent.
       This server implementation can be used to implement more sophisticated
       (persistent) servers."""

    def __init__(self):
        self.accounts = {}
        self.inv_accounts = {}
        self.gov_account = InMemoryServer.open_account(self, "@government")
        self.gov_account.auth = Authorization.DEVELOPER
        self.recurring_transfers = {}

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

    def get_government_account(self):
        """Gets the main government account for this server."""
        return self.gov_account

    def list_accounts(self):
        """Lists all accounts on this server."""
        return self.accounts.values()

    def authorize(self, author, account, auth_level):
        """Makes `author` set `account`'s authorization level to `auth_level`."""
        account.auth = auth_level

    def transfer(self, author, source, destination, amount):
        """Transfers a particular amount of money from one account on this server to another on
           the authority of `author`. `author`, `destination` and `amount` are `Account` objects.
           This action must not complete successfully if the transfer cannot be performed."""
        if not self.can_transfer(source, destination, amount):
            raise Exception("Cannot perform transfer.")

        source.balance -= amount
        destination.balance += amount

    def get_recurring_transfer(self, id):
        """Gets a recurring transfer based on its ID."""
        return self.recurring_transfers[id]

    def list_recurring_transfers(self):
        """Produces a list of all recurring transfers."""
        return self.recurring_transfers.values()

    def create_recurring_transfer(self, author, source, destination, total_amount, tick_count):
        """Creates and registers a new recurring transfer, i.e., a transfer that is spread out over
           many ticks. The transfer is authorized by `author` and consists of `total_amount` being
           transferred from `source` to `destination` over the course of `tick_count` ticks. A tick
           is a server-defined timespan."""
        rec_transfer = InMemoryRecurringTransfer(author, source, destination, total_amount, tick_count, total_amount)
        self.recurring_transfers[rec_transfer.get_id()] = rec_transfer
        return rec_transfer

    def notify_tick_elapsed(self):
        """Notifies the server that a tick has elapsed."""
        finished_transfers = set()
        for id in self.recurring_transfers:
            transfer = self.recurring_transfers[id]
            per_tick = transfer.get_total_amount() // transfer.get_tick_count()
            if transfer.get_remaining_amount() <= 0:
                finished_transfers.add(id)
            elif transfer.get_remaining_amount() >= per_tick:
                if self.can_transfer(transfer.get_source(), transfer.get_destination(), per_tick):
                    self.perform_recurring_transfer(transfer, per_tick)
            else:
                remaining = transfer.get_total_amount() % per_tick
                if self.can_transfer(transfer.get_source(), transfer.get_destination(), remaining):
                    self.perform_recurring_transfer(transfer, remaining)

        # Delete finished transfers.
        for id in finished_transfers:
            del self.recurring_transfers[id]

    def perform_recurring_transfer(self, transfer, amount):
        self.transfer(
            transfer.get_author(),
            transfer.get_source(),
            transfer.get_destination(), amount)
        transfer.remaining_amount -= amount


class InMemoryAccount(Account):
    """An in-memory account data structure."""

    def __init__(self, account_uuid=None):
        """Initializes an in-memory account."""
        self.uuid = account_uuid if account_uuid is not None else str(
            uuid.uuid4())
        self.balance = 0
        self.frozen = False
        self.auth = Authorization.CITIZEN

    def get_uuid(self):
        """Gets this account's unique identifier."""
        return self.uuid

    def get_balance(self):
        """Gets the balance on this account."""
        return self.balance

    def is_frozen(self):
        """Tells if this account is frozen."""
        return self.frozen

    def get_authorization(self):
        """Gets this account's level of authorization."""
        return self.auth


class InMemoryRecurringTransfer(RecurringTransfer):
    """An in-memory description of a recurring transfer."""

    def __init__(self, author, source, destination, total_amount, tick_count, remaining_amount, transfer_id=None):
        """Initializes an in-memory recurring transfer."""
        self.uuid = transfer_id if transfer_id is not None else str(
            uuid.uuid4())
        self.author = author
        self.source = source
        self.destination = destination
        self.total_amount = total_amount
        self.tick_count = tick_count
        self.remaining_amount = remaining_amount

    def get_id(self):
        """Gets this transfer's ID."""
        return self.uuid

    def get_author(self):
        """Gets the account that authorized the transfer."""
        return self.author

    def get_source(self):
        """Gets the account from which the money originates."""
        return self.source

    def get_destination(self):
        """Gets the account to which the money must go."""
        return self.destination

    def get_tick_count(self):
        """Gets the number of ticks over the course of which the transfer must complete."""
        return self.tick_count

    def get_total_amount(self):
        """Gets the total amount to transfer."""
        return self.total_amount

    def get_remaining_amount(self):
        """Gets the remaining amount to transfer."""
        return self.remaining_amount


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
                    self.get_account(elems[3]),
                    int(elems[4]))
            elif cmd == 'authorize':
                super().authorize(
                    self.get_account(elems[1]),
                    self.get_account(elems[2]),
                    Authorization[elems[3]])
            elif cmd == 'add-balance':
                self.get_account(elems[1]).balance += int(elems[2])
            elif cmd == 'perform-recurring-transfer':
                super().perform_recurring_transfer(
                    self.get_recurring_transfer(elems[1]),
                    int(elems[2]))
            elif cmd == 'create-recurring-transfer':
                rec_transfer = super().create_recurring_transfer(
                    self.get_account(elems[1]),
                    self.get_account(elems[2]),
                    self.get_account(elems[3]),
                    int(elems[4]),
                    int(elems[5]))
                rec_transfer.uuid = elems[6]
            else:
                raise Exception("Unknown ledger command '%s'." % cmd)

    def _ledger_write(self, *args):
        self.ledger_file.writelines(
            ' '.join([str(time.time())] + list(map(str, args))) + '\n')

    def open_account(self, id, account_uuid=None):
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        account = super().open_account(id, account_uuid)
        self._ledger_write('open', id, account.get_uuid())
        return account

    def authorize(self, author, account, auth_level):
        """Makes `author` set `account`'s authorization level to `auth_level`."""
        result = super().authorize(author, account, auth_level)
        self._ledger_write(
            'authorize',
            self.get_account_id(author),
            self.get_account_id(account),
            auth_level.name)
        return result

    def transfer(self, author, source, destination, amount):
        """Transfers a particular amount of money from one account on this server to another on
           the authority of `author`. `author`, `destination` and `amount` are `Account` objects.
           This action must not complete successfully if the transfer cannot be performed."""
        result = super().transfer(source, author, destination, amount)
        self._ledger_write(
            'transfer',
            self.get_account_id(author),
            self.get_account_id(source),
            self.get_account_id(destination),
            amount)
        return result

    def create_recurring_transfer(self, author, source, destination, total_amount, tick_count):
        """Creates and registers a new recurring transfer, i.e., a transfer that is spread out over
           many ticks. The transfer is authorized by `author` and consists of `total_amount` being
           transferred from `source` to `destination` over the course of `tick_count` ticks. A tick
           is a server-defined timespan."""
        rec_transfer = super().create_recurring_transfer(author, source, destination, total_amount, tick_count)
        self._ledger_write(
            'create-recurring-transfer',
            self.get_account_id(author),
            self.get_account_id(source),
            self.get_account_id(destination),
            total_amount,
            tick_count,
            rec_transfer.get_id())
        return rec_transfer

    def perform_recurring_transfer(self, transfer, amount):
        super().perform_recurring_transfer(transfer, amount)
        self._ledger_write(
            'perform-recurring-transfer',
            transfer.get_id(),
            amount)


# TODO: import the backend.
backend = None


class BackendServer(Server):
    """A server implementation that calls into Mobil's backend."""

    def __init__(self, server_id):
        """Initializes a backend server."""
        self.server_id = server_id

    def open_account(self, id, account_uuid=None):
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        return BackendCitizenAccount(self.server_id, backend.add_account(id, id, self.server_id, True))

    def get_account(self, id):
        """Gets the account that matches an ID. Raises an exception if there is no such account."""
        return BackendCitizenAccount(self.server_id, id)

    def get_account_id(self, account):
        """Gets an account's local ID. Raises an exception if the account is not registered here."""
        return account.account_id if isinstance(account, BackendCitizenAccount) else "@government"

    def has_account(self, id):
        """Tests if an account with a particular ID exists on this server."""
        return backend.account_exists(id, self.server_id)

    def get_government_account(self):
        """Gets the main government account for this server."""
        return BackendGovernmentAccount(self.server_id)

    def list_accounts(self):
        """Lists all accounts on this server."""
        return [self.get_government_account()] + [self.get_account(id) for id in backend.list_accounts(self.server_id)]

    def authorize(self, author, account, auth_level):
        """Makes `author` set `account`'s authorization level to `auth_level`."""
        # FIXME: imperfect match with Mobil's backend API.
        if auth_level.value > Authorization.CITIZEN:
            backend.add_local_admin(account.account_id, self.server_id)

    def transfer(self, author, source, destination, amount):
        """Transfers a particular amount of money from one account on this server to another on
           the authority of `author`. `author`, `destination` and `amount` are `Account` objects.
           This action must not complete successfully if the transfer cannot be performed."""
        if not self.can_transfer(source, destination, amount):
            raise Exception("Cannot perform transfer.")

        return backend.money_transfer(source.account_id, destination.account_id, amount, self.server_id, False)


class BackendCitizenAccount(Account):
    """An citizen account implementation that calls into Mobil's backend."""

    def __init__(self, server_id, account_id):
        """Creates a backend account."""
        self.server_id = server_id
        self.account_id = account_id

    def get_uuid(self):
        """Gets this account's unique identifier."""
        return backend.id_to_uuid(self.account_id)

    def get_balance(self):
        """Gets the balance on this account."""
        return backend.get_account_balance(self.account_id, self.server_id)

    def is_frozen(self):
        """Tells if this account is frozen."""
        return backend.is_locked(self.account_id, self.server_id)

    def get_authorization(self):
        """Gets this account's level of authorization."""
        return backend.auth_level(self.account_id, self.server_id)


class BackendGovernmentAccount(Account):
    """An government account implementation that calls into Mobil's backend."""

    def __init__(self, server_id):
        self.server_id = server_id

    def get_uuid(self):
        """Gets this account's unique identifier."""
        raise NotImplementedError()

    def get_balance(self):
        """Gets the balance on this account."""
        return backend.get_govt_balance(self.server_id)

    def is_frozen(self):
        """Tells if this account is frozen."""
        return False

    def get_authorization(self):
        """Gets this account's level of authorization."""
        return Authorization.CITIZEN
