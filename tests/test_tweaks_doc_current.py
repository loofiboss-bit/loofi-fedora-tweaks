"""docs/TWEAKS.md must match the declarative tweak catalog."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestTweaksDocCurrent(unittest.TestCase):
    def test_generated_doc_is_current(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "gen_tweaks_doc.py"), "--check"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
