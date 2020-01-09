#!/usr/bin/env python3

import sys
from os import path
sys.path.append(path.join(path.dirname(
    path.dirname(path.abspath(__file__))), 'src'))

from commands import process_command
from accounting import RedditAccountId, InMemoryServer, Server, Authorization
from typing import List
import unittest

def run_all(elements, action):
    """Runs an action on every element of a list."""
    for item in elements:
        action(item)

def run_command_stream(server, *commands):
    """Runs a sequence of commands (formatted as author, command pairs) on a server."""
    for (author, cmd) in commands:
        process_command(author, cmd, server)

def create_test_servers() -> List[Server]:
    """Creates a list of test servers."""
    return [InMemoryServer()]

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

    def test_freeze(self):
        """Tests that accounts can be frozen and unfrozen."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.ADMIN)
            run_command_stream(server, (admin_id, 'admin-open general-kenobi'))
            account = server.get_account_from_string('general-kenobi')
            self.assertFalse(account.is_frozen())
            run_command_stream(server, (admin_id, 'admin-freeze general-kenobi'))
            self.assertTrue(account.is_frozen())
            run_command_stream(server, (admin_id, 'admin-unfreeze general-kenobi'))
            self.assertFalse(account.is_frozen())

if __name__ == '__main__':
    unittest.main()
