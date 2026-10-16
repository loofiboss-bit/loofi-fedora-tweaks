"""Installation identity and inert presentation regressions."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QCheckBox

from ui.flatpak_updates import FlatpakUpdatesCard, flatpak_review_lines
from ui.care_navigation import CareNavigationMixin

REF = "app/org.example.Editor/x86_64/stable"


def candidate(installation):
    return dict(installation=installation, ref=REF, name="Editor", origin="local", installed_commit="a" * 64,
                expected_commit="b" * 64, installed_version="1", available_version="2")


class FlatpakUpdatesPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def card(self):
        card = FlatpakUpdatesCard(service=Mock())
        self.addCleanup(card.deleteLater)
        return card

    def test_same_ref_is_selected_with_exact_installation_and_filter_preserves_it(self):
        card = self.card()
        card.apply_snapshot(dict(available=True, checked_at="2026-10-16T00:00:00Z", candidates=[candidate("user"), candidate("system")]))
        reviews = []
        card.actionReviewRequested.connect(lambda action, parameters: reviews.append((action, parameters)))
        checks = card.findChildren(QCheckBox)
        checks[0].setChecked(True)
        card.search.setText("does not match")
        card.review("system")
        self.assertEqual(reviews, [("update-flatpaks", {"installation": "system", "refs": [REF]})])
        card.review("user")
        self.assertEqual(len(reviews), 1)
        self.assertIn("2026-10-16", card.status.text())

    def test_preselection_and_runtime_navigation_do_not_query(self):
        card = self.card()
        routes = []
        card.routeRequested.connect(lambda route, context: routes.append((route, context)))
        card.preselect("user", [REF])
        card.service.discover.assert_not_called()
        card.set_outcome(SimpleNamespace(run_id="run-real", message="Verified", data={}), "user")
        card.runtime_button.click()
        self.assertEqual(routes, [("software:apps", {"section": "unused-runtimes", "installation": "user"})])
        card.service.discover.assert_not_called()
        card.record_button.click()
        self.assertEqual(routes[-1], ("changes", {"run_id": "run-real"}))

    def test_review_separates_selected_and_dependencies_with_commit_disclosure(self):
        app = {**candidate("user"), "operation": "update", "selected": True}
        runtime = {**candidate("user"), "ref": "runtime/org.example.Platform/x86_64/stable", "selected": False, "operation": "install"}
        plan = SimpleNamespace(policy_decision=SimpleNamespace(facts={"flatpak_updates": {"installations": [dict(installation="user", operations=[app, runtime])]}}))
        summary, technical = flatpak_review_lines(plan, str)
        self.assertIn("Selected applications", summary)
        self.assertIn("Required runtimes and extensions", summary)
        self.assertNotIn("b" * 64, "\n".join(summary))
        self.assertIn("b" * 64, "\n".join(technical))

    def test_result_keeps_partial_verification_per_ref(self):
        card = self.card()
        card.apply_snapshot(dict(available=True, candidates=[candidate("user")]))
        card._selected.add(("user", REF))
        outcome = SimpleNamespace(run_id="run-real", message="Needs attention", data={"verification_result": {"data": {"results": [dict(installation="user", ref=REF, status="verified"), dict(installation="system", ref=REF, status="unverified")]}}})
        card.set_outcome(outcome, "user")
        self.assertIn(f"user · {REF}: Verified", card.status.text())
        self.assertIn(f"system · {REF}: Unverified", card.status.text())
        self.assertEqual(card._selected, set())
        self.assertEqual(card._groups, [])

    def test_keyboard_selection_is_preserved_when_filter_cleared(self):
        card = self.card()
        card.apply_snapshot(dict(available=True, candidates=[candidate("user")]))
        check = card.findChildren(QCheckBox)[0]
        QTest.keyClick(check, Qt.Key.Key_Space)
        card.search.setText("absent")
        card.search.clear()
        self.assertTrue(check.isChecked())
        self.assertIn(("user", REF), card._selected)

    def test_app_update_handoff_marks_the_reviewed_candidate_as_selected(self):
        card = self.card()
        card.preselect("user", [REF])
        card._auto_review = True
        reviews = []
        card.actionReviewRequested.connect(lambda action, parameters: reviews.append((action, parameters)))

        card.apply_snapshot(dict(available=True, candidates=[candidate("user")]))

        check = card.findChildren(QCheckBox)[0]
        self.assertTrue(check.isChecked())
        self.assertEqual(reviews, [("update-flatpaks", {"installation": "user", "refs": [REF]})])

    @patch("ui.flatpak_updates.OperationControllerQtAdapter.start", return_value=True)
    def test_explicit_check_passes_exact_identity_and_cooperative_cancellation(self, start):
        card = self.card()
        card.preselect("user", [REF])
        self.assertTrue(card.check())
        operation = start.call_args.args[0]
        operation()
        kwargs = card.service.discover.call_args.kwargs
        self.assertEqual(kwargs["installation"], "user")
        self.assertEqual(kwargs["refs"], (REF,))
        self.assertTrue(callable(kwargs["cancelled"]))

    def test_navigation_rejects_malformed_identity_before_switch(self):
        shell = SimpleNamespace(switch_to_route=Mock())
        result = CareNavigationMixin._open_flatpak_context(shell, "maintenance:updates", {"section": "flatpak-updates", "installation": "../../other", "refs": [REF]})
        self.assertFalse(result)
        shell.switch_to_route.assert_not_called()

    def test_new_scope_clears_actions_and_late_previous_scope_is_ignored(self):
        card = self.card()
        snapshot = dict(available=True, candidates=[candidate("system")])
        card.apply_snapshot(snapshot)
        card.findChildren(QCheckBox)[0].setChecked(True)
        generation = card._generation
        card.preselect("user", [REF])
        self.assertEqual(card._groups, [])
        self.assertEqual(card._selected, set())
        card.apply_snapshot((generation, snapshot))
        self.assertEqual(card._groups, [])
        self.assertIn("user", card.status.text())
        card.service.discover.assert_not_called()

    def test_partial_installation_errors_do_not_hide_available_candidates(self):
        card = self.card()
        card.apply_snapshot(dict(available=True, status="partial", candidates=[candidate("user")], installations=[dict(installation="system", error="Unavailable")]))
        self.assertEqual(len(card._groups), 1)
        self.assertEqual(card._groups[0].title(), "user")
        self.assertIn("Some installations", card.status.text())
        self.assertIn("system: Unavailable", card.status.text())

    @patch("ui.flatpak_updates.OperationControllerQtAdapter.cancel")
    def test_stop_cancels_and_suppresses_automatic_review(self, cancel):
        card = self.card()
        card._auto_review = True
        card.request_stop()
        cancel.assert_called_once()
        self.assertFalse(card._auto_review)

    def test_valid_update_navigation_only_focuses_exact_identity(self):
        updates = Mock()
        shell = SimpleNamespace(switch_to_route=Mock(return_value=True), _sidebar_index={"utility_update": object()}, _real_widget_for_entry=Mock(return_value=SimpleNamespace(flatpak_updates=updates)))
        self.assertTrue(CareNavigationMixin._open_flatpak_context(shell, "maintenance:updates", {"section": "flatpak-updates", "installation": "user", "refs": [REF]}))
        updates.preselect.assert_called_once_with("user", [REF])
        updates.check.assert_not_called()

    def test_global_flatpak_check_uses_installation_bound_card(self):
        from ui.update_workflow import UpdateWorkflowPage
        page = SimpleNamespace(flatpak_updates=SimpleNamespace(check=Mock(return_value=True)))
        self.assertTrue(UpdateWorkflowPage.start_check(page, "flatpak"))
        page.flatpak_updates.check.assert_called_once_with()

    def test_runtime_navigation_preserves_named_installation_without_discovery(self):
        from PyQt6.QtWidgets import QComboBox
        insights = SimpleNamespace(installation=QComboBox(), inspect_button=Mock())
        insights.installation.addItems(["user", "system"])
        view = QComboBox()
        view.addItem("Installed", "installed")
        page = SimpleNamespace(installed_card=SimpleNamespace(insights=insights), view_filter=view, body_scroll=Mock())
        shell = SimpleNamespace(switch_to_route=Mock(return_value=True), _sidebar_index={"utility_install": object()}, _real_widget_for_entry=Mock(return_value=page))
        self.assertTrue(CareNavigationMixin._open_apps_unused_runtimes(shell, {"section": "unused-runtimes", "installation": "named-games"}))
        self.assertEqual(insights.installation.currentText(), "named-games")
        insights.inspect_button.setFocus.assert_called_once()
