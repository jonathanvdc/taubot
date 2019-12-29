#!/usr/bin/env python3

import unittest

import sys
from os import path
sys.path.append(path.join(path.dirname(path.dirname(path.abspath(__file__))), 'src'))


from httpapi import length_prefix, take_length_prefixed

class IOHelpers(unittest.TestCase):

    def test_length_prefix(self):
        self.assertEqual(take_length_prefixed(length_prefix(b'hello'))[0], b'hello')
        msg = length_prefix(b'hello') + b'hi'
        hello, hi = take_length_prefixed(msg)
        self.assertEqual(hello, b'hello')
        self.assertEqual(hi, b'hi')

if __name__ == '__main__':
    unittest.main()
