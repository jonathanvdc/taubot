#!/usr/bin/env python3

import unittest
from Crypto.PublicKey import ECC
from ecies import generate_key

import sys
from os import path
sys.path.append(path.join(path.dirname(path.dirname(path.abspath(__file__))), 'src'))

from accounting import RedditAccountId, InMemoryServer
from httpapi import length_prefix, take_length_prefixed, RequestClient, RequestServer, compose_signed_plaintext_request, DecryptionException

class Cryptography(unittest.TestCase):

    def test_length_prefix(self):
        self.assertEqual(take_length_prefixed(length_prefix(b'hello'))[0], b'hello')
        msg = length_prefix(b'hello') + b'hi'
        hello, hi = take_length_prefixed(msg)
        self.assertEqual(hello, b'hello')
        self.assertEqual(hi, b'hi')

    def create_client_and_server(self):
        """Creates a client and a server."""
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
        
        return (msg_client, msg_server)

    def test_roundtrip(self):
        """Ensures that the encryption/decryption algorithm can round-trip a message request and response."""

        msg_client, msg_server = self.create_client_and_server()

        # Round-trip a message.
        msg = b'Hello there!'

        sk_bytes, enc_msg = msg_client.encrypt_request(msg)
        pk_bytes, dec_msg = msg_server.decrypt_request(enc_msg)
        self.assertEqual(dec_msg, msg)

        self.assertEqual(
            msg_client.decrypt_response(
                sk_bytes,
                msg_server.encrypt_response(pk_bytes, msg)),
            msg)

    def test_no_replay(self):
        """Ensures that message replay throws an exception."""

        msg_client, msg_server = self.create_client_and_server()

        _, enc_msg = msg_client.encrypt_request(b'Hello there!')

        _, _ = msg_server.decrypt_request(enc_msg)
        self.assertRaises(DecryptionException, lambda: msg_server.decrypt_request(enc_msg))

if __name__ == '__main__':
    unittest.main()
