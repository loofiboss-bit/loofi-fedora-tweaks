"""Local support-question drafts from one explicitly selected saved session."""
from __future__ import annotations

import json
from pathlib import Path
import zipfile

from core.privacy import redact_text
from core.troubleshooting.inspection import (
    TroubleshootingInspectionService, bounded_session_payload, sanitize_interface_payload,
)

MAX_DRAFT_LENGTH = 64000


class SupportQuestionService:
    """Render saved evidence only; never invoke a collector or network service."""

    def __init__(self, inspection: TroubleshootingInspectionService | None = None) -> None:
        self.inspection = inspection or TroubleshootingInspectionService()

    def preview(self, session_id: str, problem: str, steps: str) -> str:
        if not problem.strip():
            raise ValueError("Describe the problem before preparing a support question.")
        if len(problem) > 6000 or len(steps) > 6000:
            raise ValueError("Problem descriptions and steps are limited to 6000 characters each.")
        session = self.inspection.require(session_id)
        safe = bounded_session_payload(session)
        question = (
            "# Fedora support question\n\n## Problem\n\n" + problem.strip()
            + "\n\n## Steps to reproduce\n\n" + (steps.strip() or "Not provided.")
            + "\n\n## Selected saved check\n\n"
            + f"Session: {session.session_id}\nProfile: {session.profile_id}\nState: {session.state}\n"
            + "\nOnly the selected saved session is included. No new collection was started. "
            + "Review this draft before sharing; incomplete checks are not an all-clear.\n\n"
            + "```json\n" + json.dumps(safe, indent=2, ensure_ascii=False) + "\n```\n"
        )
        return self.sanitize(question)

    @staticmethod
    def sanitize(draft: str) -> str:
        if not isinstance(draft, str) or len(draft) > MAX_DRAFT_LENGTH:
            raise ValueError("The support question exceeds the bounded draft limit.")
        # The shared redactor bounds individual text fields to 6000 characters.
        # Split before redaction so the selected evidence is not truncated.
        masked = redact_text(draft, limit=MAX_DRAFT_LENGTH)
        return "\n".join(str(sanitize_interface_payload(line)) for line in masked.split("\n"))

    def export(self, path: str | Path, draft: str) -> None:
        destination = Path(path)
        safe = self.sanitize(draft)
        if destination.suffix.lower() == ".zip":
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("support-question.md", safe)
        elif destination.suffix.lower() == ".md":
            destination.write_text(safe, encoding="utf-8")
        else:
            raise ValueError("Choose a Markdown (.md) or ZIP (.zip) destination.")
