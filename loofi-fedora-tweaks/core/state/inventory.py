"""Registry of application-owned persistent domains."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.state.paths import StatePaths


@dataclass(frozen=True)
class StateDomain:
    id: str
    owner: str
    path: Path
    category: str
    schema_id: str
    schema_version: int
    sensitivity: str
    retention: str
    recovery: str
    optional: bool = True


class StateInventory:
    """Single catalog used by doctor, backup and support export."""

    def __init__(self, paths: StatePaths | None = None):
        self.paths = paths or StatePaths.from_environment()
        self._domains: dict[str, StateDomain] = {}
        self._register_defaults()

    def register(self, domain: StateDomain) -> None:
        if domain.id in self._domains:
            raise ValueError(f"State domain already registered: {domain.id}")
        self._domains[domain.id] = domain

    def all(self) -> tuple[StateDomain, ...]:
        return tuple(self._domains[key] for key in sorted(self._domains))

    def get(self, domain_id: str) -> StateDomain:
        return self._domains[domain_id]

    def _register_defaults(self) -> None:
        p = self.paths
        definitions = (
            ("settings", "config", p.config / "settings.json", "loofi.settings", 1, "private", "indefinite", "last-known-good"),
            ("home_onboarding", "home", p.config / "onboarding.json", "loofi.home-onboarding", 1, "private", "until completed or dismissed", "reset"),
            ("health_snapshots", "observability", p.data / "health_timeline_v12.json", "loofi.health-snapshots", 1, "private", "30 snapshots", "last-known-good"),
            ("metric_timeline", "observability", p.data / "health_timeline.db", "loofi.metric-timeline", 1, "private", "30 days", "sqlite-integrity"),
            ("action_history", "action-center", p.data / "action_center_history.jsonl", "loofi.action-history", 3, "private", "100 events", "archive-corrupt"),
            ("action_log", "executor", p.data / "action_log.jsonl", "loofi.action-log", 1, "sensitive", "500 events", "archive-corrupt"),
            ("action_plans", "action-center", p.data / "action_plans.json", "loofi.action-plans", 3, "private", "50 plans", "last-known-good"),
            ("action_runs", "action-center", p.data / "action_runs.jsonl", "loofi.action-runs", 3, "private", "100 events", "archive-corrupt"),
            (
                "troubleshooting_sessions",
                "troubleshooting",
                p.data / "troubleshooting_sessions.json",
                "loofi.troubleshooting-sessions",
                1,
                "private",
                "20 sessions",
                "last-known-good",
            ),
            ("audit_log", "audit", p.config / "audit.jsonl", "loofi.audit-log", 1, "sensitive", "bounded", "archive-corrupt"),
            ("plugin_state", "plugins", p.config / "plugins.json", "loofi.plugin-state", 1, "private", "indefinite", "last-known-good"),
            ("auth_state", "api", p.config / "auth.json", "loofi.auth-state", 1, "secret", "indefinite", "manual"),
            ("cache", "runtime", p.cache, "loofi.cache", 1, "derived", "bounded", "rebuild"),
            ("collector_lock", "daemon", p.runtime / "collector.lock", "loofi.collector-lease", 1, "private", "runtime", "stale-lock"),
            ("action_mutation_lease", "action-center", p.runtime / "action_center_mutation.lock", "loofi.action-mutation-lease", 1, "private", "runtime", "stale-lock"),
        )
        for domain_id, owner, path, schema_id, version, sensitivity, retention, recovery in definitions:
            if domain_id in {"collector_lock", "action_mutation_lease"}:
                category = "runtime"
            elif domain_id == "cache":
                category = "cache"
            elif path.is_relative_to(p.config):
                category = "config"
            else:
                category = "data"
            self.register(StateDomain(domain_id, owner, path, category, schema_id, version, sensitivity, retention, recovery))
