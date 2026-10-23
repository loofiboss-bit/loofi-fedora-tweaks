"""
Ansible playbook export utilities.
Part of v8.0 "Replicator" update.

Generates standard Ansible playbooks from current system configuration,
allowing users to replicate their setup on any Fedora machine.
"""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from services.system import SystemManager
from services.system.system import cached_which
from utils.log import get_logger
from utils.software_utils import parse_flatpak_application_list

logger = get_logger(__name__)


@dataclass
class Result:
    """Operation result with message."""

    success: bool
    message: str
    data: Optional[dict] = None


@dataclass
class PlaybookOptions:
    """Options for Ansible playbook generation."""

    include_packages: bool = True
    include_flatpaks: bool = True
    include_settings: bool = True
    include_repos: bool = True
    playbook_name: str = "Loofi Fedora Configuration"


class AnsibleExporter:
    """
    Exports current system state to Ansible playbook.

    This is the killer feature of v8.0 - users can replicate their
    entire Loofi configuration on any Fedora machine without needing
    Loofi itself.
    """

    @classmethod
    def _get_installed_packages(cls) -> list[str]:
        """Get list of user-installed packages."""
        try:
            if SystemManager.is_atomic():
                result = subprocess.run(
                    ["rpm-ostree", "status", "--json"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    deployments = data.get("deployments", [])
                    if deployments:
                        packages = deployments[0].get("requested-packages", [])
                        excluded_prefixes = (
                            "kernel",
                            "glibc",
                            "systemd",
                            "dnf",
                            "rpm",
                            "fedora-",
                        )
                        return [p for p in packages if not any(p.startswith(x) for x in excluded_prefixes)]
                return []
            else:
                package_manager = SystemManager.get_package_manager()
                result = subprocess.run(
                    [package_manager, "repoquery", "--userinstalled", "--qf", "%{name}"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    packages = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
                    excluded_prefixes = (
                        "kernel",
                        "glibc",
                        "systemd",
                        "dnf",
                        "rpm",
                        "fedora-",
                    )
                    return [p for p in packages if not any(p.startswith(x) for x in excluded_prefixes)]
                return []
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as e:
            logger.debug("Failed to get installed packages: %s", e)
            return []

    @classmethod
    def _get_flatpak_apps(cls) -> list[str]:
        """Get list of installed Flatpak apps."""
        if not cached_which("flatpak"):
            return []

        try:
            result = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return parse_flatpak_application_list(result.stdout)
            return []
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get Flatpak apps: %s", e)
            return []

    @classmethod
    def _get_gnome_settings(cls) -> dict[str, Any]:
        """Get relevant GNOME/GTK settings."""
        settings: dict[str, Any] = {}

        if not cached_which("gsettings"):
            return settings

        gsettings_keys = [
            ("org.gnome.desktop.interface", "gtk-theme"),
            ("org.gnome.desktop.interface", "icon-theme"),
            ("org.gnome.desktop.interface", "cursor-theme"),
            ("org.gnome.desktop.interface", "color-scheme"),
            ("org.gnome.desktop.interface", "font-name"),
            ("org.gnome.desktop.interface", "monospace-font-name"),
            ("org.gnome.desktop.wm.preferences", "button-layout"),
        ]

        # Group keys by schema to reduce subprocess spawn overhead
        schema_target_keys: dict[str, set[str]] = {}
        for schema, key in gsettings_keys:
            schema_target_keys.setdefault(schema, set()).add(key)

        for schema, target_keys in schema_target_keys.items():
            try:
                result = subprocess.run(
                    ["gsettings", "list-recursively", schema],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        parts = line.split(maxsplit=2)
                        if len(parts) == 3:
                            line_schema, line_key, raw_val = parts
                            if line_schema == schema and line_key in target_keys:
                                value = raw_val.strip().strip("'")
                                settings[f"{schema}/{line_key}"] = value
            except (subprocess.SubprocessError, OSError) as e:
                logger.debug("Failed to read gsettings schema %s: %s", schema, e)

        return settings

    @classmethod
    def _get_enabled_repos(cls) -> list[str]:
        """Get list of enabled third-party repos."""
        try:
            if SystemManager.is_atomic():
                return []
            else:
                package_manager = SystemManager.get_package_manager()
                result = subprocess.run(
                    [package_manager, "repolist", "--enabled", "-q"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    repos = []
                    for line in result.stdout.strip().split("\n")[1:]:
                        if line.strip():
                            parts = line.split()
                            if parts:
                                repo = parts[0]
                                if not repo.startswith(("fedora", "updates")):
                                    repos.append(repo)
                    return repos
                return []
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get enabled repos: %s", e)
            return []

    @classmethod
    def generate_playbook(
        cls,
        options: Optional[PlaybookOptions] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate an Ansible playbook from current system state.

        Args:
            options: PlaybookOptions configuration instance.
            **kwargs: Individual options for backwards compatibility.

        Returns:
            YAML playbook as string.
        """
        if options is None:
            options = PlaybookOptions(
                include_packages=kwargs.get("include_packages", True),
                include_flatpaks=kwargs.get("include_flatpaks", True),
                include_settings=kwargs.get("include_settings", True),
                include_repos=kwargs.get("include_repos", True),
                playbook_name=kwargs.get("playbook_name", "Loofi Fedora Configuration"),
            )
        elif kwargs:
            options = PlaybookOptions(
                include_packages=kwargs.get("include_packages", options.include_packages),
                include_flatpaks=kwargs.get("include_flatpaks", options.include_flatpaks),
                include_settings=kwargs.get("include_settings", options.include_settings),
                include_repos=kwargs.get("include_repos", options.include_repos),
                playbook_name=kwargs.get("playbook_name", options.playbook_name),
            )

        tasks = []
        vars_section: dict[str, Any] = {}

        header = f"""---
# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ GENERATED BY LOOFI FEDORA TWEAKS - REVIEW BEFORE EXECUTION                 ║
# ║                                                                            ║
# ║ ⚠️  WARNING: This playbook was auto-generated from a live system.          ║
# ║     Always review the tasks below before running on any machine.           ║
# ╚════════════════════════════════════════════════════════════════════════════╝
#
# {options.playbook_name}
# Generated by Loofi Fedora Tweaks v8.0
# Date: {datetime.now().isoformat()}
#
# Usage:
#   1. REVIEW this file carefully before proceeding
#   2. Install Ansible: pkexec dnf install ansible
#   3. Run: ansible-playbook site.yml --ask-become-pass
#
# This playbook replicates your Loofi configuration on any Fedora system.

"""

        if options.include_packages:
            packages = cls._get_installed_packages()
            if packages:
                vars_section["user_packages"] = packages[:100]
                tasks.append(
                    {
                        "name": "Install user packages",
                        "become": True,
                        "ansible.builtin.dnf": {
                            "name": "{{ user_packages }}",
                            "state": "present",
                        },
                    }
                )

        if options.include_flatpaks:
            flatpaks = cls._get_flatpak_apps()
            if flatpaks:
                vars_section["flatpak_apps"] = flatpaks
                tasks.append(
                    {
                        "name": "Enable Flathub",
                        "become": True,
                        "community.general.flatpak_remote": {
                            "name": "flathub",
                            "flatpakrepo_url": "https://flathub.org/repo/flathub.flatpakrepo",
                            "state": "present",
                        },
                    }
                )
                tasks.append(
                    {
                        "name": "Install Flatpak apps",
                        "become": True,
                        "community.general.flatpak": {
                            "name": "{{ item }}",
                            "state": "present",
                        },
                        "loop": "{{ flatpak_apps }}",
                    }
                )

        if options.include_settings:
            settings = cls._get_gnome_settings()
            if settings:
                vars_section["gnome_settings"] = settings
                for key, value in settings.items():
                    schema, setting = key.rsplit("/", 1)
                    tasks.append(
                        {
                            "name": f"Set {setting}",
                            "community.general.dconf": {
                                "key": f"/{schema.replace('.', '/')}/{setting}",
                                "value": f"'{value}'",
                            },
                        }
                    )

        if options.include_repos:
            cls._get_enabled_repos()

        playbook = [
            {
                "name": options.playbook_name,
                "hosts": "localhost",
                "connection": "local",
                "vars": vars_section,
                "tasks": tasks,
            }
        ]

        try:
            import yaml  # type: ignore[import-untyped]

            yaml_content: str = yaml.dump(
                playbook,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=120,
            )
        except ImportError:
            yaml_content = json.dumps(playbook, indent=2)

        return header + yaml_content

    @classmethod
    def save_playbook(
        cls,
        path: Optional[Path] = None,
        options: Optional[PlaybookOptions] = None,
        **kwargs: Any,
    ) -> Result:
        """
        Generate and save playbook to file.

        Args:
            path: Output path (default: ~/loofi-playbook/site.yml)
            options: Options for playbook generation.
            **kwargs: Arguments passed to generate_playbook

        Returns:
            Result with path to created file.
        """
        if path is None:
            playbook_dir = Path.home() / "loofi-playbook"
            playbook_dir.mkdir(exist_ok=True)
            path = playbook_dir / "site.yml"
        else:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)

        try:
            content = cls.generate_playbook(options=options, **kwargs)
            with open(path, "w") as f:
                f.write(content)

            readme_path = path.parent / "README.md"
            readme = f"""# Loofi Fedora Configuration Playbook

Generated by Loofi Fedora Tweaks v8.0 on {datetime.now().strftime("%Y-%m-%d")}.

## Requirements

- Fedora (or compatible RHEL-based distro)
- Ansible (`pkexec dnf install ansible`)
- community.general collection (`ansible-galaxy collection install community.general`)

## Usage

```bash
cd {path.parent}
ansible-playbook site.yml --ask-become-pass
```

## What's Included

- User-installed DNF packages
- Flatpak applications
- GNOME/GTK theme settings

## Customization

Edit `site.yml` to add or remove packages, apps, or settings before running.
"""
            with open(readme_path, "w") as f:
                f.write(readme)

            return Result(
                True,
                f"Playbook saved to: {path}",
                {"path": str(path), "readme": str(readme_path)},
            )

        except (OSError, IOError) as e:
            return Result(False, f"Failed to save playbook: {e}")

    @classmethod
    def validate_playbook(cls, path: Path) -> Result:
        """
        Validate a playbook with ansible-lint if available.

        Args:
            path: Path to playbook file.

        Returns:
            Result with validation output.
        """
        if not cached_which("ansible-lint"):
            try:
                import yaml
            except ImportError:
                return Result(True, "Unable to validate (yaml/ansible-lint not available)")
            try:
                with open(path) as f:
                    yaml.safe_load(f)
                return Result(True, "YAML syntax is valid (ansible-lint not installed)")
            except yaml.YAMLError as e:
                return Result(False, f"YAML syntax error: {e}")

        try:
            result = subprocess.run(["ansible-lint", str(path)], capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return Result(True, "Playbook passed ansible-lint validation")
            else:
                return Result(False, f"Validation issues:\n{result.stdout}")

        except (subprocess.SubprocessError, OSError) as e:
            return Result(False, f"Validation failed: {e}")
