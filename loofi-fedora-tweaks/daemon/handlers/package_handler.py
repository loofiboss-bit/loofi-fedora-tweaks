"""Package-related daemon handlers."""

from __future__ import annotations

from core.executor.action_result import ActionResult
from services.package.service import get_package_service

from daemon.validators import validate_package_list, validate_package_name, validate_search_limit, validate_search_query
from daemon.plan_boundary import create_manual_plan, create_plan


class PackageHandler:
    """Serve package operations for IPC callers.

    Behavior contract (v2.12.0 TASK-004):
    - Daemon handlers execute package service local methods first.
    - Fallback to non-local methods only when a local variant is unavailable.
    - Results are serialized through ActionResult envelopes only.
    """

    @staticmethod
    def _execute_action(
        service: object,
        local_method: str,
        fallback_method: str,
        *args: object,
        **kwargs: object,
    ) -> ActionResult:
        """Execute local-first package action and return ActionResult."""
        if hasattr(service, local_method):
            method = getattr(service, local_method)
            result = method(*args, **kwargs)
        else:
            method = getattr(service, fallback_method)
            result = method(*args, **kwargs)

        if isinstance(result, ActionResult):
            return result
        return ActionResult.fail("Package action returned no result")

    @staticmethod
    def install(packages: list[str]) -> dict:
        clean = validate_package_list(packages)
        if len(clean) == 1:
            return create_plan(
                "install-application",
                {"source": "fedora", "package_id": clean[0]},
            )
        return create_manual_plan("package-install", {"packages": clean})

    @staticmethod
    def remove(packages: list[str]) -> dict:
        clean = validate_package_list(packages)
        if len(clean) == 1:
            return create_plan(
                "remove-application",
                {"source": "fedora", "package_id": clean[0]},
            )
        return create_manual_plan("package-remove", {"packages": clean})

    @staticmethod
    def update(packages: list[str] | None = None) -> dict:
        cleaned = validate_package_list(
            packages) if packages is not None else []
        if not cleaned:
            return create_plan("update-fedora-system")
        return create_manual_plan("package-update-selection", {"packages": cleaned})

    @staticmethod
    def search(query: str, limit: int = 50) -> dict:
        service = get_package_service()
        clean_query = validate_search_query(query)
        valid_limit = validate_search_limit(limit)
        result = PackageHandler._execute_action(
            service,
            "search_local",
            "search",
            clean_query,
            limit=valid_limit,
        )
        return PackageHandler._serialize_result(result)

    @staticmethod
    def info(package: str) -> dict:
        service = get_package_service()
        clean_package = validate_package_name(package)
        result = PackageHandler._execute_action(
            service,
            "info_local",
            "info",
            clean_package,
        )
        return PackageHandler._serialize_result(result)

    @staticmethod
    def list_installed() -> dict:
        service = get_package_service()
        result = PackageHandler._execute_action(
            service,
            "list_installed_local",
            "list_installed",
        )
        return PackageHandler._serialize_result(result)

    @staticmethod
    def is_installed(package: str) -> bool:
        service = get_package_service()
        clean_package = validate_package_name(package)
        if hasattr(service, "is_installed_local"):
            return bool(service.is_installed_local(clean_package))
        return bool(service.is_installed(clean_package))

    @staticmethod
    def _serialize_result(result: ActionResult) -> dict:
        if isinstance(result, ActionResult):
            return result.to_dict()
        return ActionResult.fail("Package action returned no result").to_dict()
