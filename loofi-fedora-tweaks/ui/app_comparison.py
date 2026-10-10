"""Read-only installation comparison using the existing inventory snapshot."""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from services.software.app_comparison import ApplicationComparison


class ApplicationComparisonDialog(QDialog):
    detailsRequested = pyqtSignal(object)
    removalRequested = pyqtSignal(object)
    softwareManagerRequested = pyqtSignal()

    def __init__(self, comparison: ApplicationComparison, parent=None):
        super().__init__(parent)
        self.comparison = comparison
        self.setWindowTitle(self.tr("Compare installations"))
        self.setAccessibleName(self.tr("Compare installations for %1").replace("%1", comparison.app_id))
        self.resize(850, 520)
        layout = QVBoxLayout(self)
        identity = QLabel(comparison.app_id)
        identity.setWordWrap(True)
        layout.addWidget(identity)
        table = QTableWidget(5, len(comparison.installations))
        table.setAccessibleName(self.tr("Installation comparison"))
        table.setVerticalHeaderLabels([self.tr("Format"), self.tr("Version"), self.tr("Installation"), self.tr("Reference"), self.tr("Reported size")])
        table.setHorizontalHeaderLabels([app.name for app in comparison.installations])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for column, app in enumerate(comparison.installations):
            values = (self.tr("RPM") if app.source == "fedora" else self.tr("Flatpak"), app.version, app.installation, app.ref, app.size)
            for row, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value or self.tr("Not reported")))
        table.resizeColumnsToContents()
        layout.addWidget(table, 1)
        notice = QLabel(self.tr("Reported sizes include shared objects and do not predict space freed by removal. Choose an installation to inspect details or review removal."))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        if comparison.errors:
            errors = QLabel(self.tr("Some sources could not be checked; this comparison may be incomplete.") + "\n" + "\n".join(comparison.errors))
            errors.setWordWrap(True)
            layout.addWidget(errors)
        self.selection = QComboBox()
        self.selection.setAccessibleName(self.tr("Choose exact installation"))
        for app in comparison.installations:
            self.selection.addItem(f"{app.source} · {app.installation} · {app.ref}", app)
        layout.addWidget(self.selection)
        self.details_button = QPushButton(self.tr("App details"))
        self.details_button.clicked.connect(self._details)
        layout.addWidget(self.details_button)
        self.remove_button = QPushButton()
        self.remove_button.clicked.connect(self._remove)
        layout.addWidget(self.remove_button)
        self.selection.currentIndexChanged.connect(self._selected)
        self._selected()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _selected(self):
        app = self.selection.currentData()
        flatpak = app is not None and app.source == "flatpak"
        self.details_button.setEnabled(flatpak)
        self.remove_button.setEnabled(app is not None)
        self.remove_button.setText(self.tr("Review removal") if flatpak else self.tr("Open software manager"))

    def _details(self):
        app = self.selection.currentData()
        if app is not None and app.source == "flatpak":
            self.detailsRequested.emit(app)

    def _remove(self):
        app = self.selection.currentData()
        if app is not None and app.source == "flatpak":
            self.removalRequested.emit(app)
        elif app is not None:
            self.softwareManagerRequested.emit()
