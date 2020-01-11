import uuid
import time
import os.path
import random
import base64
from collections import defaultdict
from enum import Enum
from typing import List
from Crypto.Hash import SHA3_256
from Crypto.PublicKey import ECC


class AccountId(object):
    """A base class for account identifiers."""

    def __str__(self) -> str:
        """Turns the account ID into a machine-readable string."""
        raise NotImplementedError()

    def readable(self) -> str:
        """Turns the account ID into a human-readable string suitable for
           communication with humans."""
        return str(self)

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(str(self))

    def __lt__(self, other):
        return str(self) < str(other)

    def __le__(self, other):
        return str(self) <= str(other)

    def __ge__(self, other):
        return str(self) >= str(other)

    def __gt__(self, other):
        return str(self) > str(other)


class RedditAccountId(AccountId):
    """An account identifier for Reddit accounts."""
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


class DiscordAccountId(AccountId):
    """An account identifier for Discord mentions."""
    def __init__(self, discord_id):
        self.discord_id = discord_id

    def readable(self):
        return '<@%s>' % self.discord_id

    def __str__(self):
        return 'discord/%s' % self.discord_id


def parse_account_id(value: str) -> AccountId:
    """Parses an account ID."""
    if value.startswith("<@") and value.endswith(">"):
        if value.startswith("<@!"):
            return DiscordAccountId(value[value.index("!") + 1 : -1])
        else:
            return DiscordAccountId(value[value.index("@") + 1 : -1])
    elif value.startswith('discord/'):
        return DiscordAccountId(value[len('discord/'):])
    else:
        return RedditAccountId(value)


class Authorization(Enum):
    """Defines various levels of authorization for account."""
    CITIZEN = 0
    ADMIN = 1
    DEVELOPER = 2


class Account(object):
    """An account. Every account has globally unique ID. Additionally, servers have one server-local ID
       per account on the server."""

    def get_uuid(self) -> str:
        """Gets this account's unique identifier."""
        raise NotImplementedError()

    def get_balance(self) -> int:
        """Gets the balance on this account."""
        raise NotImplementedError()

    def is_frozen(self) -> bool:
        """Tells if this account is frozen."""
        raise NotImplementedError()

    def get_authorization(self) -> Authorization:
        """Gets this account's level of authorization."""
        raise NotImplementedError()

    def list_public_keys(self):
        """Produces a list of all public keys associated with this account.
           Every element of the list is a string that corresponds to the contents
           of a PEM file describing an ECC key."""
        raise NotImplementedError()


class RecurringTransfer(object):
    """A recurring transfer."""

    def get_id(self) -> str:
        """Gets the ID for the transfer."""
        raise NotImplementedError()

    def get_author(self) -> Account:
        """Gets the account that authorized the transfer."""
        raise NotImplementedError()

    def get_source(self) -> Account:
        """Gets the account from which the money originates."""
        raise NotImplementedError()

    def get_destination(self) -> Account:
        """Gets the account to which the money must go."""
        raise NotImplementedError()

    def get_tick_count(self) -> int:
        """Gets the number of ticks over the course of which the transfer must complete."""
        raise NotImplementedError()

    def get_total_amount(self) -> int:
        """Gets the total amount to transfer."""
        raise NotImplementedError()

    def get_remaining_amount(self) -> int:
        """Gets the remaining amount to transfer."""
        raise NotImplementedError()

    def get_transferred_amount(self) -> int:
        """Gets the amount of money that has already been transferred."""
        return self.get_total_amount() - self.get_remaining_amount()


class Server(object):
    """A server manages a number of accounts that all have the same currency."""

    def open_account(self, id: AccountId, account_uuid=None) -> Account:
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        raise NotImplementedError()

    def add_account_alias(self, account: Account, alias_id: AccountId):
        """Associates an additional ID with an account."""
        raise NotImplementedError()

    def get_account(self, id: AccountId) -> Account:
        """Gets the account that matches an ID. Raises an exception if there is no such account."""
        raise NotImplementedError()

    def get_account_from_string(self, id: str) -> Account:
        """Gets the account that matches a string ID. Raises an exception if there is no such account."""
        return self.get_account(parse_account_id(id))

    def get_account_ids(self, account: Account) -> List[AccountId]:
        """Gets an account's local IDs. Raises an exception if the account is not registered here."""
        raise NotImplementedError()

    def get_account_id(self, account: Account) -> AccountId:
        """Gets a representative local account ID. Raises an exception if the account is not registered here."""
        return self.get_account_ids(account)[0]

    def has_account(self, id: AccountId) -> bool:
        """Tests if an account with a particular ID exists on this server."""
        raise NotImplementedError()

    def get_government_account(self) -> Account:
        """Gets the main government account for this server."""
        raise NotImplementedError()

    def list_accounts(self):
        """Lists all accounts on this server."""
        raise NotImplementedError()

    def authorize(self, author: Account, account: Account, auth_level: Authorization):
        """Makes `author` set `account`'s authorization level to `auth_level`."""
        raise NotImplementedError()

    def set_frozen(self, author: Account, account: Account, is_frozen: bool):
        """Freezes or unfreezes `account` on the authority of `author`."""
        raise NotImplementedError()

    def print_money(self, author: Account, account: Account, amount: int):
        """Prints `amount` of money on the authority of `author` and deposits it in `account`."""
        raise NotImplementedError()

    def add_public_key(self, account: Account, key):
        """Associates a public key with an account. The key must be an ECC key."""
        raise NotImplementedError()

    def get_recurring_transfer(self, id: str) -> RecurringTransfer:
        """Gets a recurring transfer based on its ID."""
        raise NotImplementedError()

    def list_recurring_transfers(self):
        """Produces a list of all recurring transfers."""
        raise NotImplementedError()

    def create_recurring_transfer(
        self,
        author: Account,
        source: Account,
        destination: Account,
        total_amount: int,
        tick_count: int) -> RecurringTransfer:
        """Creates and registers a new recurring transfer, i.e., a transfer that is spread out over
           many ticks. The transfer is authorized by `author` and consists of `total_amount` being
           transferred from `source` to `destination` over the course of `tick_count` ticks. A tick
           is a server-defined timespan."""
        raise NotImplementedError()

    def notify_tick_elapsed(self, tick_timestamp=None):
        """Notifies the server that a tick has elapsed."""
        raise NotImplementedError()

    def transfer(self, author: Account, source: Account, destination: Account, amount: int):
        """Transfers a particular amount of money from one account on this server to another on
           the authority of `author`. `author`, `destination` and `amount` are `Account` objects.
           This action must not complete successfully if the transfer cannot be performed."""
        raise NotImplementedError()

    def can_transfer(self, source: Account, destination: Account, amount: int) -> bool:
        """Tells if a particular amount of money can be transferred from one account on this
           server to another. `destination` and `amount` are both `Account` objects."""
        return amount > 0 and \
            source.get_balance() - amount >= 0 and \
            not source.is_frozen() and \
            not destination.is_frozen()


class InMemoryServer(Server):
    """A server that maintains accounts in memory. Nothing is persistent.
       This server implementation can be used to implement more sophisticated
       (persistent) servers."""

    def __init__(self):
        self.accounts = {}
        self.inv_accounts = defaultdict(list)
        self.gov_account = InMemoryServer.open_account(self, "@government")
        self.gov_account.auth = Authorization.DEVELOPER
        self.recurring_transfers = {}

    def open_account(self, id: AccountId, account_uuid=None):
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        if self.has_account(id):
            raise Exception("Account already exists.")

        account = InMemoryAccount(account_uuid)
        self.accounts[id] = account
        self.inv_accounts[account].append(id)
        return account

    def add_account_alias(self, account: Account, alias_id: AccountId):
        """Associates an additional ID with an account."""
        self.accounts[alias_id] = account
        self.inv_accounts[account].append(alias_id)

    def get_account(self, id: AccountId) -> Account:
        """Gets the account that matches an ID. Raises an exception if there is no such account."""
        return self.accounts[id]

    def get_account_ids(self, account: Account) -> List[AccountId]:
        """Gets an account's local IDs. Raises an exception if the account is not registered here."""
        return self.inv_accounts[account]

    def has_account(self, id):
        """Tests if an account with a particular ID exists on this server."""
        return id in self.accounts

    def get_government_account(self):
        """Gets the main government account for this server."""
        return self.gov_account

    def list_accounts(self):
        """Lists all accounts on this server."""
        unique_accounts = set(self.accounts.values())
        return sorted(unique_accounts, key=lambda account: str(self.get_account_id(account)))

    def authorize(self, author: Account, account: Account, auth_level: Authorization):
        """Makes `author` set `account`'s authorization level to `auth_level`."""
        account.auth = auth_level

    def set_frozen(self, author: Account, account: Account, is_frozen: bool):
        """Freezes or unfreezes `account` on the authority of `author`."""
        account.frozen = is_frozen

    def add_public_key(self, account: Account, key):
        """Associates a public key with an account. The key must be an ECC key."""
        account.public_keys.append(key)

    def print_money(self, author: Account, account: Account, amount: int):
        """Prints `amount` of money on the authority of `author` and deposits it in `account`."""
        account.balance += amount

    def transfer(self, author: Account, source: Account, destination: Account, amount: int):
        """Transfers a particular amount of money from one account on this server to another on
           the authority of `author`. `author`, `destination` and `amount` are `Account` objects.
           This action must not complete successfully if the transfer cannot be performed."""
        if not self.can_transfer(source, destination, amount):
            raise Exception("Cannot perform transfer.")

        source.balance -= amount
        destination.balance += amount

    def get_recurring_transfer(self, id: str):
        """Gets a recurring transfer based on its ID."""
        return self.recurring_transfers[id]

    def list_recurring_transfers(self):
        """Produces a list of all recurring transfers."""
        return self.recurring_transfers.values()

    def create_recurring_transfer(self, author, source, destination, total_amount, tick_count, transfer_id=None):
        """Creates and registers a new recurring transfer, i.e., a transfer that is spread out over
           many ticks. The transfer is authorized by `author` and consists of `total_amount` being
           transferred from `source` to `destination` over the course of `tick_count` ticks. A tick
           is a server-defined timespan."""
        rec_transfer = InMemoryRecurringTransfer(author, source, destination, total_amount, tick_count, total_amount, transfer_id)
        self.recurring_transfers[rec_transfer.get_id()] = rec_transfer
        return rec_transfer

    def notify_tick_elapsed(self, tick_timestamp=None):
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
        InMemoryServer.transfer(
            self,
            transfer.get_author(),
            transfer.get_source(),
            transfer.get_destination(),
            amount)
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
        self.public_keys = []

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

    def list_public_keys(self):
        """Produces a list of all public keys associated with this account.
           Every element of the list is an ECC key."""
        return self.public_keys


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

def compute_hash(previous_hash, elements):
    """Computes the SHA3-256 hash digest of a previous hash and a list of strings."""
    hash_obj = SHA3_256.new(previous_hash)
    for item in elements:
        hash_obj.update(item.encode('utf-8'))
    return hash_obj

def generate_salt_and_hash(previous_hash, elements, zero_count):
    """Generates a salt, hash pair with the appropriate number of leading zeros."""
    while True:
        salt = str(random.randint(1, 1000000))
        hash_obj = SHA3_256.new(previous_hash)
        hash_obj.update(salt.encode('utf-8'))
        for item in elements:
            hash_obj.update(item.encode('utf-8'))
        if has_leading_zeros(hash_obj.hexdigest(), zero_count):
            return (salt, hash_obj)

def has_leading_zeros(hexdigest, zero_count):
    """Checks if a hex digest has at least `zero_count` leading zero bits."""
    i = 0
    for _ in range(zero_count // 4):
        if hexdigest[i] != '0':
            return False
        i += 1

    rem = zero_count % 4
    if rem > 0:
        digit = int(hexdigest[i], 16)
        if rem == 1:
            return digit < 8
        elif rem == 2:
            return digit < 4
        elif rem == 3:
            return digit < 2

    return True

def create_initial_ledger_entries(entries, leading_zero_count=12):
    """Creates an initial ledger by annotating hashless ledger entries with hashes and salts.
       `entries` is a list of unannotated ledger lines. A modified list of ledger lines is returned."""
    last_hash = b''
    results = []
    for line in entries:
        elems = line.split()
        salt, line_hash = generate_salt_and_hash(last_hash, elems, leading_zero_count)
        results.append(' '.join([line_hash.hexdigest(), salt] + elems))
        last_hash = line_hash.digest()

    return results

def create_initial_ledger(unannotated_ledger_path, result_path, leading_zero_count=12):
    """Creates an initial ledger by reading the unannotated ledger at `unannoted_ledger_path`,
       annotating every line with a hash and a salt and then writing the result to
       `result_path`."""
    with open(unannotated_ledger_path, 'r') as f:
        lines = f.readlines()

    lines = create_initial_ledger_entries(lines, leading_zero_count)

    with open(result_path, 'w') as f:
        f.writelines(line + '\n' for line in lines)


class LedgerServer(InMemoryServer):
    """A server implementation that logs every action in a ledger.
       The ledger can be read to reconstruct the state of the server."""

    def __init__(self, ledger_path, leading_zero_count=12):
        """Initializes a ledger-based server."""
        super().__init__()
        self.last_tick_timestamp = time.time()
        self.last_hash = b''
        self.ledger_path = ledger_path
        self.leading_zero_count = leading_zero_count
        if os.path.isfile(ledger_path):
            self._read_ledger(ledger_path)
        self.ledger_file = open(ledger_path, 'a')

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        """Closes the server's underlying ledger file."""
        self.ledger_file.close()

    def _read_ledger(self, ledger_path):
        """Reads a ledger at a particular path."""
        with open(ledger_path, 'r') as f:
            lines = f.readlines()
            f.close()

        for line_num, line in enumerate(lines):
            if line.isspace() or line == '':
                continue

            elems = line.split()
            hash_value = elems[0]
            expected_hash = compute_hash(self.last_hash, elems[1:])

            if expected_hash.hexdigest() != hash_value:
                raise Exception(
                    "Line %s: ledger hash value %s for '%s' does not match expected hash value %s." % (
                        line_num + 1, hash_value, ' '.join(elems[1:]), expected_hash.hexdigest()))
            elif not has_leading_zeros(hash_value, self.leading_zero_count):
                raise Exception(
                    "Line %s: hash value does not have at least %s leading zeros." % (
                        line_num + 1, self.leading_zero_count))

            self.last_hash = expected_hash.digest()

            timestamp = float(elems[2])
            elems = elems[3:]
            cmd = elems[0]
            if cmd == 'open':
                super().open_account(elems[1], elems[2])
            elif cmd == 'transfer':
                super().transfer(
                    self.get_account_from_string(elems[1]),
                    self.get_account_from_string(elems[2]),
                    self.get_account_from_string(elems[3]),
                    int(elems[4]))
            elif cmd == 'authorize':
                super().authorize(
                    self.get_account_from_string(elems[1]),
                    self.get_account_from_string(elems[2]),
                    Authorization[elems[3]])
            elif cmd == 'set-frozen':
                super().set_frozen(
                    self.get_account_from_string(elems[1]),
                    self.get_account_from_string(elems[2]),
                    elems[3] == 'True')
            elif cmd == 'print-money':
                super().print_money(
                    self.get_account_from_string(elems[1]),
                    self.get_account_from_string(elems[2]),
                    int(elems[3]))
            elif cmd == 'perform-recurring-transfer':
                super().perform_recurring_transfer(
                    self.get_recurring_transfer(elems[1]),
                    int(elems[2]))
            elif cmd == 'create-recurring-transfer':
                rec_transfer = super().create_recurring_transfer(
                    self.get_account_from_string(elems[1]),
                    self.get_account_from_string(elems[2]),
                    self.get_account_from_string(elems[3]),
                    int(elems[4]),
                    int(elems[5]),
                    elems[6])
            elif cmd == 'add-public-key':
                key = base64.b64decode(elems[2]).decode('utf-8')
                super().add_public_key(
                    self.get_account_from_string(elems[1]),
                    ECC.import_key(key))
            elif cmd == 'add-alias':
                super().add_account_alias(
                    self.get_account_from_string(elems[1]),
                    parse_account_id(elems[2]))
            elif cmd == 'tick':
                self.last_tick_timestamp = timestamp
            else:
                raise Exception("Unknown ledger command '%s'." % cmd)

    def _ledger_write(self, *args, t=None):
        if t is None:
            t = time.time()
        elems = [str(t)] + list(map(str, args))
        salt, new_hash = generate_salt_and_hash(self.last_hash, elems, self.leading_zero_count)
        with open(self.ledger_path, 'a') as f:
            f.writelines(' '.join([new_hash.hexdigest(), salt] + elems) + '\n')
            f.close()
        self.last_hash = new_hash.digest()
        return t

    def open_account(self, id, account_uuid=None):
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        account = super().open_account(id, account_uuid)
        self._ledger_write('open', id, account.get_uuid())
        return account

    def add_account_alias(self, account: Account, alias_id: AccountId):
        """Associates an additional ID with an account."""
        super().add_account_alias(account, alias_id)
        self._ledger_write(
            'add-alias',
            self.get_account_id(account),
            alias_id)

    def authorize(self, author, account, auth_level):
        """Makes `author` set `account`'s authorization level to `auth_level`."""
        result = super().authorize(author, account, auth_level)
        self._ledger_write(
            'authorize',
            self.get_account_id(author),
            self.get_account_id(account),
            auth_level.name)
        return result

    def set_frozen(self, author: Account, account: Account, is_frozen: bool):
        """Freezes or unfreezes `account` on the authority of `author`."""
        super().set_frozen(author, account, is_frozen)
        self._ledger_write(
            'set-frozen',
            self.get_account_id(author),
            self.get_account_id(account),
            is_frozen)

    def add_public_key(self, account, key):
        """Associates a public key with an account. The key must be an ECC key."""
        super().add_public_key(account, key)
        self._ledger_write(
            'add-public-key',
            self.get_account_id(account),
            base64.b64encode(key.export_key(format='PEM').encode('utf-8')).decode('utf-8'))

    def print_money(self, author, account, amount):
        """Prints `amount` of money on the authority of `author` and deposits it in `account`."""
        super().print_money(author, account, amount)
        self._ledger_write(
            'print-money',
            self.get_account_id(author),
            self.get_account_id(account),
            amount)

    def transfer(self, author, source, destination, amount):
        """Transfers a particular amount of money from one account on this server to another on
           the authority of `author`. `author`, `destination` and `amount` are `Account` objects.
           This action must not complete successfully if the transfer cannot be performed."""
        result = super().transfer(author, source, destination, amount)
        self._ledger_write(
            'transfer',
            self.get_account_id(author),
            self.get_account_id(source),
            self.get_account_id(destination),
            amount)
        return result

    def notify_tick_elapsed(self, tick_timestamp=None):
        """Notifies the server that a tick has elapsed."""
        super().notify_tick_elapsed()
        self.last_tick_timestamp = self._ledger_write('tick', t=tick_timestamp)

    def create_recurring_transfer(self, author, source, destination, total_amount, tick_count, transfer_id=None):
        """Creates and registers a new recurring transfer, i.e., a transfer that is spread out over
           many ticks. The transfer is authorized by `author` and consists of `total_amount` being
           transferred from `source` to `destination` over the course of `tick_count` ticks. A tick
           is a server-defined timespan."""
        rec_transfer = super().create_recurring_transfer(author, source, destination, total_amount, tick_count, transfer_id)
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

    def get_account(self, id) -> Account:
        """Gets the account that matches an ID. Raises an exception if there is no such account."""
        return BackendCitizenAccount(self.server_id, id)

    def get_account_ids(self, account):
        """Gets an account's local IDs. Raises an exception if the account is not registered here."""
        return [account.account_id if isinstance(account, BackendCitizenAccount) else "@government"]

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
