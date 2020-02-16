#!/usr/bin/env python3

import sys
from os import path, remove
sys.path.append(path.join(path.dirname(
    path.dirname(path.abspath(__file__))), 'src'))

from commands import process_command
from accounting import RedditAccountId, InMemoryServer, Server, Authorization, LedgerServer
from typing import Sequence
from base64 import b64encode
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

    def test_help(self):
        """Tests that the help command does not crash the bot."""
        for server in create_test_servers():
            account_id = RedditAccountId('general-kenobi')
            run_command_stream(server, (account_id, 'help'), (account_id, 'open'), (account_id, 'help'))

    def test_reference(self):
        """Tests that the reference command does not crash the bot."""
        for server in create_test_servers():
            account_id = RedditAccountId('general-kenobi')
            run_command_stream(server, (account_id, 'reference'), (account_id, 'open'), (account_id, 'reference'))

    def test_balance(self):
        """Tests that the balance command works."""
        for server in create_test_servers():
            account_id = RedditAccountId('general-kenobi')
            # Test the main command.
            self.assertIn('0', ''.join(run_command_stream(server, (account_id, 'open'), (account_id, 'balance'))))
            # Also test the alias.
            self.assertIn('0', ''.join(run_command_stream(server, (account_id, 'bal'))))

    def test_balance_2(self):
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

    def test_authorize(self):
        """Tests that a user can be authorized as a citizen, admin or developer."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.DEVELOPER)

            account_id = RedditAccountId('general-kenobi')
            run_command_stream(server, (account_id, 'open'))
            account = server.get_account(account_id)
            self.assertEqual(account.get_authorization(), Authorization.CITIZEN)
            run_command_stream(server, (admin_id, 'authorize general-kenobi admin'))
            self.assertEqual(account.get_authorization(), Authorization.ADMIN)
            run_command_stream(server, (admin_id, 'authorize general-kenobi developer'))
            self.assertEqual(account.get_authorization(), Authorization.DEVELOPER)
            run_command_stream(server, (admin_id, 'authorize general-kenobi citizen'))
            self.assertEqual(account.get_authorization(), Authorization.CITIZEN)

    def test_no_authorize_privilege_escalation(self):
        """Tests that a user cannot escalate their privileges using the `authorize` command."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.DEVELOPER)

            account_id = RedditAccountId('general-kenobi')
            run_command_stream(server, (account_id, 'open'))
            account = server.get_account(account_id)

            self.assertEqual(account.get_authorization(), Authorization.CITIZEN)
            run_command_stream(server, (account_id, 'authorize general-kenobi admin'))
            self.assertEqual(account.get_authorization(), Authorization.CITIZEN)
            run_command_stream(server, (account_id, 'authorize general-kenobi developer'))
            self.assertEqual(account.get_authorization(), Authorization.CITIZEN)

            run_command_stream(server, (admin_id, 'authorize general-kenobi admin'))

            self.assertEqual(account.get_authorization(), Authorization.ADMIN)
            run_command_stream(server, (account_id, 'authorize general-kenobi admin'))
            self.assertEqual(account.get_authorization(), Authorization.ADMIN)
            run_command_stream(server, (account_id, 'authorize general-kenobi developer'))
            self.assertEqual(account.get_authorization(), Authorization.ADMIN)

            run_command_stream(server, (account_id, 'authorize admin admin'))
            self.assertEqual(admin.get_authorization(), Authorization.DEVELOPER)
            run_command_stream(server, (account_id, 'authorize admin citizen'))
            self.assertEqual(admin.get_authorization(), Authorization.DEVELOPER)

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

    def test_no_print_negative_money(self):
        """Tests that negative money cannot be printed."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.ADMIN)

            self.assertEqual(admin.get_balance(), 0)
            run_command_stream(
                server,
                (admin_id, 'print-money -20 admin'))

            self.assertEqual(admin.get_balance(), 0)

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

    def test_admin_transfer(self):
        """Tests that an admin can order money can be transferred."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.ADMIN)
            run_command_stream(
                server,
                (admin_id, 'admin-open general-kenobi'),
                (admin_id, 'print-money 20 general-kenobi'))
            account_id = RedditAccountId('general-kenobi')
            account = server.get_account(account_id)

            self.assertEqual(admin.get_balance(), 0)
            self.assertEqual(account.get_balance(), 20)
            run_command_stream(
                server,
                (admin_id, 'admin-transfer 20 general-kenobi admin'))

            self.assertEqual(admin.get_balance(), 20)
            self.assertEqual(account.get_balance(), 0)

    def test_recurring_transfer(self):
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
                (account_id, 'create-recurring-transfer 2 admin 10'))

            self.assertEqual(admin.get_balance(), 20)
            self.assertEqual(account.get_balance(), 20)
            for i in range(10):
                server.notify_tick_elapsed()
                self.assertEqual(admin.get_balance(), 20 + (i + 1) * 2)
                self.assertEqual(account.get_balance(), 20 - (i + 1) * 2)

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

    def test_link_accounts(self):
        """Tests that accounts can be linked."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            alias_id = RedditAccountId('general-kenobi')
            admin = server.open_account(admin_id)
            server.authorize(admin, admin, Authorization.ADMIN)

            # Create an alias request token.
            token_msg = run_command_stream(server, (admin_id, 'request-alias general-kenobi'))[0]
            token = token_msg.split('```')[1].strip().split()[2]

            # Add the alias.
            run_command_stream(server, (alias_id, 'add-alias admin %s' % token))

            # Check that the alias was added.
            self.assertIn(admin_id, server.get_account_ids(admin))
            self.assertIn(alias_id, server.get_account_ids(admin))

            # Now have some other account try to add an alias to the admin using a garbage token.
            other_id = RedditAccountId('baby-yoda')
            run_command_stream(server, (other_id, 'add-alias admin %s' % b64encode(b'howdy').decode('utf-8')))
            # Ensure that the accounts weren't linked.
            self.assertNotIn(other_id, server.get_account_ids(admin))

            # Now have that account try to add an alias to the admin using a valid token intended
            # for another account name.
            run_command_stream(server, (other_id, 'add-alias admin %s' % token))
            # Ensure that the accounts weren't linked.
            self.assertNotIn(other_id, server.get_account_ids(admin))

    def test_name_command(self):
        """Tests that the name command returns an account's name."""
        for server in create_test_servers():
            account_id = RedditAccountId('general-kenobi')
            response = run_command_stream(server, (account_id, 'name'))[0]
            self.assertIn(str(account_id), response)

    def test_add_remove_proxy(self):
        """Tests that proxies can be added and removed."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            alias_id = RedditAccountId('general-kenobi')
            admin = server.open_account(admin_id)
            alias = server.open_account(alias_id)
            server.authorize(admin, admin, Authorization.ADMIN)

            # Make the account a proxy for the admin.
            run_command_stream(server, (admin_id, 'admin-add-proxy general-kenobi admin'))[0]
            self.assertIn(alias, admin.get_proxies())

            # Remove the proxy.
            run_command_stream(server, (admin_id, 'admin-remove-proxy general-kenobi admin'))[0]
            self.assertNotIn(alias, admin.get_proxies())

            # Ensure that proxies work like a set, not like a multiset.
            run_command_stream(server, (admin_id, 'admin-add-proxy general-kenobi admin'))[0]
            run_command_stream(server, (admin_id, 'admin-add-proxy general-kenobi admin'))[0]
            run_command_stream(server, (admin_id, 'admin-add-proxy general-kenobi admin'))[0]
            self.assertIn(alias, admin.get_proxies())

            run_command_stream(server, (admin_id, 'admin-remove-proxy general-kenobi admin'))[0]
            self.assertNotIn(alias, admin.get_proxies())

    def test_add_remove_proxy(self):
        """Tests that proxies can be added and removed."""
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            alias_id = RedditAccountId('general-kenobi')
            admin = server.open_account(admin_id)
            alias = server.open_account(alias_id)
            server.authorize(admin, admin, Authorization.ADMIN)

            # Make the account a proxy for the admin.
            run_command_stream(server, (admin_id, 'admin-add-proxy general-kenobi admin'))[0]
            self.assertIn(alias, admin.get_proxies())

            # Remove the proxy.
            run_command_stream(server, (admin_id, 'admin-remove-proxy general-kenobi admin'))[0]
            self.assertNotIn(alias, admin.get_proxies())

            # Ensure that proxies work like a set, not like a multiset.
            run_command_stream(server, (admin_id, 'admin-add-proxy general-kenobi admin'))[0]
            run_command_stream(server, (admin_id, 'admin-add-proxy general-kenobi admin'))[0]
            run_command_stream(server, (admin_id, 'admin-add-proxy general-kenobi admin'))[0]
            self.assertIn(alias, admin.get_proxies())

            run_command_stream(server, (admin_id, 'admin-remove-proxy general-kenobi admin'))[0]
            self.assertNotIn(alias, admin.get_proxies())

    def test_run_proxy_command(self):
        for server in create_test_servers():
            admin_id = RedditAccountId('admin')
            alias_id = RedditAccountId('general-kenobi')
            admin = server.open_account(admin_id)
            alias = server.open_account(alias_id)
            server.print_money(admin, admin, 200)
            server.authorize(admin, admin, Authorization.ADMIN)

            # Make the account a proxy for the admin.
            run_command_stream(server, (admin_id, 'admin-add-proxy general-kenobi admin'))[0]
            self.assertIn(alias, admin.get_proxies())

            # Transfer money by proxy.
            run_command_stream(server, (alias_id, 'proxy admin \n\n transfer 20 general-kenobi'))[0]
            self.assertEqual(admin.get_balance(), 180)
            self.assertEqual(alias.get_balance(), 20)

            # Remove the proxy.
            run_command_stream(server, (admin_id, 'admin-remove-proxy general-kenobi admin'))[0]
            self.assertNotIn(alias, admin.get_proxies())

            # Try to transfer money by proxy (this will fail and do nothing).
            run_command_stream(server, (alias_id, 'proxy admin \n\n transfer 20 general-kenobi'))[0]
            self.assertEqual(admin.get_balance(), 180)
            self.assertEqual(alias.get_balance(), 20)

if __name__ == '__main__':
    unittest.main()
