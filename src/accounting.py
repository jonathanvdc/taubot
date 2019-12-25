import uuid


class Server(object):
    """A server manages a number of accounts that all have the same currency."""

    def open_account(self, id):
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
            source.get_balance() - amount > 0 and \
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

    def open_account(self, id):
        """Opens an empty account with a particular ID. Raises an exception if the account
           already exists. Otherwise returns the newly opened account."""
        if self.has_account(id):
            raise Exception("Account already exists.")

        account = InMemoryAccount()
        self.accounts[id] = account
        return account

    def get_account(self, id):
        """Gets the account that matches an ID. Raises an exception if there is no such account."""
        return self.accounts[id]

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

    def __init__(self):
        """Initializes an in-memory account."""
        self.uuid = str(uuid.uuid4())
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
