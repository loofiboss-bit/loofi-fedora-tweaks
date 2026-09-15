"""v29 Fix surface backed by the closed symptom-first Troubleshoot widget."""

from __future__ import annotations

from ui.troubleshoot_widget import TroubleshootWidget


class FixWorkflowPage(TroubleshootWidget):
    """Compatibility-friendly name for the symptom-first Fix journey.

    ``TroubleshootWidget`` already owns the bounded read-only collection,
    findings, and one-safe-next-step presentation. This subclass gives the
    v29 shell a product-facing type without creating a second execution path.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("fixWorkflowPage")
        self.setAccessibleName(self.tr("Fix Fedora problems"))
        self.setAccessibleDescription(self.tr("Choose a symptom, review findings, and follow one safe next step."))

    def focus_task(self, task_id: str) -> bool:
        """Focus a symptom row when global task search enters Fix."""
        key = str(task_id or "").strip()
        # Task catalog IDs (``fix:system-slow``) and the troubleshooting
        # widget's symptom IDs (``system-slow``) are deliberately distinct.
        # Resolve both forms through the closed profile mapping so goal search
        # never lands on an unfocused Fix page.
        index = self.profile_selector.findData(key)
        if index < 0 and key.startswith("fix:"):
            profile_id = key.removeprefix("fix:").replace("-", "_")
            for row in range(self.profile_selector.count()):
                symptom_id = str(self.profile_selector.itemData(row) or "")
                if symptom_id == key.removeprefix("fix:"):
                    index = row
                    break
                try:
                    if self._selected_symptom_for_id(symptom_id)[2] == profile_id:
                        index = row
                        break
                except (IndexError, StopIteration, TypeError, ValueError):
                    continue
        if index < 0:
            self.profile_selector.setFocus()
            return key in {"fix", "fix:overview"}
        self.profile_selector.setCurrentIndex(index)
        self.profile_selector.setFocus()
        return True

    def _selected_symptom_for_id(self, symptom_id: str):
        """Return the closed troubleshooting tuple for a symptom ID."""
        return next(symptom for symptom in self._SYMPTOMS if symptom[0] == symptom_id)


FixWorkflowWidget = FixWorkflowPage
FixPage = FixWorkflowPage


__all__ = ["FixPage", "FixWorkflowPage", "FixWorkflowWidget"]
