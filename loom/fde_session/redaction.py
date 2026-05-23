"""Redaction helpers for persisted Self-Design brief drafts."""
from __future__ import annotations

import re

from loom.fde_session.brief import WorkflowBriefDraft

MAX_TEXT_CHARS = 10_000
REDACTED_TEXT = "[REDACTED]"

_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[a-z0-9_\-.]{16,}"),
    re.compile(r"(?i)\bauthorization\s*:\s*[a-z0-9_\-. ]{16,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*[A-Za-z0-9_\-.]{16,}"),
)


def has_potential_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def redact_text(text: str) -> str:
    if has_potential_secret(text):
        return REDACTED_TEXT
    return text[:MAX_TEXT_CHARS]


def redact_draft(draft: WorkflowBriefDraft) -> WorkflowBriefDraft:
    return draft.model_copy(
        update={
            "intent": _redact_optional_text(draft.intent),
            "success_criteria": redact_text(draft.success_criteria),
            "credentials": [
                credential.model_copy(update={"allowed_hosts": credential.allowed_hosts})
                for credential in draft.credentials
            ],
        }
    )


def _redact_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return redact_text(value)
