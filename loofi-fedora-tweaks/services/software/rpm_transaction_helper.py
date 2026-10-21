"""Isolated libdnf5 adapter with a closed, digest-bound privileged boundary."""
from __future__ import annotations

import json
import os
import signal
import sys
from dataclasses import replace
from typing import Any

from services.software.rpm_transactions import (
    CODEC_REPLACEMENTS, ERROR_MESSAGES, INBOUND, OUTBOUND, PROTECTED, RpmTransactionPreview, evidence_digest, parse_args,
)

try:
    from libdnf5 import exception as dnf_exception
except ImportError:
    _DNF_ERRORS: tuple[type[Exception], ...] = ()
else:
    # SWIG exceptions inherit Exception directly, not Python RuntimeError.
    _DNF_ERRORS = (dnf_exception.Error, dnf_exception.NonLibdnf5Exception,
                   dnf_exception.AssertionError, dnf_exception.UserAssertionError)

_HELPER_ERRORS: tuple[type[Exception], ...] = (
    ImportError, OSError, RuntimeError, ValueError, TypeError, AttributeError, TimeoutError,
) + _DNF_ERRORS


def _repository_facts(base: Any, dnf_repo: Any) -> list[dict[str, Any]]:
    facts = []
    for repo in dnf_repo.RepoQuery(base):
        config = repo.get_config()
        facts.append({"id": repo.get_id(), **{name: getattr(config, name) for name in
                      ("enabled", "baseurl", "metalink", "mirrorlist", "gpgkey", "pkg_gpgcheck", "repo_gpgcheck", "sslverify")}})
    return sorted(facts, key=lambda item: item["id"])


def _record(item: Any, transaction: Any) -> dict[str, str]:
    package = item.get_package()
    action = transaction.transaction_item_action_to_string(item.get_action())
    checksum = package.get_checksum().get_checksum() if action in INBOUND else ""
    return {"action": action, "name": package.get_name(), "nevra": package.get_full_nevra(),
            "repo_id": package.get_repo_id(), "checksum": checksum}


def validate_operations(operation: str, packages: tuple[str, ...], operations: tuple[dict[str, Any], ...], replacements: bool) -> None:
    if not operations or len(operations) > 4096:
        raise ValueError("No bounded package transaction is available.")
    incoming = {(item["name"], item["nevra"].rpartition(".")[2]) for item in operations if item["action"] in INBOUND}
    for item in operations:
        action, name = item["action"], item["name"]
        if operation == "codecs" and (name in {"kernel", "mesa", "nvidia"} or name.startswith(("kernel-", "mesa-", "nvidia-", "xorg-x11-drv-", "akmod-", "kmod-"))):
            raise ValueError("The multimedia recipe must not change drivers or the graphics stack.")
        paired_upgrade = action == "Replaced" and (name, item["nevra"].rpartition(".")[2]) in incoming
        if action not in INBOUND | OUTBOUND:
            raise ValueError("Downgrades and unreviewable package operations are unavailable.")
        if action in OUTBOUND and not paired_upgrade and (name in PROTECTED or name.startswith(("kernel-", "grub2-", "shim-"))):
            raise ValueError("The transaction would remove a protected system or desktop component.")
        if operation == "install" and action in OUTBOUND and action != "Replaced":
            raise ValueError("Application installation must not erase unrelated packages.")
        if operation == "remove" and action in INBOUND:
            raise ValueError("Application removal must not install or upgrade packages.")
        if operation == "codecs" and action in OUTBOUND and not paired_upgrade and (not replacements or name not in CODEC_REPLACEMENTS):
            raise ValueError("This codec replacement requires separate consent or is outside the approved recipe.")
    if operation == "install":
        incoming_names = {item["name"] for item in operations if item["action"] in INBOUND}
        if any(item["action"] == "Replaced" and item["name"] not in incoming_names for item in operations):
            raise ValueError("Application installation must not replace a different package.")


def load_api() -> tuple[Any, Any, Any, Any, Any]:
    import libdnf5.base as dnf_base
    import libdnf5.repo as dnf_repo
    import libdnf5.rpm as dnf_rpm
    import libdnf5.transaction as dnf_transaction
    import libdnf5.utils as dnf_utils
    return dnf_base, dnf_repo, dnf_rpm, dnf_transaction, dnf_utils


class RpmSession:
    """One session holds the system repository lock until execution completes."""

    def __init__(self, *, writable: bool = False) -> None:
        dnf_base, dnf_repo, dnf_rpm, dnf_transaction, dnf_utils = load_api()

        self.dnf_base, self.dnf_repo, self.dnf_rpm, self.dnf_transaction = dnf_base, dnf_repo, dnf_rpm, dnf_transaction
        self.base = dnf_base.Base()
        self.base.load_config()
        config = self.base.get_config()
        config.get_plugins_option().set(False)
        config.get_cacheonly_option().set("all")
        config.get_clean_requirements_on_remove_option().set(False)
        config.get_install_weak_deps_option().set(False)
        config.get_allow_downgrade_option().set(False)
        config.get_assumeno_option().set(True)
        config.get_pkg_gpgcheck_option().set(True)
        config.get_localpkg_gpgcheck_option().set(True)
        config.get_skip_if_unavailable_option().set(False)
        self.base.setup()
        if writable and not self.base.lock_system_repo(dnf_utils.LockAccess_WRITE, dnf_utils.LockBlocking_NON_BLOCKING):
            raise ValueError("Another package operation holds the system repository lock.")
        self.base.get_repo_sack().create_repos_from_system_configuration()
        for repo in self.dnf_repo.RepoQuery(self.base):
            repo.get_config().get_skip_if_unavailable_option().set(False)

    def close(self) -> None:
        self.base.unlock_system_repo()

    def source_state(self) -> dict[str, Any]:
        """Read only effective source configuration, without loading metadata."""
        repositories = _repository_facts(self.base, self.dnf_repo)
        return {"available": True, "repository_digest": evidence_digest({"repositories": repositories}),
                "enabled_count": sum(bool(item["enabled"]) for item in repositories)}

    def resolve(self, operation: str, packages: tuple[str, ...], repo_id: str, replacements: bool) -> tuple[RpmTransactionPreview, Any]:
        # All enabled source failures are fatal; no partial repository view can
        # silently choose another source or dependency set.
        if operation == "remove":
            self.base.get_repo_sack().load_repos(self.dnf_repo.Repo.Type_SYSTEM)
        else:
            self.base.get_repo_sack().load_repos()
        installed_query = self.dnf_rpm.PackageQuery(self.base)
        installed_query.filter_installed()
        installed = tuple(sorted(package.get_full_nevra() for package in installed_query))
        goal = self.dnf_base.Goal(self.base)
        settings = self.dnf_base.GoalJobSettings()
        settings.set_clean_requirements_on_remove(False)
        settings.set_with_provides(False)
        settings.set_with_filenames(False)
        settings.set_with_binaries(False)
        settings.set_expand_globs(False)
        settings.set_skip_unavailable(False)
        settings.set_skip_broken(False)
        if repo_id:
            settings.set_to_repo_ids([repo_id])
        for package in packages:
            if operation == "remove":
                goal.add_rpm_remove(package, settings)
            else:
                goal.add_rpm_install(package, settings)
        if operation == "remove" or (operation == "codecs" and replacements):
            goal.set_allow_erasing(True)
        transaction = goal.resolve()
        if transaction.get_problems():
            raise ValueError("Package dependencies could not be resolved without conflicts.")
        operations = tuple(sorted((_record(item, self.dnf_transaction) for item in transaction.get_transaction_packages()),
                                  key=lambda item: (item["nevra"], item["action"], item["repo_id"])))
        validate_operations(operation, packages, operations, replacements)
        # Refuse unsigned repositories even if an inherited per-repo override
        # would weaken the global setting; never auto-import a new signing key.
        if any(not item.get_package().is_pkg_gpgcheck_enabled() for item in transaction.get_transaction_packages()
               if self.dnf_transaction.transaction_item_action_is_inbound(item.get_action())):
            raise ValueError("All incoming packages require signature verification.")
        repository_digest = evidence_digest({"repositories": _repository_facts(self.base, self.dnf_repo)})
        preview = RpmTransactionPreview(True, "", operation=operation, packages=packages, repo_id=repo_id, allow_replacements=replacements,
                                        operations=operations, installed=installed, repository_digest=repository_digest)
        return replace(preview, digest=evidence_digest(preview.to_dict())), transaction


def _timeout(_signum: int, _frame: Any) -> None:
    raise TimeoutError("RPM helper exceeded its time limit.")


def _error_code(error: Exception) -> str:
    """Classify private backend failures into a closed set of safe explanations."""
    text = str(error).casefold()
    if isinstance(error, ImportError):
        return "backend_unavailable"
    if isinstance(error, TimeoutError):
        return "operation_timeout"
    for code, fragments in (
        ("no_space", ("no space left", "not enough space", "insufficient space")),
        ("package_lock", ("holds the", "lock is held", "failed to obtain lock")),
        ("signature_error", ("signature", "gpg check")),
        ("transaction_drift", ("changed. create a fresh review",)),
        ("protected_package", ("protected system",)),
        ("network_error", ("could not resolve", "network is unreachable", "connection timed out", "curl error")),
    ):
        if any(fragment in text for fragment in fragments):
            return code
    return "rpm_transaction_unavailable"


def main(argv: list[str] | None = None) -> int:
    session = None
    try:
        mode, operation, packages, repo_id, replacements, digest = parse_args(sys.argv[1:] if argv is None else argv)
        if mode == "apply" and os.geteuid() != 0:
            raise ValueError("RPM changes require native administrator authorization.")
        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(1800 if mode == "apply" else 85)
        session = RpmSession(writable=mode == "apply")
        if mode == "sources":
            print(json.dumps(session.source_state(), sort_keys=True))
            return 0
        preview, transaction = session.resolve(operation, packages, repo_id, replacements)
        if mode == "apply":
            if preview.digest != digest:
                raise ValueError("Package state or sources changed. Create a fresh review.")
            # Resolution remains cache-only. Payload downloads use the already
            # approved transaction and its repository checksums, without resolving again.
            session.base.get_config().get_cacheonly_option().set("metadata")
            transaction.download()
            if not transaction.check_gpg_signatures():
                raise ValueError("Package signatures could not be verified with existing trusted keys.")
            transaction.set_description("Loofi reviewed " + operation)
            if transaction.run() != transaction.TransactionRunResult_SUCCESS:
                raise ValueError("The RPM transaction did not complete. Inspect Activity and verify the result.")
        payload = preview.to_dict()
        encoded = json.dumps(payload, sort_keys=True)
        if len(encoded) > 1024 * 1024:
            raise ValueError("RPM transaction evidence exceeded its output limit.")
        print(encoded)
        return 0
    except _HELPER_ERRORS as error:
        # Backend exceptions may contain private URLs or credentials.
        code = _error_code(error)
        print(json.dumps({"available": False, "error_code": code, "error": ERROR_MESSAGES[code]}))
        return 1
    finally:
        if session is not None:
            session.close()
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
