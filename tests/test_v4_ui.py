import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Add source path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QCheckBox, QMessageBox
from ui.task_wizard import AtlasTaskWizard
from core.diagnostics.release_readiness import ReadinessCheck, ReadinessRecommendation, ReleaseReadinessReport
from core.diagnostics.health_model import HealthResult
from core.executor.action_result import ActionResult

# Create a QApplication instance for UI tests if it doesn't exist
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

@patch("core.diagnostics.health_registry.HealthRegistry.run_check")
def test_task_wizard_initialization(mock_run_check):
    mock_run_check.return_value = HealthResult(
        check_id="test-check",
        status="healthy",
        message="All good"
    )
    
    wizard = AtlasTaskWizard(
        task_id="task-test",
        check_ids=["test-check"],
        action_ids=["test-action"]
    )
    
    assert wizard.windowTitle().startswith("Atlas Assistant")
    assert wizard.stack.count() == 4
    
    # Simulate first step completion
    wizard._run_diagnostics()
    assert len(wizard.results) == 1
    assert wizard.results[0].status == "healthy"

def test_task_wizard_step_navigation():
    wizard = AtlasTaskWizard(
        task_id="task-test",
        check_ids=[],
        action_ids=[]
    )
    
    assert wizard.stack.currentIndex() == 0
    
    # Manually move to next step
    wizard._set_step(1)
    assert wizard.stack.currentIndex() == 1
    assert not wizard.btn_back.isHidden()

@patch("core.executor.action_executor.ActionExecutor.execute")
def test_task_wizard_repair_execution(mock_execute):
    mock_execute.return_value = ActionResult(
        success=True, 
        message="Success", 
        exit_code=0
    )
    
    wizard = AtlasTaskWizard(
        task_id="task-test",
        check_ids=[],
        action_ids=["dnf-clean-all"]
    )
    
    # Setup actions step
    wizard._set_step(2)
    assert len(wizard.action_checkboxes) == 1
    
    # Ensure it's checked (dnf-clean-all is low risk)
    wizard.action_checkboxes[0].setChecked(True)
    
    # Run repairs
    wizard._run_repairs()
    
    assert "1 actions succeeded" in wizard.result_label.text()
    assert wizard.stack.currentIndex() == 3
    assert mock_execute.called

def test_task_wizard_risk_ui():
    wizard = AtlasTaskWizard(
        task_id="task-test",
        check_ids=[],
        action_ids=["dnf-clean-all"]
    )
    
    # Populate actions step
    wizard._populate_actions()
    
    # Verify we have at least one action card
    assert len(wizard.action_checkboxes) == 1
    
    # Find the container
    container = wizard.actions_layout.itemAt(0).widget()
    
    # Locate widgets by type/content
    all_labels = container.findChildren(QLabel)
    # 0: Risk label, 1: Command preview label
    # Note: QCheckBox also contains a label internally but findChildren(QLabel) 
    # usually finds the ones we explicitly added to the layout.
    
    preview_lbl = None
    for lbl in all_labels:
        if "<code>" in lbl.text():
            preview_lbl = lbl
            break
            
    assert preview_lbl is not None
    assert preview_lbl.isHidden()
    
    preview_btn = container.findChild(QPushButton)
    preview_btn.click()
    assert not preview_lbl.isHidden()
    assert "dnf clean all" in preview_lbl.text()

@patch("core.executor.action_executor.ActionExecutor.execute")
def test_task_wizard_dynamic_execution_fixed(mock_execute):
    mock_execute.return_value = ActionResult(success=True, message="OK", exit_code=0)
    
    wizard = AtlasTaskWizard(
        task_id="task-repair",
        check_ids=["failed-services"],
        action_ids=["restart-failed-service"]
    )
    
    # Mock some failed services
    wizard.results = [
        HealthResult(
            check_id="failed-services",
            status="unhealthy",
            message="2 failed",
            affected_entities=["s1.service", "s2.service"]
        )
    ]
    
    wizard._populate_actions()
    assert len(wizard.action_checkboxes) == 2
    
    # Manually check them (they might be Medium risk)
    for cb in wizard.action_checkboxes:
        cb.setChecked(True)
    
    # Run repairs
    wizard._run_repairs()
    
    assert mock_execute.call_count == 2
    assert "2 actions succeeded" in wizard.result_label.text()

@patch("core.export.support_bundle_v5.SupportBundleV5.generate_bundle")
def test_support_bundle_wizard(mock_generate):
    mock_generate.return_value = {
        "v": "7.0.0-aegis-support-v5",
        "system": {"os": "Fedora"},
        "health": []
    }
    
    from ui.support_bundle_wizard import SupportBundleWizard
    wizard = SupportBundleWizard()
    
    assert "Atlas Assistant" in wizard.windowTitle()
    # Check if preview contains the mock JSON data
    assert "\"os\": \"Fedora\"" in wizard.preview.toPlainText()
    assert mock_generate.called


def test_release_readiness_dialog_groups_and_filters():
    from ui.release_readiness_dialog import ReleaseReadinessDialog

    dialog = ReleaseReadinessDialog(auto_run=False)
    dialog.report = ReleaseReadinessReport(
        target="Fedora KDE 44",
        generated_at=1.0,
        score=91,
        status="ready",
        summary="ready",
        checks=[
            ReadinessCheck(
                id="fedora-version",
                title="Fedora Version",
                category="system",
                status="pass",
                severity="info",
                summary="Fedora 44",
                beginner_guidance="ok",
            ),
            ReadinessCheck(
                id="third-party-repos",
                title="Third-Party Repository Risk",
                category="package",
                status="warning",
                severity="warning",
                summary="One repo",
                beginner_guidance="Review it",
                advanced_detail="raw repo detail",
            ),
        ],
    )

    dialog._render()
    labels = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "System" in labels
    assert "Packages" in labels
    assert "Third-Party Repository Risk" in labels

    dialog.severity_filter.setCurrentIndex(dialog.severity_filter.findData("pass"))
    dialog._render()
    labels = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Fedora Version" in labels


@patch("core.diagnostics.readiness_actions.SystemManager.get_package_manager", return_value="dnf")
@patch("ui.release_readiness_dialog.ReadinessActionService.run", return_value=ActionResult.ok("cleaned"))
@patch("ui.release_readiness_dialog.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
@patch("ui.release_readiness_dialog.QMessageBox.information")
def test_release_readiness_dialog_action_inbox_run_path(mock_info, _mock_question, mock_run, _mock_pm):
    from ui.release_readiness_dialog import ReleaseReadinessDialog

    dialog = ReleaseReadinessDialog(auto_run=False)
    dialog.report = ReleaseReadinessReport(
        target="Fedora KDE 44",
        generated_at=1.0,
        score=78,
        status="review",
        summary="review",
        checks=[
            ReadinessCheck(
                id="repo-health",
                title="Repository Metadata",
                category="package",
                status="warning",
                severity="warning",
                summary="Metadata needs refresh",
                beginner_guidance="Review repositories first.",
                command_preview=["dnf", "repolist", "--enabled"],
                recommendation=ReadinessRecommendation(
                    title="Review enabled repositories",
                    description="Refresh package metadata after review.",
                    command_preview=["dnf", "repolist", "--enabled"],
                    risk_level="low",
                    rollback_hint="Package metadata is rebuilt on the next query.",
                    docs_link="https://example.invalid/readiness",
                ),
            )
        ],
    )

    dialog._render()
    labels = " ".join(label.text() for label in dialog.findChildren(QLabel))
    buttons = [button.text() for button in dialog.findChildren(QPushButton)]

    assert "Action Inbox" in labels
    assert "Clean package metadata cache" in labels
    assert "https://example.invalid/readiness" in labels
    assert "Run..." in buttons
    assert "Verify" in buttons

    dialog._confirm_and_run_action("readiness-repo-cache-clean")
    mock_run.assert_called_once_with(
        "readiness-repo-cache-clean",
        target_key="44",
        confirm=True,
        report=dialog.report,
    )
    mock_info.assert_called_once()


@patch("ui.release_readiness_dialog.ReadinessActionService.verify", return_value=ActionResult.fail("still needs attention"))
@patch("ui.release_readiness_dialog.QMessageBox.warning")
def test_release_readiness_dialog_manual_action_and_warning_paths(mock_warning, mock_verify):
    from ui.release_readiness_dialog import ReleaseReadinessDialog

    dialog = ReleaseReadinessDialog(auto_run=False)
    dialog.report = ReleaseReadinessReport(
        target="Fedora KDE 44",
        generated_at=1.0,
        score=76,
        status="review",
        summary="review",
        checks=[
            ReadinessCheck(
                id="third-party-repos",
                title="Third-Party Repository Risk",
                category="package",
                status="warning",
                severity="warning",
                summary="Review enabled repositories",
                beginner_guidance="Open the repository list and decide what to keep.",
                command_preview=["dnf", "repolist", "--enabled"],
                recommendation=ReadinessRecommendation(
                    title="Review third-party repositories",
                    description="Manual repository review is required before release work.",
                    command_preview=["dnf", "repolist", "--enabled"],
                    risk_level="medium",
                    manual_only=True,
                    reversible=False,
                    rollback_hint="Re-enable any repository you decide to keep.",
                ),
            )
        ],
    )

    dialog._render()
    labels = " ".join(label.text() for label in dialog.findChildren(QLabel))
    buttons = [button.text() for button in dialog.findChildren(QPushButton)]

    assert "Manual only" in labels
    assert "Run..." not in buttons

    dialog._confirm_and_run_action("missing-action")
    dialog._verify_action("readiness-third-party-repos")
    mock_verify.assert_called_once_with("readiness-third-party-repos", target_key="44")
    assert mock_warning.call_count == 2

    empty = ReleaseReadinessDialog(auto_run=False)
    empty._confirm_and_run_action("missing-action")
    empty._verify_action("missing-action")


@patch("ui.release_readiness_dialog.SupportBundleV5.save_json")
@patch("ui.release_readiness_dialog.QMessageBox.information")
@patch("ui.release_readiness_dialog.QFileDialog.getSaveFileName", return_value=("/tmp/loofi-test-bundle.json", ""))
def test_release_readiness_dialog_export_action(mock_file, mock_message, mock_save):
    from ui.release_readiness_dialog import ReleaseReadinessDialog

    dialog = ReleaseReadinessDialog(auto_run=False)
    dialog.report = ReleaseReadinessReport(
        target="Fedora KDE 45 Preview",
        generated_at=1.0,
        score=80,
        status="preview",
        summary="preview",
        checks=[],
    )
    dialog.target_key = "45-preview"
    dialog.export_support_bundle()
    mock_save.assert_called_once_with("/tmp/loofi-test-bundle.json", target="45-preview")

def test_task_wizard_log_and_rollback():
    wizard = AtlasTaskWizard(
        task_id="task-test",
        check_ids=[],
        action_ids=[]
    )
    
    # Mock some repair results
    from core.executor.action_model import SystemAction
    from core.executor.action_result import ActionResult
    
    mock_action = SystemAction(
        id="a1", title="Failed Task", explanation="X", 
        command="false", revert_hint="Try manually"
    )
    mock_res = ActionResult(success=False, message="Command failed")
    
    wizard.repair_results = [{
        "action": mock_action,
        "result": mock_res,
        "display_title": "Failed Task"
    }]
    
    # Enter final step
    wizard._set_step(3)
    
    # Find log container content
    log_widgets = wizard.log_layout.count()
    assert log_widgets > 1 # entries + stretch
    
    # Find the log frame
    log_frame = wizard.log_layout.itemAt(0).widget()
    all_labels = log_frame.findChildren(QLabel)
    
    text_blob = " ".join([l.text() for l in all_labels])
    assert "FAILED" in text_blob
    assert "Command failed" in text_blob
    assert "Rollback hint: Try manually" in text_blob
