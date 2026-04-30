"""
Package Service Implementations — v23.0 Architecture Hardening.

Concrete implementations of BasePackageService for DNF and rpm-ostree.
Uses CommandWorker for async operations, delegates to existing utils.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from core.executor.action_result import ActionResult
from core.workers.command_worker import CommandWorker

from services.ipc import daemon_client
from services.package.base import BasePackageService
from services.system.system import SystemManager

logger = logging.getLogger(__name__)


class DnfPackageService(BasePackageService):
    """
    Package service implementation for DNF (traditional Fedora).

    Delegates to DNF package manager for traditional Fedora installations.

    Behavior contract (v2.12.0 TASK-002):
    - All public methods are daemon-first via ``daemon_client.call_json``.
    - Local methods are compatibility fallback paths only.
    - No method in this class is intentional-local-read only.
    """

    @staticmethod
    def _package_manager_binary() -> str:
        """Return the non-atomic package manager binary for this service."""
        package_manager = SystemManager.get_package_manager()
        return "dnf" if package_manager == "rpm-ostree" else package_manager

    @staticmethod
    def _from_daemon_payload(payload: object) -> ActionResult | None:
        if not isinstance(payload, dict):
            return None
        if "success" not in payload:
            return None
        try:
            return ActionResult.from_dict(payload)
        except (TypeError, ValueError):
            return None

    def install(
        self,
        packages: List[str],
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Install packages using daemon-first with local DNF fallback."""
        payload = daemon_client.call_json("PackageInstall", packages)
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.install_local(packages, description=description, callback=callback)

    def install_local(
        self,
        packages: List[str],
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Local fallback for installing packages with DNF and pkexec."""
        if not packages:
            return ActionResult(
                success=False,
                message="No packages specified",
                action_id="dnf_install_empty"
            )

        desc = description or f"Installing {len(packages)} package(s) with DNF"
        package_manager = self._package_manager_binary()

        # Use CommandWorker for async execution
        worker = CommandWorker(
            "pkexec",
            [package_manager, "install", "-y"] + packages,
            description=desc,
        )

        if callback:
            worker.progress.connect(lambda msg, pct: callback(msg, pct))

        # For now, run synchronously (can be made async by returning worker)
        worker.start()
        worker.wait()

        result = worker.get_result()
        return result if result else ActionResult(
            success=False,
            message="Worker returned no result",
            action_id="dnf_install_no_result"
        )

    def remove(
        self,
        packages: List[str],
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Remove packages using daemon-first with local DNF fallback."""
        payload = daemon_client.call_json("PackageRemove", packages)
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.remove_local(packages, description=description, callback=callback)

    def remove_local(
        self,
        packages: List[str],
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Local fallback for removing packages with DNF and pkexec."""
        if not packages:
            return ActionResult(success=False, message="No packages specified")

        desc = description or f"Removing {len(packages)} package(s) with DNF"
        package_manager = self._package_manager_binary()
        worker = CommandWorker(
            "pkexec",
            [package_manager, "remove", "-y"] + packages,
            description=desc,
        )

        if callback:
            worker.progress.connect(lambda msg, pct: callback(msg, pct))

        worker.start()
        worker.wait()
        result = worker.get_result()
        return result if result else ActionResult(success=False, message="Worker returned no result")

    def update(
        self,
        packages: Optional[List[str]] = None,
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Update packages using daemon-first with local DNF fallback."""
        payload = daemon_client.call_json("PackageUpdate", packages)
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.update_local(packages, description=description, callback=callback)

    def update_local(
        self,
        packages: Optional[List[str]] = None,
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Local fallback for updating packages with DNF and pkexec."""
        package_manager = self._package_manager_binary()
        if packages:
            desc = description or f"Updating {len(packages)} package(s) with DNF"
            args = ["pkexec", package_manager, "update", "-y"] + packages
        else:
            desc = description or "Updating all packages with DNF"
            args = ["pkexec", package_manager, "update", "-y"]

        worker = CommandWorker("pkexec", args[1:], description=desc)
        if callback:
            worker.progress.connect(lambda msg, pct: callback(msg, pct))

        worker.start()
        worker.wait()
        result = worker.get_result()
        return result if result else ActionResult(success=False, message="Worker returned no result")

    def search(self, query: str, *, limit: int = 50) -> ActionResult:
        """Search for packages using daemon-first with local DNF fallback."""
        payload = daemon_client.call_json("PackageSearch", query, int(limit))
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.search_local(query, limit=limit)

    def search_local(self, query: str, *, limit: int = 50) -> ActionResult:
        """Local fallback for package search using DNF."""
        package_manager = self._package_manager_binary()
        worker = CommandWorker(
            package_manager,
            ["search", query],
            description=f"Searching for '{query}'",
        )
        worker.start()
        worker.wait()
        result = worker.get_result()

        if result and result.success:
            # Parse stdout to extract package names (simplified)
            lines = result.stdout.split('\n')
            matches = [line.split('.')[0].strip(
            ) for line in lines if '.x86_64' in line or '.noarch' in line]
            result.data = {"matches": matches[:limit], "total": len(matches)}

        return result if result else ActionResult(success=False, message="Search failed")

    def info(self, package: str) -> ActionResult:
        """Get package info using daemon-first with local DNF fallback."""
        payload = daemon_client.call_json("PackageInfo", package)
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.info_local(package)

    def info_local(self, package: str) -> ActionResult:
        """Local fallback for package info using DNF."""
        package_manager = self._package_manager_binary()
        worker = CommandWorker(
            package_manager,
            ["info", package],
            description=f"Getting info for '{package}'",
        )
        worker.start()
        worker.wait()
        result = worker.get_result()

        if result and result.success:
            # Parse info from stdout (simplified)
            result.data = {"package": package, "raw_info": result.stdout}

        return result if result else ActionResult(success=False, message="Info query failed")

    def list_installed(self) -> ActionResult:
        """List installed packages using daemon-first with local DNF fallback."""
        payload = daemon_client.call_json("PackageListInstalled")
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.list_installed_local()

    def list_installed_local(self) -> ActionResult:
        """Local fallback for listing installed packages using DNF."""
        package_manager = self._package_manager_binary()
        worker = CommandWorker(
            package_manager,
            ["list", "installed"],
            description="Listing installed packages",
        )
        worker.start()
        worker.wait()
        result = worker.get_result()

        if result and result.success:
            lines = result.stdout.split('\n')
            packages = [line.split('.')[0].strip(
            ) for line in lines if '.x86_64' in line or '.noarch' in line]
            result.data = {"packages": packages, "count": len(packages)}

        return result if result else ActionResult(success=False, message="List failed")

    def is_installed(self, package: str) -> bool:
        """Check installed status using daemon-first with local DNF fallback."""
        payload = daemon_client.call_json("PackageIsInstalled", package)
        if isinstance(payload, bool):
            return payload

        return self.is_installed_local(package)

    def is_installed_local(self, package: str) -> bool:
        """Local fallback for checking installed package status with DNF."""
        worker = CommandWorker(
            "rpm", ["-q", package], description=f"Checking if '{package}' is installed")
        worker.start()
        worker.wait()
        result = worker.get_result()
        return result and result.exit_code == 0 if result else False


class RpmOstreePackageService(BasePackageService):
    """
    Package service implementation for rpm-ostree (Atomic Fedora).

    Delegates to rpm-ostree for Silverblue, Kinoite, and other OSTree variants.

    Behavior contract (v2.12.0 TASK-002):
    - All public methods are daemon-first via ``daemon_client.call_json``.
    - Local methods are compatibility fallback paths only.
    - No method in this class is intentional-local-read only.
    """

    @staticmethod
    def _from_daemon_payload(payload: object) -> ActionResult | None:
        if not isinstance(payload, dict):
            return None
        try:
            return ActionResult.from_dict(payload)
        except (TypeError, ValueError):
            return None

    def install(
        self,
        packages: List[str],
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Install packages using daemon-first with local rpm-ostree fallback."""
        payload = daemon_client.call_json("PackageInstall", packages)
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.install_local(packages, description=description, callback=callback)

    def install_local(
        self,
        packages: List[str],
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Local fallback for installing packages with rpm-ostree."""
        if not packages:
            return ActionResult(success=False, message="No packages specified")

        desc = description or f"Installing {len(packages)} package(s) with rpm-ostree"

        # Try --apply-live first for immediate effect
        worker = CommandWorker(
            "pkexec",
            ["rpm-ostree", "install", "--apply-live"] + packages,
            description=desc
        )

        if callback:
            worker.progress.connect(lambda msg, pct: callback(msg, pct))

        worker.start()
        worker.wait()
        result = worker.get_result()

        if result and result.exit_code != 0 and "cannot apply" in result.stdout.lower():
            # Fallback to regular install (requires reboot)
            logger.info(
                "--apply-live not available, falling back to regular install")
            worker = CommandWorker(
                "pkexec",
                ["rpm-ostree", "install"] + packages,
                description=f"{desc} (reboot required)"
            )
            worker.start()
            worker.wait()
            result = worker.get_result()
            if result:
                result.needs_reboot = True

        return result if result else ActionResult(success=False, message="Install failed")

    def remove(
        self,
        packages: List[str],
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Remove packages using daemon-first with local rpm-ostree fallback."""
        payload = daemon_client.call_json("PackageRemove", packages)
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.remove_local(packages, description=description, callback=callback)

    def remove_local(
        self,
        packages: List[str],
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Local fallback for removing packages with rpm-ostree."""
        if not packages:
            return ActionResult(success=False, message="No packages specified")

        desc = description or f"Removing {len(packages)} package(s) with rpm-ostree"
        worker = CommandWorker(
            "pkexec",
            ["rpm-ostree", "uninstall"] + packages,
            description=desc
        )

        if callback:
            worker.progress.connect(lambda msg, pct: callback(msg, pct))

        worker.start()
        worker.wait()
        result = worker.get_result()

        if result:
            result.needs_reboot = True  # rpm-ostree typically requires reboot

        return result if result else ActionResult(success=False, message="Remove failed")

    def update(
        self,
        packages: Optional[List[str]] = None,
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Update system using daemon-first with local rpm-ostree fallback."""
        payload = daemon_client.call_json("PackageUpdate", packages)
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.update_local(packages, description=description, callback=callback)

    def update_local(
        self,
        packages: Optional[List[str]] = None,
        *,
        description: str = "",
        callback: Optional[Callable[..., None]] = None
    ) -> ActionResult:
        """Local fallback for updating rpm-ostree system."""
        if packages:
            # rpm-ostree doesn't support selective updates
            return ActionResult(
                success=False,
                message="rpm-ostree does not support selective package updates"
            )

        desc = description or "Upgrading system with rpm-ostree"
        worker = CommandWorker(
            "pkexec", ["rpm-ostree", "upgrade"], description=desc)

        if callback:
            worker.progress.connect(lambda msg, pct: callback(msg, pct))

        worker.start()
        worker.wait()
        result = worker.get_result()

        if result:
            result.needs_reboot = True

        return result if result else ActionResult(success=False, message="Update failed")

    def search(self, query: str, *, limit: int = 50) -> ActionResult:
        """Search packages using daemon-first with local rpm-ostree fallback."""
        payload = daemon_client.call_json("PackageSearch", query, int(limit))
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.search_local(query, limit=limit)

    def search_local(self, query: str, *, limit: int = 50) -> ActionResult:
        """Local fallback for search when using rpm-ostree backend."""
        return ActionResult(
            success=False,
            message="Search not implemented for rpm-ostree, use DNF search instead"
        )

    def info(self, package: str) -> ActionResult:
        """Get package info using daemon-first with local rpm fallback."""
        payload = daemon_client.call_json("PackageInfo", package)
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.info_local(package)

    def info_local(self, package: str) -> ActionResult:
        """Local fallback for package info using rpm."""
        worker = CommandWorker(
            "rpm", ["-qi", package], description=f"Getting info for '{package}'")
        worker.start()
        worker.wait()
        result = worker.get_result()

        if result and result.success:
            result.data = {"package": package, "raw_info": result.stdout}

        return result if result else ActionResult(success=False, message="Info query failed")

    def list_installed(self) -> ActionResult:
        """List installed packages using daemon-first with local rpm fallback."""
        payload = daemon_client.call_json("PackageListInstalled")
        parsed = self._from_daemon_payload(payload)
        if parsed is not None:
            return parsed

        return self.list_installed_local()

    def list_installed_local(self) -> ActionResult:
        """Local fallback for listing installed packages using rpm."""
        worker = CommandWorker(
            "rpm", ["-qa"], description="Listing installed packages")
        worker.start()
        worker.wait()
        result = worker.get_result()

        if result and result.success:
            packages = [line.strip()
                        for line in result.stdout.split('\n') if line.strip()]
            result.data = {"packages": packages, "count": len(packages)}

        return result if result else ActionResult(success=False, message="List failed")

    def is_installed(self, package: str) -> bool:
        """Check installed status using daemon-first with local rpm fallback."""
        payload = daemon_client.call_json("PackageIsInstalled", package)
        if isinstance(payload, bool):
            return payload

        return self.is_installed_local(package)

    def is_installed_local(self, package: str) -> bool:
        """Local fallback for checking installed package status with rpm."""
        worker = CommandWorker(
            "rpm", ["-q", package], description=f"Checking if '{package}' is installed")
        worker.start()
        worker.wait()
        result = worker.get_result()
        return result and result.exit_code == 0 if result else False


def get_package_service() -> BasePackageService:
    """
    Factory function to get the appropriate package service for this system.

    Auto-detects whether running on Atomic (rpm-ostree) or traditional (DNF)
    Fedora and returns the corresponding service implementation.

    Returns:
        BasePackageService: DnfPackageService or RpmOstreePackageService
    """
    pm = SystemManager.get_package_manager()

    if pm == "rpm-ostree":
        logger.debug("Using RpmOstreePackageService for Atomic Fedora")
        return RpmOstreePackageService()
    else:
        logger.debug("Using DnfPackageService for traditional Fedora")
        return DnfPackageService()
