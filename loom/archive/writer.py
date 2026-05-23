"""Archive writer wrapper for instance metadata and keyed identifiers."""
from __future__ import annotations

import hmac
from uuid import UUID

from loom.archive.jsonl import ArchiveWriter
from loom.archive.schema import ArchiveEvent, ArchiveEventType


class InstanceArchiveWriter:
    def __init__(self, writer: ArchiveWriter, *, instance_id: str, hmac_key: bytes):
        self._writer = writer
        self.instance_id = instance_id
        self._hmac_key = hmac_key

    def append(
        self,
        session_id: UUID | str,
        *,
        actor_id: str,
        event_type: ArchiveEventType,
        payload: dict[str, object],
    ) -> ArchiveEvent:
        merged = {**payload, "instance_id": self.instance_id}
        return self._writer.append(session_id, actor_id=actor_id, event_type=event_type, payload=merged)

    def hmac_text(self, value: str) -> str:
        return hmac.new(self._hmac_key, value.encode("utf-8"), "sha256").hexdigest()

    def validate_chain(self, session_id: UUID | str) -> list[ArchiveEvent]:
        return self._writer.validate_chain(session_id)

    def read_session_text(self, session_id: UUID | str) -> str:
        return self._writer.read_session_text(session_id)
