"""Size-rotated JSONL archive writer with per-session hash chains."""
from __future__ import annotations

from pathlib import Path  # noqa: TC003
from uuid import UUID

from loom.archive.schema import ArchiveEvent, ArchiveEventType, payload_digest


class ArchiveChainError(ValueError):
    """Raised when archive chain validation fails."""


class ArchiveWriter:
    """Append ArchiveEvent JSON lines under archive/<session_id>/<NNNN>.jsonl."""

    def __init__(self, data_dir: Path, *, max_bytes: int = 10 * 1024 * 1024):
        self.data_dir = data_dir
        self.archive_dir = data_dir / "archive"
        self.max_bytes = max_bytes
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        session_id: UUID | str,
        *,
        actor_id: str,
        event_type: ArchiveEventType,
        payload: dict[str, object],
    ) -> ArchiveEvent:
        sid = UUID(str(session_id))
        prior = self.validate_chain(sid) if (self.archive_dir / str(sid)).exists() else []
        event = ArchiveEvent.new(
            session_id=sid,
            actor_id=actor_id,
            seq=len(prior) + 1,
            event_type=event_type,
            payload=dict(payload),
            previous_event_sha256=prior[-1].payload_sha256 if prior else None,
        )
        line = event.model_dump_json() + "\n"
        path = self._write_path(sid, len(line.encode("utf-8")))
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
        return event

    def validate_chain(self, session_id: UUID | str) -> list[ArchiveEvent]:
        events: list[ArchiveEvent] = []
        previous: str | None = None
        expected_seq = 1
        for path in self._chunk_paths(UUID(str(session_id))):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = ArchiveEvent.model_validate_json(line)
                if event.seq != expected_seq:
                    raise ArchiveChainError(f"non-contiguous archive seq: {event.seq} != {expected_seq}")
                if event.payload_sha256 != payload_digest(event.payload):
                    raise ArchiveChainError(f"payload digest mismatch at seq {event.seq}")
                if event.previous_event_sha256 != previous:
                    raise ArchiveChainError(f"previous digest mismatch at seq {event.seq}")
                events.append(event)
                previous = event.payload_sha256
                expected_seq += 1
        return events

    def read_session_text(self, session_id: UUID | str) -> str:
        return "".join(path.read_text(encoding="utf-8") for path in self._chunk_paths(UUID(str(session_id))))

    def _chunk_paths(self, session_id: UUID) -> list[Path]:
        session_dir = self.archive_dir / str(session_id)
        if not session_dir.exists():
            return []
        return sorted(session_dir.glob("*.jsonl"))

    def _write_path(self, session_id: UUID, next_line_bytes: int) -> Path:
        session_dir = self.archive_dir / str(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        chunks = sorted(session_dir.glob("*.jsonl"))
        if not chunks:
            return session_dir / "0001.jsonl"
        current = chunks[-1]
        if current.stat().st_size > 0 and current.stat().st_size + next_line_bytes > self.max_bytes:
            return session_dir / f"{len(chunks) + 1:04d}.jsonl"
        return current
