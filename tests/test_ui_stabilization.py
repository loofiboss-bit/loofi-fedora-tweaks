"""Regression coverage for activity lifetimes, date filters, and app selection."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import Qt

from core.catalog_models import FedoraVariant
from core.change_journal.models import ChangeJournalSnapshot
from core.tasks import ApplicationContext
from ui.activity_recovery_tab import ActivityRecoveryTab
from ui.install_workflow import InstallWorkflowPage


class TestStableApplicationSelection(unittest.TestCase):
    def setUp(self):
        self.context = ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"fedora", "dnf5"}), online=True)
        self.page = InstallWorkflowPage(context=self.context)
        self.addCleanup(self.page.close)

    def test_hidden_selections_remain_in_summary_and_review(self):
        self.page._rows["firefox"][2].setCheckState(Qt.CheckState.Checked)
        self.page.search_input.setText("git")
        self.assertNotIn("firefox", self.page._rows)
        self.assertEqual(self.page.selected_application_ids(), ("firefox",))
        self.assertIn("Firefox", self.page.review_summary.text())
        self.page._rows["git"][2].setCheckState(Qt.CheckState.Checked)
        self.page.category_filter.setCurrentText("Multimedia")
        self.assertEqual(set(self.page.selected_application_ids()), {"firefox", "git"})
        self.assertIn("2 selected", self.page.review_summary.text())
        selection = self.page.review_selection()
        self.assertIsNotNone(selection)
        self.assertEqual(selection.count, 2)
        self.page.category_filter.setCurrentIndex(0)
        self.page.search_input.clear()
        self.assertEqual(self.page._rows["firefox"][2].checkState(), Qt.CheckState.Checked)
        self.page._rows["firefox"][2].setCheckState(Qt.CheckState.Unchecked)
        self.assertEqual(self.page.selected_application_ids(), ("git",))

    def test_context_prunes_hidden_installed_or_unavailable_selections(self):
        self.page._rows["firefox"][2].setCheckState(Qt.CheckState.Checked)
        self.page._rows["git"][2].setCheckState(Qt.CheckState.Checked)
        self.page.search_input.setText("vlc")
        self.page.set_context(ApplicationContext(
            FedoraVariant.TRADITIONAL, frozenset({"fedora", "dnf5"}), online=True, installed_ids=frozenset({"firefox"}),
        ))
        self.assertEqual(self.page.selected_application_ids(), ("git",))
        self.page.set_context(ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"fedora"}), online=True))
        self.assertEqual(self.page.selected_application_ids(), ())
        self.assertFalse(self.page.review_button.isEnabled())


class TestActivityDateValidation(unittest.TestCase):
    @patch("ui.activity_recovery_tab.ActivityJournalWorker")
    def test_invalid_dates_never_start_collection_or_discard_snapshot(self, worker_class):
        service = Mock()
        page = ActivityRecoveryTab(journal_service=service)
        self.addCleanup(page.close)
        snapshot = ChangeJournalSnapshot(events=(), sources=(), generated_at=100.0)
        page._loaded(snapshot)
        for since, until in (("invalid", ""), ("2026-02-30", ""), ("nan", ""), ("", "inf"), ("-inf", ""), ("1e500", ""), ("200", "100")):
            with self.subTest(since=since, until=until):
                page.since_input.setText(since)
                page.until_input.setText(until)
                page.load_activity(refresh=False)
                self.assertIs(page._snapshot, snapshot)
                self.assertEqual(page.property("presentationState"), "empty")
                self.assertTrue(page.feedback.isVisibleTo(page))
                worker_class.assert_not_called()
                service.snapshot.assert_not_called()

    def test_valid_dates_timestamps_and_equal_bounds(self):
        page = ActivityRecoveryTab(journal_service=Mock())
        self.addCleanup(page.close)
        page.since_input.setText("2026-10-02T00:00:00Z")
        page.until_input.setText("2026-10-03")
        filters = page._current_filters()
        self.assertLess(filters["since"], filters["until"])
        page.since_input.setText("100")
        page.until_input.setText("100")
        self.assertEqual(page._current_filters()["since"], 100.0)

    @patch("ui.activity_recovery_tab.ActivityJournalWorker")
    def test_cleanup_is_idempotent_and_blocks_new_work(self, worker_class):
        page = ActivityRecoveryTab(journal_service=Mock())
        page.cleanup()
        page.cleanup()
        page.load_activity(refresh=True)
        worker_class.assert_not_called()
        page.close()


class TestActivityThreadShutdown(unittest.TestCase):
    def test_close_and_direct_destruction_survive_slow_error_and_cancelled_workers(self):
        source = Path(__file__).resolve().parents[1] / "loofi-fedora-tweaks"
        script = textwrap.dedent("""
            import sys, threading, time
            from unittest.mock import Mock
            from PyQt6 import sip
            from PyQt6.QtCore import QCoreApplication, QEvent
            from PyQt6.QtWidgets import QApplication
            from core.change_journal.models import ChangeJournalSnapshot
            from ui.activity_recovery_tab import ActivityRecoveryTab, _ACTIVE_JOURNAL_WORKERS
            app = QApplication([])
            started = threading.Event()
            release = threading.Event()
            mode, destruction = sys.argv[1:]
            def collect(**kwargs):
                started.set()
                assert release.wait(3)
                if mode == 'error':
                    raise ValueError('synthetic source failure')
                return ChangeJournalSnapshot(events=(), sources=(), generated_at=100.0)
            page = ActivityRecoveryTab(journal_service=Mock(snapshot=Mock(side_effect=collect)))
            page.load_activity(refresh=False)
            worker = page._worker
            assert started.wait(2)
            if mode == 'cancel':
                worker.cancel()
            if destruction == 'close':
                page.close()
                assert page._closing
                assert page._snapshot is None
            else:
                sip.delete(page)
            assert worker in _ACTIVE_JOURNAL_WORKERS
            release.set()
            deadline = time.monotonic() + 3
            while _ACTIVE_JOURNAL_WORKERS and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.005)
            assert not _ACTIVE_JOURNAL_WORKERS
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            if destruction == 'close':
                assert page._snapshot is None
                sip.delete(page)
            print('clean shutdown')
        """)
        env = dict(os.environ, PYTHONPATH=str(source), QT_QPA_PLATFORM="offscreen")
        for mode in ("slow", "error", "cancel"):
            for destruction in ("close", "delete"):
                with self.subTest(mode=mode, destruction=destruction):
                    result = subprocess.run(
                        [sys.executable, "-c", script, mode, destruction], capture_output=True, text=True, env=env, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("clean shutdown", result.stdout)
                    self.assertNotIn("QThread: Destroyed", result.stderr)
