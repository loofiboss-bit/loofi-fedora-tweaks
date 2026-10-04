"""Wayfinder application identities, retained selection, and update source UX."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from core.catalog_models import FedoraVariant
from core.tasks import ApplicationContext, UpdateSourceState
from ui.install_workflow import InstallWorkflowPage
from ui.update_workflow import UpdateWorkflowPage


class TestWayfinderApplications(unittest.TestCase):
    def setUp(self):
        self.context = ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"fedora", "dnf5"}), online=True)
        self.page = InstallWorkflowPage(context=self.context)
        self.addCleanup(self.page.close)

    def test_rich_identity_and_bidirectional_selection_survive_filters(self):
        record, eligibility, item = self.page._rows["firefox"]
        row = self.page.application_list.itemWidget(item)
        self.assertEqual(row.findChild(QLabel, "applicationRowTitle").text(), record.name)
        self.assertEqual(row.findChild(QLabel, "applicationRowDescription").text(), record.description)
        self.assertIn(record.source_label, str(item.data(Qt.ItemDataRole.AccessibleTextRole)))
        self.assertNotIn("Installed", str(item.data(Qt.ItemDataRole.AccessibleTextRole)))
        self.page._row_checks[record.id].click()
        self.assertEqual(item.checkState(), Qt.CheckState.Checked)
        self.page.search_input.setText("git")
        self.assertEqual(self.page.selected_application_ids(), ("firefox",))
        self.page.search_input.clear()
        item = self.page._rows["firefox"][2]
        self.assertTrue(self.page._row_checks["firefox"].isChecked())
        item.setCheckState(Qt.CheckState.Unchecked)
        self.assertFalse(self.page._row_checks["firefox"].isChecked())
        self.assertFalse(self.page.review_button.isEnabled())

    def test_bundle_results_show_application_names_and_independent_failure(self):
        self.page._row_checks["firefox"].click()
        self.page._row_checks["git"].click()
        selection = self.page.review_selection()
        results = tuple(SimpleNamespace(item_id=item.item_id, action_id=item.action_id,
                                        status="succeeded" if index == 0 else "failed", message="Result")
                        for index, item in enumerate(selection.bundle.items))
        self.page.set_results(SimpleNamespace(items=results))
        self.assertIn("Firefox", self.page.results_list.item(0).text())
        self.assertIn("Git", self.page.results_list.item(1).text())
        self.assertIn("Failed", self.page.results_list.item(1).text())
        self.assertEqual(self.page.selected_application_ids(), ("firefox", "git"))

    def test_zero_matches_preserve_selection_and_footer_outside_content(self):
        self.page._row_checks["git"].click()
        self.page.search_input.setText("no-such-curated-application")
        self.assertIn("No applications match", self.page.match_summary.text())
        self.assertTrue(self.page.review_button.isEnabled())
        self.assertEqual(self.page.layout().indexOf(self.page.review_card), 1)


class TestWayfinderUpdateSources(unittest.TestCase):
    def setUp(self):
        self.page = UpdateWorkflowPage(service=Mock())
        self.addCleanup(self.page.close)

    def test_independent_status_timestamp_and_next_action(self):
        self.assertIn("Never", self.page._checked_labels["system"].text())
        self.assertEqual(self.page._cards["system"][1].text_label.text(), "Not checked")
        self.page.set_source(UpdateSourceState("system", "up_to_date", checked_at="2026-10-04T10:00:00Z", stale=False))
        self.assertEqual(self.page._cards["system"][1].text_label.text(), "No updates")
        self.assertIn("2026-10-04T10:00:00Z", self.page._checked_labels["system"].text())
        self.page.set_source(UpdateSourceState("flatpak", "error", message="Remote failed"))
        self.assertEqual(self.page._cards["flatpak"][1].text_label.text(), "Check failed")
        self.assertIn("Remote failed", self.page._cards["flatpak"][2].text())
        self.page.set_source(UpdateSourceState("firmware", "awaiting_reboot", reboot_required=True, stale=False))
        self.assertEqual(self.page._cards["firmware"][1].text_label.text(), "Reboot required")
        self.assertEqual(self.page.source_button("firmware").text(), "Continue")
        self.assertEqual(self.page.source_state("system").status, "up_to_date")

    def test_grid_stacks_narrow_and_equal_cards_wide(self):
        grid = self.page.source_grid
        grid._reflow(600)
        self.assertEqual(grid._columns, 1)
        grid._reflow(1000)
        self.assertEqual(grid._columns, 3)
        for index, source in enumerate(("system", "flatpak", "firmware")):
            self.assertIs(grid.grid.itemAtPosition(0, index).widget(), self.page._cards[source][0])
