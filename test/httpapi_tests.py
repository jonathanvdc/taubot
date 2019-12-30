#!/usr/bin/env python3

import sys
from os import path
sys.path.append(path.join(path.dirname(
    path.dirname(path.abspath(__file__))), 'src'))

import asyncio
from httpapi import length_prefix, take_length_prefixed, RequestClient, RequestServer, compose_signed_plaintext_request, DecryptionException
from accounting import RedditAccountId, InMemoryServer
import unittest
from Crypto.PublicKey import ECC
from ecies import generate_key


def create_client_and_server():
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
    msg_client = RequestClient(
        account_id, server_key.public_key.format(True), account_key)

    # Create a message server.
    msg_server = RequestServer(server, server_key.secret)

    return (msg_client, msg_server)


class Cryptography(unittest.TestCase):

    def test_length_prefix(self):
        self.assertEqual(take_length_prefixed(
            length_prefix(b'hello'))[0], b'hello')
        msg = length_prefix(b'hello') + b'hi'
        hello, hi = take_length_prefixed(msg)
        self.assertEqual(hello, b'hello')
        self.assertEqual(hi, b'hi')

    def test_roundtrip(self):
        """Ensures that the encryption/decryption algorithm can round-trip a message request and response."""

        msg_client, msg_server = create_client_and_server()

        # Round-trip a message.
        msg = b'Hello there!'

        sk_bytes, enc_msg = msg_client.encrypt_request(msg)
        _, pk_bytes, dec_msg = msg_server.decrypt_request(enc_msg)
        self.assertEqual(dec_msg, msg)

        self.assertEqual(
            msg_client.decrypt_response(
                sk_bytes,
                msg_server.encrypt_response(pk_bytes, msg)),
            msg)

    def test_no_replay(self):
        """Ensures that message replay throws an exception."""

        msg_client, msg_server = create_client_and_server()

        _, enc_msg = msg_client.encrypt_request(b'Hello there!')

        _, _, _ = msg_server.decrypt_request(enc_msg)
        self.assertRaises(
            DecryptionException,
            lambda: msg_server.decrypt_request(enc_msg))

    def test_signature_strictness(self):
        """Ensures that signatures are checked."""

        msg_client, msg_server = create_client_and_server()

        # Use an unknown key to sign messages.
        msg_client.client_private_key = ECC.generate(curve='P-256')

        _, enc_msg = msg_client.encrypt_request(b'Hello there!')

        self.assertRaises(
            DecryptionException,
            lambda: msg_server.decrypt_request(enc_msg))


def async_test(coro):
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper


class Requests(unittest.TestCase):
    @async_test
    async def test_balance(self):
        msg_client, msg_server = create_client_and_server()

        async def send_request(message):
            return msg_server.handle_request_body(message)

        self.assertEqual(
            await msg_client.get_balance(send_request),
            0)

        account = msg_server.server.get_account(msg_client.account_id)
        msg_server.server.print_money(account, account, 100)
        self.assertEqual(
            await msg_client.get_balance(send_request),
            100)


if __name__ == '__main__':
    unittest.main()
