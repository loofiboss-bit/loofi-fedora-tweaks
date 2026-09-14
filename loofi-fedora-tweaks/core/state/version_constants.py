"""Shared persistent-state versions used by writers and read-only diagnostics."""

from __future__ import annotations

# Keep these values in a dependency-neutral module.  Action stores and the
# state inventory both import them, so diagnostics cannot lag behind writers
# through a second hard-coded version table.
ACTION_PLAN_SCHEMA_VERSION = 4
ACTION_RUN_SCHEMA_VERSION = 4
