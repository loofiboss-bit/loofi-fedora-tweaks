"""Bounded read-only tweak inspection and schema reuse coverage."""

from __future__ import annotations

import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.executor.action_result import ActionResult
from core.tasks.tweaks import BY_ID, kde_capability_error, snapshot


def _profile() -> SimpleNamespace:
    return SimpleNamespace(
        is_fedora=True,
        is_atomic=False,
        desktop=SimpleNamespace(value="gnome"),
        deployment_backend=SimpleNamespace(value="dnf5"),
    )


@patch("core.tasks.tweaks.kde_capability_error", return_value="")
@patch("core.tasks.tweaks.visible_tweaks")
@patch("core.tasks.tweak_history.read_tweak_runs", return_value=((), ""))
class TestTweakSnapshotBudget(unittest.TestCase):
    def setUp(self) -> None:
        self.tweaks = tuple(BY_ID[item] for item in ("gnome-hot-corners", "gnome-clock-date", "gnome-edge-tiling"))
        self.profile = _profile()
        self.runtime = SimpleNamespace(execute_read_only=Mock())

    def _snapshot(self, visible_tweaks, **kwargs):
        visible_tweaks.return_value = self.tweaks
        return snapshot(self.profile, self.runtime, **kwargs)

    def test_zero_budget_marks_every_value_unknown_without_probing(self, _read_runs, visible_tweaks, _capability) -> None:
        progress = []

        states = self._snapshot(visible_tweaks, budget_seconds=0, on_progress=lambda done, total: progress.append((done, total)))

        self.runtime.execute_read_only.assert_not_called()
        self.assertEqual([state.status for state in states], ["unavailable"] * 3)
        self.assertTrue(all("0-second" in state.message for state in states))
        self.assertEqual(progress, [(0, 3)])

    def test_timeout_keeps_completed_result_and_marks_remaining_values_unknown(self, _read_runs, visible_tweaks, _capability) -> None:
        now = [0.0]
        timeouts = []

        def read(_vector, **kwargs):
            timeouts.append(kwargs["timeout"])
            now[0] = 17.0 if len(timeouts) == 1 else 20.0
            return ActionResult.ok("Read setting", stdout="true\n")

        self.runtime.execute_read_only.side_effect = read
        progress = []

        states = self._snapshot(
            visible_tweaks,
            budget_seconds=20,
            clock=lambda: now[0],
            on_progress=lambda done, total: progress.append((done, total)),
        )

        self.assertEqual([state.status for state in states[:2]], ["ready", "ready"])
        self.assertTrue(all(state.value == "true" for state in states[:2]))
        self.assertEqual(states[2].status, "unavailable")
        self.assertIn("20-second", states[2].message)
        self.assertEqual(timeouts, [8.0, 3.0])
        self.assertEqual(progress[-1], (2, 3))
        self.assertEqual(self.runtime.execute_read_only.call_count, 2)

    def test_cancellation_keeps_completed_result_and_marks_remaining_values_unknown(self, _read_runs, visible_tweaks, _capability) -> None:
        cancelled = [False]

        def read(_vector, **_kwargs):
            cancelled[0] = True
            return ActionResult.ok("Read setting", stdout="true\n")

        self.runtime.execute_read_only.side_effect = read
        progress = []

        states = self._snapshot(
            visible_tweaks,
            is_cancelled=lambda: cancelled[0],
            on_progress=lambda done, total: progress.append((done, total)),
        )

        self.assertEqual(states[0].status, "ready")
        self.assertTrue(all(state.status == "unavailable" for state in states[1:]))
        self.assertTrue(all("cancelled" in state.message for state in states[1:]))
        self.assertEqual(progress[-1], (1, 3))
        self.assertEqual(self.runtime.execute_read_only.call_count, 1)


class TestKdeSchemaCache(unittest.TestCase):
    @patch("pathlib.Path.open")
    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    @patch("core.tasks.tweaks._DOLPHIN_SCHEMA", Path("dolphin_generalsettings.kcfg"))
    def test_snapshot_cache_reads_shared_dolphin_schema_once(self, _which, open_schema) -> None:
        schema = b"""<?xml version='1.0'?>
          <!DOCTYPE kcfg SYSTEM "http://www.kde.org/standards/kcfg/1.0/kcfg.dtd">
          <kcfg><group name='General'>
          <entry key='EditableUrl' type='Bool'/>
          <entry key='RememberOpenedTabs' type='Bool'/>
        </group></kcfg>"""
        cache = {}
        open_schema.return_value = io.BytesIO(schema)
        self.assertEqual(kde_capability_error("kde-dolphin-editable-location", schema_cache=cache), "")
        self.assertEqual(kde_capability_error("kde-dolphin-remember-tabs", schema_cache=cache), "")

        self.assertEqual(open_schema.call_count, 1)
        self.assertEqual(len(cache), 1)

    @patch("pathlib.Path.open")
    @patch("core.tasks.tweaks.shutil.which", return_value="/usr/bin/tool")
    def test_unexpected_doctype_remains_rejected(self, _which, open_schema) -> None:
        open_schema.return_value = io.BytesIO(b"<!DOCTYPE kcfg [<!ENTITY unsafe 'value'>]><kcfg/>")

        error = kde_capability_error("kde-dolphin-editable-location", schema_cache={})

        self.assertIn("could not be read safely", error)


if __name__ == "__main__":
    unittest.main()
