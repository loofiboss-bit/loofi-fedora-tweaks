"""Backward-compat shim — use services.network instead."""
import warnings
warnings.warn(
    "utils.ports is deprecated. Import from services.network instead.",
    DeprecationWarning,
    stacklevel=2,
)
from services.network.ports import OpenPort, PortAuditor, Result  # noqa: F401, E402
