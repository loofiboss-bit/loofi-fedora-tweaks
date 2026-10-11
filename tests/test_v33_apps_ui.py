"""Focused presentation regressions for the v33 application workflow."""
import unittest

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.catalog_models import FedoraVariant
from core.tasks.applications import ApplicationContext
from ui.install_workflow import InstallWorkflowPage


class AppsV33PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_page(self):
        page = InstallWorkflowPage(context=ApplicationContext(
            FedoraVariant.TRADITIONAL, frozenset({"fedora", "dnf5", "flatpak"}), online=True,
        ))
        page.show()
        self.app.processEvents()
        self.addCleanup(page.deleteLater)
        return page

    def test_tabs_are_catalog_installed_sources_and_details_live_in_sources(self):
        page = self.make_page()
        self.assertEqual([page.view_tabs.tabText(i) for i in range(page.view_tabs.count())], ["Catalog", "Installed", "Sources"])
        self.assertFalse(page.flathub_details.isVisible())
        page.view_tabs.setCurrentIndex(2)
        self.app.processEvents()
        self.assertTrue(page.sources_widget.isVisible())
        self.assertTrue(page.application_list.isHidden())
        self.assertTrue(page.review_card.isHidden())

    def test_switching_app_tabs_restores_visible_content_from_a_scrolled_catalog(self):
        page = self.make_page()
        page.resize(820, 520)
        self.app.processEvents()
        scrollbar = page.body_scroll.verticalScrollBar()
        self.assertGreater(scrollbar.maximum(), 0)
        scrollbar.setValue(scrollbar.maximum())
        page.view_tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.app.processEvents()

        self.assertEqual(scrollbar.value(), 0)
        self.assertTrue(page.installed_card.isVisible())
        button = page.installed_card.refresh_button
        button_rect = QRect(button.mapTo(page.body_scroll.viewport(), QPoint(0, 0)), button.size())
        self.assertTrue(page.body_scroll.viewport().rect().intersects(button_rect))

    def test_application_tabs_support_horizontal_keyboard_navigation(self):
        page = self.make_page()
        page.view_tabs.setCurrentIndex(0)
        page.view_tabs.setFocus()

        QTest.keyClick(page.view_tabs, Qt.Key.Key_Right)
        self.app.processEvents()

        self.assertEqual(page.view_tabs.currentData(), "installed")
        self.assertTrue(page.installed_card.isVisible())

    def test_selected_view_ignores_search_and_category_and_restores_filters(self):
        page = self.make_page()
        page._row_checks["firefox"].setChecked(True)
        page.search_input.setText("no matching application")
        page.category_filter.setCurrentIndex(page.category_filter.findData("Office"))
        self.assertTrue(all(item.isHidden() for _record, _eligibility, item in page._rows.values()))
        page.show_selected_button.click()
        self.app.processEvents()
        self.assertFalse(page._rows["firefox"][2].isHidden())
        self.assertTrue(all(item.isHidden() for app_id, (_record, _eligibility, item) in page._rows.items() if app_id != "firefox"))
        page.show_selected_button.click()
        self.app.processEvents()
        self.assertTrue(page._rows["firefox"][2].isHidden())
        self.assertEqual(page.search_input.text(), "no matching application")
        self.assertEqual(page.category_filter.currentData(), "Office")

    def test_individual_deselect_and_clear_selection(self):
        page = self.make_page()
        page._row_checks["firefox"].setChecked(True)
        page._row_checks["vlc"].setChecked(True)
        page.show_selected_button.click()
        self.assertEqual(set(page.selected_application_ids()), {"firefox", "vlc"})
        page._row_checks["firefox"].setChecked(False)
        self.assertEqual(page.selected_application_ids(), ("vlc",))
        page.clear_selection_button.click()
        self.assertEqual(page.selected_application_ids(), ())
        self.assertFalse(page.show_selected_button.isChecked())
        self.assertFalse(page.review_button.isEnabled())

    def test_catalog_keeps_compact_dnf_source_status_visible(self):
        from services.software.source_status import DnfRepository, DnfSourceSnapshot

        page = self.make_page()
        page._apply_dnf_source_badges(DnfSourceSnapshot(
            "2026-10-11T12:00:00Z",
            (DnfRepository("rpmfusion-free", "RPM Fusion Free", True),),
        ))
        self.assertTrue(page.dnf_source_summary.isVisible())
        self.assertIn("RPM Fusion Free: Enabled", page.dnf_source_summary.text())
        page.view_tabs.setCurrentIndex(2)
        self.app.processEvents()
        self.assertTrue(page.sources_widget.isVisible())
        self.assertFalse(page.dnf_source_summary.isVisible())

    def test_review_bundle_uses_shared_dialog_with_visible_exact_scope(self):
        from types import MappingProxyType, SimpleNamespace
        from unittest.mock import Mock, patch

        from PyQt6.QtWidgets import QDialog
        from ui.main_window_utility import MainWindowUtilityMixin

        item = SimpleNamespace(
            title="Firefox",
            parameters=MappingProxyType({"source": "flatpak", "package_id": "org.mozilla.firefox"}),
            metadata=MappingProxyType({"source_label": "Flathub"}),
        )
        bundle = SimpleNamespace(
            title="Install selected applications", description="Review selected apps.",
            metadata=MappingProxyType({"variant": "traditional"}), items=(item,),
        )
        owner = SimpleNamespace(
            tr=lambda text: text, _utility_operation_adapter=None,
            _set_utility_notice=Mock(), _start_utility_bundle=Mock(return_value=True),
        )
        page = object()
        with patch("ui.confirm_dialog.ReviewedActionDialog") as dialog_type:
            dialog_type.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.assertFalse(MainWindowUtilityMixin._review_utility_bundle(owner, page, SimpleNamespace(bundle=bundle)))
            scope = dialog_type.call_args.args[2]
            self.assertIn("Firefox", scope)
            self.assertIn("Source: Flathub", scope)
            self.assertIn("Package identifier: org.mozilla.firefox", scope)
            self.assertIn("System Flatpak installation", scope)
            owner._start_utility_bundle.assert_not_called()

            dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
            self.assertTrue(MainWindowUtilityMixin._review_utility_bundle(owner, page, SimpleNamespace(bundle=bundle)))
            owner._start_utility_bundle.assert_called_once()


if __name__ == "__main__":
    unittest.main()
