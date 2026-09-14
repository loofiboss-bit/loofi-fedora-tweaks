"""Single source of truth for supported and preview Fedora targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FedoraSupportStatus = Literal["supported", "preview", "unknown"]


@dataclass(frozen=True)
class FedoraReleasePolicy:
    """Release targets used by GUI, CLI, Action Center, and diagnostics."""

    stable_release: str = "44"
    preview_release: str = "45"
    supported_stable_releases: tuple[str, ...] = ("43", "44")

    @property
    def stable_target(self) -> str:
        return self.stable_release

    @property
    def preview_target(self) -> str:
        return f"{self.preview_release}-preview"

    @property
    def action_targets(self) -> tuple[str, ...]:
        return (self.stable_target, self.preview_target)

    def is_stable_target(self, target: str) -> bool:
        return str(target) == self.stable_target

    def is_preview_target(self, target: str) -> bool:
        return str(target) == self.preview_target

    def host_is_preview(self, host_version: str) -> bool:
        return self.classify_host(host_version) == "preview"

    def classify_host(self, host_version: str) -> FedoraSupportStatus:
        """Classify a host release consistently across GUI, CLI, and actions."""
        major = str(host_version or "").strip().split(".", 1)[0]
        if major in self.supported_stable_releases:
            return "supported"
        if major == self.preview_release:
            return "preview"
        return "unknown"

    def is_supported_version(self, host_version: str) -> bool:
        return self.classify_host(host_version) == "supported"

    def is_preview_version(self, host_version: str) -> bool:
        return self.classify_host(host_version) == "preview"


FEDORA_RELEASE_POLICY = FedoraReleasePolicy()
