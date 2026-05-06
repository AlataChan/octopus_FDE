# ADR 0003 — Credential binding strategy

**Status:** Accepted
**Date:** 2026-05-06

## Decision

1. LLM credentials are configured inside the target runtime platform. FDE-generated YAML / JSON / ZIP artifacts reference provider/model bindings but never include provider API keys. After import, the operator binds the workflow to the platform's configured LLM credential.
2. Non-LLM credentials are represented as HTTP-node auth bindings: handle, auth scheme, allowed host, header/query placement, and TLS requirement. Secret values are configured in the target platform or supplied during import/configuration; FDE does not store them.
3. Generated artifacts contain binding points and handles only. No secret values in IR, DSL, YAML, JSON, ZIP, logs, reports, or tests.

## Context

This matches the first-build deployment model: FDE produces importable artifacts and the target platform owns credential configuration. A dedicated central secret manager may be added later for enterprise deployment, but it is not a Phase 0 blocker.

## Consequences

- The registry records credential handles with auth binding metadata, not secret-value storage paths.
- Runtime adapters emit platform-specific credential binding slots.
- Tests assert generated artifacts contain no values that look like secrets.

## Alternatives considered

- **Dedicated central secret manager in v1**: stronger central governance, but heavier than the current import/configure workflow.
- **Inline secrets in generated artifacts**: rejected.
