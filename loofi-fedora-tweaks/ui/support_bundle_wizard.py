import os
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFileDialog, QMessageBox
)
from core.export.support_bundle_v4 import SupportBundleV4
from utils.log import get_logger

logger = get_logger(__name__)


class SupportBundleWizard(QDialog):
    """
    v4.0 "Atlas" Support Bundle Export UI.
    Provides a preview of collected data and a file-save dialog.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Atlas Assistant - Support Bundle")
        self.setMinimumSize(700, 500)

        self.bundle_gen = SupportBundleV4()
        self.bundle_data = {}

        self._setup_ui()
        self._gather_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)

        header = QLabel("Export Diagnostic Support Bundle")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "The assistant has collected safe diagnostic information about your system. "
            "Personal data, tokens, and private files have been excluded."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6c7086; margin-bottom: 10px;")
        layout.addWidget(desc)

        layout.addWidget(QLabel("Data Preview:"))

        # Preview Area
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet("font-family: monospace; font-size: 11px; background: #1c2030; color: #bac2de;")
        layout.addWidget(self.preview, 1)

        # Buttons
        nav = QHBoxLayout()
        nav.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        nav.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Bundle...")
        self.btn_save.setObjectName("wizardBtnNext")
        self.btn_save.clicked.connect(self._save_bundle)
        nav.addWidget(self.btn_save)

        layout.addLayout(nav)

    def _gather_data(self):
        """Collect data from SupportBundleV3 and update preview."""
        try:
            self.bundle_data = self.bundle_gen.generate_bundle()
            # Pretty-print for preview
            preview_text = json.dumps(self.bundle_data, indent=2)
            self.preview.setText(preview_text)
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error("Failed to generate support bundle: %s", e, exc_info=True)
            self.preview.setText(f"Error gathering diagnostic data: {e}")
            self.btn_save.setEnabled(False)

    def _save_bundle(self):
        """Opens file dialog and saves the bundle JSON."""
        default_name = f"loofi-fedora-support-{self.bundle_data.get('timestamp', 0):.0f}.json"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Support Bundle",
            os.path.join(os.path.expanduser("~"), default_name),
            "JSON Files (*.json)"
        )

        if file_path:
            try:
                self.bundle_gen.save_json(file_path)
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Support bundle has been saved to:\n{file_path}"
                )
                self.accept()
            except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.error("Failed to save bundle: %s", e)
                QMessageBox.critical(self, "Export Failed", f"Could not save the bundle: {e}")
