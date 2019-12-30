#!/usr/bin/env python3

import unittest
from Crypto.PublicKey import ECC
from ecies import generate_key

import sys
from os import path
sys.path.append(path.join(path.dirname(path.dirname(path.abspath(__file__))), 'src'))

from accounting import RedditAccountId, InMemoryServer
from httpapi import length_prefix, take_length_prefixed, RequestClient, RequestServer

class IOHelpers(unittest.TestCase):

    def test_length_prefix(self):
        self.assertEqual(take_length_prefixed(length_prefix(b'hello'))[0], b'hello')
        msg = length_prefix(b'hello') + b'hi'
        hello, hi = take_length_prefixed(msg)
        self.assertEqual(hello, b'hello')
        self.assertEqual(hi, b'hi')

    def test_roundtrip_request(self):
        """Ensures that the encryption/decryption algorithm can round-trip a message request."""

        # Set up a server containing exactly one account.
        server = InMemoryServer()
        account_id = RedditAccountId('general-kenobi')
        account = server.open_account(account_id)

        # Create a key for the account.
        account_key = ECC.generate(curve='P-256')
        server.add_public_key(account, account_key.public_key())

        # Create a key for the server.
        server_key = generate_key()

        # Create a message client.
        msg_client = RequestClient(account_id, server_key.public_key.format(True), account_key)

        # Create a message server.
        msg_server = RequestServer(server, server_key.secret)

        # Round-trip a message.
        msg = b'Hello there!'

        _, enc_msg = msg_client.encrypt_request(msg)
        _, dec_msg = msg_server.decrypt_request(enc_msg)
        self.assertEqual(dec_msg, msg)

if __name__ == '__main__':
    unittest.main()
