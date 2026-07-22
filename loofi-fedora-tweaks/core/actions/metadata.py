"""Haven metadata applied to audited Action Center definitions."""

from __future__ import annotations

from dataclasses import replace

from core.actions.contracts import ActionDefinition

_TRADITIONAL_ONLY = frozenset({"traditional"})
_BOTH_VARIANTS = frozenset({"traditional", "atomic"})

_AFFECTED_RESOURCES: dict[str, tuple[str, ...]] = {
    "dnf-clean-all": ("package-cache", "repositories"),
    "restart-failed-service": ("systemd-unit",),
    "fstrim-all": ("mounted-filesystems",),
    "update-fedora-system": ("packages", "deployment"),
    "update-flatpaks": ("flatpak-applications",),
    "update-firmware": ("firmware", "boot-state"),
    "install-application": ("applications", "packages", "deployment"),
    "remove-application": ("applications", "packages", "deployment"),
    "vacuum-journal": ("system-journal",),
    "autoremove-packages": ("packages",),
    "create-recovery-point": ("recovery-points",),
}

_TRADITIONAL_ACTIONS = frozenset({"dnf-clean-all", "autoremove-packages"})
_MAY_REQUIRE_REBOOT = frozenset(
    {
        "update-fedora-system",
        "update-firmware",
        "install-application",
        "remove-application",
    }
)


def with_haven_metadata(definition: ActionDefinition) -> ActionDefinition:
    """Return a definition with explicit, digest-bound v18 policy metadata."""
    if definition.operation_class == "manual_only":
        return definition
    variants = _TRADITIONAL_ONLY if definition.id in _TRADITIONAL_ACTIONS else _BOTH_VARIANTS
    reboot_policy = "may_require" if definition.id in _MAY_REQUIRE_REBOOT else "none"
    return replace(
        definition,
        operation_class="host",
        supported_variants=variants,  # type: ignore[arg-type]
        reboot_policy=reboot_policy,  # type: ignore[arg-type]
        affected_resources=_AFFECTED_RESOURCES.get(
            definition.id,
            (definition.capability_id,),
        ),
    )
