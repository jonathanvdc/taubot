# This module defines the HTTP API. Note that this HTTP API is an atypical one; it is not REST-like
# and all data is encrypted. This has the advantage of requiring neither an HTTPS setup nor an
# authentication mechanism.
#
# The flow between client and server is as follows:
#
#    1. Client sends a message.
#        i.  The message starts off with a header, encrypted using PKCS#1 OAEP with the server's public key.
#            Such a header is simply a 16-byte AES128 key. Headers are length-prefixed.
#
#        ii. A 32-byte nonce and a length-prefixed MAC for the body.
#
#        iii.The message then proceeds with a body. The body is encrypted using AES128 in GCM with the key
#            specified in the header. Its plaintext consists of:
#            (a) a length-prefixed UTF-8 encoded account ID,
#            (b) a length-prefixed new 16-byte AES128 key for the server's response,
#            (c) the actual request (length-prefixed), and
#            (d) an ECDSA signature of the SHA3-512 digest of (ii)(a)(b)(c), signed with one of the client's associated keys.
#
#    2. Server responds. Its response is encrypted using the AES128 key (GCM again) sent by the client.
#       The encrypted data is again prefixed by a 32-byte nonce and a length-prefixed MAC.
#

import random
import struct
from fractions import Fraction
from enum import Enum
from Crypto.Signature import DSS
from Crypto.Hash import SHA3_512
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
from Crypto.PublicKey import RSA
from aiohttp import web
from accounting import parse_account_id, BaseAccount, AccountId, Server


def generate_server_key():
    """Generates a private server key."""
    return RSA.generate(2048)


def generate_nonce(length):
    """Generates a pseudorandom number."""
    return get_random_bytes(length)


def length_prefix(data: bytes) -> bytes:
    """Creates a length-prefixed byte string."""
    return struct.pack('<i', len(data)) + data


def take_length_prefixed(data: bytes):
    """Takes a byte string that starts with a length-prefixed byte string.
       Returns the contents of the length-prefixed byte string and the remaining
       bytes in `data`."""
    length, = struct.unpack('<i', data[:4])
    return take_bytes(data[4:], length)


def take_bytes(data: bytes, count: int):
    """Takes a byte string that starts with a length-prefixed byte string.
       Returns the contents of the length-prefixed byte string and the remaining
       bytes in `data`."""
    return (data[:count], data[count:])

def compose_unsigned_plaintext_request(account_id: AccountId, response_key_bytes: bytes, request_data: bytes):
    """Composes an unsigned plaintext request."""
    return b''.join([
        length_prefix(str(account_id).encode('utf-8')),
        length_prefix(response_key_bytes),
        length_prefix(request_data)
    ])


def sign_message(message: bytes, private_key) -> bytes:
    """Signs a message, producing a digital signature."""
    signer = DSS.new(private_key, 'fips-186-3')
    return signer.sign(SHA3_512.new(message))


def compose_signed_plaintext_request(
        nonce: bytes,
        account_id: AccountId,
        response_key_bytes: bytes,
        request_data: bytes,
        private_key) -> bytes:
    """Composes an signed plaintext request."""
    # Compose the message.
    message = compose_unsigned_plaintext_request(
        account_id,
        response_key_bytes,
        request_data)

    # Sign the message.
    message += sign_message(nonce + message, private_key)

    return message


class RequestClient(object):
    """Creates outgoing requests and accepts responses."""

    def __init__(self, account_id: AccountId, server_public_key, client_private_key):
        self.account_id = account_id
        self.server_public_key = server_public_key
        self.client_private_key = client_private_key

    def encrypt_request(self, request_data: bytes):
        """Encrypts a request message. Returns a (response secret key, encrypted message) pair."""

        # First create the nonce.
        nonce = generate_nonce(32)

        # Generate a response key.
        reply_key = get_random_bytes(16)

        # Compose the message.
        plaintext_body = compose_signed_plaintext_request(
            nonce,
            self.account_id,
            reply_key,
            request_data,
            self.client_private_key)

        # Generate the header.
        message_key = get_random_bytes(16)
        header = PKCS1_OAEP.new(self.server_public_key).encrypt(message_key)

        # Encrypt the message body with AES in GCM.
        cipher = AES.new(message_key, AES.MODE_GCM, nonce=nonce)
        body, tag = cipher.encrypt_and_digest(plaintext_body)

        # Encrypt the message.
        return (reply_key, length_prefix(header) + nonce + length_prefix(tag) + body)

    def create_request(self, request_command: str, request_data: bytes):
        """Creates an encrypted request from a command and the request data."""
        return self.encrypt_request(length_prefix(request_command.encode('utf-8')) + request_data)

    def decrypt_response(self, response_key, encrypted_response: bytes) -> bytes:
        """Decrypts an encrypted response message."""
        nonce, encrypted_response = take_bytes(encrypted_response, 32)
        tag, encrypted_response = take_length_prefixed(encrypted_response)
        return AES.new(response_key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(encrypted_response, tag)

    async def get_response(self, request_command: str, request_data: bytes, send_request) -> bytes:
        """Sends a command and reads the response."""
        reply_key, msg = self.create_request(request_command, request_data)
        enc_response = await send_request(msg)
        response = self.decrypt_response(reply_key, enc_response)
        status_code = StatusCode(struct.unpack('<i', response[:4])[0])
        response_body = response[4:]
        if status_code != StatusCode.SUCCESS:
            raise ResponseErrorException(
                status_code, response_body.decode('utf-8'))

        return response_body

    async def get_balance(self, send_request) -> bytes:
        """Gets an account's balance."""
        response = await self.get_response('balance', b'', send_request)
        numerator, denominator = struct.unpack('<ll', response)
        return Fraction(numerator, denominator)


class ResponseErrorException(Exception):
    """An exception that is thrown when a response cannot be obtained."""

    def __init__(self, status_code, message):
        super(message)
        self.status_code = status_code


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
        account, reply_key, message = self.decrypt_request(request_body)

        # Decompose the request message into a command and data.
        request_command_bytes, request_data = take_length_prefixed(message)
        request_command = request_command_bytes.decode('utf-8')

        # Run the command on the data.
        if request_command not in self.request_handlers:
            raise RequestProcessingException(
                'Unknown request command %r.' % request_command)

        status_code, response_body = self.request_handlers[request_command](
            request_data, account, self.server)
        response = struct.pack('<i', status_code.value) + response_body

        # Encrypt the response.
        return self.encrypt_response(reply_key, response)

    def encrypt_response(self, message_key, response: bytes) -> bytes:
        """Encrypts an outgoing message."""
        nonce = generate_nonce(32)
        enc_response, tag = AES.new(message_key, AES.MODE_GCM, nonce=nonce).encrypt_and_digest(response)
        return nonce + length_prefix(tag) + enc_response

    def decrypt_request(self, encrypted_data: bytes):
        """Decrypts and verifies an incoming encrypted request message."""
        # Decode and decrypt the header.
        header, encrypted_data = take_length_prefixed(encrypted_data)
        body_key = PKCS1_OAEP.new(self.private_key).decrypt(header)

        # Process the nonce.
        nonce, encrypted_data = take_bytes(encrypted_data, 32)
        if nonce in self.used_nonces:
            raise DecryptionException('Nonce %r is reused.' % nonce)

        if len(self.used_nonces) >= self.max_nonce_count:
            self.used_nonces.remove(random.choice(self.used_nonces))

        self.used_nonces.add(nonce)

        # Decrypt the body.
        tag, encrypted_data = take_length_prefixed(encrypted_data)
        plaintext = data = AES.new(body_key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(encrypted_data, tag)

        # Read the account name.
        account_id_bytes, data = take_length_prefixed(data)
        account_id = parse_account_id(account_id_bytes.decode('utf-8'))
        if not self.server.has_account(account_id):
            raise DecryptionException('Account %r does not exist.' % account_id)

        account = self.server.get_account(account_id)

        # Read all the other data.
        reply_key, data = take_length_prefixed(data)
        message, data = take_length_prefixed(data)

        data_hash = SHA3_512.new(nonce + plaintext[:-len(data)])

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

        return (account, reply_key, message)


def _handle_balance_request(data: bytes, account: BaseAccount, server: Server):
    """Handles an account balance request."""
    balance = account.get_balance()
    return (StatusCode.SUCCESS, struct.pack('<ll', balance.numerator, balance.denominator))


# The server's default request handlers. A request handler takes request data, an account
# and a server as arguments and produces a (status code, response data) pair as return value.
DEFAULT_REQUEST_HANDLERS = {
    'balance': _handle_balance_request
}
