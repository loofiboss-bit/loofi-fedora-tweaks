"""Tests for the v18 Haven release gate."""

import unittest

from scripts.validate_v18_haven import validate


class TestHavenGate(unittest.TestCase):
    def test_repository_contracts_are_consistent(self):
        self.assertEqual(validate(), [])


if __name__ == "__main__":
    unittest.main()
