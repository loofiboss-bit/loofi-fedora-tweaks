"""Executor API routes for ActionExecutor operations.

Security:
- Command allowlist enforced — only known-safe executables accepted.
- All executions audit-logged via AuditLogger.
- Bearer JWT required on all endpoints.
"""

import logging
from typing import List

from core.executor.action_executor import ActionExecutor
from core.executor.action_result import ActionResult
from core.executor.command_policy import CommandValidationError, validate_command
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from services.security import AuditLogger
from utils.auth import AuthManager

logger = logging.getLogger(__name__)

router = APIRouter()


class ActionPayload(BaseModel):
    """Payload for executing a system action."""

    command: str = Field(..., description="Executable or command name")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    pkexec: bool = Field(False, description="Require privilege escalation")
    preview: bool = Field(True, description="Run in preview mode first")
    action_id: str = Field("", description="Optional action identifier")


class ActionResponse(BaseModel):
    """Serialized ActionResult response."""

    result: dict
    preview: dict


def _validate_command(command: str, args: List[str]) -> None:
    """Reject commands not on the allowlist.

    Raises:
        HTTPException: 403 if command is not allowed.
    """
    try:
        validate_command(command, args)
    except CommandValidationError as exc:
        audit = AuditLogger()
        audit.log(
            "api.execute.rejected",
            params={"command": command, "args": args, "reason": str(exc)},
            exit_code=None,
        )
        logger.warning("API rejected disallowed command: %s", command)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )


@router.post(
    "/execute",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
)
def execute_action(
    payload: ActionPayload,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Execute an action via ActionExecutor with mandatory preview.

    Security: command must be in COMMAND_ALLOWLIST. All invocations are
    audit-logged with timestamp, params, and exit code.
    """
    _validate_command(payload.command, payload.args)

    audit = AuditLogger()

    preview_result = ActionExecutor.run(
        payload.command,
        payload.args,
        preview=True,
        pkexec=payload.pkexec,
        action_id=payload.action_id,
    )

    if not payload.preview:
        result = ActionExecutor.run(
            payload.command,
            payload.args,
            preview=False,
            pkexec=payload.pkexec,
            action_id=payload.action_id,
        )
        audit.log(
            "api.execute",
            params={
                "command": payload.command,
                "args": payload.args,
                "pkexec": payload.pkexec,
                "action_id": payload.action_id,
            },
            exit_code=result.exit_code if hasattr(result, "exit_code") else None,
        )
    else:
        result = ActionResult.previewed(
            payload.command,
            payload.args,
            action_id=payload.action_id,
        )
        audit.log(
            "api.execute.preview",
            params={
                "command": payload.command,
                "args": payload.args,
                "pkexec": payload.pkexec,
                "action_id": payload.action_id,
            },
            exit_code=None,
        )

    return ActionResponse(result=result.to_dict(), preview=preview_result.to_dict())
