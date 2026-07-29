"""Safe, PyQt-free troubleshooting contracts for Compass."""

from core.troubleshooting.adapters import (
    ReadOnlyEvidenceAdapter,
    SourceChange,
    SourceEvidence,
    adapt_action_center,
    adapt_change_journal,
    adapt_observability,
    adapt_structured_source,
    adapt_system_check,
)
from core.troubleshooting.comparison import compare_sessions
from core.troubleshooting.composition import compose_session
from core.troubleshooting.correlation import correlate_changes
from core.troubleshooting.lifecycle import (
    CancellationSignal,
    finalize_session,
    new_session,
    start_session,
)
from core.troubleshooting.models import (
    CompatibilityMetadata,
    FindingComparison,
    NextStep,
    RelatedChangeReference,
    SourceResult,
    TroubleshootingComparison,
    TroubleshootingFinding,
    TroubleshootingSession,
)
from core.troubleshooting.profiles import (
    SourceBudget,
    TroubleshootingProfile,
    all_profiles,
    get_profile,
    require_profile,
)
from core.troubleshooting.storage import (
    SessionStoreSnapshot,
    TroubleshootingSessionStore,
    UnsupportedFutureSessionSchema,
)

__all__ = [
    "CancellationSignal",
    "CompatibilityMetadata",
    "FindingComparison",
    "NextStep",
    "RelatedChangeReference",
    "ReadOnlyEvidenceAdapter",
    "SessionStoreSnapshot",
    "SourceBudget",
    "SourceChange",
    "SourceEvidence",
    "SourceResult",
    "TroubleshootingComparison",
    "TroubleshootingFinding",
    "TroubleshootingProfile",
    "TroubleshootingSession",
    "TroubleshootingSessionStore",
    "UnsupportedFutureSessionSchema",
    "all_profiles",
    "adapt_action_center",
    "adapt_change_journal",
    "adapt_observability",
    "adapt_structured_source",
    "adapt_system_check",
    "compare_sessions",
    "compose_session",
    "correlate_changes",
    "finalize_session",
    "get_profile",
    "new_session",
    "require_profile",
    "start_session",
]
