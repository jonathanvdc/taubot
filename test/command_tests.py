#!/usr/bin/env python3

import sys
from os import path, remove
sys.path.append(path.join(path.dirname(
    path.dirname(path.abspath(__file__))), 'src'))

from commands import process_command
from accounting import RedditAccountId, InMemoryServer, Server, Authorization, LedgerServer
from typing import List
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

def create_test_servers() -> List[Server]:
    """Creates a list of test servers."""
    path = 'test-ledger.txt'
    try:
        remove(path)
    except:
        pass

    return [InMemoryServer(), LedgerServer(path)]

def close_server(server: Server):
    """Closes a server."""
    if isinstance(server, LedgerServer):
        server.close()

class ServerTests(unittest.TestCase):
    """Tests that verify that the implementation of a Server and related data types are correct."""

    def test_open_account(self):
        """Tests that an account can be opened."""
        for server in create_test_servers():
            self.assertFalse(server.has_account(RedditAccountId('taubot')))
            account = server.open_account(RedditAccountId('taubot'))
            self.assertEqual(account.get_balance(), 0)
            close_server(server)

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
            close_server(server)

    def test_user_open(self):
        """Tests that a user can open an account."""
        for server in create_test_servers():
            account_id = RedditAccountId('general-kenobi')
            self.assertFalse(server.has_account(account_id))
            run_command_stream(server, (account_id, 'open'))
            self.assertTrue(server.has_account(account_id))
            account = server.get_account(account_id)
            self.assertEqual(account.get_balance(), 0)
            close_server(server)

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
            close_server(server)

if __name__ == '__main__':
    unittest.main()
