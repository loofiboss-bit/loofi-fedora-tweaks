"""
Journal log utilities.
Part of v7.5 "Watchtower" update.

Provides focused journalctl access with a "Panic Button" for
exporting logs ready for support forums.
"""

import json
import logging
import os
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.privacy import redact_payload, redact_text

logger = logging.getLogger(__name__)


@dataclass
class Result:
    """Operation result with message."""
    success: bool
    message: str
    data: Optional[dict] = None


class JournalManager:
    """
    Focused journalctl wrapper for error export.

    Unlike full log viewers (Cockpit, journalctl directly), this focuses on:
    - Current boot errors only
    - Forum-ready exports with system info
    - Quick access to common error scenarios
    """

    @classmethod
    def get_boot_errors(cls, priority: int = 3, *, strict: bool = False) -> str:
        """
        Get error messages from current boot.

        Args:
            priority: Maximum priority level (0=emerg, 3=err, 4=warning)

        Returns:
            Log output as string.
        """
        try:
            result = subprocess.run(
                ["journalctl", "-p", str(priority), "-xb", "--no-pager", "-n", "100"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if strict and result.returncode != 0:
                raise OSError(f"Collection failed (exit {result.returncode}): {result.stderr}")
            return result.stdout if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get boot errors: %s", e)
            if strict:
                raise
            return ""

    @classmethod
    def get_recent_errors(cls, since: str = "1 hour ago", *, strict: bool = False) -> str:
        """
        Get recent error messages.

        Args:
            since: Time specification (e.g., "1 hour ago", "today")

        Returns:
            Log output as string.
        """
        try:
            result = subprocess.run(
                ["journalctl", "-p", "3", "--since", since, "--no-pager", "-n", "200"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if strict and result.returncode != 0:
                raise OSError(f"Collection failed (exit {result.returncode}): {result.stderr}")
            return result.stdout if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get recent errors: %s", e)
            if strict:
                raise
            return ""

    @classmethod
    def get_service_logs(cls, service: str, lines: int = 50) -> str:
        """
        Get logs for a specific service.

        Args:
            service: Service unit name (e.g., "NetworkManager")
            lines: Number of lines to retrieve

        Returns:
            Log output as string.
        """
        try:
            result = subprocess.run(
                ["journalctl", "-u", f"{service}.service", "-n", str(lines),
                 "--no-pager", "-b"],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get service logs for %s: %s", service, e)
            return ""

    @classmethod
    def get_kernel_messages(cls, lines: int = 100, *, strict: bool = False) -> str:
        """
        Get kernel messages (dmesg-like).

        Returns:
            Kernel log output.
        """
        try:
            result = subprocess.run(
                ["journalctl", "-k", "-b", "-n", str(lines), "--no-pager"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if strict and result.returncode != 0:
                raise OSError(f"Collection failed (exit {result.returncode}): {result.stderr}")
            return result.stdout if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get kernel messages: %s", e)
            if strict:
                raise
            return ""

    @classmethod
    def _get_system_info(cls) -> str:
        """Gather system info for forum post."""
        info_lines = []

        # OS Release
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith(("NAME=", "VERSION_ID=", "VARIANT=")):
                        info_lines.append(line.strip())
        except OSError as e:
            logger.debug("Failed to read os-release: %s", e)
            info_lines.append("COLLECTION_ERROR=os-release unavailable")

        # Kernel version
        try:
            result = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                info_lines.append(f"KERNEL={result.stdout.strip()}")
            else:
                info_lines.append("COLLECTION_ERROR=kernel query failed")
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get kernel version: %s", e)
            info_lines.append("COLLECTION_ERROR=kernel query unavailable")

        # Desktop environment
        de = os.environ.get("XDG_CURRENT_DESKTOP", "Unknown")
        info_lines.append(f"DESKTOP={de}")

        # GPU
        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "VGA" in line or "3D" in line:
                        info_lines.append(f"GPU={line.split(': ')[-1][:80]}")
                        break
            else:
                info_lines.append("COLLECTION_ERROR=GPU query failed")
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get GPU info: %s", e)
            info_lines.append("COLLECTION_ERROR=GPU query unavailable")

        return "\n".join(info_lines)

    @classmethod
    def export_panic_log(cls, output_path: Optional[Path] = None, *, strict: bool = False) -> Result:
        """
        Export a forum-ready panic log.

        Creates a formatted text file with:
        - System info
        - Current boot errors
        - Recent kernel messages
        - Failed services

        Args:
            output_path: Where to save (default: ~/loofi-panic-log-{timestamp}.txt)

        Returns:
            Result with path to created file.
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path.home() / f"loofi-panic-log-{timestamp}.txt"

        try:
            sections = []

            # Header
            sections.append("=" * 60)
            sections.append("LOOFI FEDORA TWEAKS - PANIC LOG")
            sections.append(f"Generated: {datetime.now().isoformat()}")
            sections.append("=" * 60)
            sections.append("")

            # System Info
            sections.append("## SYSTEM INFORMATION")
            sections.append("-" * 40)
            sections.append(cls._get_system_info())
            sections.append("")

            # Failed Services
            sections.append("## FAILED SERVICES")
            sections.append("-" * 40)
            try:
                result = subprocess.run(
                    ["systemctl", "--failed", "--no-pager", "--plain"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                sections.append(result.stdout.strip() if result.returncode == 0 else "Unable to query")
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
                logger.debug("Failed to query failed services: %s", e)
                sections.append("Unable to query failed services")
            sections.append("")

            # Boot Errors
            sections.append("## BOOT ERRORS (Priority: Error and above)")
            sections.append("-" * 40)
            errors = cls.get_boot_errors(strict=True) if strict else cls.get_boot_errors()
            sections.append(errors if errors else "No errors found")
            sections.append("")

            # Kernel Messages
            sections.append("## RECENT KERNEL MESSAGES")
            sections.append("-" * 40)
            kernel = cls.get_kernel_messages(lines=50, strict=True) if strict else cls.get_kernel_messages(lines=50)
            sections.append(kernel if kernel else "Unable to retrieve")
            sections.append("")

            # Footer
            sections.append("=" * 60)
            sections.append("END OF LOG")
            sections.append("=" * 60)

            # Write file
            content = redact_text("\n".join(sections), limit=2**63 - 1)
            from core.state.atomic_io import atomic_write_text

            if not output_path.parent.is_dir():
                raise OSError("The export directory does not exist.")
            atomic_write_text(output_path, content, keep_backup=False)

            return Result(
                True,
                f"Panic log exported to: {output_path}",
                {"path": str(output_path), "size": len(content)}
            )

        except OSError as e:
            logger.debug("Failed to export panic log: %s", e)
            return Result(False, f"Failed to export log: {e}")

    @classmethod
    def export_support_bundle(
        cls,
        output_path: Optional[Path] = None,
        *,
        troubleshooting_session_id: str | None = None,
    ) -> Result:
        """
        Export a support bundle ZIP with key diagnostics.

        Includes:
        - panic log
        - recent journal errors
        - failed services
        - basic system info
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path.home() / f"loofi-support-bundle-{timestamp}.zip"

        try:
            with tempfile.TemporaryDirectory(prefix="loofi-support-") as tmpdir:
                tmp = Path(tmpdir)

                # Panic log
                panic_path = tmp / "panic-log.txt"
                collection_errors = []
                panic_result = cls.export_panic_log(panic_path, strict=True)
                if not panic_result.success:
                    collection_errors.append("panic-log: " + panic_result.message)
                    panic_path.write_text("Collection failed: " + panic_result.message, encoding="utf-8")

                # Recent errors
                try:
                    recent_errors = cls.get_recent_errors("6 hours ago", strict=True)
                except (subprocess.SubprocessError, OSError) as exc:
                    collection_errors.append("recent-errors: " + str(exc))
                    recent_errors = "Collection failed: " + str(exc)
                (tmp / "recent-errors.txt").write_text(recent_errors or "No recent errors")

                # Failed services
                try:
                    result = subprocess.run(
                        ["systemctl", "--failed", "--no-pager", "--plain"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode != 0:
                        raise OSError(f"Collection failed (exit {result.returncode}): {result.stderr}")
                    (tmp / "failed-services.txt").write_text(result.stdout or "No failed services")
                except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
                    logger.debug("Failed to query failed services for bundle: %s", e)
                    collection_errors.append("failed-services: " + str(e))
                    (tmp / "failed-services.txt").write_text("Collection failed: " + str(e))

                # System info
                system_info = cls._get_system_info()
                collection_errors.extend(line for line in system_info.splitlines() if line.startswith("COLLECTION_ERROR="))
                (tmp / "system-info.txt").write_text(system_info or "System information unavailable")

                # Current release-readiness payload plus explicit legacy aliases.
                try:
                    from core.export.support_bundle import SupportBundleWriter

                    bundle = SupportBundleWriter.generate_bundle(
                        session_id=troubleshooting_session_id,
                    )
                    bundle_text = json.dumps(redact_payload(bundle), indent=2, default=str)
                    (tmp / "support-bundle.json").write_text(
                        bundle_text,
                        encoding="utf-8",
                    )
                    (tmp / "support-bundle-v5.json").write_text(
                        bundle_text,
                        encoding="utf-8",
                    )
                    (tmp / "support-bundle-v4.json").write_text(
                        bundle_text,
                        encoding="utf-8",
                    )
                except (ImportError, OSError, RuntimeError, ValueError, TypeError, AttributeError) as e:
                    logger.debug("Failed to include support bundle payload: %s", e)
                    if troubleshooting_session_id is not None:
                        return Result(
                            False,
                            "Failed to export the selected troubleshooting session.",
                        )
                    collection_errors.append("structured-payload: unavailable")
                    fallback = '{"v": "7.0.0-aegis-support-v5", "error": "unavailable"}'
                    (tmp / "support-bundle.json").write_text(fallback, encoding="utf-8")
                    (tmp / "support-bundle-v5.json").write_text(
                        fallback,
                        encoding="utf-8",
                    )
                    (tmp / "support-bundle-v4.json").write_text(
                        fallback,
                        encoding="utf-8",
                    )

                (tmp / "collection-status.json").write_text(json.dumps(redact_payload({
                    "status": "partial" if collection_errors else "complete",
                    "errors": collection_errors,
                })), encoding="utf-8")

                # Sanitize every member at the archive boundary, including aliases.
                # Build beside the destination so replace is atomic on its filesystem.
                archive_path = None
                try:
                    with tempfile.NamedTemporaryFile(dir=output_path.parent, prefix=".loofi-support-", delete=False) as handle:
                        archive_path = Path(handle.name)
                        os.chmod(archive_path, 0o600)
                    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                        for file in sorted(tmp.iterdir()):
                            content = file.read_text(encoding="utf-8")
                            if file.suffix == ".json":
                                content = json.dumps(redact_payload(json.loads(content)), indent=2, default=str)
                            else:
                                content = redact_text(content, limit=2**63 - 1)
                            zf.writestr(file.name, content)
                    with archive_path.open("rb") as handle:
                        os.fsync(handle.fileno())
                    size = archive_path.stat().st_size
                    os.replace(archive_path, output_path)
                    archive_path = None
                finally:
                    if archive_path is not None:
                        archive_path.unlink(missing_ok=True)

                return Result(
                    True,
                    f"Support bundle exported to: {output_path}" + (" (partial collection; see collection-status.json)" if collection_errors else ""),
                    {"path": str(output_path), "size": size, "panic_log_ok": panic_result.success, "collection_status": "partial" if collection_errors else "complete",
                     "collection_errors": redact_payload(collection_errors)}
                )
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            logger.debug("Failed to export support bundle: %s", e)
            return Result(False, f"Failed to export support bundle: {e}")

    @classmethod
    def get_quick_diagnostic(cls) -> dict:
        """
        Get a quick diagnostic summary.

        Returns dict with:
        - error_count: Number of errors in current boot
        - failed_services: List of failed service names
        - recent_errors: Last 5 error messages
        """
        diagnostic: dict[str, Any] = {
            "error_count": 0,
            "failed_services": [],
            "recent_errors": []
        }

        try:
            # Count errors
            errors = cls.get_boot_errors()
            if errors:
                diagnostic["error_count"] = errors.count("\n")
                # Get last 5 unique messages
                lines = [line.strip() for line in errors.split("\n") if line.strip()]
                diagnostic["recent_errors"] = lines[-5:]

            # Failed services
            result = subprocess.run(
                ["systemctl", "--failed", "--no-pager", "--plain", "--no-legend"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        parts = line.split()
                        if parts:
                            diagnostic["failed_services"].append(parts[0])
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get quick diagnostic: %s", e)

        return diagnostic
