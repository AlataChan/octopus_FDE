# Planner PII Egress Guard Design

Date: 2026-07-27  
Status: approved by the dispatched P0 policy

## Problem

`redact_text()` only recognizes API-key-like secrets. The current production
path serializes an entire `WorkflowBriefDraft` into the Planner prompt, so
patient identifiers, contact details, and medical free text can reach a
third-party LLM.

The live reproduction on the unmodified branch returned this input unchanged:

```text
Patient 张伟, 13812345678, patient@clinic.cn, ID 110101199003072316, Diagnosis: type 2 diabetes
```

The same outbound boundary is used for planner-assisted edits. Any fix must
therefore cover fresh generation and edit generation, not only the draft
renderer.

## Considered approaches

1. **Allowlist structured brief fields and block unsafe intent at one outbound
   chokepoint (selected).** This minimizes transmitted data, preserves the
   Planner's load-bearing intent, and gives both call paths one fail-closed
   boundary.
2. **Expand in-place redaction over the whole draft.** Rejected because names
   and arbitrary medical detail cannot be reliably regex-redacted, and silent
   replacement of the intent can materially change the requested workflow.
3. **Rely on provider-side DLP or a wrapper around one LLM client.** Rejected
   because the sensitive payload has already left the service boundary, and it
   would not prove that every Planner callable or future provider is covered.

## Boundary and payload contract

Add a single `prepare_outbound_planner_payload()` function. Every service call
to `request.app.state.planner` must pass through it.

The function accepts the free-text intent plus an optional brief and optional
edit context. It returns the exact outbound `user_message` and the sanitized
structured edit context.

The brief is serialized from an explicit allowlist:

- `intent`
- `target_runtime`
- `scope`
- `trigger`
- `compliance_boundary`
- `data_sources`
- `credentials`
- `approval_points`
- `inputs`, limited to `name`, `type`, and `required`
- `tools`

It omits `title`, `success_criteria`, `intent_clarifications`, `known_edits`,
`workflow_id`, and every input `description`. The stored draft remains
unchanged.

For planner-assisted edits, the chokepoint also replaces the
`workflow_brief` member of the edit context with the same allowlisted form
before either the prompt string or the separately supplied `extra_context` is
created.

## Detection and failure behavior

Only `intent` is treated as an allowed free-text channel. Before serialization,
the chokepoint detects:

- existing secret patterns;
- email addresses;
- mainland China mobile numbers;
- checksum-valid 18-character mainland China resident IDs;
- bank-card-length or other long digit runs.

A match raises a typed error containing only `field_path` and `category`. A
detector exception is converted to the same typed error with category
`detector_error`, so no Planner call occurs on uncertain detector state.

The route maps this error to HTTP 422:

```json
{
  "detail": {
    "error": "planner_payload_blocked",
    "field": "intent",
    "category": "email"
  }
}
```

The failed turn, stderr record, and archive event may store only the error code,
field path, and category. They must never store or echo the detected value.

## Detection limits

The guard does **not** detect personal names, diagnoses without another
detector marker, addresses, passport numbers, non-mainland phone or identity
formats, or obfuscated/spelled-out identifiers. There is deliberately no claim
that `张伟` or `Diagnosis: type 2 diabetes` is detected. Those limitations are
why all non-load-bearing brief free text is dropped and why a detected intent
is blocked instead of partially redacted.

## Verification

Tests exercise each category, checksum behavior, detector failure, safe API
errors, both Planner call paths, actual outbound strings, preservation of
structured fields, clean generation, and the existing secret-redaction
contract. Final gates are the complete pytest suite, Ruff, and mypy. Web types
are unchanged, so no web build is required unless implementation changes an
API type consumed by the web package.
