"""Safe, PyQt-free troubleshooting contracts for Compass."""

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
    "SessionStoreSnapshot",
    "SourceBudget",
    "SourceResult",
    "TroubleshootingComparison",
    "TroubleshootingFinding",
    "TroubleshootingProfile",
    "TroubleshootingSession",
    "TroubleshootingSessionStore",
    "UnsupportedFutureSessionSchema",
    "all_profiles",
    "finalize_session",
    "get_profile",
    "new_session",
    "require_profile",
    "start_session",
]
