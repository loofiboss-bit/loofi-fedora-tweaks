"""Installation-bound Flatpak discovery and review presentation."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui.components import Card, DetailsDisclosure
from ui.operation_worker import OperationControllerQtAdapter


class FlatpakUpdatesCard(Card):
    actionReviewRequested = pyqtSignal(str, object)
    routeRequested = pyqtSignal(str, object)
    stopped = pyqtSignal()
    checkStarted = pyqtSignal()

    def __init__(self, *, service=None, show_updates_link=False, parent=None):
        super().__init__(self.tr("Flatpak applications"), self.tr("Check each installation, select applications, then review their complete transaction."))
        self.service = service
        self._installation = None
        self._refs = ()
        self._auto_review = False
        self._selected = set()
        self._groups = []
        self._rows = []
        self._run_id = ""
        self._generation = 0
        self.check_button = QPushButton(self.tr("Check for updates"))
        self.check_button.clicked.connect(lambda: self.check())
        self.cancel_button = QPushButton(self.tr("Cancel check"))
        self.cancel_button.clicked.connect(self.request_stop)
        self.cancel_button.hide()
        self.add_widget(self.check_button)
        self.add_widget(self.cancel_button)
        self.status = QLabel(self.tr("Updates have not been checked."))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.add_widget(self.status)
        self.updates_button = QPushButton(self.tr("Open in Updates"))
        self.updates_button.clicked.connect(lambda: self.routeRequested.emit("maintenance:updates", {"section": "flatpak-updates", "installation": self._installation or "", "refs": list(self._refs)}))
        self.add_widget(self.updates_button)
        self.updates_button.setVisible(show_updates_link)
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr("Filter Flatpak updates…"))
        self.search.setAccessibleName(self.tr("Filter Flatpak updates"))
        self.search.textChanged.connect(self._filter)
        self.add_widget(self.search)
        self.record_button = QPushButton(self.tr("Open recorded operation"))
        self.record_button.clicked.connect(lambda: self.routeRequested.emit("changes", {"run_id": self._run_id}))
        self.record_button.hide()
        self.add_widget(self.record_button)
        self.runtime_button = QPushButton(self.tr("Inspect unused runtimes"))
        self.runtime_button.clicked.connect(self._open_runtimes)
        self.runtime_button.hide()
        self.add_widget(self.runtime_button)
        self._adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.started.connect(self.checkStarted.emit)
        self._adapter.finished.connect(self.apply_snapshot)
        self._adapter.failed.connect(lambda message: self.status.setText(self.tr("Update check unavailable: %1").replace("%1", str(message))))
        self._adapter.cancelled.connect(lambda: self.status.setText(self.tr("Update check cancelled.")))
        self._adapter.stopped.connect(self._stopped)

    @property
    def busy(self):
        return self._adapter.busy

    def preselect(self, installation=None, refs=()):
        """Carry identity without querying or executing anything."""
        self._generation += 1
        if self.busy:
            self._adapter.cancel()
        self._run_id = ""
        self.record_button.hide()
        self.runtime_button.hide()
        self._auto_review = False
        self._selected.clear()
        self._clear_candidates()
        self._installation, self._refs = installation, tuple(refs)
        self.status.setText(self.tr("Selected installation: %1. Check to read current updates.").replace("%1", installation or self.tr("All installations")))
        self.check_button.setFocus()

    def check(self, installation=None, refs=None, *, auto_review=False):
        if self.busy:
            return False
        if installation is not None or refs is not None:
            self.preselect(installation, refs or ())
        if self.service is None:
            from services.software.flatpak_updates import FlatpakUpdatesService
            self.service = FlatpakUpdatesService()
        self._auto_review = auto_review
        self.check_button.setEnabled(False)
        self.cancel_button.show()
        for group in self._groups:
            group.setEnabled(False)
        self.status.setText(self.tr("Checking Flatpak installations…"))
        generation, scope, refs = self._generation, self._installation, self._refs
        return self._adapter.start(lambda: (generation, self.service.discover(installation=scope, refs=refs, cancelled=lambda: self._adapter.cancel_requested)))

    def _clear_candidates(self):
        for group in self._groups:
            self.body.removeWidget(group)
            group.deleteLater()
        self._groups, self._rows = [], []

    def apply_snapshot(self, snapshot):
        if isinstance(snapshot, tuple) and len(snapshot) == 2:
            generation, snapshot = snapshot
            if generation != self._generation:
                return
        data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
        self._clear_candidates()
        candidates = data.get("candidates", [])
        identities = {(item["installation"], item["ref"]) for item in candidates}
        auto_review = bool(self._auto_review and self._installation and candidates)
        if auto_review:
            self._selected = identities
        else:
            self._selected.intersection_update(identities)
        messages = [self.tr("Checked: %1").replace("%1", str(data.get("checked_at", "")))]
        if data.get("status") == "partial":
            messages.append(self.tr("Some installations could not be checked. Available results remain usable."))
        if data.get("error"):
            messages.append(str(data["error"]))
        for installation in data.get("installations", []):
            if installation.get("error"):
                messages.append(f"{installation['installation']}: {installation['error']}")
        if not candidates:
            messages.append(self.tr("No update candidates were reported.") if data.get("available") else self.tr("Update discovery is unavailable."))
        self.status.setText("\n".join(messages))
        for installation in sorted({item["installation"] for item in candidates}):
            group = QGroupBox(installation)
            layout = QVBoxLayout(group)
            items = [item for item in candidates if item["installation"] == installation]
            checks = []
            for item in items:
                key = (installation, item["ref"])
                label = self.tr("%1 · %2 → %3 · %4").replace("%1", item.get("name") or item["ref"]).replace("%2", item.get("installed_version") or self.tr("Unknown version")).replace("%3", item.get("available_version") or self.tr("Update available")).replace("%4", item.get("origin", ""))
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                check = QCheckBox()
                check.setAccessibleName(self.tr("Select %1 in %2").replace("%1", item.get("name") or item["ref"]).replace("%2", installation))
                check.setAccessibleDescription(label)
                text = QLabel(label)
                text.setTextFormat(Qt.TextFormat.PlainText)
                text.setWordWrap(True)
                row_layout.addWidget(check)
                row_layout.addWidget(text, 1)
                check.setChecked(key in self._selected)
                check.toggled.connect(lambda checked, identity=key: self._select(identity, checked))
                layout.addWidget(row)
                details = DetailsDisclosure(summary=self.tr("Show update identity"))
                details.set_details(f"{item['ref']}\n{installation}\n{item.get('installed_commit', '')} → {item.get('expected_commit', '')}")
                layout.addWidget(details)
                view = QPushButton(self.tr("View installed application"))
                view.clicked.connect(lambda _checked=False, identity=installation, ref=item["ref"]: self.routeRequested.emit("software:apps", {"section": "installed-app", "installation": identity, "refs": [ref]}))
                layout.addWidget(view)
                self._rows.append((label.casefold(), row, details, view))
                checks.append(check)
            buttons = QHBoxLayout()
            select_all = QPushButton(self.tr("Select all"))
            select_all.clicked.connect(lambda _checked=False, controls=checks: [control.setChecked(True) for control in controls])
            review = QPushButton(self.tr("Review selected updates"))
            review.clicked.connect(lambda _checked=False, identity=installation: self.review(identity))
            buttons.addWidget(select_all)
            buttons.addWidget(review)
            layout.addLayout(buttons)
            self._groups.append(group)
            self.add_widget(group)
        self._filter(self.search.text())
        if auto_review:
            self.review(self._installation)
        self._auto_review = False

    def _select(self, identity, checked):
        if checked:
            self._selected.add(identity)
        else:
            self._selected.discard(identity)

    def _filter(self, query):
        for label, check, details, view in self._rows:
            shown = query.casefold().strip() in label
            check.setVisible(shown)
            details.setVisible(shown)
            view.setVisible(shown)

    def review(self, installation):
        refs = sorted(ref for scope, ref in self._selected if scope == installation)
        if refs and not self.busy:
            self._installation = installation
            self.actionReviewRequested.emit("update-flatpaks", {"installation": installation, "refs": refs})

    def set_outcome(self, outcome, installation=None):
        self._selected.clear()
        self._clear_candidates()
        self._run_id = str(getattr(outcome, "run_id", "") or "")
        self._installation = installation
        lines = [str(getattr(outcome, "message", ""))]
        verification = getattr(getattr(outcome, "run", None), "verification_result", None) or getattr(outcome, "data", {}).get("verification_result", {})
        results = verification.get("data", {}).get("results", [])
        facts = getattr(getattr(getattr(outcome, "plan", None), "policy_decision", None), "facts", {})
        operations = {(scope["installation"], operation["ref"]): operation for scope in facts.get("flatpak_updates", {}).get("installations", []) for operation in scope.get("operations", [])}
        for result in results:
            operation = operations.get((result.get("installation"), result.get("ref")), {})
            role = self.tr("Selected application") if operation.get("selected") else self.tr("Required dependency") if operation else self.tr("Reviewed ref")
            state = {"verified": self.tr("Verified"), "failed": self.tr("Failed"), "cancelled": self.tr("Cancelled"), "unverified": self.tr("Unverified")}.get(result.get("status"), self.tr("Unverified"))
            lines.append(f"{result.get('installation', '')} · {result.get('ref', '')}: {state} · {role}")
        self.status.setText("\n".join(lines))
        self.record_button.setVisible(bool(self._run_id))
        self.runtime_button.setVisible(bool(self._run_id and installation))

    def _open_runtimes(self):
        if self._installation:
            self.routeRequested.emit("software:apps", {"section": "unused-runtimes", "installation": self._installation})

    def request_stop(self):
        self._auto_review = False
        self._adapter.cancel()

    def _stopped(self):
        self.check_button.setEnabled(True)
        self.cancel_button.hide()
        for group in self._groups:
            group.setEnabled(True)
        self.stopped.emit()

    def cleanup(self, timeout_ms=1000):
        self.request_stop()
        return self._adapter.close(timeout_ms)


def flatpak_review_lines(plan, translate):
    """Render reviewed names and dependencies separately from exact commits."""
    facts = getattr(getattr(plan, "policy_decision", None), "facts", {})
    snapshot = facts.get("flatpak_updates", facts.get("updates", {}))
    summary, technical = [], []
    for installation in snapshot.get("installations", []):
        summary.append(f"{translate('Installation')}: {installation['installation']}")
        for selected, heading in ((True, "Selected applications"), (False, "Required runtimes and extensions")):
            operations = [item for item in installation.get("operations", []) if bool(item.get("selected")) == selected]
            if not operations:
                continue
            summary.append(str(translate(heading)))
            for item in operations:
                name = item.get("name") or item["ref"]
                before = item.get("installed_version") or str(translate("Version not reported"))
                after = item.get("available_version") or str(translate("Version not reported"))
                version = f"{before} → {after}"
                summary.append(f"  {name} · {version} · {item.get('origin', '')}")
                technical.append(f"{installation['installation']} · {item['ref']} · {item.get('operation', '')}\n{item.get('installed_commit', '')} → {item.get('expected_commit', '')}")
    return tuple(summary), tuple(technical)
