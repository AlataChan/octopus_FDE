# Phase 0 security review

Date: 2026-05-07
Reviewer: Claude [architect] + Codex [executor] — automated scan + heuristic review

## Static-helper findings

Command:

```bash
python scripts/security_review.py examples/ir/01-ecommerce-customer-faq.json examples/ir/02-tcm-intake-triage.json examples/ir/03-clinic-ops-summary.json examples/ir/04-tcm-followup.json examples/ir/05-ecommerce-order-exception.json
```

Exit code: 1

Output:

```text
examples/ir/02-tcm-intake-triage.json:
  - node extract: code without idempotency_key — re-run safety unclear

examples/ir/03-clinic-ops-summary.json:
  - node transform: code without idempotency_key — re-run safety unclear

examples/ir/04-tcm-followup.json:
  - node research_outcome: code without idempotency_key — re-run safety unclear

examples/ir/05-ecommerce-order-exception.json:
  - node decide_priority: code without idempotency_key — re-run safety unclear
```

Triage:

- `02-tcm-intake-triage.extract`: false positive for Phase 0 archetype review. The code node is a deterministic local extraction transform over uploaded input and classifier output; it does not call network, filesystem, process, dynamic import, eval, or exec APIs.
- `03-clinic-ops-summary.transform`: false positive for Phase 0 archetype review. The code node normalizes already-fetched HTTP response data into a small records list; no side-effecting API is used.
- `04-tcm-followup.research_outcome`: false positive for Phase 0 archetype review. The code node selects between agent and fallback outputs and returns a normalized object; no side effect is present.
- `05-ecommerce-order-exception.decide_priority`: false positive for Phase 0 archetype review. The code node maps classifier annotations to a priority enum; no side effect is present.

No static-helper findings for:

- Dangerous Python source patterns such as `eval`, `exec`, `__import__`, `open('/...')`, `os.system`, `subprocess`, sockets, `requests`, `urllib`, `pickle`, or `marshal`.
- Dangerous JavaScript source patterns.
- Credentialed HTTP nodes with user-controlled URLs.
- Agent system prompts containing the configured prompt-injection hint patterns.
- Agent nodes with an empty tools list.

## Manual review

### `code` sandbox

- Phase 0 IR can only review source text and node shape; it does not prove runtime sandbox isolation.
- The five archetypes contain four `code` nodes. All four are deterministic transforms and do not use obvious sandbox escape APIs.
- The helper currently flags all `code` nodes without `idempotency_key`. That is too broad for pure transforms. Phase 1 Validator should distinguish pure code from side-effecting code and require `idempotency_key` only when code declares or implies side effects.
- Runtime sandbox requirements remain for Phase 1 and later runtime adapters: CPU, memory, wall-clock caps, no filesystem outside scratch, and no network from `code` nodes. Network access should remain modeled through explicit `http` nodes.

### Prompt / tool-description injection

- Phase 0 archetypes include LLM and agent prompts, but no prompt contains the configured high-risk markers (`untrusted`, `user_input`, `<|`, code fences).
- TCM follow-up uses an `agent` node with explicit tools (`patient_history_lookup`, `clinic_policy_lookup`) and bounded budget. The prompt says staff-review context only and avoids autonomous clinical advice.
- Phase 0 IR does not yet enforce typed registry isolation or untrusted-content delimiters. Phase 1 Planner/Validator should enforce prompt rendering rules: tool descriptions in a typed registry block, user content in explicit delimiters, and no raw registry text mixed into instructions.

### HTTP SSRF

- `03-clinic-ops-summary` contains credentialed HTTP nodes, but their URLs are fixed literals, not `${input...}` values.
- Other archetypes do not contain credentialed user-controlled HTTP URLs.
- Phase 0 IR layer does not enforce URL allowlists. Phase 1 Validator should reject credentialed HTTP nodes whose URL is user-controlled, and should require registry-backed URL allowlists for credentialed HTTP calls.

### Trace PII

- Phase 0 archetypes use symbolic variables and do not include sample customer or patient PII literals in checked-in IR files.
- TCM shadow archetypes can process patient-facing data at runtime, and ecommerce primary archetypes can process buyer messages/order exception text. The IR layer alone does not redact traces.
- Phase 1 should tag PII-sensitive inputs and datasets in registry/validator contracts where available. Phase 2A runtime trace ingestion must enforce redaction at write time, retention, and erasure semantics.

## Action items into Phase 1

- Add Validator rule: `code` nodes may omit `idempotency_key` only when classified as pure transforms with no external side effects.
- Add Validator rule: reject dangerous `code.source` patterns already covered by `scripts/security_review.py`; keep this script as a pre-gate helper.
- Add Validator rule: reject network APIs inside `code` nodes; require explicit `http` nodes for network access.
- Add Validator rule: credentialed `http` nodes must use registry-allowlisted URL bases and must not take full URLs from `${input...}`.
- Add Planner/Validator prompt rule: render untrusted user or retrieved content inside delimiters and keep registry tool descriptions in a typed block.
- Add registry metadata for PII-sensitive inputs/datasets and carry it into runtime trace redaction planning.
