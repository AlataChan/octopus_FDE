"""Archive event envelope for AgentOS Layer 1 local archives."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

ArchiveEventType = Literal[
    "session.created",
    "llm_config_inherited",
    "session.llm_config_set",
    "auth.login_succeeded",
    "auth.login_failed",
    "auth.logout",
    "auth.session_expired",
    "turn.started",
    "turn.clarify_started",
    "turn.clarify_replied",
    "turn.questionnaire_emitted",
    "turn.succeeded",
    "turn.failed",
    "template_seeded",
    "compile.produced",
    "artifact.downloaded",
    "registry.deployed",
]


class ArchiveEvent(BaseModel):
    """Tamper-evident archive event envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    event_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    actor_id: str
    seq: int = Field(ge=1)
    event_type: ArchiveEventType
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any]
    payload_sha256: str
    previous_event_sha256: str | None = None

    @classmethod
    def new(
        cls,
        *,
        session_id: UUID,
        actor_id: str,
        seq: int,
        event_type: ArchiveEventType,
        payload: dict[str, Any],
        previous_event_sha256: str | None,
    ) -> ArchiveEvent:
        return cls(
            session_id=session_id,
            actor_id=actor_id,
            seq=seq,
            event_type=event_type,
            payload=payload,
            payload_sha256=payload_digest(payload),
            previous_event_sha256=previous_event_sha256,
        )


def payload_digest(payload: dict[str, Any]) -> str:
    """Return stable SHA-256 hex digest for an archive payload."""
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
