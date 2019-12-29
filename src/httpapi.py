# This module defines the HTTP API. Note that this HTTP API is an atypical one; it is not REST-like
# and all data is encrypted. This has the advantage of requiring neither an HTTPS setup nor an
# authentication mechanism.
#
# The flow between client and server is as follows:
#
#   1. Client sends the following message, encrypted using ecies and the server's public key.
#      (a) a 32-digit nonce,
#      (b) a UTF-8 encoded account ID,
#      (c) an ecies key pair for the server's response,
#      (d) the actual request, and
#      (e) an ECDSA signature of the SHA3-512 digest of (a)(b)(c), signed with one of the client's associated keys.
#
#   2. Server responds. Its response is encrypted using the ecies key pair sent by the client.
#

import random
import struct
from ecies.utils import generate_key
from ecies import encrypt, decrypt
from Crypto.Signature import DSS
from Crypto.Hash import SHA3_512
from aiohttp import web
from accounting import parse_account_id, AccountId, Server

def generate_nonce(length):
    """Generates a pseudorandom number."""
    return ''.join(str(random.randint(0, 9)) for i in range(length)).encode('utf-8')

def length_prefix(data: bytes) -> bytes:
    """Creates a length-prefixed byte string."""
    return struct.pack('<i', len(data)) + data

def take_length_prefixed(data: bytes):
    """Takes a byte string that starts with a length-prefixed byte string.
       Returns the contents of the length-prefixed byte string and the remaining
       bytes in `data`."""
    length, = struct.unpack('<i', data)
    return (data[4:4 + length], data[4 + length:])

def encrypt_request(account_id: AccountId, request_data: bytes, server_public_key, client_private_key) -> bytes:
    """Encrypts a request message."""

    # First create the nonce.
    nonce = generate_nonce(32)
    message = nonce

    # Insert the account ID.
    message += length_prefix(str(account_id).encode('utf-8'))

    # Then add in the reply key pair.
    reply_key = generate_key()
    sk_bytes = reply_key.secret
    pk_bytes = reply_key.public_key.format(True)
    message += length_prefix(sk_bytes)
    message += length_prefix(pk_bytes)

    # Insert the actual request here.
    message += length_prefix(request_data)

    # Sign the message.
    signer = DSS.new(client_private_key, 'fips-186-3')
    message += signer.sign(SHA3_512.new(message))

    # Encrypt the message.
    return encrypt(server_public_key, message)

class RequestHandler(object):
    """Handles incoming requests."""
    def __init__(self, server: Server, private_key, max_nonce_count=10000):
        self.used_nonces = set()
        self.server = server
        self.max_nonce_count = max_nonce_count
        self.private_key = private_key

    async def handle_request(self, request):
        """Handles a request."""
        sk_bytes, pk_bytes, message = self.decrypt_request(await request.read())

        # TODO: implement actual request handling.
        response = message

        return web.Response(body=encrypt(pk_bytes, response))

    def decrypt_request(self, encrypted_data: bytes):
        """Decrypts and verifies an incoming encrypted request message."""
        data = decrypt(self.private_key, encrypted_data)
        data_hash = SHA3_512.new(data)

        # Process the nonce.
        nonce = data[:32]
        data = data[32:]
        if nonce in self.used_nonces:
            raise Exception('Nonce is reused.')

        if len(self.used_nonces) >= self.max_nonce_count:
            self.used_nonces.remove(random.choice(self.used_nonces))

        self.used_nonces.add(nonce)

        # Read the account name.
        account_id_bytes, data = take_length_prefixed(data)
        account = self.server.get_account_from_string(str(account_id_bytes))

        # Read all the other data.
        sk_bytes, data = take_length_prefixed(data)
        pk_bytes, data = take_length_prefixed(data)
        message, data = take_length_prefixed(data)

        # Check the digital signature.
        any_verified = False
        for key in account.list_public_keys():
            verifier = DSS.new(key, 'fips-186-3')
            try:
                verifier.verify(data_hash, data)
                any_verified = True
            except ValueError:
                pass

            if any_verified:
                break

        if not any_verified:
            raise Exception('Invalid signature.')

        return (sk_bytes, pk_bytes, message)
