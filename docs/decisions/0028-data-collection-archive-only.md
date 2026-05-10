# ADR 0028: AgentOS Data Collection via Local Archive and Workflow Registry Only

Status: Accepted

Date: 2026-05-10

## Context

FDE is the entry vehicle for the AgentOS data flywheel. Phase 2 must start
capturing implementation memory, but customer artifacts must stay clean:
compiled Hiagent ZIPs and Dify YAML must not contain telemetry taps, callbacks,
phone-home URLs, hidden webhooks, or other data exfiltration hooks.

Layer 2 runtime telemetry is deferred to the sibling `adapter-mcp` project,
which will pull from platform-native trace APIs later.

## Decision

Phase 2 implements:

- Layer 1 Archive: append-only, full-fidelity local JSONL events.
- Layer 3 Workflow Registry: a standalone SQLite DB at
  `<DATA_DIR>/workflow_registry.db`.

Phase 2 does not implement artifact-side telemetry.

## Archive Event Envelope

Every archive row is an `ArchiveEvent`:

```python
class ArchiveEvent(BaseModel):
    schema_version: Literal["1"]
    event_id: UUID
    session_id: UUID
    actor_id: str
    seq: int
    event_type: Literal[
        "session.created", "session.llm_config_set",
        "turn.started", "turn.succeeded", "turn.failed",
        "compile.produced", "artifact.downloaded",
        "registry.deployed",
    ]
    occurred_at: datetime
    payload: dict[str, Any]
    payload_sha256: str
    previous_event_sha256: str | None
```

`payload_sha256` is computed as
`sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")))`.
`previous_event_sha256` links to the prior event payload digest in the same
session. The first event has `previous_event_sha256 = None`.

Events are stored under:

```text
<DATA_DIR>/archive/<session_id>/<NNNN>.jsonl
```

Files rotate by size, starting at `0001.jsonl`.

## Minimum Payload Fields

- `session.created`: `actor_id`
- `session.llm_config_set`: `model`; API key and base URL are never logged
- `turn.started`: `turn_id`, `user_message_sha256`
- `turn.succeeded`: `turn_id`, `ir_after_sha256`, `validation_status`
- `turn.failed`: `turn_id`, `error_kind`
- `compile.produced`: `workflow_id`, `target`, `mode`, `binding_handle`,
  `artifact_id`, `artifact_sha256`, `artifact_size`, `compiler_version`,
  `ir_version`
- `artifact.downloaded`: `artifact_id`, `artifact_sha256`
- `registry.deployed`: `workflow_id`, `platform_app_id`, `deployment_note`,
  `deployed_by_actor`

## Privacy Posture

The local archive is full fidelity by design. Cross-deployment anonymization and
export to AgentOS are deferred until an AgentOS receiver exists.

Controls in Phase 2:

- `<DATA_DIR>` is created with mode `0700`.
- `<DATA_DIR>` is runtime state and must not be copied into Docker images.
- Archive download is scoped by session and actor seam.
- BYOK secrets are not logged into archive payloads.
- Default retention is keep-forever for MVP.
- Manual cleanup is allowed by deleting a session directory under
  `<DATA_DIR>/archive/` and corresponding artifacts after export/review.

## Workflow Registry

The workflow registry is a separate SQLite DB for future federation. It stores
opaque `session_id` and `artifact_id` references, but performs no SQL joins with
the sessions DB. Service code composes records at the application layer.

Registry rows include:

- workflow id
- session id
- artifact id/name/kind/SHA-256
- canonical IR signature and IR version
- target runtime and mode
- binding handle
- compiler version
- actor and timestamp
- optional manual deployment callback fields

## Consequences

- AgentOS gets deterministic local implementation memory without polluting
  customer runtime artifacts.
- The archive is tamper-evident, not tamper-proof.
- Full-fidelity local storage increases local data sensitivity; deployment docs
  must treat `<DATA_DIR>` as sensitive backup material.
