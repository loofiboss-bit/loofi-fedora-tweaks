"""Single source of truth for supported and preview Fedora targets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FedoraReleasePolicy:
    """Release targets used by GUI, CLI, Action Center, and diagnostics."""

    stable_release: str = "44"
    preview_release: str = "45"

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
        major = str(host_version).split(".", 1)[0]
        return major.isdigit() and int(major) >= int(self.preview_release)


FEDORA_RELEASE_POLICY = FedoraReleasePolicy()
