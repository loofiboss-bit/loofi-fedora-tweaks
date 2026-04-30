from dataclasses import dataclass, field
from typing import List, Optional

from services.system.system import SystemManager


@dataclass
class SystemAction:
    """
    Enhanced action model for v4.0 "Atlas".
    Wraps command execution with safety and rollback metadata.
    """
    id: str
    title: str
    explanation: str
    command: str
    args: List[str] = field(default_factory=list)

    # Safety Metadata
    risk_level: str = "info"  # info | low | medium | high
    privileged: bool = False
    confirmation_required: bool = True
    dry_run_supported: bool = True

    # Pre-checks & Reverts
    preflight_checks: List[str] = field(default_factory=list)
    revert_hint: Optional[str] = None
    backup_recommended: bool = False

    # External Refs
    docs_link: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "explanation": self.explanation,
            "risk_level": self.risk_level,
            "command": self.command,
            "args": self.args,
            "privileged": self.privileged,
            "revert_hint": self.revert_hint
        }


class AtlasActionRegistry:
    """
    Registry for v4.0 SystemActions.
    Pairs with HealthCheck items for guided repairs.
    """

    def __init__(self):
        self._actions: dict[str, SystemAction] = {}
        self._initialize_core_actions()

    def register(self, action: SystemAction):
        self._actions[action.id] = action

    def get_action(self, action_id: str) -> Optional[SystemAction]:
        return self._actions.get(action_id)

    def _initialize_core_actions(self):
        """Register baseline actions for guided assistant."""
        package_manager = SystemManager.get_package_manager()

        self.register(SystemAction(
            id="dnf-clean-all",
            title="Clean DNF Cache",
            explanation="Removes all cached package data to free space and fix metadata issues.",
            command=package_manager,
            args=["clean", "all"],
            risk_level="low",
            privileged=True,
            revert_hint="N/A (cache will be rebuilt on next DNF command)"
        ))

        self.register(SystemAction(
            id="restart-failed-service",
            title="Restart Service",
            explanation="Attempts to restart a failed system service.",
            command="systemctl",
            args=["restart"],  # Needs service name appended at runtime
            risk_level="medium",
            privileged=True,
            revert_hint="Stop the service if it causes issues."
        ))

        self.register(SystemAction(
            id="fstrim-all",
            title="Trim SSD",
            explanation="Informs the SSD about unused blocks to improve performance and longevity.",
            command="fstrim",
            args=["-av"],
            risk_level="info",
            privileged=True
        ))

        # Gaming Actions
        self.register(SystemAction(
            id="gaming-install-tools",
            title="Install Gaming Tools",
            explanation="Installs GameMode, MangoHud, and Steam Devices rules.",
            command=package_manager,
            args=["install", "-y", "gamemode", "mangohud", "steam-devices"],
            risk_level="medium",
            privileged=True
        ))

        self.register(SystemAction(
            id="gaming-set-performance",
            title="Set Performance Profile",
            explanation="Configures the system power profile to 'performance' for maximum gaming throughput.",
            command="powerprofilesctl",
            args=["set", "performance"],
            risk_level="low",
            privileged=True,
            revert_hint="Set profile back to 'balanced' or 'power-saver'."
        ))
