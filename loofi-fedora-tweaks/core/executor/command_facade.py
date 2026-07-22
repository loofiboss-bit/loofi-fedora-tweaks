"""Small command-vector facade for v9 execution consistency."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from core.executor.action_executor import ActionExecutor, COMMAND_TIMEOUT
from core.executor.action_result import ActionResult
from core.executor.command_policy import CommandValidationError, validate_command_vector
from core.execution_policy import ExecutionAuthority


@dataclass(frozen=True)
class CommandRequest:
    """Normalized request passed to the shared executor boundary."""

    command: str
    args: tuple[str, ...] = field(default_factory=tuple)
    privileged: bool = False
    timeout: int = COMMAND_TIMEOUT
    action_id: str = ""
    env: Mapping[str, str] | None = None

    @classmethod
    def from_vector(
        cls,
        vector: Sequence[str],
        *,
        privileged: bool = False,
        timeout: int = COMMAND_TIMEOUT,
        action_id: str = "",
        env: Mapping[str, str] | None = None,
    ) -> "CommandRequest":
        """Build a request from a complete command vector."""
        normalized = tuple(str(part) for part in vector)
        validate_command_vector(normalized)
        return cls(
            command=normalized[0],
            args=normalized[1:],
            privileged=privileged,
            timeout=timeout,
            action_id=action_id,
            env=env,
        )

    def vector(self) -> list[str]:
        """Return the unprivileged command vector."""
        return [self.command, *self.args]


class CommandFacade:
    """Unified preview/execute entrypoint for list-based system commands."""

    def __init__(self, executor: ActionExecutor | None = None):
        self._executor = executor or ActionExecutor()

    def preview(
        self,
        vector: Sequence[str],
        *,
        privileged: bool = False,
        action_id: str = "",
    ) -> ActionResult:
        """Validate and preview a command vector without executing it."""
        try:
            request = CommandRequest.from_vector(
                vector,
                privileged=privileged,
                action_id=action_id,
            )
        except CommandValidationError as exc:
            return ActionResult.fail(str(exc), exit_code=126, action_id=action_id)
        result = self._executor.preview(
            request.command,
            list(request.args),
            privileged=request.privileged,
            action_id=request.action_id,
        )
        result.data = {
            **(result.data or {}),
            "facade": "command-vector",
            "requested_vector": request.vector(),
            "privileged": request.privileged,
        }
        return result

    def execute(
        self,
        vector: Sequence[str],
        *,
        privileged: bool = False,
        timeout: int = COMMAND_TIMEOUT,
        action_id: str = "",
        env: Mapping[str, str] | None = None,
        authority: ExecutionAuthority = "legacy",
    ) -> ActionResult:
        """Validate and execute a command vector through the shared executor."""
        try:
            request = CommandRequest.from_vector(
                vector,
                privileged=privileged,
                timeout=timeout,
                action_id=action_id,
                env=env,
            )
        except CommandValidationError as exc:
            return ActionResult.fail(str(exc), exit_code=126, action_id=action_id)
        result = self._executor.execute(
            request.command,
            list(request.args),
            privileged=request.privileged,
            timeout=request.timeout,
            action_id=request.action_id,
            env=dict(request.env) if request.env else None,
            authority=authority,
        )
        result.data = {
            **(result.data or {}),
            "facade": "command-vector",
            "requested_vector": request.vector(),
            "privileged": request.privileged,
        }
        return result

    def asynchronous_execution_vector(
        self,
        vector: Sequence[str],
        *,
        privileged: bool = False,
        action_id: str = "",
    ) -> list[str]:
        """Prepare one validated QProcess vector without spawning it.

        Canonical Action Center vectors remain wrapper-free. Privilege is
        applied exactly once here before ``CommandRunner`` starts the process.
        """
        if "pkexec" in [str(part) for part in vector]:
            raise CommandValidationError("Canonical asynchronous vectors must not contain pkexec.")
        request = CommandRequest.from_vector(
            vector,
            privileged=privileged,
            action_id=action_id,
        )
        prepared = request.vector()
        return ["pkexec", *prepared] if request.privileged else prepared
