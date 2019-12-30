# This module defines the HTTP API. Note that this HTTP API is an atypical one; it is not REST-like
# and all data is encrypted. This has the advantage of requiring neither an HTTPS setup nor an
# authentication mechanism.
#
# The flow between client and server is as follows:
#
#   1. Client sends the following message, encrypted using ecies and the server's public key.
#      (a) a 32-digit nonce,
#      (b) a UTF-8 encoded account ID,
#      (c) a new ecies public key for the server's response,
#      (d) the actual request, and
#      (e) an ECDSA signature of the SHA3-512 digest of (a)(b)(c), signed with one of the client's associated keys.
#
#   2. Server responds. Its response is encrypted using the ecies key pair sent by the client.
#

import random
import struct
from enum import Enum
from ecies.utils import generate_key
from ecies import encrypt, decrypt
from Crypto.Signature import DSS
from Crypto.Hash import SHA3_512
from aiohttp import web
from accounting import parse_account_id, Account, AccountId, Server


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
    length, = struct.unpack('<i', data[:4])
    return (data[4:4 + length], data[4 + length:])


def compose_unsigned_plaintext_request(nonce: bytes, account_id: AccountId, response_pk_bytes: bytes, request_data: bytes):
    """Composes an unsigned plaintext request."""
    return b''.join([
        nonce,
        length_prefix(str(account_id).encode('utf-8')),
        length_prefix(response_pk_bytes),
        length_prefix(request_data)
    ])


def sign_message(message: bytes, private_key) -> bytes:
    """Signs a message, producing a digital signature."""
    signer = DSS.new(private_key, 'fips-186-3')
    return signer.sign(SHA3_512.new(message))


def compose_signed_plaintext_request(
        nonce: bytes,
        account_id: AccountId,
        response_pk_bytes: bytes,
        request_data: bytes,
        private_key) -> bytes:
    """Composes an signed plaintext request."""
    # Compose the message.
    message = compose_unsigned_plaintext_request(
        nonce,
        account_id,
        response_pk_bytes,
        request_data)

    # Sign the message.
    message += sign_message(message, private_key)

    return message


class RequestClient(object):
    """Creates outgoing requests and accepts responses."""

    def __init__(self, account_id: AccountId, server_public_key, client_private_key):
        self.account_id = account_id
        self.server_public_key = server_public_key
        self.client_private_key = client_private_key

    def encrypt_request(self, request_data: bytes):
        """Encrypts a request message. Returns a (response private key, encrypted message) pair."""

        # First create the nonce.
        nonce = generate_nonce(32)

        # Generate a response key pair.
        reply_key = generate_key()
        sk_bytes = reply_key.secret
        pk_bytes = reply_key.public_key.format(True)

        # Compose the message.
        message = compose_signed_plaintext_request(
            nonce,
            self.account_id,
            pk_bytes,
            request_data,
            self.client_private_key)

        # Encrypt the message.
        return (sk_bytes, encrypt(self.server_public_key, message))

    def create_request(self, request_command: str, request_data: bytes):
        """Creates an encrypted request from a command and the request data."""
        return self.encrypt_request(request_command.encode('utf-8') + request_data)

    def decrypt_response(self, sk_bytes, encrypted_response: bytes) -> bytes:
        """Decrypts an encrypted response message."""
        return decrypt(sk_bytes, encrypted_response)


class RequestProcessingException(Exception):
    """An exception that is thrown when a request cannot be processed."""
    pass


class DecryptionException(Exception):
    """An exception that is thrown when decryption fails."""
    pass


class StatusCode(Enum):
    """An enumeration of possible response statuses."""
    SUCCESS = 0


class RequestServer(object):
    """Handles incoming requests."""

    def __init__(self, server: Server, private_key, max_nonce_count=10000, request_handlers=None):
        if request_handlers is None:
            request_handlers = DEFAULT_REQUEST_HANDLERS

        self.used_nonces = set()
        self.server = server
        self.max_nonce_count = max_nonce_count
        self.private_key = private_key
        self.request_handlers = request_handlers

    async def handle_request(self, request):
        """Handles an HTTP request."""
        # Decrypt the request.
        return web.Response(body=self.handle_request_body(await request.read()))

    def handle_request_body(self, request_body: bytes) -> bytes:
        """Handles an HTTP request body."""
        # Decrypt the request.
        account, pk_bytes, message = self.decrypt_request(request_body)

        # Decompose the request message into a command and data.
        request_command_bytes, request_data = take_length_prefixed(message)
        request_command = request_command_bytes.decrypt('utf-8')

        # Run the command on the data.
        if request_command not in self.request_handlers:
            raise RequestProcessingException(
                'Unknown request command %r.' % request_command)

        status_code, response_body = self.request_handlers[request_command](
            request_data, account, self.server)
        response = struct.pack('<i', status_code) + response_body

        # Encrypt the response.
        return self.encrypt_response(pk_bytes, response)

    def encrypt_response(self, pk_bytes, response: bytes) -> bytes:
        """Encrypts an outgoing message."""
        return encrypt(pk_bytes, response)

    def decrypt_request(self, encrypted_data: bytes):
        """Decrypts and verifies an incoming encrypted request message."""
        plaintext = data = decrypt(self.private_key, encrypted_data)

        # Process the nonce.
        nonce = data[:32]
        data = data[32:]
        if nonce in self.used_nonces:
            raise DecryptionException('Nonce %r is reused.' % nonce)

        if len(self.used_nonces) >= self.max_nonce_count:
            self.used_nonces.remove(random.choice(self.used_nonces))

        self.used_nonces.add(nonce)

        # Read the account name.
        account_id_bytes, data = take_length_prefixed(data)
        account_id = parse_account_id(account_id_bytes.decode('utf-8'))
        if not self.server.has_account(account_id):
            raise DecryptionException('Account %r does not exist.', account_id)

        account = self.server.get_account(account_id)

        # Read all the other data.
        pk_bytes, data = take_length_prefixed(data)
        message, data = take_length_prefixed(data)

        data_hash = SHA3_512.new(plaintext[:-len(data)])

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
            raise DecryptionException('Invalid signature.')

        return (account, pk_bytes, message)


def _handle_balance_request(data: bytes, account: Account, server: Server):
    """Handles an account balance request."""
    return (StatusCode.SUCCESS, struct.pack('<l', account.get_balance()))


# The server's default request handlers. A request handler takes request data, an account
# and a server as arguments and produces a (status code, response data) pair as return value.
DEFAULT_REQUEST_HANDLERS = {
    'balance': _handle_balance_request
}
