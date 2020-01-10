#!/usr/bin/env python3

import sys
from os import path
sys.path.append(path.join(path.dirname(
    path.dirname(path.abspath(__file__))), 'src'))

import unittest
from utils import split_into_chunks


class UtilTests(unittest.TestCase):

    def test_split_into_chunks(self):
        """Tests that a message can be split into chunks."""
        self.assertListEqual(
            split_into_chunks(b'a' * 20 + b'\n' + b'a' * 20, 30),
            [b'a' * 20, b'a' * 20])
        self.assertListEqual(
            split_into_chunks(b'a' * 40 + b'\n' + b'a' * 10, 30),
            [b'a' * 30, b'a' * 10 + b'\n' + b'a' * 10])
        self.assertListEqual(
            split_into_chunks(b'a' * 10 + b'\n' + b'a' * 10 + b'\n' + b'a' * 10, 30),
            [b'a' * 10 + b'\n' + b'a' * 10, b'a' * 10])
        self.assertListEqual(
            split_into_chunks(b'a' * 10 + b'\n' + b'a' * 10 + b'\n' + b'a' * 50, 30),
            [b'a' * 10 + b'\n' + b'a' * 10, b'a' * 30, b'a' * 20])
        self.assertListEqual(
            split_into_chunks(b'a' * 10 + b'\n' + b'a' * 10 + b'\n' + b'a' * 80, 30),
            [b'a' * 10 + b'\n' + b'a' * 10, b'a' * 30, b'a' * 30, b'a' * 20])


if __name__ == '__main__':
    unittest.main()
