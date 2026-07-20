"""Regression gate for v17 canonical UI mutation ownership."""

import unittest

from scripts.validate_v17_assurance import violations


class TestV17AssuranceInventory(unittest.TestCase):
    def test_canonical_ui_entry_points_have_no_direct_execution_calls(self):
        self.assertEqual(violations(), [])


if __name__ == "__main__":
    unittest.main()
