"""Asynchronous local AppStream index presentation for the Apps workflow."""
from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton
from services.software.application_discovery import ApplicationDiscoveryCatalog, ApplicationDiscoveryService, DiscoverySnapshot
from ui.operation_worker import OperationControllerQtAdapter

CATALOG_PACKAGES = frozenset({"appstream-data", "rpmfusion-free-appstream-data", "rpmfusion-nonfree-appstream-data"})


class ApplicationDiscoveryMixin:
    def _init_discovery(self: Any, service=None) -> None:
        self._curated_catalog = self.catalog
        self._discovery_service = service or ApplicationDiscoveryService()
        self._discovery_snapshot = None
        self._discovery_adapter = OperationControllerQtAdapter(parent=self)
        self._discovery_adapter.finished.connect(self._apply_discovery)
        self._discovery_adapter.failed.connect(self._discovery_failed)
        self._discovery_adapter.stopped.connect(self._discovery_stopped)
        self.discovery_toggle = QCheckBox(self.tr("Include applications from local AppStream metadata"))
        self.discovery_toggle.setObjectName("applicationDiscoveryToggle")
        self.discovery_toggle.toggled.connect(self._toggle_discovery)
        self.intro.add_widget(self.discovery_toggle)
        controls = QHBoxLayout()
        self.discovery_status = QLabel(self.tr("Recommended applications are shown. The local metadata index has not been checked."))
        self.discovery_status.setWordWrap(True)
        self.discovery_status.setObjectName("applicationDiscoveryStatus")
        controls.addWidget(self.discovery_status, 1)
        self.discovery_refresh = QPushButton(self.tr("Reload local metadata"))
        self.discovery_refresh.setToolTip(self.tr("Read locally cached AppStream and package metadata. No network download is started."))
        self.discovery_refresh.clicked.connect(self.refresh_application_metadata)
        controls.addWidget(self.discovery_refresh)
        self.discovery_cancel = QPushButton(self.tr("Cancel"))
        self.discovery_cancel.clicked.connect(self._discovery_adapter.cancel)
        self.discovery_cancel.hide()
        controls.addWidget(self.discovery_cancel)
        self.intro.body.addLayout(controls)
        downloads = QHBoxLayout()
        self.discovery_refresh_target = QComboBox()
        self.discovery_refresh_target.setAccessibleName(self.tr("Metadata source or catalog package"))
        self.discovery_refresh_target.setToolTip(self.tr("RPM application catalogs are packages. Their installation or update requires a separate transaction review; RPM Fusion catalogs require the corresponding source."))
        self.discovery_refresh_target.addItem(self.tr("Choose metadata source…"), None)
        downloads.addWidget(self.discovery_refresh_target, 1)
        self.discovery_download = QPushButton(self.tr("Review metadata download"))
        self.discovery_download.setEnabled(False)
        self.discovery_refresh_target.currentIndexChanged.connect(self._metadata_target_changed)
        self.discovery_download.clicked.connect(self._review_metadata_download)
        downloads.addWidget(self.discovery_download)
        self.intro.body.addLayout(downloads)

    def _metadata_target_changed(self: Any) -> None:
        target = self.discovery_refresh_target.currentData()
        package = isinstance(target, tuple) and len(target) == 3 and target[0] == "catalog-rpm"
        self.discovery_download.setEnabled(target is not None)
        self.discovery_download.setText(self.tr("Review catalog package") if package else self.tr("Review metadata download"))

    def _review_metadata_download(self: Any) -> None:
        target = self.discovery_refresh_target.currentData()
        if not isinstance(target, tuple) or len(target) != 3:
            return
        source, installation, remote = target
        if source == "catalog-rpm":
            if remote in CATALOG_PACKAGES:
                self.actionReviewRequested.emit("install-application", {"source": "fedora", "package_id": remote})
            return
        parameters = {"source": source}
        if source == "flatpak":
            parameters.update(installation=installation, remote=remote)
        self.actionReviewRequested.emit("refresh-application-metadata", parameters)

    def _toggle_discovery(self: Any, enabled: bool) -> None:
        if enabled and self._discovery_snapshot is None:
            self.refresh_application_metadata()
        self._replace_discovery_catalog()

    def refresh_application_metadata(self: Any) -> None:
        if self._discovery_adapter.busy:
            return
        self.discovery_refresh.setEnabled(False)
        self.discovery_cancel.show()
        self.discovery_status.setText(self.tr("Reading local metadata…"))
        self._discovery_adapter.start(lambda: self._discovery_service.snapshot(cancelled=lambda: self._discovery_adapter.cancel_requested))

    def _apply_discovery(self: Any, snapshot: object) -> None:
        if not isinstance(snapshot, DiscoverySnapshot):
            self._discovery_failed("")
            return
        if snapshot.status == "cancelled":
            self.discovery_status.setText(self.tr("Metadata reload cancelled. The previous catalog is retained."))
            return
        self._discovery_snapshot = snapshot
        self.discovery_refresh_target.clear()
        self.discovery_refresh_target.addItem(self.tr("Choose metadata source…"), None)
        for source, installation, remote in snapshot.refresh_targets:
            label = self.tr("RPM package cache") if source == "fedora" else f"Flatpak · {installation} · {remote}"
            self.discovery_refresh_target.addItem(label, (source, installation, remote))
        if ("fedora", "", "") in snapshot.refresh_targets:
            for label, package in ((self.tr("Fedora catalog (RPM)"), "appstream-data"),
                                   (self.tr("RPM Fusion Free catalog (RPM)"), "rpmfusion-free-appstream-data"),
                                   (self.tr("RPM Fusion Nonfree catalog (RPM)"), "rpmfusion-nonfree-appstream-data")):
                self.discovery_refresh_target.addItem(label, ("catalog-rpm", "", package))
        state = {"available": self.tr("Local metadata available"), "partial": self.tr("Partial local metadata"),
                 "missing": self.tr("Metadata unavailable; applications may exist outside this index")}.get(snapshot.status, self.tr("Metadata unavailable"))
        self.discovery_status.setText(self.tr("%1 · Checked: %2 · Oldest metadata: %3").replace("%1", state).replace("%2", snapshot.checked_at).replace("%3", snapshot.metadata_updated_at or self.tr("Unknown")))
        self.discovery_status.setToolTip("\n".join(snapshot.issues))
        self._replace_discovery_catalog()

    def _replace_discovery_catalog(self: Any) -> None:
        snapshot = self._discovery_snapshot
        discovered = snapshot.records if snapshot is not None and self.discovery_toggle.isChecked() else ()
        identities = frozenset((item.installation, item.ref) for item in self.installed_card.inventory.applications if item.source == "flatpak")
        self.catalog = ApplicationDiscoveryCatalog(self._curated_catalog, discovered, installed_identities=identities) if discovered else self._curated_catalog
        current_category = self.category_filter.currentData()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem(self.tr("All categories"), "")
        for category in self.catalog.categories():
            self.category_filter.addItem(category, category)
        self.category_filter.setCurrentIndex(max(0, self.category_filter.findData(current_category)))
        self.category_filter.blockSignals(False)
        self._catalog_rows_initialized = False
        self._refresh_rows()

    def _discovery_failed(self: Any, _message: str) -> None:
        self.discovery_status.setText(self.tr("Local metadata could not be read. Applications may still be available. Reload to try again."))

    def _discovery_stopped(self: Any) -> None:
        self.discovery_refresh.setEnabled(True)
        self.discovery_cancel.hide()
        self._notify_stopped()
