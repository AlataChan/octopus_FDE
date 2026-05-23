import json
from uuid import uuid4

import pytest

from loom.archive.jsonl import ArchiveChainError, ArchiveWriter
from loom.archive.writer import InstanceArchiveWriter


def test_archive_appends_contiguous_hash_chained_events(tmp_path):
    writer = ArchiveWriter(tmp_path, max_bytes=10_000)
    session_id = uuid4()

    first = writer.append(session_id, actor_id="fde", event_type="session.created", payload={"actor_id": "fde"})
    second = writer.append(
        session_id,
        actor_id="fde",
        event_type="turn.succeeded",
        payload={"turn_id": str(uuid4()), "ir_after_sha256": "a" * 64, "validation_status": "ok"},
    )

    assert first.seq == 1
    assert second.seq == 2
    assert second.previous_event_sha256 == first.payload_sha256
    assert writer.validate_chain(session_id) == [first, second]


def test_archive_detects_payload_tampering(tmp_path):
    writer = ArchiveWriter(tmp_path, max_bytes=10_000)
    session_id = uuid4()
    writer.append(session_id, actor_id="fde", event_type="session.created", payload={"actor_id": "fde"})
    path = tmp_path / "archive" / str(session_id) / "0001.jsonl"
    line = json.loads(path.read_text().splitlines()[0])
    line["payload"]["actor_id"] = "mallory"
    path.write_text(json.dumps(line) + "\n")

    with pytest.raises(ArchiveChainError):
        writer.validate_chain(session_id)


def test_archive_rotates_by_size(tmp_path):
    writer = ArchiveWriter(tmp_path, max_bytes=350)
    session_id = uuid4()

    for i in range(5):
        writer.append(
            session_id,
            actor_id="fde",
            event_type="turn.started",
            payload={"turn_id": str(uuid4()), "user_message_sha256": f"{i}" * 64},
        )

    chunks = sorted((tmp_path / "archive" / str(session_id)).glob("*.jsonl"))
    assert [p.name for p in chunks] != ["0001.jsonl"]
    assert writer.validate_chain(session_id)[-1].seq == 5


def test_archive_stream_text_concatenates_chunks(tmp_path):
    writer = ArchiveWriter(tmp_path, max_bytes=350)
    session_id = uuid4()
    writer.append(session_id, actor_id="fde", event_type="session.created", payload={"actor_id": "fde"})

    text = writer.read_session_text(session_id)
    assert "session.created" in text


def test_instance_archive_writer_instance_id_is_authoritative(tmp_path):
    writer = InstanceArchiveWriter(ArchiveWriter(tmp_path, max_bytes=10_000), instance_id="real", hmac_key=b"key")
    session_id = uuid4()

    event = writer.append(
        session_id,
        actor_id="fde",
        event_type="session.created",
        payload={"instance_id": "fake", "k": "v"},
    )

    assert event.payload["instance_id"] == "real"
    assert event.payload["k"] == "v"
    assert writer.validate_chain(session_id)[0].payload["instance_id"] == "real"
