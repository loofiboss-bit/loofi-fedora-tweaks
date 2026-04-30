from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class HealthCheck:
    """
    Structured model for a system health check.
    v4.0 "Atlas" foundation for guided diagnostics.
    """
    id: str                 # Unique slug (e.g., 'dnf-lock-detected')
    title: str              # User-friendly name
    severity: str           # info | warning | error | critical
    category: str           # system | package | security | hardware | network
    description: str        # Explanation of the issue

    # Detection metadata
    detection_cmd: Optional[List[str]] = None
    expected_output: Optional[str] = None

    # Fix metadata
    safe_to_auto_fix: bool = False
    dry_run_supported: bool = True
    suggested_fix: Optional[str] = None
    manual_commands: List[str] = field(default_factory=list)
    rollback_hint: Optional[str] = None

    # Help/Docs
    docs_link: Optional[str] = None
    help_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "safe_to_auto_fix": self.safe_to_auto_fix,
            "suggested_fix": self.suggested_fix,
            "docs_link": self.docs_link
        }


@dataclass
class HealthResult:
    """
    Result of a HealthCheck execution.
    """
    check_id: str
    status: str             # healthy | unhealthy | error | skipped
    message: str
    details: Optional[str] = None
    timestamp: float = 0.0
    detected_at: Optional[str] = None
    # e.g., ["bluetooth.service", "auditd.service"]
    affected_entities: List[str] = field(default_factory=list)
