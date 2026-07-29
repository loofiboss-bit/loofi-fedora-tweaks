"""Import and authority boundaries for the Compass Phase 1 domain."""

from __future__ import annotations

import subprocess
import sys
import unittest


class TestTroubleshootingArchitecture(unittest.TestCase):
    def test_import_starts_no_probe_write_timer_thread_or_ui(self):
        script = r"""
import pathlib
import subprocess
import sys
import threading

def reject(*args, **kwargs):
    raise AssertionError("side effect during troubleshooting import")

subprocess.run = reject
subprocess.Popen = reject
pathlib.Path.write_text = reject
pathlib.Path.write_bytes = reject
before = {(item.name, item.ident) for item in threading.enumerate()}
import core.troubleshooting
after = {(item.name, item.ident) for item in threading.enumerate()}
assert before == after
assert not any(name.startswith("PyQt6") for name in sys.modules)
assert "core.system_check.service" not in sys.modules
assert "core.change_journal.service" not in sys.modules
"""
        probe = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        self.assertEqual(probe.returncode, 0, probe.stderr)

    def test_domain_exports_data_contracts_not_collectors_or_executors(self):
        import core.troubleshooting as troubleshooting

        forbidden = {
            "CommandFacade",
            "ActionCenterOrchestrator",
            "SystemCheckService",
            "subprocess",
        }
        self.assertTrue(forbidden.isdisjoint(troubleshooting.__all__))


if __name__ == "__main__":
    unittest.main()
