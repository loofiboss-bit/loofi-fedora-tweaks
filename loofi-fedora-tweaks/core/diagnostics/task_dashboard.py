from dataclasses import dataclass, field
from typing import List, Optional
from .health_model import HealthCheck
from .health_registry import HealthRegistry

@dataclass
class DashboardTask:
    """
    High-level task representation for the v4.0 Home/Dashboard.
    Bundles multiple health checks and actions into a goal.
    """
    id: str
    title: str
    description: str
    icon_id: str
    check_ids: List[str] = field(default_factory=list)
    action_ids: List[str] = field(default_factory=list)
    priority: int = 10  # Lower is higher priority

class TaskManager:
    """
    Manager for task-based home dashboard.
    """
    def __init__(self, registry: HealthRegistry):
        self.registry = registry
        self._tasks: List[DashboardTask] = []
        self._initialize_default_tasks()

    def _initialize_default_tasks(self):
        """Register the primary v4.0 task cards."""
        
        self._tasks.append(DashboardTask(
            id="task-maintenance",
            title="Maintain my system",
            description="Run routine cleanup, check for updates, and optimize storage.",
            icon_id="maintenance-health",
            check_ids=["dnf-lock", "pending-updates", "disk-space-root"],
            action_ids=["dnf-clean-all", "fstrim-all"],
            priority=1
        ))

        self._tasks.append(DashboardTask(
            id="task-repair",
            title="Fix problems",
            description="Identify and repair failed services or system inconsistencies.",
            icon_id="status-ok", # Will use error icon if unhealthy
            check_ids=["failed-services", "nvidia-akmods"],
            action_ids=["restart-failed-service"],
            priority=0
        ))

        self._tasks.append(DashboardTask(
            id="task-upgrade",
            title="Prepare upgrade",
            description="Check if your system is ready for the next Fedora version.",
            icon_id="update",
            check_ids=[
                "upgrade-fedora-version", 
                "upgrade-repo-risk", 
                "upgrade-storage-readiness"
            ],
            priority=2
        ))

        self._tasks.append(DashboardTask(
            id="task-gaming",
            title="Optimize Gaming",
            description="Improve gaming performance with safe power profiles and optimization tools.",
            icon_id="gaming",
            check_ids=["gaming-gamemode", "gaming-mangohud", "gaming-cpu-governor"],
            action_ids=["gaming-install-tools", "gaming-set-performance"],
            priority=3
        ))

        self._tasks.append(DashboardTask(
            id="task-security",
            title="Secure my Fedora",
            description="Harden system security by checking SELinux and updates.",
            icon_id="security",
            check_ids=["selinux-status", "pending-updates"],
            priority=4
        ))

        self._tasks.append(DashboardTask(
            id="task-support-bundle",
            title="Export Support Bundle",
            description="Collect diagnostic logs and health data to help troubleshoot issues.",
            icon_id="export",
            priority=5
        ))

    def get_tasks(self) -> List[DashboardTask]:
        return sorted(self._tasks, key=lambda x: x.priority)
