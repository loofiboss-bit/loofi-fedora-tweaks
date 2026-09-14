"""Focused v27 UX contracts for the five core user journeys."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QFrame, QPushButton

from core.home import HomeSummary, Recommendation
from core.navigation import (
    FedoraVariant,
    GlobalSearchModel,
    NavigationContext,
    SearchFilter,
    SearchResultKind,
)
from services.software.update_overview import (
    UpdateItem,
    UpdateOverviewSnapshot,
    UpdateSourceResult,
)
from ui.atlas_dashboard_tab import AtlasDashboardTab
from ui.global_search import GlobalSearchDialog
from ui.maintenance_updates import _UpdatesSubTab


def _empty_summary() -> HomeSummary:
    return HomeSummary(
        overall_state="unknown",
        data_state="empty",
        summary="No system check has been run yet.",
        generated_at=datetime.now(timezone.utc),
        primary_recommendation=Recommendation(
            "home-first-review",
            "first_health_review",
            "Review system health",
            "Run a local system check.",
            "maintenance:health-timeline",
            "info",
        ),
        attention_items=(),
        common_tasks=(),
        recent_change=None,
        freshness_state="unavailable",
    )


class _SummaryProvider:
    def summary(self) -> HomeSummary:
        return _empty_summary()


class TestV27HomePresentation:
    def test_empty_home_has_one_explicit_system_check_action(self):
        app = QApplication.instance() or QApplication([])
        del app
        tab = AtlasDashboardTab(home_service=_SummaryProvider())
        try:
            check = tab.findChild(QPushButton, "homeCheckNow")
            assert check is not None
            assert check.text() == "Run system check"
            assert tab.findChild(QFrame, "homePrimaryRecommendation") is None
            assert tab.status_unavailable.title_label.text() == "No system check has been run yet"
            assert tab.state_card.property("overallState") == "unknown"
        finally:
            tab.deleteLater()


class TestV27UpdatesJourney:
    @classmethod
    def setup_class(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @patch("ui.maintenance_updates.SystemManager.get_platform_profile", return_value=MagicMock(
        deployment_backend=MagicMock(value="dnf5"),
        package_manager_name="dnf5",
    ))
    def test_fresh_source_opens_review_directly(self, _profile):
        tab = _UpdatesSubTab()
        try:
            requests: list[tuple[str, object]] = []
            tab.actionCenterRequested.connect(
                lambda action_id, parameters: requests.append((action_id, parameters))
            )
            assert not tab.btn_dnf.isEnabled()
            snapshot = UpdateOverviewSnapshot(
                sources=(
                    UpdateSourceResult(
                        "system",
                        "available",
                        "2026-09-13T10:00:00+00:00",
                        (UpdateItem("bash.x86_64", "5.2"),),
                        stale=False,
                    ),
                    UpdateSourceResult("flatpak"),
                    UpdateSourceResult("firmware"),
                ),
                backend="dnf5",
                support_status="supported",
            )
            tab.overview.set_snapshot(snapshot)
            assert tab.btn_dnf.isEnabled()

            tab.btn_dnf.click()
            assert requests == [("update-fedora-system", {})]
            assert tab.update_state.property("updateLifecycleState") == "review"
        finally:
            tab.deleteLater()

    @patch("ui.maintenance_updates.SystemManager.get_platform_profile", return_value=MagicMock(
        deployment_backend=MagicMock(value="dnf5"),
        package_manager_name="dnf5",
    ))
    def test_preview_source_remains_visible_but_cannot_open_review(self, _profile):
        tab = _UpdatesSubTab()
        try:
            snapshot = UpdateOverviewSnapshot(
                sources=(
                    UpdateSourceResult(
                        "system",
                        "available",
                        "2026-09-13T10:00:00+00:00",
                        (UpdateItem("bash.x86_64", "5.2"),),
                        stale=False,
                    ),
                    UpdateSourceResult("flatpak"),
                    UpdateSourceResult("firmware"),
                ),
                backend="dnf5",
                support_status="preview",
            )
            tab.overview.set_snapshot(snapshot)

            assert tab.btn_dnf.property("sourceStatus") == "available"
            assert tab.btn_dnf.property("reviewPolicyAllowed") is False
            assert not tab.btn_dnf.isEnabled()
        finally:
            tab.deleteLater()


class TestV27GlobalSearch:
    @classmethod
    def setup_class(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_page_search_keeps_actions_in_separate_mode(self):
        known_fedora = NavigationContext(
            fedora_variant=FedoraVariant.TRADITIONAL,
            capabilities=frozenset({"dnf", "dnf5", "fedora"}),
        )
        page_dialog = GlobalSearchDialog(GlobalSearchModel(known_fedora), MagicMock())
        action_dialog = GlobalSearchDialog(
            GlobalSearchModel(known_fedora),
            MagicMock(),
            search_filter=SearchFilter.ACTIONS,
        )
        try:
            assert page_dialog._visible_results
            assert all(
                result.kind is not SearchResultKind.ACTION
                for result in page_dialog._visible_results
            )
            assert action_dialog._visible_results
            assert all(
                result.kind is SearchResultKind.ACTION
                for result in action_dialog._visible_results
            )
            assert "Ctrl+Shift+K" in page_dialog.hint_label.text()
        finally:
            page_dialog.deleteLater()
            action_dialog.deleteLater()
