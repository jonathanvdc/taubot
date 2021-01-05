import uuid
import time
import os.path
import random
import base64

# sqlalchemy stuff
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import String, Integer, Boolean, Column, ForeignKey, Float, DateTime, JSON
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.types import CHAR
from sqlalchemy.sql import func

from fractions import Fraction
from functools import total_ordering
from collections import defaultdict
from enum import Enum
from typing import List, Union, Dict, Any
from Crypto.Hash import SHA3_256
from Crypto.PublicKey import ECC

Base = declarative_base()
Session = sessionmaker()
DEFAULT = sqlalchemy.text("default")


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
    """An account identifier type for Reddit accounts."""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __repr__(self):
        return 'RedditAccountId(%r)' % self.value


class DiscordAccountId(AccountId):
    """An account identifier type for Discord mentions."""

    def __init__(self, discord_id):
        self.discord_id = discord_id

    def readable(self):
        return '<@%s>' % self.discord_id

    def __str__(self):
        return 'discord/%s' % self.discord_id

    def __repr__(self):
        return 'DiscordAccountId(%r)' % self.discord_id


class ProxyAccountId(AccountId):
    """An account identifier type for proxy account accesses."""

    def __init__(self, proxy_id, proxied_id):
        """Creates a proxy account identifier."""
        self.proxy_id = proxy_id
        self.proxied_id = proxied_id

    def readable(self):
        return '%s (by proxy: %s)' % (self.proxied_id, self.proxy_id)

    def __str__(self):
        return '%s:%s' % (self.proxy_id, self.proxied_id)

    def __repr__(self):
        return 'ProxyAccountId(%r, %r)' % (self.proxy_id, self.proxied_id)


def parse_atomic_account_id(value: str) -> AccountId:
    """Parses a non-proxy account ID."""
    if value.startswith("<@") and value.endswith(">"):
        if value.startswith("<@!"):
            return DiscordAccountId(value[value.index("!") + 1: -1])
        else:
            return DiscordAccountId(value[value.index("@") + 1: -1])
    elif value.startswith('discord/'):
        return DiscordAccountId(value[len('discord/'):])
    else:
        return RedditAccountId(value)


def parse_account_id(value: Union[str, AccountId]) -> AccountId:
    """Parses an account ID."""
    if isinstance(value, AccountId):
        return value

    elems = value.split(':')
    result = parse_atomic_account_id(elems[-1])
    for proxy in reversed(elems[:-1]):
        result = ProxyAccountId(parse_atomic_account_id(proxy), result)

    return result


def unwrap_proxies(account_id: AccountId) -> AccountId:
    """Unwraps proxy account identifiers, if any, to find the account that
       actually performed a transaction."""
    if isinstance(account_id, ProxyAccountId):
        return unwrap_proxies(account_id.proxied_id)
    else:
        return account_id


@total_ordering
class Authorization(Enum):
    """Defines various levels of authorization for account."""
    CITIZEN = 0
    OFFICER = 1
    ADMIN = 2
    DEVELOPER = 3

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplementedError


class BaseAccount(object):
    """An account. Every account has globally unique ID. Additionally, servers have one server-local ID
       per account on the server."""

    def get_uuid(self) -> str:
        """Gets this account's unique identifier."""
        raise NotImplementedError()

    def get_balance(self) -> Fraction:
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

    def get_proxies(self):
        """Gets all accounts that have been authorized as proxies for this account."""
        raise NotImplementedError()


class RecurringTransfer(object):
    """A recurring transfer."""

    def get_id(self) -> str:
        """Gets the ID for the transfer."""
        raise NotImplementedError()

    def get_author(self) -> BaseAccount:
        """Gets the account that authorized the transfer."""
        raise NotImplementedError()

    def get_source(self) -> BaseAccount:
        """Gets the account from which the money originates."""
        raise NotImplementedError()

    def get_destination(self) -> BaseAccount:
        """Gets the account to which the money must go."""
        raise NotImplementedError()

    def get_tick_count(self) -> int:
        """Gets the number of ticks over the course of which the transfer must complete."""
        raise NotImplementedError()

    def get_total_amount(self) -> Fraction:
        """Gets the total amount to transfer."""
        raise NotImplementedError()

    def get_remaining_amount(self) -> Fraction:
        """Gets the remaining amount to transfer."""
        raise NotImplementedError()

    def get_transferred_amount(self) -> Fraction:
        """Gets the amount of money that has already been transferred."""
        return self.get_total_amount() - self.get_remaining_amount()


class Server(object):
    """A server manages a number of accounts that all have the same currency."""

    def open_account(self, id: AccountId, account_uuid=None) -> BaseAccount:
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        raise NotImplementedError()

    def add_account_alias(self, account: BaseAccount, alias_id: AccountId):
        """Associates an additional ID with an account."""
        raise NotImplementedError()

    def get_account(self, id: AccountId) -> BaseAccount:
        """Gets the account that matches an ID. Raises an exception if there is no such account."""
        raise NotImplementedError()

    def get_accounts(self) -> List[BaseAccount]:
        """Gets a list of all accounts on this server."""
        raise NotImplementedError()

    def get_account_from_string(self, id: str) -> BaseAccount:
        """Gets the account that matches a string ID. Raises an exception if there is no such account."""
        return self.get_account(parse_account_id(id))

    def get_account_ids(self, account: BaseAccount) -> List[AccountId]:
        """Gets an account's local IDs. Raises an exception if the account is not registered here."""
        raise NotImplementedError()

    def get_account_id(self, account: BaseAccount) -> AccountId:
        """Gets a representative local account ID. Raises an exception if the account is not registered here."""
        return self.get_account_ids(account)[0]

    def has_account(self, id: AccountId) -> bool:
        """Tests if an account with a particular ID exists on this server."""
        raise NotImplementedError()

    def get_government_account(self) -> BaseAccount:
        """Gets the main government account for this server."""
        raise NotImplementedError()

    def list_accounts(self) -> List[BaseAccount]:
        """Lists all accounts on this server."""
        raise NotImplementedError()

    def authorize(self, author: AccountId, account: BaseAccount, auth_level: Authorization):
        """Makes `author` set `account`'s authorization level to `auth_level`."""
        raise NotImplementedError()

    def set_frozen(self, author: AccountId, account: BaseAccount, is_frozen: bool):
        """Freezes or unfreezes `account` on the authority of `author`."""
        raise NotImplementedError()

    def print_money(self, author: AccountId, account: BaseAccount, amount: Fraction):
        """Prints `amount` of money on the authority of `author` and deposits it in `account`."""
        raise NotImplementedError()

    def add_public_key(self, account: BaseAccount, key):
        """Associates a public key with an account. The key must be an ECC key."""
        raise NotImplementedError()

    def add_proxy(self, author: AccountId, account: BaseAccount, proxied_account: BaseAccount):
        """Makes `account` a proxy for `proxied_account`."""
        raise NotImplementedError()

    def remove_proxy(self, author: AccountId, account: BaseAccount, proxied_account: BaseAccount) -> bool:
        """Ensures that `account` is not a proxy for `proxied_account`. Returns
           `False` is `account` was not a proxy for `procied_account`;
           otherwise, `True`."""
        raise NotImplementedError()

    def get_recurring_transfer(self, id: str) -> RecurringTransfer:
        """Gets a recurring transfer based on its ID."""
        raise NotImplementedError()

    def list_recurring_transfers(self):
        """Produces a list of all recurring transfers."""
        raise NotImplementedError()

    def create_recurring_transfer(
            self,
            author: AccountId,
            source: BaseAccount,
            destination: BaseAccount,
            total_amount: Fraction,
            tick_count: int) -> RecurringTransfer:
        """Creates and registers a new recurring transfer, i.e., a transfer that is spread out over
           many ticks. The transfer is authorized by `author` and consists of `total_amount` being
           transferred from `source` to `destination` over the course of `tick_count` ticks. A tick
           is a server-defined timespan."""
        raise NotImplementedError()

    def notify_tick_elapsed(self, tick_timestamp=None):
        """Notifies the server that a tick has elapsed."""
        raise NotImplementedError()

    def transfer(self, author: AccountId, source: BaseAccount, destination: BaseAccount, amount: Fraction):
        """Transfers a particular amount of money from one account on this server to another on
           the authority of `author`. `author`, `destination` and `amount` are `Account` objects.
           This action must not complete successfully if the transfer cannot be performed."""
        raise NotImplementedError()

    def can_transfer(self, source: BaseAccount, destination: BaseAccount, amount: Fraction) -> bool:
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

    def delete_account(self, author: AccountId, id: AccountId):
        if self.has_account(id):
            account = self.accounts[id]
            to_be_deleted = []
            for rec_transfer in self.recurring_transfers:
                if self.recurring_transfers[rec_transfer].get_destination() == account or self.recurring_transfers[
                    rec_transfer].get_source() == account:
                    to_be_deleted.append(rec_transfer)

            for key in to_be_deleted:
                del self.recurring_transfers[key]

            del self.accounts[id]
            del self.inv_accounts[account][0]

            return True

    def add_account_alias(self, account: BaseAccount, alias_id: AccountId):
        """Associates an additional ID with an account."""
        self.accounts[alias_id] = account
        self.inv_accounts[account].append(alias_id)

    def get_account(self, id: AccountId) -> BaseAccount:
        """Gets the account that matches an ID. Raises an exception if there is no such account."""
        return self.accounts[unwrap_proxies(id)]

    def get_accounts(self) -> List[BaseAccount]:
        """Gets a list of all accounts on this server."""
        return list(set(self.accounts.values()))

    def get_account_ids(self, account: BaseAccount) -> List[AccountId]:
        """Gets an account's local IDs. Raises an exception if the account is not registered here."""
        return self.inv_accounts[account]

    def has_account(self, id):
        """Tests if an account with a particular ID exists on this server."""
        return unwrap_proxies(id) in self.accounts

    def get_government_account(self):
        """Gets the main government account for this server."""
        return self.gov_account

    def list_accounts(self):
        """Lists all accounts on this server."""
        unique_accounts = set(self.get_accounts())
        return sorted(unique_accounts, key=lambda account: str(self.get_account_id(account)))

    def mark_public(self, author: AccountId, account: BaseAccount, new_public: bool):
        """Sets account.public to new_public"""
        account.public = new_public

    def authorize(self, author: AccountId, account: BaseAccount, auth_level: Authorization):
        """Makes `author` set `account`'s authorization level to `auth_level`."""
        account.auth = auth_level

    def set_frozen(self, author: AccountId, account: BaseAccount, is_frozen: bool):
        """Freezes or unfreezes `account` on the authority of `author`."""
        account.frozen = is_frozen

    def add_public_key(self, account: BaseAccount, key):
        """Associates a public key with an account. The key must be an ECC key."""
        account.public_keys.append(key)

    def add_proxy(self, author: AccountId, account: BaseAccount, proxied_account: BaseAccount):
        """Makes `account` a proxy for `proxied_account`."""
        proxied_account.proxies.add(account)

    def remove_proxy(self, author: AccountId, account: BaseAccount, proxied_account: BaseAccount) -> bool:
        """Ensures that `account` is not a proxy for `proxied_account`. Returns
           `False` is `account` was not a proxy for `procied_account`;
           otherwise, `True`."""
        prev_in = account in proxied_account.proxies
        if prev_in:
            proxied_account.proxies.remove(account)

        return not prev_in

    def print_money(self, author: AccountId, account: BaseAccount, amount: float):
        """Prints `amount` of money on the authority of `author` and deposits it in `account`."""
        account.balance += amount

    def remove_funds(self, author: AccountId, account: BaseAccount, amount: float):
        account.balance -= amount

    def transfer(self, author: AccountId, source: BaseAccount, destination: BaseAccount, amount: Fraction):
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

    def create_recurring_transfer(self, author: AccountId, source, destination, total_amount, tick_count,
                                  transfer_id=None):
        """Creates and registers a new recurring transfer, i.e., a transfer that is spread out over
           many ticks. The transfer is authorized by `author` and consists of `total_amount` being
           transferred from `source` to `destination` over the course of `tick_count` ticks. A tick
           is a server-defined timespan."""
        rec_transfer = InMemoryRecurringTransfer(author, source, destination, total_amount, tick_count, total_amount,
                                                 transfer_id)
        self.recurring_transfers[rec_transfer.get_id()] = rec_transfer
        return rec_transfer

    def notify_tick_elapsed(self, tick_timestamp=None):
        """Notifies the server that a tick has elapsed."""
        finished_transfers = set()
        for id in self.recurring_transfers:
            transfer = self.recurring_transfers[id]
            per_tick = transfer.get_total_amount() / transfer.get_tick_count()
            if transfer.get_remaining_amount() <= 0:
                finished_transfers.add(id)
            elif transfer.get_remaining_amount() >= per_tick:
                if self.can_transfer(transfer.get_source(), transfer.get_destination(), per_tick):
                    self.perform_recurring_transfer(transfer, per_tick)
            else:
                remaining = transfer.get_total_amount()
                if self.can_transfer(transfer.get_source(), transfer.get_destination(), remaining):
                    self.perform_recurring_transfer(transfer, remaining)
                    finished_transfers.add(id)

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


class InMemoryAccount(BaseAccount):
    """An in-memory account data structure."""

    def __init__(self, account_uuid=None):
        """Initializes an in-memory account."""
        self.uuid = account_uuid if account_uuid is not None else str(
            uuid.uuid4())
        self.balance = 0
        self.frozen = False
        self.public = False
        self.auth = Authorization.CITIZEN
        self.public_keys = []
        self.proxies = set()

    def set_balance(self, bal):
        self.balance = bal

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

    def get_proxies(self) -> List[BaseAccount]:
        """Gets all accounts that have been authorized as proxies for this account."""
        return list(self.proxies)


class InMemoryRecurringTransfer(RecurringTransfer):
    """An in-memory description of a recurring transfer."""

    def __init__(self, author: AccountId, source: BaseAccount, destination: BaseAccount, total_amount, tick_count,
                 remaining_amount, transfer_id=None):
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

    def get_author(self) -> AccountId:
        """Gets the account ID that authorized the transfer."""
        return self.author

    def get_source(self) -> BaseAccount:
        """Gets the account from which the money originates."""
        return self.source

    def get_destination(self) -> BaseAccount:
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


class SQLTaxBracket(Base):
    __tablename__ = 'tax'

    uuid = Column(CHAR(36), primary_key=True)
    start = Column(Float, nullable=False)
    end = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    name = Column(String, nullable=False)
    exempt_prefixes = ["&",
                       "@"]  # TODO: make account types an attribute stored in the database along with exempt prefixes

    def __repr__(self):
        return f"<SQLTaxBracket(uuid='{self.uuid}', start={self.start}, end={self.end}, rate={self.rate})>"

    def set_rate(self, rate):
        # sets tax rate
        self.rate = rate

    def get_rate(self):
        return self.rate

    def set_end(self, end):
        self.end = end

    def set_start(self, start):
        self.start = start

    def get_start(self):
        return self.start

    def get_end(self):
        return self.end

    def get_tax(self, account):
        bal = account.get_balance()
        if bal < self.start:
            return 0
        elif self.end is None or bal <= self.end:
            tax_amount = round(((bal - self.start) / 100) * self.rate)
            return tax_amount
        elif bal > self.end:
            tax_amount = round(((self.end - self.start) / 100) * self.rate)
            return tax_amount


class Account(Base):
    __tablename__ = 'accounts'

    uuid = Column(CHAR(36), primary_key=True)
    auth = Column(sqlalchemy.types.Enum(Authorization), server_default='CITIZEN', nullable=True)
    balance = Column(Float, server_default=sqlalchemy.text('0'), nullable=True)
    frozen = Column(Boolean, server_default=sqlalchemy.text('False'), nullable=True)
    public = Column(Boolean, server_default=sqlalchemy.text('False'), nullable=True)

    """
    In order to maintain an audit log I'm leaving accounts that have been deleted in the database and flagging them as deleted,
    I will also nullify there balance and the other flags, if they reopen an account we will reactivate this account
    """

    deleted = Column(Boolean, server_default=sqlalchemy.text('False'), nullable=False)

    names = relationship("Alias")

    public_keys = relationship("PublicKey")

    proxies = relationship("Proxy", foreign_keys="Proxy.account")

    def __repr__(self):
        return f"<Account(uuid='{self.uuid}', auth={self.auth}, balance={self.balance}, frozen={self.frozen}, public={self.public}>"

    def get_balance(self):
        return self.balance

    def get_uuid(self):
        return self.uuid

    def is_frozen(self) -> bool:
        """Tells if this account is frozen."""
        return self.frozen

    def get_authorization(self) -> Authorization:
        """Gets this account's level of authorization."""
        return self.auth

    def list_public_keys(self):
        """Produces a list of all public keys associated with this account.
           Every element of the list is a string that corresponds to the contents
           of a PEM file describing an ECC key."""
        return [ECC.import_key(base64.b64decode(key.key).decode('utf-8')) for key in self.public_keys]

    def get_proxies(self):
        """Gets all accounts that have been authorized as proxies for this account."""
        print(self.proxies)
        return [proxy.proxy_account for proxy in self.proxies]


class Configuration(Base):
    __tablename__ = 'configuration'

    key = Column(String, primary_key=True)
    value = Column(String)

    def __repr__(self):
        return f"<Configuration(key='{self.key}', value='{self.value}')>"


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    author = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=False)
    source = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=True)
    destination = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=True)
    value = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Transaction(id={self.id}, source='{self.source}', destination='{self.destination}', value={self.value}, timestamp={self.timestamp.__repr__()})>"


class Action(Base):
    """
    A class used to represent non monetary and less structured actions in the database
    """
    __tablename__ = 'actions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    author = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    arguments = Column(JSON, nullable=False, server_default='{}')
    action = Column(String, nullable=False)


class PublicKey(Base):
    __tablename__ = 'public_keys'

    id = Column(Integer, primary_key=True, autoincrement=True)  # the orm needs a primary key to construct the object
    account = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=False)
    key = Column(CHAR(320), nullable=False)

    def __repr__(self):
        return f"<PublicKey(id={self.id}, account='{self.account}', key='{self.key}')>"


class Alias(Base):
    __tablename__ = 'aliases'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=False)
    account_object = relationship("Account")
    alias_id = Column(String, nullable=False)


class Proxy(Base):
    __tablename__ = 'proxies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=False)
    proxy_account_id = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=False)
    proxy_account = relationship("Account", foreign_keys=[proxy_account_id])

    def __repr__(self):
        return f"<Proxy id={self.id}, account='{self.account}', proxy_account='{self.proxy_account}'"


class SQLRecurringTransfer(Base):
    __tablename__ = "recurring_transfers"
    uuid = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    author = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=False)
    source = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=False)
    destination = Column(CHAR(36), ForeignKey('accounts.uuid'), nullable=False)

    source_account = relationship(Account, foreign_keys=[source])
    destination_account = relationship(Account, foreign_keys=[destination])

    tick_count = Column(Integer, nullable=False)
    ticks_left = Column(Integer, nullable=False)
    remaining_amount = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)

    def get_id(self):
        """Gets this transfer's ID."""
        return self.uuid

    def get_author(self) -> AccountId:
        """Gets the account ID that authorized the transfer."""
        return self.author

    def get_source(self) -> BaseAccount:
        """Gets the account from which the money originates."""
        return self.source_account

    def get_destination(self) -> BaseAccount:
        """Gets the account to which the money must go."""
        return self.destination_account

    def get_tick_count(self):
        """Gets the number of ticks over the course of which the transfer must complete."""
        return self.tick_count

    def get_total_amount(self):
        """Gets the total amount to transfer."""
        return self.total_amount

    def get_remaining_amount(self):
        """Gets the remaining amount to transfer."""
        return self.remaining_amount


class SQLServer(InMemoryServer):

    def __init__(self, psswd: str = None, uname: str = "taubot", db: str = "taubot", host: str = "localhost",
                 dialect: str = "postgresql", url: str = None):
        """
        A server object that uses a SQL database for persistence rather than the Ledger, this means faster start up times
        but has the disadvantage of being harder to audit, all SQL databases *should* be supported but was designed
        using postgresql.

        :param psswd: this is the password to be used when connecting to the database, leave as None if no password is needed
        :param uname: this is the username to connect to the database with defaults to 'taubot'
        :param db: this is the database to connect to defaults to 'taubot'
        :param host: this is the host to connect to defaults to 'localhost'
        :param dialect: the database type to connect too defaults to 'localhost'
        :param url: optional connection url will override the previous parameters
        """
        url = url \
            if url is not None else f"{dialect}://{uname}{f':{psswd}' if psswd is not None else ''}@{host}/{db}" \
            if dialect != 'sqlite' else f'sqlite:///{db}'
        self.engine = sqlalchemy.create_engine(url)
        Session.configure(bind=self.engine)
        self.session = Session()
        if self.get_session().bind.dialect.name == 'sqlite':
            print(
                "[WARN] sqlite databases are inefficient and should not be used in production")  # TODO: add proper logging

        Base.metadata.create_all(self.engine)
        gov_id = RedditAccountId("@government")
        if not self.has_account(gov_id):
            gov_acc = self.open_account(gov_id)
            self.authorize(gov_id, gov_acc, Authorization.DEVELOPER)

        self.last_tick_timestamp = float(self.read_config("LAST-TICK-TIME", time.time()))

        self.ticks_till_tax = int(self.read_config("TAX-REGULARITY", 28))

        self.ticks_till_tax_tmp = int(self.read_config("TAX-TICKS-LEFT", self.ticks_till_tax))

        self.auto_tax = self.read_config("DO-AUTO-TAX", False).lower() == 'true'

        self.session.commit()

    def read_config(self, key, default_value) -> str:
        value = self.get_session().query(Configuration).filter_by(key=key).one_or_none()
        if value is None:
            value = Configuration(key=key, value=str(default_value))
            self.get_session().add(value)
        value = value.value

        return value

    def update_config(self, key, new_value):
        self.get_session().query(Configuration).filter_by(key=key).update({"value": str(new_value)})
        self.get_session().commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.get_session().flush()
        self.get_session().close()

    def reset(self):
        """drop all tables"""
        self.session.close()
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    def open_account(self, id: AccountId, account_uuid=None) -> Account:
        """
        opens a new account,
        if the account was once deleted it will reactivate that account rather than creating a new one.

        :param id: the id to use with the account
        :param account_uuid: the uuid to use with the account
        :return: the new account object
        """

        account_uuid = account_uuid if account_uuid is not None else str(uuid.uuid4())
        if self.has_account(id):
            raise Exception("Account already exists.")
        if self.has_account(id, deleted=True):
            account = self.get_account(id, deleted=True)
            self.get_session().query(Account).filter_by(uuid=account.get_uuid(), deleted=True).update(
                {"balance": DEFAULT, "auth": DEFAULT, "frozen": DEFAULT, "public": DEFAULT, "deleted": False},
                synchronize_session=False)
        else:
            account = Account(uuid=account_uuid)
            self.session.add(account)
            self.add_account_alias(account, id)
        self.get_session().add(Action(author=account.get_uuid(), action="open", arguments={"account": account.get_uuid()}))
        self.session.commit()
        return account

    def delete_account(self, author: AccountId, id: AccountId) -> bool:
        """
        marks an account as deleted and marks all the accounts values as null
        apart from the uuid and name to make the account auditable

        :param author: the person who authorised the accounts deletion
        :param id: the id of the account that is due to be deleted
        :return: whether or not the account was deleted successfully
        """
        account = self.get_account(id)
        self.get_session().add(Action(author=self.get_account(author).get_uuid(), action="delete-account", arguments={"account": account.get_uuid()}))
        self.get_session().query(Account).filter_by(uuid=account.get_uuid()).update(
            {"balance": None, "auth": None, "frozen": None, "public": None, "deleted": True}
        )
        self.get_session().commit()
        return True

    def add_account_alias(self, account: Account, alias_id: AccountId):
        self.get_session().add(Action(author=account.get_uuid(), action='add-alias', arguments={"id": str(alias_id)}))
        self.get_session().add(Alias(account=account.get_uuid(), alias_id=str(alias_id)))
        self.get_session().commit()

    def get_account(self, id: AccountId, deleted=False) -> Account:
        if isinstance(id, Account):
            return id
        id = str(id)
        account_id = self.get_session().query(Alias).filter_by(alias_id=id).one_or_none()
        if account_id is None:
            raise Exception("Account does not exist")
        account = account_id.account_object
        if account.deleted != deleted:
            raise Exception("Account does not exist")
        return account

    def get_accounts(self) -> List[Account]:
        return self.session.query(Account).filter_by(deleted=False).all()

    def get_account_ids(self, account: Account) -> List[AccountId]:
        return [alias.alias_id for alias in account.names]

    def has_account(self, id: Union[AccountId, str], deleted=False) -> bool:
        try:
            self.get_account(id, deleted)
            return True
        except:
            return False

    def get_government_account(self) -> Account:
        return self.get_account(RedditAccountId("@government"))

    def authorize(self, author: AccountId, account: Account, auth_level: Authorization):
        account.auth = auth_level
        self.get_session().add(Action(author=self.get_account(author).get_uuid(), action='authorize', arguments={"account": account.get_uuid(), "auth": auth_level.name}))
        self.session.commit()

    def mark_public(self, author: AccountId, account: Account, new_public: bool):
        self.get_session().add(Action(
            author=self.get_account(author).get_uuid(),
            action='mark-public',
            arguments={
                'new-public': new_public
            }
        ))
        super().mark_public(author, account, new_public)
        self.get_session().commit()

    def set_frozen(self, author: AccountId, account: Account, is_frozen: bool):
        super().set_frozen(author, account, is_frozen)
        self.get_session().add(Action(
            author=self.get_account(author).get_uuid(),
            action='set-frozen',
            arguments={
                'new-frozen': is_frozen
            }
        ))
        self.session.commit()

    def print_money(self, author: AccountId, account: Account, amount: float):
        self.get_session().add(Transaction(author=self.get_account(author).get_uuid(), source=None, destination=account.get_uuid(), value=amount))
        super().print_money(author, account, amount)
        self.session.commit()

    def remove_funds(self, author: AccountId, account: Account, amount: float):
        self.get_session().add(Transaction(author=self.get_account(author).get_uuid(), source=None, destination=account.get_uuid(), value=amount))
        super().remove_funds(author, account, amount)
        self.session.commit()

    def add_public_key(self, account: Account, key):
        key = base64.b64encode(key.export_key(format='PEM').encode('utf-8')).decode('utf-8')
        self.get_session().add(
            PublicKey(
                account=account.get_uuid(),
                key=key
            )
        )
        self.get_session().add(Action(
            author=account.get_uuid(),
            action='add-public-key',
            arguments={
                'key': key
            }
        ))
        self.get_session().commit()

    def add_proxy(self, author: AccountId, account: Account, proxied_account: Account):
        if self.get_session().query(Proxy).filter_by(account=proxied_account.get_uuid(),proxy_account_id=account.get_uuid()).one_or_none() is not None:
            return
        self.get_session().add(Proxy(account=proxied_account.get_uuid(), proxy_account_id=account.get_uuid()))
        self.get_session().add(Action(
            author=self.get_account(author).get_uuid(),
            action='add-proxy',
            arguments={
                "proxied_account": proxied_account.get_uuid()
            }
        ))
        self.get_session().commit()

    def remove_proxy(self, author: AccountId, account: Account, proxied_account: Account):
        proxy = self.get_session().query(Proxy).filter_by(account=proxied_account.get_uuid(),
                                                          proxy_account_id=account.get_uuid()).first()
        self.get_session().delete(proxy)
        self.get_session().add(Action(
            author=self.get_account(author).get_uuid(),
            action='remove-proxy',
            arguments={
                "proxied_account": proxied_account.get_uuid()
            }
        ))
        self.get_session().commit()

    def get_recurring_transfer(self, id: str) -> RecurringTransfer:
        return self.get_session().query(SQLRecurringTransfer).filter_by(uuid=id).one()

    def list_recurring_transfers(self):
        return self.get_session().query(SQLRecurringTransfer).all()

    def create_recurring_transfer(self, author: AccountId, source, destination, total_amount, tick_count,
                                  transfer_id=None):
        transfer = SQLRecurringTransfer(
            author=self.get_account(author).get_uuid(),
            source=source.get_uuid(),
            destination=destination.get_uuid(),
            tick_count=tick_count,
            ticks_left=tick_count,
            remaining_amount=total_amount,
            total_amount=total_amount
        )
        self.get_session().add(transfer)
        self.get_session().add(Action(
            author=self.get_account(author).get_uuid(),
            action='create-recurring-transfer',
            arguments={
                'source': source.get_uuid(),
                'destination': destination.get_uuid(),
                'total_amount': total_amount,
                'tick_count': tick_count
            }
        ))
        self.get_session().commit()
        return transfer

    def notify_tick_elapsed(self, tick_timestamp=None):
        self.last_tick_timestamp = tick_timestamp if tick_timestamp is not None else time.time()
        self.update_config("LAST-TICK-TIME", self.last_tick_timestamp)

        self.get_session().add(Action(
            author=self.get_government_account().get_uuid(),
            action='tick',
            arguments={}
        ))

        if self.auto_tax:
            self.ticks_till_tax_tmp -= 1
            if self.ticks_till_tax_tmp == 0:
                self.force_tax(RedditAccountId("@government"))
                self.ticks_till_tax_tmp = self.ticks_till_tax

            self.update_config("TAX-TICKS-LEFT", self.ticks_till_tax_tmp)

        finished_transfers = []

        for transfer in self.get_session().query(SQLRecurringTransfer).all():
            per_tick = transfer.get_total_amount() / transfer.get_tick_count()
            if transfer.get_remaining_amount() <= 0:
                finished_transfers.append(transfer)
            elif transfer.get_remaining_amount() >= per_tick:
                if self.can_transfer(transfer.get_source(), transfer.get_destination(), per_tick):
                    self.perform_recurring_transfer(transfer, per_tick)
            else:
                remaining = transfer.get_total_amount()
                if self.can_transfer(transfer.get_source(), transfer.get_destination(), remaining):
                    self.perform_recurring_transfer(transfer, remaining)
                    finished_transfers.append(transfer)

        for i in finished_transfers:
            self.get_session().delete(i)

        self.get_session().commit()

    def perform_recurring_transfer(self, transfer, amount):
        super().perform_recurring_transfer(transfer, amount)
        self.get_session().commit()

    def transfer(self, author: AccountId, source: Account, destination: Account, amount: float):
        super().transfer(author, source, destination, amount)
        self.session.add(Transaction(author=self.get_account(author).get_uuid(), source=source.get_uuid(), destination=destination.get_uuid(), value=amount))
        self.session.commit()

    def add_tax_bracket(self, author: AccountId, start, end, rate, name, tax_uuid=None):
        self.session.add(
            SQLTaxBracket(
                uuid=tax_uuid if tax_uuid is not None else str(uuid.uuid4()),
                start=start,
                end=end,
                rate=rate,
                name=name
            )
        )
        self.session.commit()

    def get_session(self) -> sqlalchemy.orm.Session:
        return self.session

    def get_tax_brackets(self):
        return self.get_session().query(SQLTaxBracket).all()

    def get_tax_bracket(self, name=None, uuid=None):
        if uuid is None and name is None:
            raise Exception("You must specify at least a name or a uuid")
        kwargs = {"uuid": uuid} if uuid is not None else {"name": name}
        return self.get_session().query(SQLTaxBracket).filter_by(**kwargs)

    def force_tax(self, author):
        self.get_session().add(Action(author=self.get_account(author).get_uuid(), action='force-tax', arguments={}))

        self.ticks_till_tax_tmp = self.ticks_till_tax

        for tax_bracket in self.get_tax_brackets():
            for account in self.get_accounts():
                if str(self.get_account_id(account)).startswith(
                        tuple(tax_bracket.exempt_prefixes)): continue
                tax_amount = tax_bracket.get_tax(account)
                if tax_amount != 0:
                    self.transfer(RedditAccountId('@government'), account, self.get_government_account(), tax_amount)
        return

    def toggle_auto_tax(self, author):
        self.auto_tax = not self.auto_tax
        self.update_config("DO-AUTO-TAX", self.auto_tax)
        self.get_session().add(Action(author=self.get_account(author).get_uuid(), action='toggle-auto-tax', arguments={}))
        return self.auto_tax
