"""Contract tests for Fedora review workflow gates."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
AUTO_RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "auto-release.yml"
COPR_WORKFLOW = ROOT / ".github" / "workflows" / "copr-publish.yml"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ci_workflow_has_required_fedora_review_gate():
    text = _read_text(CI_WORKFLOW)

    assert "fedora_review:" in text
    assert "fedora-review mock" in text
    assert "python3 scripts/check_fedora_review.py" in text
    assert "fedora-review -n loofi-fedora-tweaks -r -p" in text
    assert "rpmbuild/SRPMS/*.src.rpm" in text
    assert text.count("name: Bootstrap Git for checkout") == 1
    assert "--setopt=install_weak_deps=False" in text
    assert "--disablerepo=fedora-cisco-openh264" in text
    assert text.count("name: Create mock-enabled reviewer") == 1
    assert 'su -s /bin/bash reviewer -c' in text


def test_ci_workflow_adapter_drift_checks_sync_and_render():
    text = _read_text(CI_WORKFLOW)

    assert "adapter_drift:" in text
    assert "python3 scripts/sync_ai_adapters.py --check" in text
    assert "python3 scripts/sync_ai_adapters.py --render --check" in text


def test_ci_workflow_flatpak_job_is_blocking():
    text = _read_text(CI_WORKFLOW)

    assert "package_flatpak:" in text
    assert "continue-on-error: true" not in text
    assert "org.kde.Platform//6.10" in text
    assert "org.kde.Sdk//6.10" in text
    assert "com.riverbankcomputing.PyQt.BaseApp//6.10" in text
    assert "flatpak run org.loofi.FedoraTweaks" in text


def test_auto_release_workflow_has_required_fedora_review_gate():
    text = _read_text(AUTO_RELEASE_WORKFLOW)

    assert "fedora_review:" in text
    assert "fedora-review mock" in text
    assert "python3 scripts/check_fedora_review.py" in text
    assert "fedora-review -n loofi-fedora-tweaks -r -p" in text
    assert "name: srpm-package" in text
    assert text.count("name: Bootstrap Git for checkout") == 1
    assert "--setopt=install_weak_deps=False" in text
    assert "--disablerepo=fedora-cisco-openh264" in text
    assert text.count("name: Create mock-enabled reviewer") == 1
    assert 'su -s /bin/bash reviewer -c' in text


def test_auto_release_rpm_smoke_requires_fedora_review_gate_success():
    text = _read_text(AUTO_RELEASE_WORKFLOW)

    assert "needs: [build, fedora_review]" in text
    assert "needs.fedora_review.result == 'success'" in text


def test_auto_release_has_pipeline_gate_job():
    text = _read_text(AUTO_RELEASE_WORKFLOW)

    assert "pipeline_gate:" in text
    assert "Validate workflow specs exist" in text
    assert "Validate race-lock version" in text
    assert "--require-publish-ready-tasks" in text
    assert "continue-on-error: true" not in text
    assert "needs.pipeline_gate.result == 'success'" in text


def test_release_workflows_require_exact_peeled_tag_commit():
    auto_release = _read_text(AUTO_RELEASE_WORKFLOW)
    copr_publish = _read_text(COPR_WORKFLOW)

    assert "Validate release tag identity" in auto_release
    assert "Release tag ${TAG} peels to ${REMOTE_TAG_SHA}" in auto_release
    assert "Existing release tag ${TAG} peels to ${REMOTE_TAG_SHA}" in auto_release
    assert "refs/tags/${TAG}^{}" in auto_release
    assert "refs/tags/${TAG}^{}" in copr_publish
    assert "COPR publish requires ${TAG} to peel to ${GITHUB_SHA}" in copr_publish


def test_ci_and_release_typecheck_the_full_source_tree():
    for workflow in (CI_WORKFLOW, AUTO_RELEASE_WORKFLOW):
        text = _read_text(workflow)
        assert "mypy loofi-fedora-tweaks/ --ignore-missing-imports --no-error-summary" in text
        assert "mypy loofi-fedora-tweaks/services/security" not in text


def test_copr_workflows_wait_for_exact_fedora_44_success():
    for workflow in (AUTO_RELEASE_WORKFLOW, COPR_WORKFLOW):
        text = _read_text(workflow)
        assert 'COPR_CHROOT: "fedora-44-x86_64"' in text
        assert "--chroot \"${COPR_CHROOT}\"" in text
        assert "--nowait" not in text
        assert 'STATUS=$(copr-cli status "$BUILD_ID"' in text
        assert 'if [ "$STATUS" != "succeeded" ]' in text
        assert "dnf --refresh install" in text
