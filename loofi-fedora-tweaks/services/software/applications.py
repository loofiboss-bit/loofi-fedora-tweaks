"""Normalize application-catalog entries into safe, variant-aware operations."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Mapping, Sequence

from services.system import SystemManager
from utils.batch_ops import BatchOpsManager


@dataclass(frozen=True)
class ApplicationPresentation:
    """One application's source, state-independent identity, and availability."""

    name: str
    description: str
    source: str
    package_id: str
    install_target: str
    available: bool
    explanation: str


@dataclass(frozen=True)
class ApplicationOperation:
    """One confirmed install/remove operation for CommandRunner."""

    binary: str
    arguments: tuple[str, ...]
    description: str
    reboot_expected: bool


class ApplicationOperationService:
    """Adapt the existing catalog without trusting embedded shell programs."""

    @staticmethod
    def describe(entry: Mapping[str, object]) -> ApplicationPresentation:
        name = str(entry.get("name") or "Unknown App")
        description = str(entry.get("desc") or entry.get("description") or "")
        command = str(entry.get("cmd") or "")
        arguments = _string_arguments(entry.get("args"))
        package_id = _package_id(str(entry.get("check_cmd") or ""), command, arguments)

        if command == "flatpak" and package_id:
            return ApplicationPresentation(
                name,
                description,
                "Flathub (Flatpak)",
                package_id,
                package_id,
                True,
                "Flatpak runs independently of the host RPM deployment.",
            )

        scripted = command in {"sh", "bash"} or (command == "pkexec" and arguments[:2] in (("sh", "-c"), ("bash", "-c")))
        if scripted or not package_id:
            return ApplicationPresentation(
                name,
                description,
                "External repository",
                package_id,
                "",
                False,
                "Repository enablement must be reviewed in Repositories before installation.",
            )

        install_target = arguments[-1] if arguments else package_id
        atomic = SystemManager.is_atomic()
        external_rpm = install_target.startswith(("http://", "https://"))
        source = "Vendor RPM" if external_rpm else "Fedora RPM"
        explanation = (
            "rpm-ostree layers this package into a new deployment; a reboot may be required."
            if atomic
            else "The system package manager installs this RPM on the current deployment."
        )
        return ApplicationPresentation(
            name,
            description,
            source,
            package_id,
            install_target,
            not external_rpm,
            "External RPM URLs remain manual-only in Assurance." if external_rpm else explanation,
        )

    @staticmethod
    def operation(
        entry: Mapping[str, object],
        *,
        installed: bool,
    ) -> ApplicationOperation:
        app = ApplicationOperationService.describe(entry)
        if not app.available:
            raise ValueError(app.explanation)
        if app.source == "Flathub (Flatpak)":
            action = "uninstall" if installed else "install"
            flatpak_args: tuple[str, ...] = (action, "-y")
            if not installed:
                flatpak_args += ("flathub",)
            flatpak_args += (app.package_id,)
            return ApplicationOperation(
                "flatpak",
                flatpak_args,
                f"{'Removing' if installed else 'Installing'} {app.name} from Flathub",
                False,
            )

        builder = BatchOpsManager.batch_remove if installed else BatchOpsManager.batch_install
        target = app.package_id if installed else app.install_target
        binary, built_args, description = builder([target])
        return ApplicationOperation(
            binary,
            tuple(built_args),
            description,
            SystemManager.is_atomic(),
        )


def _string_arguments(value: object) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(str(item) for item in value)
    return ()


def _package_id(check_command: str, command: str, arguments: tuple[str, ...]) -> str:
    try:
        check = shlex.split(check_command)
    except ValueError:
        check = []
    if len(check) >= 3 and check[:2] == ["rpm", "-q"]:
        return check[2]
    if command == "flatpak" and arguments:
        candidate = arguments[-1]
        return candidate if "." in candidate else ""
    return ""
