#!/usr/bin/env python3

import sys
from os import path, remove
sys.path.append(path.join(path.dirname(
    path.dirname(path.abspath(__file__))), 'src'))

from commands import process_command
from accounting import RedditAccountId, InMemoryServer, Server, Authorization, LedgerServer
from typing import Sequence
import unittest

def run_all(elements, action):
    """Runs an action on every element of a list."""
    for item in elements:
        action(item)

def run_command_stream(server, *commands):
    """Runs a sequence of commands (formatted as author, command pairs) on a server."""
    responses = []
    for (author, cmd) in commands:
        responses.append(process_command(author, cmd, server))
    return responses

def create_test_servers() -> Sequence[Server]:
    """Creates a sequence of test servers."""
    # First test with an in-memory server.
    yield InMemoryServer()

    # Then test with a clean ledger server.
    ledger_path = 'test-ledger.txt'
    try:
        remove(ledger_path)
    except:
        pass

    with LedgerServer(ledger_path) as ledger_server:
        yield ledger_server

    # Load the ledger to ensure that the created ledger remains readable.
    with LedgerServer(ledger_path) as ledger_server:
        pass

class ServerTests(unittest.TestCase):
    """Tests that verify that the implementation of a Server and related data types are correct."""

    def test_open_account(self):
        """Tests that an account can be opened."""
        for server in create_test_servers():
            self.assertFalse(server.has_account(RedditAccountId('taubot')))
            account = server.open_account(RedditAccountId('taubot'))
            self.assertEqual(account.get_balance(), 0)

class CommandTests(unittest.TestCase):

    def test_admin_open(self):
        """Tests that an account can be opened by an admin."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.ADMIN)
            self.assertFalse(server.has_account(RedditAccountId('general-kenobi')))
            run_command_stream(server, (admin_id, 'admin-open general-kenobi'))
            self.assertTrue(server.has_account(RedditAccountId('general-kenobi')))
            account = server.get_account_from_string('general-kenobi')
            self.assertEqual(account.get_balance(), 0)

    def test_user_open(self):
        """Tests that a user can open an account."""
        for server in create_test_servers():
            account_id = RedditAccountId('general-kenobi')
            self.assertFalse(server.has_account(account_id))
            run_command_stream(server, (account_id, 'open'))
            self.assertTrue(server.has_account(account_id))
            account = server.get_account(account_id)
            self.assertEqual(account.get_balance(), 0)

    def test_print_money(self):
        """Tests that money printing works."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.ADMIN)

            self.assertEqual(admin.get_balance(), 0)
            run_command_stream(
                server,
                (admin_id, 'print-money 20 admin'))

            self.assertEqual(admin.get_balance(), 20)

    def test_balance(self):
        """Tests that the balance command works."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.ADMIN)
            server.print_money(admin, admin, 123)

            self.assertIn(
                '123',
                ''.join(
                    run_command_stream(
                        server,
                        (admin_id, 'balance'))))

    def test_transfer(self):
        """Tests that money can be transferred."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.ADMIN)
            run_command_stream(
                server,
                (admin_id, 'admin-open general-kenobi'),
                (admin_id, 'print-money 20 general-kenobi'),
                (admin_id, 'print-money 20 admin'))
            account_id = RedditAccountId('general-kenobi')
            account = server.get_account(account_id)

            self.assertEqual(admin.get_balance(), 20)
            self.assertEqual(account.get_balance(), 20)
            run_command_stream(
                server,
                (account_id, 'transfer 20 admin'))

            self.assertEqual(admin.get_balance(), 40)
            self.assertEqual(account.get_balance(), 0)

            # This command should fail (will be reported as a message to the user).
            run_command_stream(
                server,
                (account_id, 'transfer 20 admin'))

            # State shouldn't have changed.
            self.assertEqual(admin.get_balance(), 40)
            self.assertEqual(account.get_balance(), 0)

    def test_freeze(self):
        """Tests that accounts can be frozen and unfrozen."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.ADMIN)
            run_command_stream(
                server,
                (admin_id, 'admin-open general-kenobi'),
                (admin_id, 'print-money 20 general-kenobi'),
                (admin_id, 'print-money 20 admin'))
            account_id = RedditAccountId('general-kenobi')
            account = server.get_account(account_id)
            self.assertFalse(account.is_frozen())
            self.assertTrue(server.can_transfer(account, admin, 20))
            self.assertTrue(server.can_transfer(admin, account, 20))
            run_command_stream(server, (admin_id, 'admin-freeze general-kenobi'))
            self.assertTrue(account.is_frozen())
            self.assertFalse(server.can_transfer(account, admin, 20))
            self.assertFalse(server.can_transfer(admin, account, 20))
            run_command_stream(server, (account_id, 'transfer 20 admin'))
            run_command_stream(server, (admin_id, 'admin-unfreeze general-kenobi'))
            self.assertFalse(account.is_frozen())
            self.assertTrue(server.can_transfer(account, admin, 20))
            self.assertTrue(server.can_transfer(admin, account, 20))

if __name__ == '__main__':
    unittest.main()
