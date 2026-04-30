from typing import List
from .health_model import HealthCheck, HealthResult
from .health_registry import HealthRegistry


class UpgradeAssistant:
    """
    Fedora Upgrade Assistant foundation for v4.0 "Atlas".
    Provides specialized pre-upgrade diagnostic suites.
    """

    def __init__(self, health_registry: HealthRegistry):
        self.registry = health_registry
        self._initialize_upgrade_checks()

    def _initialize_upgrade_checks(self):
        """Register checks specifically for Fedora version upgrades."""

        # 1. Major Version Check
        self.registry.register(HealthCheck(
            id="upgrade-fedora-version",
            title="Fedora Current Version",
            severity="info",
            category="system",
            description="Identifies the current Fedora version and release type.",
            suggested_fix="Ensure you are on a supported Fedora version before upgrading.",
            docs_link="https://docs.fedoraproject.org/en-US/releases/lifecycle/"
        ))

        # 2. Kernel Stability Check
        self.registry.register(HealthCheck(
            id="upgrade-kernel-status",
            title="Running Kernel Stability",
            severity="info",
            category="system",
            description="Verifies if the current kernel is stable and matches the installed version.",
            suggested_fix="Reboot if a new kernel was recently installed but not yet running."
        ))

        # 3. Third-Party Repo Scan
        self.registry.register(HealthCheck(
            id="upgrade-repo-risk",
            title="Third-Party Repository Risk",
            severity="warning",
            category="package",
            description="Detects active COPRs or non-standard repositories that may cause upgrade conflicts.",
            suggested_fix="Consider disabling high-risk COPRs before starting the major upgrade.",
            manual_commands=["dnf repolist", "dnf copr list"]
        ))

        # 4. Storage Readiness
        self.registry.register(HealthCheck(
            id="upgrade-storage-readiness",
            title="Upgrade Storage Space",
            severity="error",
            category="system",
            description="Ensures at least 5GB of free space is available on the root partition.",
            suggested_fix="Free up space by cleaning caches or removing large unused files.",
            manual_commands=["dnf clean all", "journalctl --vacuum-size=100M"]
        ))

        # 5. Atomic Rebase Detection
        self.registry.register(HealthCheck(
            id="upgrade-atomic-rebase",
            title="Atomic/rpm-ostree Rebase Path",
            severity="info",
            category="system",
            description="Detects if this is an Atomic Fedora system and identifies the rebase path.",
            suggested_fix="Use rpm-ostree rebase for version upgrades.",
            docs_link="https://docs.fedoraproject.org/en-US/fedora-silverblue/updates-upgrades/"
        ))

    def run_pre_upgrade_audit(self) -> List[HealthResult]:
        """Runs all upgrade-related checks and returns the results."""
        upgrade_checks = [
            "upgrade-fedora-version",
            "upgrade-kernel-status",
            "upgrade-repo-risk",
            "upgrade-storage-readiness",
            "upgrade-atomic-rebase"
        ]
        results = []
        for cid in upgrade_checks:
            results.append(self.registry.run_check(cid))
        return results
